"""Offline tests for the idempotent loader (uses tiny local fixture files, no network)."""
import json

import pandas as pd

from steam_pulse import load


def _fixture(raw):
    p = raw / "players" / "dt=2026-01-01"; p.mkdir(parents=True)
    ts = pd.Timestamp("2026-01-01T00:00:00Z")
    pd.DataFrame([{"snapshot_id": "s1", "snapshot_ts": ts, "fetched_at": ts, "appid": a,
                   "player_count": c, "api_result": 1, "ok": True} for a, c in [(10, 5), (20, 7)]]
                 ).to_parquet(p / "players_x.parquet")
    s = raw / "steamspy" / "dt=2026-01-01"; s.mkdir(parents=True)
    (s / "steamspy_all_page0_20260101T000000Z.json").write_text(json.dumps(
        {"10": {"appid": 10, "name": "A", "owners": "1,000 .. 2,000", "price": "999"}}))


def test_load_is_idempotent(tmp_path, monkeypatch):
    raw = tmp_path / "raw"; _fixture(raw)
    monkeypatch.setattr(load, "RAW", raw)
    db = tmp_path / "t.duckdb"
    first = load.load_all(db)
    second = load.load_all(db)
    assert first == second
    assert first["player_counts"] == 2 and first["steamspy_owners"] == 1 and first["snapshots"] == 1


def test_reviews_and_tags_load_idempotent(tmp_path, monkeypatch):
    raw = tmp_path / "raw"; _fixture(raw)
    ts = pd.Timestamp("2026-01-01T00:00:00Z")
    r = raw / "reviews" / "dt=2026-01-01"; r.mkdir(parents=True)
    pd.DataFrame([{"appid": 10, "fetched_at": ts, "ok": True, "review_score": 8, "review_score_desc": "Very Positive",
                   "total_positive": 9, "total_negative": 1, "total_reviews": 10}]).to_parquet(r / "reviews_x.parquet")
    t = raw / "steamspy_tags" / "dt=2026-01-01"; t.mkdir(parents=True)
    pd.DataFrame([{"appid": 10, "fetched_at": ts, "ok": True, "owners_estimate_range": "1 .. 2",
                   "tags_json": json.dumps({"FPS": 5}), "payload_json": "{}"}]).to_parquet(t / "steamspy_tags_x.parquet")
    monkeypatch.setattr(load, "RAW", raw)
    db = tmp_path / "t.duckdb"
    assert load.load_all(db) == load.load_all(db)
    assert load.load_all(db)["app_reviews"] == 1 and load.load_all(db)["steamspy_tags"] == 1
