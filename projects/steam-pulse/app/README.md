# Steam Pulse dashboard (Streamlit)

Pages: Overview, Launch decay curves, Free-to-play vs paid, Sales impact, Game lookup, Game Finder, Category leaderboards.

## Run locally
From `projects/steam-pulse/` (see the project README for the full copy-paste steps):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```
Some pages read result files from `analysis/` (`results.json`, `history_results.json`), so keep that folder alongside `app/`.

Data comes from the dbt marts in `data/steam_pulse.duckdb` (`marts.dim_game`, `bridge_game_category`,
`fct_daily_players`, `fct_daily_price`, plus `staging.stg_steamspy_owners` for score inputs), opened **read-only**.
Set `STEAM_PULSE_DB` to use another path. If the database is missing, the app falls back to the parquet extract in
`app/data/` (or `STEAM_PULSE_EXTRACT`). If both are missing, it shows a clear message instead of crashing.

**Composite score:** read from `marts.mart_game_scores` (a dbt port of `best_score.py`; verified
identical; re-checked at full coverage on 2026-10-12: 991 scored of 1,030 rows, same 8 software apps, 30 excluded for no reviews and 1 for no player count). `best_score.py` and scipy aren't needed at runtime.
The mart doesn't score software, so the "Include software" toggle only lists the software apps, unscored, at the bottom.

**History pages:** Launch decay and Sales impact read the analysis layer's `analysis/history_results.json` (SteamCharts monthly
retention; 2019-20 discount event study). Deploy the `analysis/` folder with the app. If the file is missing, those pages show a notice.

## Free deployment: Streamlit Community Cloud (prepared, not deployed)
The repo is already set up for it: the parquet extract is committed in `app/data/`, `app/requirements.txt` sits next to the entrypoint, and the theme is in `.streamlit/config.toml` at the **repo root** (Community Cloud only reads the config there).
1. Sign in at https://share.streamlit.io with GitHub (edeaver06) and allow access to `Data_Analytics_Portfolio`.
2. Choose **Create app → Deploy a public app from GitHub**: repo `edeaver06/Data_Analytics_Portfolio`, branch `main`, main file path `projects/steam-pulse/app/streamlit_app.py`.
3. Optional: pick a custom subdomain such as `steam-pulse.streamlit.app`; under Advanced settings choose Python 3.12. Then click **Deploy**.
4. Paste the app URL into the project README and the hub.

**Limits:** about 1 GB RAM, and the app sleeps after a period without traffic (the first visitor wakes it in under a minute). The data only updates when a new extract is committed (`python app/marts.py` re-exports `app/data/*.parquet` from a local DuckDB).
