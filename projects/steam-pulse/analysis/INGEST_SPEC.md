# Backfill ingest spec for Code Builder (requested by Data Analyst)

Source files: `analysis/data/backfill/tables/*.parquet` (provenance and licenses in `analysis/data/backfill/SOURCES.md`). Please ingest them as **separate source-tagged tables**. Don't merge them into `fct_daily_players`, because the granularity and the definitions differ.

| proposed model | grain / PK | columns | from |
|---|---|---|---|
| `stg_backfill_steamcharts_monthly` | (appid, month) | appid int, month date (1st of month), avg_players double, peak_players bigint, source='steamcharts', fetched_at | steamcharts_monthly.parquet |
| `stg_backfill_reviews_monthly` | (appid, month), unique after the fixed build | appid, month, reviews_up bigint, reviews_down bigint, n_buckets int, rollup_type (month|week; weekly buckets already summed), language='english', source='steam_histogram' | reviews_monthly.parquet |
| `stg_backfill_price_daily` | (appid, date) | appid, date, initial_price_usd, final_price_usd, discount_pct, source='mendeley_ycy3sy3vj2', license='CC BY 4.0' | mendeley_price_daily.parquet |
| `stg_backfill_players_daily` | (appid, date) | appid, date, avg_players, peak_players, n_hourly_obs, source='mendeley_ycy3sy3vj2' | mendeley_players_daily.parquet |
| `fct_monthly_players` (mart) | (appid, month) | union of steamcharts monthly + monthly rollup of your `fct_daily_players`, with a `source` column; flag partial months | above |
| `dim_game.launch_month_observed` | appid | first SteamCharts month if > 2012-08, else null | above |

Tests: unique PK; avg_players ≤ peak_players; discount_pct in [0,100]; month ≤ current month; relationships to `dim_game` (Mendeley apps outside today's top 1,000 should stay unrelated, so use `severity: warn`).

Ongoing (forward-fill, so the backfill isn't needed again):
1. Keep the 6-hourly snapshots and append `snap_game_price` daily. This becomes the price history from 2026-10 onward.
2. Monthly refresh of the review histogram endpoint (1 call per app).
3. Optional: IsThereAnyDeal `games/history/v2` once Evan registers an API key. That would cover the 2020-2026 price gap.
