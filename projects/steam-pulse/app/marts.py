"""Load Steam Pulse marts. Prefers built dbt marts (marts.dim_game / marts.fct_daily_players);
falls back to the same SQL as the dbt models run in-memory on raw tables (read-only), or to a
parquet extract in app/data/ (for Streamlit Cloud)."""
from pathlib import Path
import sys
import duckdb, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "steam_pulse.duckdb"
EXTRACT = Path(__file__).resolve().parent / "data"

STG = """
create temp view stg_steamspy_owners as
with ranked as (select *, row_number() over (partition by appid order by fetched_at desc) rn from raw.steamspy_owners)
select appid, name, developer, publisher, fetched_at, owners_estimate_range,
  cast(replace(split_part(owners_estimate_range,' .. ',1),',','') as bigint) owners_estimate_low,
  cast(replace(split_part(owners_estimate_range,' .. ',2),',','') as bigint) owners_estimate_high,
  positive, negative, case when positive+negative>0 then positive/(positive+negative) end positive_review_share,
  price_cents/100.0 price_usd, initialprice_cents/100.0 initial_price_usd, discount_pct, ccu_yesterday_peak
from ranked where rn=1;
create temp view stg_appdetails as
with ranked as (select *, row_number() over (partition by appid order by fetched_at desc) rn from raw.appdetails where success)
select appid, payload->>'$.name' store_name, payload->>'$.type' app_type, cast(payload->>'$.is_free' as boolean) is_free,
  try_strptime(payload->>'$.release_date.date',['%d %b, %Y','%b %d, %Y','%b %Y'])::date release_date,
  cast(payload->>'$.price_overview.final' as integer)/100.0 store_price_usd,
  cast(payload->>'$.metacritic.score' as integer) metacritic_score, payload->>'$.genres[0].description' primary_genre
from ranked where rn=1;
create temp view stg_player_counts as
select snapshot_id, snapshot_ts, cast(snapshot_ts at time zone 'UTC' as date) snapshot_date_utc, appid, player_count
from raw.player_counts where ok and player_count is not null;
"""
DIM = """select s.appid, coalesce(a.store_name,s.name) game_name, s.developer, s.publisher, a.app_type, a.is_free,
  a.release_date, a.primary_genre, a.metacritic_score, coalesce(a.store_price_usd,s.price_usd) price_usd,
  s.owners_estimate_range, s.owners_estimate_low, s.owners_estimate_high, s.positive_review_share,
  a.appid is not null has_store_details,
  -- extra SteamSpy fields used by the viz layer (not in dim_game yet)
  s.price_usd as steamspy_price_usd, s.initial_price_usd, s.discount_pct, s.ccu_yesterday_peak, s.positive, s.negative
from stg_steamspy_owners s left join stg_appdetails a using(appid)"""
FCT = """with d as (select appid, snapshot_date_utc, count(*) n_snapshots, max(player_count) peak_players_sampled,
  avg(player_count) avg_players_sampled, min(player_count) min_players_sampled,
  arg_max(player_count,snapshot_ts) last_players, max(snapshot_ts) last_snapshot_ts from stg_player_counts group by 1,2)
select *, peak_players_sampled - lag(peak_players_sampled) over (partition by appid order by snapshot_date_utc) peak_change_vs_prev_day from d"""
SNAPS = "select snapshot_ts, count(*) n_games, sum(player_count) total_players from stg_player_counts group by 1 order by 1"

def load():
    """Returns (dim, fct, snaps, source_label)."""
    if (EXTRACT / "dim_game.parquet").exists() and not DB.exists():
        r = lambda n: pd.read_parquet(EXTRACT / f"{n}.parquet")
        return r("dim_game"), r("fct_daily_players"), r("snapshots"), "parquet extract"
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("set TimeZone='UTC'")
    con.execute(STG)
    dim = con.sql(DIM).df(); fct = con.sql(FCT).df(); snaps = con.sql(SNAPS).df()
    con.close()
    return dim, fct, snaps, "raw tables via dbt mart SQL (marts not yet materialized)"

def enrich(dim, fct):
    latest = fct.sort_values("snapshot_date_utc").groupby("appid").tail(1)[["appid","last_players","snapshot_date_utc"]]
    g = dim.merge(latest, on="appid", how="left")
    g["pricing"] = g["price_usd"].fillna(-1).eq(0).map({True: "Free-to-play", False: "Paid"})
    g.loc[g["price_usd"].isna(), "pricing"] = "Unknown"
    g["on_sale"] = g["discount_pct"].fillna(0) > 0
    g["owners_mid"] = (g["owners_estimate_low"] + g["owners_estimate_high"]) / 2
    ref = pd.Timestamp("2026-10-12")
    g["years_since_release"] = (ref - pd.to_datetime(g["release_date"])).dt.days / 365.25
    g["players_per_1k_owners"] = 1000 * g["last_players"] / g["owners_mid"].where(g["owners_mid"] > 0)
    return g

def export_parquet():
    dim, fct, snaps, _ = load(); EXTRACT.mkdir(exist_ok=True)
    for n, d in [("dim_game", dim), ("fct_daily_players", fct), ("snapshots", snaps)]:
        d.to_parquet(EXTRACT / f"{n}.parquet", index=False)


# ---- Composite score (Data Analyst, analysis/src/best_score.py) ------------------------
# Reused, not reimplemented: we import best_score.score() and feed it the same population and
# columns as analysis/sql/00_views.sql a_game (SteamSpy price, SteamSpy reviews, snapshot CCU).
sys.path.insert(0, str(ROOT / "analysis" / "src"))
import best_score  # noqa: E402
SCORE_JSON = ROOT / "analysis" / "best_score_results.json"
COMPONENTS = ["review_bayes", "player_strength", "value_per_dollar"]

def add_score(g):
    pop = g[g.last_players.notna() & ((g.positive + g.negative) > 0)]
    inp = pop[["appid", "positive", "negative"]].assign(player_count=pop.last_players, price_usd=pop.steamspy_price_usd)
    s = best_score.score(inp)
    w = best_score.WEIGHTS
    for k in COMPONENTS:  # weighted parts sum to the score (active weights sum to 1)
        s[k + "_part"] = w[k] * s[k].rank(pct=True) / sum(w[c] for c in COMPONENTS)
    keep = ["appid", "score"] + COMPONENTS + [k + "_part" for k in COMPONENTS]
    out = g.merge(s[keep], on="appid", how="left")
    out["score_rank"] = out.score.rank(ascending=False, method="min")
    return out

# ---- Game Finder support -------------------------------------------------------------
# No Code Builder category bridge or score mart exists yet (checked dbt/models/marts and the DB),
# so this builds a long-form bridge from raw.appdetails (store categories + genres) in memory.
BRIDGE = """
select appid, 'category' as kind, c->>'description' as label from raw.appdetails,
  unnest(from_json(payload->'$.categories','["json"]')) t(c) where success
union all
select appid, 'genre', g->>'description' from raw.appdetails,
  unnest(from_json(payload->'$.genres','["json"]')) t(g) where success
"""
FEATS = """select appid, payload->>'$.controller_support' controller_support,
  try_strptime(payload->>'$.release_date.date',['%d %b, %Y','%b %d, %Y','%b %Y'])::date release_date
  from raw.appdetails where success qualify row_number() over (partition by appid order by fetched_at desc)=1"""

def load_bridge():
    if (EXTRACT / "game_labels.parquet").exists() and not DB.exists():
        return pd.read_parquet(EXTRACT / "game_labels.parquet")
    con = duckdb.connect(str(DB), read_only=True)
    b = con.sql(f"select distinct * from ({BRIDGE})").df(); con.close()
    return b

def export_bridge():
    EXTRACT.mkdir(exist_ok=True); load_bridge().to_parquet(EXTRACT / "game_labels.parquet", index=False)

if __name__ == "__main__":
    export_parquet(); export_bridge()
