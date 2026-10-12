"""Load Steam Pulse data for the app from the dbt marts (read-only).

Order of preference:
  1. data/steam_pulse.duckdb (override with STEAM_PULSE_DB), marts.* tables, opened read_only
  2. parquet extract in app/data/ (written by `python app/marts.py`, used on Streamlit Cloud)
  3. neither -> DataUnavailable, which the app shows as a clear message
"""
import os, sys, functools
from pathlib import Path
import duckdb, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("STEAM_PULSE_DB", ROOT / "data" / "steam_pulse.duckdb"))
EXTRACT = Path(os.environ.get("STEAM_PULSE_EXTRACT", Path(__file__).resolve().parent / "data"))
TABLES = ["dim_game", "fct_daily_players", "fct_daily_price", "bridge_game_category", "score_inputs", "mart_game_scores", "snapshots"]

class DataUnavailable(RuntimeError):
    pass

QUERIES = {
    "dim_game": "select * from marts.dim_game",
    "fct_daily_players": "select * from marts.fct_daily_players",
    "fct_daily_price": "select * from marts.fct_daily_price",
    "bridge_game_category": "select * from marts.bridge_game_category",
    # Inputs the analysis layer's best_score.py expects: SteamSpy review counts + SteamSpy price (the pipeline's
    # staging view; the marts only carry the share) and the latest concurrent-player reading.
    "score_inputs": """select o.appid, o.positive, o.negative, o.price_usd as steamspy_price_usd
                       from staging.stg_steamspy_owners o""",
    "mart_game_scores": """select appid, is_software, software_rule, excluded, excluded_reason, review_bayes, player_strength,
                           value_per_dollar, pct_review_bayes, pct_player_strength, pct_value_per_dollar, composite_score,
                           composite_rank, price_usd as score_price_usd from marts.mart_game_scores""",
    "snapshots": """select snapshot_ts, count(*) n_games, sum(player_count) total_players
                    from staging.stg_player_counts group by 1 order by 1""",
}

def _from_db():
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return {k: con.sql(q).df() for k, q in QUERIES.items()}
    finally:
        con.close()

@functools.lru_cache(maxsize=1)
def _load_tables_cached():
    return _load_tables_uncached()

def load_tables():
    """Cached once per process. Returns (dict of DataFrame copies, source label)."""
    t, src = _load_tables_cached()
    return {k: v.copy() for k, v in t.items()}, src

def _load_tables_uncached():
    """Returns (dict of DataFrames, source label). Raises DataUnavailable if no source exists."""
    if DB.exists():
        try:
            return _from_db(), f"dbt marts in {DB.name} (read-only)"
        except duckdb.Error as e:  # e.g. marts not built yet, or file locked
            err = e
    else:
        err = None
    if all((EXTRACT / f"{t}.parquet").exists() for t in TABLES):
        return {t: pd.read_parquet(EXTRACT / f"{t}.parquet") for t in TABLES}, "parquet extract (app/data)"
    raise DataUnavailable(f"No data source found. Database {DB} {'is missing' if err is None else f'could not be read ({err})'} "
                          f"and the parquet extract in {EXTRACT} is incomplete. Run the pipeline (dbt build) "
                          f"or `python app/marts.py` to create the extract.")

def load():
    """Back-compat: (dim, fct, snaps, source_label) with dim enriched with SteamSpy score inputs."""
    t, src = load_tables()
    dim = t["dim_game"].merge(t["score_inputs"], on="appid", how="left")
    return dim, t["fct_daily_players"], t["snapshots"], src

def load_bridge():
    t, _ = load_tables()
    b = t["bridge_game_category"].rename(columns={"attribute_type": "kind", "attribute": "label"})
    return b

def enrich(dim, fct):
    latest = fct.sort_values("snapshot_date_utc").groupby("appid").tail(1)[["appid", "last_players", "snapshot_date_utc"]]
    g = dim.merge(latest, on="appid", how="left")
    g["positive_review_share"] = g["steamspy_positive_share"]
    g["discount_pct"] = g["store_discount_pct"]            # store details only (449 games); NULL elsewhere
    g["initial_price_usd"] = g["store_list_price_usd"]
    # F2P = store is_free (the analysis layer's definition since full coverage); SteamSpy price $0 only as fallback
    free = g["is_free"].astype("boolean").fillna(g["price_usd"].eq(0))
    g["pricing"] = free.map({True: "Free-to-play", False: "Paid"})
    g.loc[free.isna(), "pricing"] = "Unknown"
    g["on_sale"] = g["discount_pct"].fillna(0) > 0
    g["owners_mid"] = (g["owners_estimate_low"] + g["owners_estimate_high"]) / 2
    ref = pd.Timestamp("2026-10-12")
    g["years_since_release"] = (ref - pd.to_datetime(g["release_date"])).dt.days / 365.25
    g["players_per_1k_owners"] = 1000 * g["last_players"] / g["owners_mid"].where(g["owners_mid"] > 0)
    return g

# ---- Composite score: marts.mart_game_scores ------------------------------------------
# The dbt mart is a port of the analysis layer's best_score.py into the mart (verified 2026-10-12: 991 scores and ranks
# identical, same 8 software apps excluded; GTA IV is excluded for no_player_count, which best_score also drops).
# So best_score.py is no longer imported at runtime.
WEIGHTS = {"review_bayes": 0.45, "player_strength": 0.35, "value_per_dollar": 0.20}  # mart_game_scores.sql
COMPONENTS = list(WEIGHTS)

def add_score(g, include_software=False):
    """Attach mart scores. The mart does not score software, so include_software=True only adds the
    8 software apps back to the list, unscored (score NaN), flagged is_software."""
    t, _ = load_tables(); ms = t["mart_game_scores"].copy()
    ms = ms.rename(columns={"composite_score": "score", "composite_rank": "score_rank"})
    for k, w in WEIGHTS.items():  # weighted parts sum to the score
        ms[k + "_part"] = w * ms["pct_" + k] / sum(WEIGHTS.values())
    keep = ["appid", "score", "score_rank", "is_software", "excluded", "excluded_reason", "score_price_usd"] + COMPONENTS + [k + "_part" for k in COMPONENTS]
    out = g.merge(ms[keep], on="appid", how="left")
    out["is_software"] = out.is_software.fillna(False).astype(bool)
    out["show_in_finder"] = out.score.notna() | (include_software & out.is_software)
    return out

HISTORY_JSON = ROOT / "analysis" / "history_results.json"

def load_history():
    """the analysis layer's history results (SteamCharts monthly retention, 2019-20 discount DiD). None if absent."""
    import json
    return json.loads(HISTORY_JSON.read_text()) if HISTORY_JSON.exists() else None

RESULTS_JSON = ROOT / "analysis" / "results.json"

def load_results():
    """the analysis layer's snapshot results (f2p test, genres). None if absent."""
    import json
    return json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else None

def coverage(dim):
    return {"games": len(dim), "tags": int(dim.has_tags.fillna(False).sum()),
            "deck": int(dim.deck_status.notna().sum()), "store_details": int(dim.has_store_details.fillna(False).sum())}

def export_parquet():
    t, src = load_tables()
    if not src.startswith("dbt marts"):
        raise SystemExit("Refusing to export: source is not the database.")
    EXTRACT.mkdir(exist_ok=True)
    for n, d in t.items():
        d.to_parquet(EXTRACT / f"{n}.parquet", index=False)
    for old in ["game_labels.parquet"]:  # superseded by bridge_game_category
        (EXTRACT / old).unlink(missing_ok=True)

if __name__ == "__main__":
    export_parquet()
