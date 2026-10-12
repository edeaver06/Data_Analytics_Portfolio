# Steam Pulse dashboard (Streamlit)

Pages: Overview, Launch decay curves, Free-to-play vs paid, Sales impact, Game lookup, Game Finder, Category leaderboards.

## Run locally
```bash
.venv/bin/pip install -r app/requirements.txt
.venv/bin/streamlit run app/streamlit_app.py
```
The Game Finder and leaderboards import `analysis/src/best_score.py` (Data Analyst), so deploy the whole repo including `analysis/`.

Data comes from Code Builder's dbt marts in `data/steam_pulse.duckdb` (`marts.dim_game`, `bridge_game_category`,
`fct_daily_players`, `fct_daily_price`, plus `staging.stg_steamspy_owners` for score inputs), opened **read-only**.
Set `STEAM_PULSE_DB` to use another path. If the database is missing, the app falls back to the parquet extract in
`app/data/` (or `STEAM_PULSE_EXTRACT`). If both are missing, it shows a clear message instead of crashing.

**Composite score:** read from `marts.mart_game_scores` (Code Builder's port of Data Analyst's `best_score.py`; verified
identical; re-checked at full coverage on 2026-10-12: 991 scored of 1,030 rows, same 8 software apps, 30 excluded for no reviews and 1 for no player count). `best_score.py` and scipy aren't needed at runtime.
The mart doesn't score software, so the "Include software" toggle only lists the software apps, unscored, at the bottom.

**History pages:** Launch decay and Sales impact read Data Analyst's `analysis/history_results.json` (SteamCharts monthly
retention; 2019-20 discount event study). Deploy the `analysis/` folder with the app. If the file is missing, those pages show a notice.

## Free deployment: Streamlit Community Cloud
1. Push the repo to GitHub (public, or private with Cloud access).
2. At share.streamlit.io choose "New app", pick the repo and set the main file to `app/streamlit_app.py`. Cloud installs `app/requirements.txt`.
3. **Data:** the DuckDB file is gitignored and is written to by the snapshot cron, so don't ship it. Instead commit the
   small parquet extract: `python app/marts.py` writes `app/data/*.parquet` (~300 KB today). `marts.load()` uses the
   extract automatically when the DuckDB file is absent. Refresh it in the snapshot GitHub Action (re-export and commit).
4. **Limits:** Community Cloud gives about 1 GB RAM, apps sleep when idle, and GitHub warns at 50 MB and blocks files over 100 MB.
   At ~1,000 games x 1 row per day, `fct_daily_players` grows by about 365K rows a year, which is still only a few MB in parquet.
   No sampling is needed. If it ever gets too big, keep the most recent N days or move to MotherDuck's free tier.
