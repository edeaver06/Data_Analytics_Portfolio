# Steam Pulse: What keeps a video game alive?

**Overview.** Steam is the biggest online store for PC games, and it shows how many people are playing each game right now. I built a pipeline that collects those live player counts, prices, reviews and features for about 1,000 of Steam's most popular games, plus monthly history back to 2012. Then I used it to answer one question: which games do people actually play, and what do the busy ones have in common?

### Key findings
- **Winner takes most.** 6.22M people were playing 1,029 tracked games; the **top 10 held 40.1%**, and the typical game had just 417 players.
- **Playing with friends matters.** Games with online co-op have a typical crowd of about 1,090 players, almost 4× the 278 for games without it.
- **The first month is make-or-break.** Games lose about **44%** of their players after month one, then level off for years.
- **Sales work.** In the first week of a sale, games had about **39% more** daily players than similar games not on sale (10,756 sales, 2019–20).
- **The "best" games are cheap old favourites:** Terraria, Stardew Valley and Left 4 Dead 2 top a combined review, popularity and value score.

**[📖 Read the story (notebook)](notebooks/steam_pulse_story.ipynb)**: the plain-English walkthrough, one question and one chart at a time.  
**[▶️ Run the app](#run-the-app)**: an interactive dashboard, including a Game Finder where you pick categories and get the top game.

![Top 15 games by concurrent players](images/hero_concentration.png)

## Run the app
Copy and paste (Python 3.10+). The dashboard runs on the bundled parquet extract in `app/data/`, so no database or API key is needed:
```bash
git clone https://github.com/edeaver06/Data_Analytics_Portfolio.git
cd Data_Analytics_Portfolio/projects/steam-pulse
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```
Then open http://localhost:8501. Pages: Overview, Launch decay curves, Free-to-play vs paid, Sales impact, Game lookup, Game Finder, Category leaderboards.

---

## For engineers
Everything below is technical detail: how the data is collected, modelled and tested.

**What it is:** a scheduled data pipeline (Python → DuckDB → dbt) that snapshots concurrent players, prices, reviews, tags and Steam Deck status, with a Streamlit dashboard on top.

> **Status: in progress.** Live snapshots began 2026-10-12 (4 so far). A historical backfill (SteamCharts monthly since 2012, Mendeley daily 2017–2020) powers the retention, discount and sentiment findings in [`analysis/`](analysis/README.md). Metrics based on live history fill in as days accumulate.

### What's in this folder
| Folder | What it's for |
|---|---|
| `steam_pulse/` | Python ingestion: API clients with rate limits and retries, one-snapshot ingest, idempotent raw load into DuckDB |
| `dbt/` | Warehouse models (staging → marts), SCD2 snapshots for price and tags, data tests, and the software-exclusion seed |
| `app/` | Streamlit dashboard (`streamlit_app.py`) and its parquet data extract (`data/`) |
| `analysis/` | Historical analyses (retention, discount event study, sentiment lead/lag, composite score) with their SQL, code, charts and results |
| `scripts/` | `snapshot.sh` (runs the full pipeline) and the chart generators (`make_hero.py`, `make_viz.py`, `polish_figures.py`) |
| `images/` | Charts used in this README (`scripts/make_viz.py` can regenerate more chart PNGs here) |
| `notebooks/` | The plain-English story notebook (`steam_pulse_story.ipynb`); its chart helpers are in `steam_pulse/story.py` |
| `tests/` | pytest checks for the HTTP client, the loader and score parity |
| `data/` | *Not in git.* Raw snapshots and `steam_pulse.duckdb`, created when you run the pipeline |

### How the app gets its data
The app reads the dbt marts in `data/steam_pulse.duckdb` (`marts.dim_game`, `bridge_game_category`, `fct_daily_players`, `fct_daily_price`, plus `staging.stg_steamspy_owners` for score inputs), opened **read-only**. Set `STEAM_PULSE_DB` to use another path. If the database is missing, it falls back to the parquet extract in `app/data/` (or `STEAM_PULSE_EXTRACT`); if both are missing it shows a clear message instead of crashing. `python app/marts.py` re-exports the extract from a local DuckDB.
- **Composite score:** read from `marts.mart_game_scores` (a verified dbt port of `best_score.py`: 991 scored of 1,030 rows, 8 software apps, 30 excluded for no reviews and 1 for no player count). The mart doesn't score software, so the "Include software" toggle only lists software apps, unscored, at the bottom.
- **History pages:** Launch decay and Sales impact read `analysis/history_results.json`, so deploy the `analysis/` folder with the app. If the file is missing, those pages show a notice.

### Free deployment: Streamlit Community Cloud (prepared, not deployed)
The parquet extract is committed in `app/data/`, `app/requirements.txt` sits next to the entrypoint (Community Cloud looks for dependencies in the entrypoint's folder, then the repo root, so this file is required), and the theme is in `.streamlit/config.toml` at the **repo root**.
1. Sign in at https://share.streamlit.io with GitHub (edeaver06) and allow access to `Data_Analytics_Portfolio`.
2. **Create app → Deploy a public app from GitHub**: repo `edeaver06/Data_Analytics_Portfolio`, branch `main`, main file `projects/steam-pulse/app/streamlit_app.py`.
3. Optional: a custom subdomain such as `steam-pulse.streamlit.app`; Python 3.12 under Advanced settings. Click **Deploy**.
4. Paste the app URL into this README and the hub.

Limits: about 1 GB RAM, and the app sleeps when idle (the first visitor wakes it in under a minute). Data only updates when a new extract is committed.

### What the snapshots show (12 Oct 2026)
- **Attention is extremely concentrated.** Across 1,029 tracked games there were 6.22M concurrent players, and **10 games held 40.1%** of them (latest snapshot, 2026-10-12 09:29 CST). Counter-Strike 2 alone had 1.16M, more than the next 3 games combined.
- **"Game" on Steam isn't always a game.** Wallpaper Engine ranks #6 with 104k concurrent users, and the store labels it `app_type = game`. `dim_game.genres_any` and `tags` are there so analyses can exclude software (rule: `analysis/README.md`).
- **Steam Deck readiness is mixed.** Of 1,029 games checked, 301 are Verified, 478 Playable, 182 Unsupported and 67 Unknown (1 not yet checked).
- **Few games were on sale at the time.** 126 of 1,028 games with store details had a discount. Price changes will be tracked over time in `snap_game_price`.
- **Top composite scores** (8 software apps excluded, 991 games scored): Terraria, Stardew Valley, Left 4 Dead 2, The Binding of Isaac: Rebirth and Garry's Mod.

**From the live snapshots, coming once history builds up:** retention curves (need 28 days), week-over-week momentum (14 days), launch-decay curves, sale and price elasticity (before/after panels from `snap_game_price`), and review-sentiment lead/lag. Until then these are NULL or blocked on purpose. Nothing is extrapolated.

### Run the pipeline (optional)
```bash
./scripts/snapshot.sh          # ingest -> raw parquet/json -> DuckDB (idempotent) -> dbt build (models, snapshots, tests)
```
For a one-off coverage pass (every tracked game for store details, reviews, tags and Deck status; about 70 minutes at polite rates), run `./scripts/snapshot.sh --catch-up`. It uses the same lock file, so it never overlaps a scheduled run.

Suggested schedule: **every 6 hours** (`17 */6 * * *`), which gives 4 player-count samples per day. Run it at least once a day. Overlapping runs exit cleanly because of a lock file. Logs go to `logs/snapshot.log`.

```cron
17 */6 * * * cd /path/to/projects/steam-pulse && ./scripts/snapshot.sh >/dev/null 2>&1
```

### Sources (all public, no keys)
| Source | Endpoint | Cadence per run | Notes |
|---|---|---|---|
| Steam Web API | `ISteamUserStats/GetNumberOfCurrentPlayers` | all ~1,000 games | exact concurrent players at fetch time |
| SteamSpy | `request=all&page=0` | cached 7 days | defines the universe (top ~1,000 by owners) |
| SteamSpy | `request=appdetails` | 150 games/run, oldest first, 7-day refresh | user tags plus owner and playtime **ESTIMATES** |
| Steam store | `api/appdetails?filters=price_overview` (batches of 50) | **all games, every run** | daily price and discount history |
| Steam store | `api/featuredcategories` → new_releases, and SteamSpy `top100in2weeks` | every run | **new-release tracking**: once seen, an app stays tracked |
| Steam store | `api/appdetails` | 150 games/run, 14-day refresh | price, discount, genres, categories, platforms, languages, Metacritic score, release date. Full JSON kept |
| Steam store | `appreviews/{id}?num_per_page=0` | 250 games/run, 20-hour refresh | review **counts** only (no text) |
| Steam store | `saleaction/ajaxgetdeckappcompatibilityreport` | 200 games/run, 14-day refresh | Deck Verified/Playable/Unsupported. **Undocumented endpoint** |

Budgets keep store requests to 1 every 1.6 s (or slower). Every request uses retries, exponential backoff with jitter, and `Retry-After`. The budgeted sources are resumable: each run refreshes the never-fetched or stalest games first, so full coverage of all 1,000 games builds up within about 7 runs.

**SteamSpy owner counts and playtimes are third-party estimates (bucketed ranges), not Valve figures.**

### Marts: grain and refresh
| Model | Grain | Refresh |
|---|---|---|
| `marts.fct_daily_players` | appid × UTC day (peak/avg/min/last over that day's samples) | incremental, every run; the current day is reprocessed |
| `marts.fct_daily_price` | appid × UTC day (last observation that day: price, initial price, discount_pct, obs_source) | incremental, every run, all tracked games |
| `marts.fct_monthly_players` | appid × month × source (`steamcharts` 2012-07 onward, or `steam_pulse` rollup) plus `is_partial_month` | rebuilt every run. The two sources are **not merged** because their definitions differ |
| `staging.stg_backfill_*` | steamcharts_monthly and reviews_monthly (appid × month); price_daily and players_daily (appid × date, Mendeley 2017-20) | reloaded in full from `analysis/data/backfill/tables/` on every load (idempotent, picks up crawl progress) |
| `marts.fct_review_counts` | appid × UTC day (total positive, negative and overall reviews) | incremental. Daily new reviews = diff |
| `marts.dim_game` | appid (current state) | rebuilt every run |
| `marts.bridge_game_category` | appid × attribute_type (`genre`/`category`/`tag`) × attribute | rebuilt every run, for multi-filtering |
| `marts.mart_game_scores` | appid (current state) | rebuilt every run |
| `snapshots.snap_game_price` | SCD2 row per price/discount state (`dbt_valid_from/to`) | every run |
| `snapshots.snap_game_tags` | SCD2 row per tag-set and genre-set state | every run |

`dim_game` covers the SteamSpy top 1,000 plus every app seen on a new-release list (`universe_source`, `first_seen_on_new_release_list`). It also has `launch_month_observed`: the first SteamCharts month, if later than 2012-08; otherwise NULL. It includes app_type, is_free, release_date (parsed), metacritic_score, genres, categories, tags, developers, publishers, platform flags, languages, deck_status, `first_seen_date_utc` (the first time the pipeline saw the game), owner estimates, and review totals. It also has these flags: `is_single_player, has_online_coop, has_local_coop, has_split_screen, has_pvp, full_controller_support, has_remote_play_together, has_workshop, has_achievements`.

#### `mart_game_scores` (composite ported from `analysis/src/best_score.py`)
The dbt model reproduces it exactly. `tests/test_score_parity.py` checks this against the current DB: across 991 scored games the largest absolute difference is 0.0 and the Spearman correlation is 1.0.
- **Scored set:** the latest player count is not null, SteamSpy positive + negative > 0, and `is_software` is false. Every other row has `excluded = true`, an `excluded_reason` (`software`, `no_player_count` or `no_reviews`) and a NULL score.
- `review_bayes = (pos + 1000·μ) / (pos + neg + 1000)`. This uses SteamSpy review counts, with μ the global positive share over the scored set (1,000 pseudo-reviews).
- `player_strength = ln(1 + players)`, using the latest day's `last_players`.
- `value_per_dollar = review_bayes · ln(1 + players) / max(price_usd, $1)`. Free games are floored at $1.
- `composite_score = 0.45·pct(review_bayes) + 0.35·pct(player_strength) + 0.20·pct(value_per_dollar)`. pct is the average-tie percentile rank among scored games (pandas `rank(pct=True)`). `composite_rank` orders the scores.
- **Software rule (`is_software`, `software_rule`):** a game counts as software if it's on the curated list (`dbt/seeds/software_exclusions.csv`, the single copy, also read by `analysis/src/best_score.py`). It also counts if `genres_any` includes Utilities, Software, Design & Illustration, Animation & Modeling, Audio Production, Video Production, Photo Editing, Web Publishing, Game Development or Education, and none of Action, Adventure, RPG, Strategy, Simulation, Sports or Racing.
- `retention_4w_ratio` needs 28 days of history and `momentum_wow` needs 14. Both have **weight 0** for now and are kept as information. `hours_per_dollar` (SteamSpy playtime estimate) is information only.

### Data sources, licensing and attribution
| Source | Terms | How it's used here |
|---|---|---|
| Steam Web API (`GetNumberOfCurrentPlayers`) | Steam Web API Terms of Use | live counts; only derived aggregates are published |
| Steam store endpoints (appdetails, appreviews, appreviewhistogram, featuredcategories, Deck report) | public but **undocumented** store endpoints, under the Steam Subscriber Agreement. **Redistribution terms are unclear** | raw responses stay local (git-ignored); only aggregates are published |
| SteamSpy API | no published license. **Terms are unclear**; credit "Data: SteamSpy.com" | owner, playtime and tag **estimates** |
| SteamCharts.com monthly tables (backfill) | no ToS and no robots.txt found on 2026-10-12. **Terms are unclear** | fetched politely (1 request every 1.5 s); attribution "Data: SteamCharts.com"; raw data not redistributed |
| Vihanga et al., *Steam Games Dataset: Player count history, Price history and data about games*, Mendeley Data v1, doi:10.17632/ycy3sy3vj2.1 | **CC BY 4.0** (redistribution allowed with attribution) | daily price for 2019-04 to 2020-08 and daily players for 2017-12 to 2020-08 |

Not used: SteamDB (its terms forbid scraping), IsThereAnyDeal (needs an API key; it's the recommended source for 2020-26 price history), and Kaggle (needs an account). Full provenance: `analysis/data/backfill/SOURCES.md`.

### Tests
`pytest` runs offline tests of loader idempotency and the rate-limit and refresh policy, plus a parity test of the score against `best_score.py`. The parity test is skipped when there's no local DB. `dbt build` runs schema tests (unique, not_null, relationships, accepted_values, unique key combinations) plus custom tests: non-negative players, owner ranges in order, review counts that add up, and scores within [0, 1].

### Known limits
- The universe is the top ~1,000 most-owned games, so brand-new releases enter only if they reach that list. `first_seen` is measured within this universe.
- Concurrent players are point samples, not true daily peaks.
- GitHub Actions runners are ephemeral. The workflow caches `data/`, and durable history needs MotherDuck or a data branch (Phase 2).

Data: Valve Steam Web API and store endpoints; SteamSpy (steamspy.com). This project is not affiliated with Valve.
