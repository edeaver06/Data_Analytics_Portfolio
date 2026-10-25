"""Steam Pulse ingestion: one call = one snapshot.

1. Game universe: SteamSpy `request=all&page=0` (top ~1,000 games by owner estimate). Cached, refreshed weekly.
2. Current players for every game in the universe (Steam Web API, no key).
3. Store appdetails: slow, cached; only up to --appdetails-budget stale/missing games refreshed per run.
4. Store appreviews summary counts (num_per_page=0): rotating budget, oldest-first.
5. SteamSpy per-app details (user tags + owner ESTIMATES): rotating budget, oldest-first.
6. Raw files are landed timestamped under data/raw/, then loaded idempotently into data/steam_pulse.duckdb.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from steam_pulse.http import PoliteSession, Redirected
from steam_pulse import load

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PLAYERS_URL = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
STEAMSPY_URL = "https://steamspy.com/api.php"
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
DECK_URL = "https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport"
REVIEWS_URL = "https://store.steampowered.com/appreviews/{appid}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp(ts: datetime) -> str:
    return ts.strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj))
    tmp.replace(path)  # atomic


def latest(pattern: str, base: Path) -> Path | None:
    files = sorted(base.glob(pattern))
    return files[-1] if files else None


def get_universe(http: PoliteSession, ts: datetime, max_age_days: int = 7, limit: int = 1000) -> tuple[list[int], Path]:
    base = RAW / "steamspy"
    cached = latest("dt=*/steamspy_all_page0_*.json", base)
    if cached:
        age = ts - datetime.strptime(cached.stem.split("_")[-1], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if age < timedelta(days=max_age_days):
            data = json.loads(cached.read_text())
            return _top(data, limit), cached
    data = http.get_json(STEAMSPY_URL, {"request": "all", "page": 0})
    if not data:
        if cached:  # degrade gracefully to the stale universe
            print("WARN: SteamSpy unavailable, reusing", cached, file=sys.stderr)
            return _top(json.loads(cached.read_text()), limit), cached
        raise RuntimeError("SteamSpy universe unavailable and no cache")
    path = base / f"dt={ts:%Y-%m-%d}" / f"steamspy_all_page0_{stamp(ts)}.json"
    write_json(path, data)
    return _top(data, limit), path


FEATURED_URL = "https://store.steampowered.com/api/featuredcategories"


def get_new_releases(http: PoliteSession, ts: datetime) -> list[int]:
    """New-release tracking: SteamSpy top100in2weeks + store 'new_releases'. Every app ever seen here stays tracked
    (cumulative), so launch decay can be observed. Lands raw/universe/ parquet (appid, list_source, name)."""
    rows = []
    t2w = http.get_json(STEAMSPY_URL, {"request": "top100in2weeks"}) or {}
    for k, v in (t2w.items() if isinstance(t2w, dict) else []):
        rows.append({"appid": int(k), "list_source": "steamspy_top100in2weeks", "name": (v or {}).get("name")})
    feat = http.get_json(FEATURED_URL, {"cc": "us", "l": "english"}) or {}
    for it in ((feat.get("new_releases") or {}).get("items") or []):
        if it.get("type") == 0 and it.get("id"):  # type 0 = app
            rows.append({"appid": int(it["id"]), "list_source": "store_new_releases", "name": it.get("name")})
    if rows:
        df = pd.DataFrame(rows).drop_duplicates(["appid", "list_source"]); df["fetched_at"] = ts
        path = RAW / "universe" / f"dt={ts:%Y-%m-%d}" / f"universe_{stamp(ts)}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
    files = sorted(RAW.glob("universe/dt=*/*.parquet"))
    return sorted(set(pd.concat([pd.read_parquet(f, columns=["appid"]) for f in files]).appid.astype(int))) if files else []


def _top(data: dict, limit: int) -> list[int]:
    return [int(k) for k in list(data.keys())[:limit]]


def snapshot_players(http: PoliteSession, appids: list[int], ts: datetime, snapshot_id: str) -> Path:
    def one(appid: int) -> dict:
        fetched = utcnow()
        j = http.get_json(PLAYERS_URL, {"appid": appid})
        resp = (j or {}).get("response", {})
        ok = resp.get("result") == 1
        return {"snapshot_id": snapshot_id, "snapshot_ts": ts, "fetched_at": fetched, "appid": appid,
                "player_count": resp.get("player_count") if ok else None,
                "api_result": resp.get("result"), "ok": ok}

    with ThreadPoolExecutor(max_workers=4) as ex:  # spacing is enforced globally in PoliteSession
        rows = list(ex.map(one, appids))
    df = pd.DataFrame(rows)
    path = RAW / "players" / f"dt={ts:%Y-%m-%d}" / f"players_{stamp(ts)}_{snapshot_id[:8]}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def refresh_appdetails(http: PoliteSession, appids: list[int], ts: datetime, budget: int, max_age_days: int = 14) -> int:
    """Cache one JSON per app (latest) + an append-only timestamped history file per fetch."""
    cache = RAW / "appdetails" / "latest"
    def age(appid):
        p = cache / f"{appid}.json"
        if not p.exists():
            return timedelta.max
        return ts - datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
    todo = [a for a in sorted(appids, key=age, reverse=True) if age(a) > timedelta(days=max_age_days)][:budget]
    fetched = 0
    for appid in todo:
        j = http.get_json(APPDETAILS_URL, {"appids": appid, "cc": "us", "l": "english"})
        if j is None:
            continue
        rec = {"appid": appid, "fetched_at": utcnow().isoformat(), "payload": j.get(str(appid))}
        write_json(cache / f"{appid}.json", rec)
        write_json(RAW / "appdetails" / "history" / f"dt={ts:%Y-%m-%d}" / f"{appid}_{stamp(ts)}.json", rec)
        fetched += 1
    return fetched


def _oldest_first(appids: list[int], seen: dict[int, datetime], ts: datetime, max_age: timedelta, budget: int) -> list[int]:
    """Never-fetched games first, then the stalest; only those older than max_age; at most budget."""
    never = datetime.min.replace(tzinfo=timezone.utc)
    cand = [a for a in appids if ts - seen.get(a, never) > max_age]
    return sorted(cand, key=lambda a: seen.get(a, never))[:budget]


def _last_seen_parquet(pattern: str, col: str = "fetched_at") -> dict[int, datetime]:
    files = sorted(RAW.glob(pattern))
    if not files:
        return {}
    df = pd.concat([pd.read_parquet(f, columns=["appid", col, "ok"]) for f in files])
    df = df[df.ok]
    return {int(k): v.to_pydatetime() for k, v in df.groupby("appid")[col].max().items()}


def refresh_reviews(http: PoliteSession, appids: list[int], ts: datetime, budget: int, max_age_hours: int = 20,
                   time_budget_s: float = 180.0, breaker_n: int = 5) -> int:
    """Review summary counts from the store (no review text). Lands one parquet per run.

    Safety valves so a misbehaving endpoint can never stall the snapshot:
    - redirects / HTML answers are not retried; that app's row is written with ok=False
    - time_budget_s: once this many seconds have passed, the remaining apps are skipped
    - circuit breaker: if the first breaker_n calls all redirect, skip reviews for the whole run
    """
    seen = _last_seen_parquet("reviews/dt=*/*.parquet")
    todo = _oldest_first(appids, seen, ts, timedelta(hours=max_age_hours), budget)
    rows = []
    start, redirects = time.monotonic(), 0
    for i, appid in enumerate(todo):
        if time.monotonic() - start > time_budget_s:
            print(f"reviews: time budget of {time_budget_s:.0f}s used up; skipping {len(todo) - i} remaining apps",
                  file=sys.stderr)
            break
        if breaker_n and i == breaker_n and redirects == breaker_n:
            print(f"reviews: first {breaker_n} calls were all redirected; skipping reviews for this run "
                  f"({len(todo) - i} apps)", file=sys.stderr)
            break
        try:
            j = http.get_json(REVIEWS_URL.format(appid=appid),
                              {"json": 1, "language": "all", "purchase_type": "all", "num_per_page": 0,
                               "filter": "all"}, follow_redirects=False, raise_on_redirect=True)
        except Redirected:
            redirects, j = redirects + 1, None
        q = (j or {}).get("query_summary") or {} if isinstance(j, dict) else {}
        ok = isinstance(j, dict) and j.get("success") == 1 and "total_reviews" in q
        rows.append({"appid": appid, "fetched_at": utcnow(), "ok": ok,
                     "review_score": q.get("review_score"), "review_score_desc": q.get("review_score_desc"),
                     "total_positive": q.get("total_positive"), "total_negative": q.get("total_negative"),
                     "total_reviews": q.get("total_reviews")})
    if rows:
        path = RAW / "reviews" / f"dt={ts:%Y-%m-%d}" / f"reviews_{stamp(ts)}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).astype({"review_score": "Int64", "total_positive": "Int64",
                                   "total_negative": "Int64", "total_reviews": "Int64"}).to_parquet(path, index=False)
    return sum(r["ok"] for r in rows)


def refresh_steamspy_details(http: PoliteSession, appids: list[int], ts: datetime, budget: int, max_age_days: int = 7) -> int:
    """SteamSpy per-app: user tags (with vote counts) + owner ESTIMATE range. Lands one parquet per run."""
    seen = _last_seen_parquet("steamspy_tags/dt=*/*.parquet")
    todo = _oldest_first(appids, seen, ts, timedelta(days=max_age_days), budget)
    rows = []
    for appid in todo:
        j = http.get_json(STEAMSPY_URL, {"request": "appdetails", "appid": appid})
        ok = bool(j) and str(j.get("appid")) == str(appid)
        tags = (j or {}).get("tags") or {}
        rows.append({"appid": appid, "fetched_at": utcnow(), "ok": ok,
                     "owners_estimate_range": (j or {}).get("owners"),
                     "tags_json": json.dumps(tags if isinstance(tags, dict) else {}, sort_keys=True),
                     "payload_json": json.dumps(j) if j else None})  # full raw record, nothing lost
    if rows:
        path = RAW / "steamspy_tags" / f"dt={ts:%Y-%m-%d}" / f"steamspy_tags_{stamp(ts)}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(path, index=False)
    return sum(r["ok"] for r in rows)


def snapshot_prices(http: PoliteSession, appids: list[int], ts: datetime, batch: int = 50) -> int:
    """Every run: price_overview for ALL tracked games via batched appdetails?filters=price_overview (~20 calls).
    This is the forward daily price history (fct_daily_price / snap_game_price)."""
    rows = []
    for i in range(0, len(appids), batch):
        chunk = appids[i:i + batch]
        j = http.get_json(APPDETAILS_URL, {"appids": ",".join(map(str, chunk)), "filters": "price_overview", "cc": "us"})
        fetched = utcnow()
        for a in chunk:
            rec = (j or {}).get(str(a)) or {}
            data = rec.get("data")
            po = data.get("price_overview") if isinstance(data, dict) else None
            rows.append({"appid": a, "fetched_at": fetched, "ok": bool(rec.get("success")), "has_price": po is not None,
                         "currency": (po or {}).get("currency"), "initial_cents": (po or {}).get("initial"),
                         "final_cents": (po or {}).get("final"), "discount_pct": (po or {}).get("discount_percent")})
    df = pd.DataFrame(rows).astype({"initial_cents": "Int64", "final_cents": "Int64", "discount_pct": "Int64"})
    path = RAW / "prices" / f"dt={ts:%Y-%m-%d}" / f"prices_{stamp(ts)}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return int(df.has_price.sum())


DECK_LABELS = {0: "Unknown", 1: "Unsupported", 2: "Playable", 3: "Verified"}


def refresh_deck(http: PoliteSession, appids: list[int], ts: datetime, budget: int, max_age_days: int = 14) -> int:
    """Steam Deck compatibility (undocumented public store endpoint). Lands one parquet per run."""
    seen = _last_seen_parquet("deck/dt=*/*.parquet")
    todo = _oldest_first(appids, seen, ts, timedelta(days=max_age_days), budget)
    rows = []
    for appid in todo:
        j = http.get_json(DECK_URL, {"nAppID": appid, "l": "english"})
        res = (j or {}).get("results") or {}
        cat = res.get("resolved_category") if isinstance(res, dict) else None
        rows.append({"appid": appid, "fetched_at": utcnow(), "ok": bool(j) and j.get("success") == 1 and cat is not None,
                     "deck_category": cat, "deck_status": DECK_LABELS.get(cat),
                     "payload_json": json.dumps(j) if j else None})
    if rows:
        path = RAW / "deck" / f"dt={ts:%Y-%m-%d}" / f"deck_{stamp(ts)}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).astype({"deck_category": "Int64"}).to_parquet(path, index=False)
    return sum(r["ok"] for r in rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Take one Steam Pulse snapshot.")
    ap.add_argument("--limit", type=int, default=1000, help="games in universe")
    ap.add_argument("--appdetails-budget", type=int, default=150,
                    help="max store appdetails requests this run (~1.6 s each)")
    ap.add_argument("--reviews-budget", type=int, default=250, help="max appreviews summary requests this run")
    ap.add_argument("--tags-budget", type=int, default=150, help="max SteamSpy per-app requests this run (~1.1 s each)")
    ap.add_argument("--deck-budget", type=int, default=200, help="max Steam Deck compatibility requests this run")
    ap.add_argument("--catch-up", action="store_true",
                    help="one-off coverage pass: budgets large enough to cover every tracked game (~60-70 min, polite rate)")
    ap.add_argument("--skip-load", action="store_true")
    a = ap.parse_args(argv)

    if a.catch_up:
        a.appdetails_budget = a.reviews_budget = a.tags_budget = a.deck_budget = 5000
    RAW.mkdir(parents=True, exist_ok=True)
    lock = open(ROOT / "data" / ".snapshot.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another snapshot is running; exiting", file=sys.stderr)
        return 0

    http, ts, sid = PoliteSession(), utcnow(), uuid.uuid4().hex
    appids, uni_path = get_universe(http, ts, limit=a.limit)
    extra = [x for x in get_new_releases(http, ts) if x not in set(appids)]
    appids = appids + extra
    players_path = snapshot_players(http, appids, ts, sid)
    n_prices = snapshot_prices(http, appids, ts)
    n_details = refresh_appdetails(http, appids, ts, a.appdetails_budget)
    n_reviews = refresh_reviews(http, appids, ts, a.reviews_budget)
    n_tags = refresh_steamspy_details(http, appids, ts, a.tags_budget)
    n_deck = refresh_deck(http, appids, ts, a.deck_budget)
    df = pd.read_parquet(players_path)
    print(f"snapshot {sid} at {ts.isoformat()}: {len(df)} games, {int(df.ok.sum())} ok, "
          f"{int(df.player_count.fillna(0).sum()):,} concurrent players; appdetails fetched {n_details}, "
          f"reviews {n_reviews}, steamspy tags {n_tags}, deck {n_deck}, priced games {n_prices}")
    if not a.skip_load:
        print(load.load_all())
    return 0


if __name__ == "__main__":
    sys.exit(main())
