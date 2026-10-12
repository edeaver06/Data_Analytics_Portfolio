"""Without the real warehouse (clean checkout / CI), point the analysis layer at a tiny SYNTHETIC
DuckDB built here, so the view and SQL tests still run. Rows are generated from a fixed seed; only
the schemas and table names match the pipeline's marts. Real-data thresholds stay real-only."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import steam_analysis as sa  # noqa: E402

REAL = sa.DB.exists()
# Public Steam app ids of known software titles, used to exercise the software exclusion rule.
SOFTWARE_IDS = {431960: ["Casual", "Indie", "Utilities", "Photo Editing"], 365670: ["Utilities"], 629520: ["Audio Production"]}
GENRES = [["Action"], ["RPG", "Indie"], ["Strategy"], ["Casual", "Indie"], ["Simulation"], ["Adventure", "Action"]]


def build_fixture_db(path: Path, n_games: int = 60, seed: int = 0) -> Path:
    import duckdb
    rng = np.random.default_rng(seed)
    c = duckdb.connect(str(path))
    for s in ("staging", "marts", "snapshots"):
        c.execute(f"create schema {s}")
    c.execute("""create table marts.dim_game (appid integer, game_name varchar, developer varchar, publisher varchar,
        owners_estimate_range varchar, app_type varchar, is_free boolean, release_date date, primary_genre varchar,
        genres_any varchar[], categories varchar[], has_store_details boolean, price_usd double,
        store_list_price_usd double, store_discount_pct integer, deck_status varchar, has_online_coop boolean,
        has_local_coop boolean, has_split_screen boolean, full_controller_support boolean,
        has_remote_play_together boolean)""")
    c.execute("create table staging.stg_steamspy_owners (appid integer, positive bigint, negative bigint)")
    c.execute("""create table snapshots.snap_game_price (appid integer, store_discount_pct integer,
        dbt_valid_from timestamp, dbt_valid_to timestamp)""")
    c.execute("""create table staging.stg_player_counts (snapshot_id varchar, snapshot_ts timestamptz,
        snapshot_date_utc date, appid integer, player_count bigint)""")
    ids = list(range(10, 10 + n_games - len(SOFTWARE_IDS))) + list(SOFTWARE_IDS)
    for i, a in enumerate(ids):
        g = SOFTWARE_IDS.get(a, GENRES[i % len(GENRES)])
        price = 0.0 if i % 7 == 0 else float(rng.choice([4.99, 9.99, 19.99, 29.99]))
        c.execute("insert into marts.dim_game values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  [a, f"Synthetic Game {a}", "Synth Dev", "Synth Pub", "20,000 .. 50,000", "game", price == 0,
                   f"20{15 + i % 10}-0{1 + i % 9}-15", g[0], g, ["Single-player"], i % 5 != 4, price, price,
                   int(rng.choice([0, 0, 25, 50])), "Verified", i % 3 == 0, i % 4 == 0, False, i % 2 == 0, False])
        c.execute("insert into staging.stg_steamspy_owners values (?,?,?)",
                  [a, int(rng.integers(50, 50_000)), int(rng.integers(5, 5_000))])
        c.execute("insert into snapshots.snap_game_price values (?, 0, '2026-10-01', null)", [a])
        for day in range(3):
            c.execute("insert into staging.stg_player_counts values (?,?,?,?,?)",
                      [f"syn{day}", f"2026-10-0{day + 1} 12:00:00+00", f"2026-10-0{day + 1}", a, int(rng.integers(10, 20_000))])
    c.execute("""create table marts.fct_daily_players as
        select appid, snapshot_date_utc, count(*) n_snapshots, max(player_count) peak_players_sampled,
               avg(player_count) avg_players_sampled, min(player_count) min_players_sampled,
               arg_max(player_count, snapshot_ts) last_players, max(snapshot_ts) last_snapshot_ts
        from staging.stg_player_counts group by all""")
    c.close()
    return path


@pytest.fixture(scope="session", autouse=True)
def analysis_db(tmp_path_factory):
    if REAL:
        yield sa.DB
        return
    db = build_fixture_db(tmp_path_factory.mktemp("sp") / "steam_pulse.duckdb")
    old_db, old_defaults = sa.DB, sa.connect.__defaults__
    sa.DB, sa.connect.__defaults__ = db, (db,)
    yield db
    sa.DB, sa.connect.__defaults__ = old_db, old_defaults


@pytest.fixture
def using_real_db():
    return REAL
