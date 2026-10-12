"""Idempotent load of everything under data/raw into data/steam_pulse.duckdb.

Re-running is safe: player snapshots are keyed by (snapshot_id, appid), SteamSpy by (file, appid),
appdetails history by (appid, fetched_at). Anything already loaded is skipped.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "steam_pulse.duckdb"

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.player_counts (
    snapshot_id VARCHAR, snapshot_ts TIMESTAMPTZ, fetched_at TIMESTAMPTZ, appid INTEGER,
    player_count BIGINT, api_result INTEGER, ok BOOLEAN, source_file VARCHAR,
    PRIMARY KEY (snapshot_id, appid));
CREATE TABLE IF NOT EXISTS raw.steamspy_owners (
    source_file VARCHAR, fetched_at TIMESTAMPTZ, appid INTEGER, name VARCHAR, developer VARCHAR,
    publisher VARCHAR, owners_estimate_range VARCHAR, positive BIGINT, negative BIGINT,
    price_cents INTEGER, initialprice_cents INTEGER, discount_pct INTEGER, ccu_yesterday_peak BIGINT,
    PRIMARY KEY (source_file, appid));
CREATE TABLE IF NOT EXISTS raw.appdetails (
    appid INTEGER, fetched_at TIMESTAMPTZ, success BOOLEAN, payload JSON,
    PRIMARY KEY (appid, fetched_at));
CREATE TABLE IF NOT EXISTS raw.app_reviews (
    appid INTEGER, fetched_at TIMESTAMPTZ, ok BOOLEAN, review_score INTEGER, review_score_desc VARCHAR,
    total_positive BIGINT, total_negative BIGINT, total_reviews BIGINT, source_file VARCHAR,
    PRIMARY KEY (appid, fetched_at));
CREATE TABLE IF NOT EXISTS raw.steamspy_tags (
    appid INTEGER, fetched_at TIMESTAMPTZ, ok BOOLEAN, owners_estimate_range VARCHAR, tags JSON,
    payload JSON, source_file VARCHAR, PRIMARY KEY (appid, fetched_at));
CREATE TABLE IF NOT EXISTS raw.deck_compat (
    appid INTEGER, fetched_at TIMESTAMPTZ, ok BOOLEAN, deck_category INTEGER, deck_status VARCHAR, payload JSON,
    source_file VARCHAR, PRIMARY KEY (appid, fetched_at));
CREATE TABLE IF NOT EXISTS raw.price_checks (
    appid INTEGER, fetched_at TIMESTAMPTZ, ok BOOLEAN, has_price BOOLEAN, currency VARCHAR,
    initial_cents INTEGER, final_cents INTEGER, discount_pct INTEGER, source_file VARCHAR,
    PRIMARY KEY (appid, fetched_at));
CREATE TABLE IF NOT EXISTS raw.universe_members (
    appid INTEGER, list_source VARCHAR, name VARCHAR, fetched_at TIMESTAMPTZ, source_file VARCHAR,
    PRIMARY KEY (appid, list_source, fetched_at));
"""

BACKFILL = ROOT / "analysis" / "data" / "backfill" / "tables"
# table -> (parquet file, select list, empty-schema DDL). Full replace from the current parquet = idempotent and
# picks up rows added by a still-running crawl on the next load.
BACKFILL_TABLES = {
    "backfill_steamcharts_monthly": ("steamcharts_monthly.parquet",
        "cast(appid as integer) appid, month, avg_players, cast(peak_players as bigint) peak_players",
        "appid INTEGER, month DATE, avg_players DOUBLE, peak_players BIGINT"),
    "backfill_reviews_monthly": ("reviews_monthly.parquet",
        "cast(appid as integer) appid, month, cast(up as bigint) reviews_up, cast(down as bigint) reviews_down, cast(n_buckets as integer) n_buckets, rollup_type",
        "appid INTEGER, month DATE, reviews_up BIGINT, reviews_down BIGINT, n_buckets INTEGER, rollup_type VARCHAR"),
    "backfill_mendeley_price_daily": ("mendeley_price_daily.parquet",
        "appid, date, initialprice initial_price_usd, finalprice final_price_usd, discount discount_pct",
        "appid INTEGER, date DATE, initial_price_usd DOUBLE, final_price_usd DOUBLE, discount_pct DOUBLE"),
    "backfill_mendeley_players_daily": ("mendeley_players_daily.parquet",
        "appid, date, avg_players, peak_players, n_obs n_hourly_obs",
        "appid INTEGER, date DATE, avg_players DOUBLE, peak_players DOUBLE, n_hourly_obs BIGINT"),
}


def load_backfill(con) -> dict:
    out = {}
    for t, (fname, sel, ddl) in BACKFILL_TABLES.items():
        f = BACKFILL / fname
        if f.exists():
            mtime = pd.Timestamp(f.stat().st_mtime, unit="s", tz="UTC")
            con.execute(f"CREATE OR REPLACE TABLE raw.{t} AS SELECT {sel}, TIMESTAMPTZ '{mtime.isoformat()}' AS fetched_at, "
                        f"'{fname}' AS source_file FROM read_parquet('{f.as_posix()}')")
        else:
            con.execute(f"CREATE TABLE IF NOT EXISTS raw.{t} ({ddl}, fetched_at TIMESTAMPTZ, source_file VARCHAR)")
        out[t] = con.execute(f"SELECT COUNT(*) FROM raw.{t}").fetchone()[0]
    return out


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load_all(db_path: Path = DB) -> dict:
    con = duckdb.connect(str(db_path))
    con.execute(DDL)
    counts = {}

    files = sorted(RAW.glob("players/dt=*/*.parquet"))
    for f in files:
        df = pd.read_parquet(f)
        df["source_file"] = f.relative_to(RAW).as_posix()
        con.register("df", df)
        con.execute("INSERT OR IGNORE INTO raw.player_counts SELECT snapshot_id, snapshot_ts, fetched_at, appid, "
                    "player_count, api_result, ok, source_file FROM df")
        con.unregister("df")

    for f in sorted(RAW.glob("steamspy/dt=*/*.json")):
        ts = pd.to_datetime(f.stem.split("_")[-1], format="%Y%m%dT%H%M%SZ", utc=True)
        rows = [{
            "source_file": f.relative_to(RAW).as_posix(), "fetched_at": ts, "appid": _int(v.get("appid")),
            "name": v.get("name"), "developer": v.get("developer"), "publisher": v.get("publisher"),
            "owners_estimate_range": v.get("owners"), "positive": _int(v.get("positive")),
            "negative": _int(v.get("negative")), "price_cents": _int(v.get("price")),
            "initialprice_cents": _int(v.get("initialprice")), "discount_pct": _int(v.get("discount")),
            "ccu_yesterday_peak": _int(v.get("ccu")),
        } for v in json.loads(f.read_text()).values()]
        df = pd.DataFrame(rows)
        con.register("df", df)
        con.execute("INSERT OR IGNORE INTO raw.steamspy_owners SELECT * FROM df")
        con.unregister("df")

    rows = []
    for f in sorted(RAW.glob("appdetails/history/dt=*/*.json")):
        rec = json.loads(f.read_text())
        p = rec.get("payload") or {}
        rows.append({"appid": rec["appid"], "fetched_at": pd.Timestamp(rec["fetched_at"]),
                     "success": bool(p.get("success")), "payload": json.dumps(p.get("data"))})
    if rows:
        con.register("df", pd.DataFrame(rows))
        con.execute("INSERT OR IGNORE INTO raw.appdetails SELECT appid, fetched_at, success, payload::JSON FROM df")
        con.unregister("df")

    for f in sorted(RAW.glob("reviews/dt=*/*.parquet")):
        df = pd.read_parquet(f); df["source_file"] = f.relative_to(RAW).as_posix()
        con.register("df", df)
        con.execute("INSERT OR IGNORE INTO raw.app_reviews SELECT appid, fetched_at, ok, review_score, review_score_desc, "
                    "total_positive, total_negative, total_reviews, source_file FROM df")
        con.unregister("df")

    for f in sorted(RAW.glob("steamspy_tags/dt=*/*.parquet")):
        df = pd.read_parquet(f); df["source_file"] = f.relative_to(RAW).as_posix()
        con.register("df", df)
        con.execute("INSERT OR IGNORE INTO raw.steamspy_tags SELECT appid, fetched_at, ok, owners_estimate_range, "
                    "tags_json::JSON, payload_json::JSON, source_file FROM df")
        con.unregister("df")

    for f in sorted(RAW.glob("deck/dt=*/*.parquet")):
        df = pd.read_parquet(f); df["source_file"] = f.relative_to(RAW).as_posix()
        con.register("df", df)
        con.execute("INSERT OR IGNORE INTO raw.deck_compat SELECT appid, fetched_at, ok, deck_category, deck_status, "
                    "payload_json::JSON, source_file FROM df")
        con.unregister("df")

    for f in sorted(RAW.glob("universe/dt=*/*.parquet")):
        df = pd.read_parquet(f); df["source_file"] = f.relative_to(RAW).as_posix()
        con.register("df", df)
        con.execute("INSERT OR IGNORE INTO raw.universe_members SELECT appid, list_source, name, fetched_at, source_file FROM df")
        con.unregister("df")

    for f in sorted(RAW.glob("prices/dt=*/*.parquet")):
        df = pd.read_parquet(f); df["source_file"] = f.relative_to(RAW).as_posix()
        con.register("df", df)
        con.execute("INSERT OR IGNORE INTO raw.price_checks SELECT appid, fetched_at, ok, has_price, currency, "
                    "initial_cents, final_cents, discount_pct, source_file FROM df")
        con.unregister("df")

    counts.update(load_backfill(con))
    for t in ["player_counts", "steamspy_owners", "appdetails", "app_reviews", "steamspy_tags", "deck_compat", "universe_members", "price_checks"]:
        counts[t] = con.execute(f"SELECT COUNT(*) FROM raw.{t}").fetchone()[0]
    counts["snapshots"] = con.execute("SELECT COUNT(DISTINCT snapshot_id) FROM raw.player_counts").fetchone()[0]
    con.close()
    return counts


if __name__ == "__main__":
    print(load_all())
