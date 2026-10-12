# Steam Pulse dashboard (Streamlit)

Pages: Overview, Launch decay curves, Free-to-play vs paid, Sales impact, Game lookup, Game Finder, Category leaderboards.

## Run locally
```bash
.venv/bin/pip install -r app/requirements.txt
.venv/bin/streamlit run app/streamlit_app.py
```
The Game Finder and leaderboards import `analysis/src/best_score.py` (Data Analyst), so deploy the whole repo including `analysis/`.

Data comes from `data/steam_pulse.duckdb` (opened read-only). The app replicates the dbt mart SQL
(`dim_game`, `fct_daily_players`) in memory because the marts are not materialized in the DB yet; once
`dbt run` builds them, `app/marts.py` can switch to reading `marts.*` directly.

## Free deployment: Streamlit Community Cloud
1. Push the repo to GitHub (public, or private with Cloud access).
2. At share.streamlit.io choose "New app", pick the repo and set the main file to `app/streamlit_app.py`. Cloud installs `app/requirements.txt`.
3. **Data:** the DuckDB file is gitignored and is written to by the snapshot cron, so don't ship it. Instead commit the
   small parquet extract: `python app/marts.py` writes `app/data/*.parquet` (~140 KB today). `marts.load()` uses the
   extract automatically when the DuckDB file is absent. Refresh it in the snapshot GitHub Action (re-export and commit).
4. **Limits:** Community Cloud gives about 1 GB RAM, apps sleep when idle, and GitHub warns at 50 MB and blocks files over 100 MB.
   At ~1,000 games x 1 row per day, `fct_daily_players` grows by about 365K rows a year, which is still only a few MB in parquet.
   No sampling is needed. If it ever gets too big, keep the most recent N days or move to MotherDuck's free tier.
