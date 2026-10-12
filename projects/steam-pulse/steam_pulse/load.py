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
"""


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

    for t in ["player_counts", "steamspy_owners", "appdetails", "app_reviews", "steamspy_tags", "deck_compat"]:
        counts[t] = con.execute(f"SELECT COUNT(*) FROM raw.{t}").fetchone()[0]
    counts["snapshots"] = con.execute("SELECT COUNT(DISTINCT snapshot_id) FROM raw.player_counts").fetchone()[0]
    con.close()
    return counts


if __name__ == "__main__":
    print(load_all())
