# Steam Pulse

A scheduled pipeline that tracks concurrent players, prices, reviews, tags and Steam Deck status for about 1,000 of the most-owned Steam games. It builds a growing history to answer one question: what keeps a game alive?

> **Status: Phase 1 (ingestion and warehouse).** History started on 2026-10-12. The findings and the hero chart get added once there are enough days of data.

## One command

```bash
./scripts/snapshot.sh          # ingest -> raw parquet/json -> DuckDB (idempotent) -> dbt build (models, snapshots, tests)
```
Suggested schedule: **every 6 hours** (`17 */6 * * *`), which gives 4 player-count samples per day. Run it at least once a day. Overlapping runs exit cleanly because of a lock file. Logs go to `logs/snapshot.log`.

```cron
17 */6 * * * cd /path/to/Data_Analytics_Portfolio/projects/steam-pulse && ./scripts/snapshot.sh >/dev/null 2>&1
```

## Sources (all public, no keys)
| Source | Endpoint | Cadence per run | Notes |
|---|---|---|---|
| Steam Web API | `ISteamUserStats/GetNumberOfCurrentPlayers` | all ~1,000 games | exact concurrent players at fetch time |
| SteamSpy | `request=all&page=0` | cached 7 days | defines the universe (top ~1,000 by owners) |
| SteamSpy | `request=appdetails` | 150 games/run, oldest first, 7-day refresh | user tags plus owner and playtime **ESTIMATES** |
| Steam store | `api/appdetails` | 150 games/run, 14-day refresh | price, discount, genres, categories, platforms, languages, Metacritic score, release date. Full JSON kept |
| Steam store | `appreviews/{id}?num_per_page=0` | 250 games/run, 20-hour refresh | review **counts** only (no text) |
| Steam store | `saleaction/ajaxgetdeckappcompatibilityreport` | 200 games/run, 14-day refresh | Deck Verified/Playable/Unsupported. **Undocumented endpoint** |

Budgets keep store requests to 1 every 1.6 s (or slower). Every request uses retries, exponential backoff with jitter, and `Retry-After`. The budgeted sources are resumable: each run refreshes the never-fetched or stalest games first, so full coverage of all 1,000 games builds up within about 7 runs.

**SteamSpy owner counts and playtimes are third-party estimates (bucketed ranges), not Valve figures.**

## Layout
```
steam_pulse/   http.py (rate limits + retries) · ingest.py (one snapshot) · load.py (idempotent raw load)
dbt/           models/{staging,marts} · snapshots/ (SCD2 price + tags) · tests/
scripts/snapshot.sh   tests/   .github/workflows/snapshot.yml
data/          (git-ignored) raw/<source>/dt=YYYY-MM-DD/*  +  steam_pulse.duckdb
```
The raw files are immutable and timestamped. The loads use `INSERT OR IGNORE` on natural keys, so running a load again never duplicates data.

## Marts: grain and refresh
| Model | Grain | Refresh |
|---|---|---|
| `marts.fct_daily_players` | appid × UTC day (peak/avg/min/last over that day's samples) | incremental, every run; the current day is reprocessed |
| `marts.fct_daily_price` | appid × UTC day with an appdetails fetch (price, initial price, discount_pct) | incremental. Days are sparse because of the budget, so use `snap_game_price` for continuous ranges |
| `marts.fct_review_counts` | appid × UTC day (total positive, negative and overall reviews) | incremental. Daily new reviews = diff |
| `marts.dim_game` | appid (current state) | rebuilt every run |
| `marts.bridge_game_category` | appid × attribute_type (`genre`/`category`/`tag`) × attribute | rebuilt every run, for multi-filtering |
| `marts.mart_game_scores` | appid (current state) | rebuilt every run |
| `snapshots.snap_game_price` | SCD2 row per price/discount state (`dbt_valid_from/to`) | every run |
| `snapshots.snap_game_tags` | SCD2 row per tag-set and genre-set state | every run |

`dim_game` includes app_type, is_free, release_date (parsed), metacritic_score, genres, categories, tags, developers, publishers, platform flags, languages, deck_status, `first_seen_date_utc` (the first time the pipeline saw the game), owner estimates, and review totals. It also has these flags: `is_single_player, has_online_coop, has_local_coop, has_split_screen, has_pvp, full_controller_support, has_remote_play_together, has_workshop, has_achievements`.

### `mart_game_scores` (documented composite)
- `bayes_review_score = (C·m + positive) / (C + total)`, where m is the global positive share weighted by review count and C is the median review count across tracked games.
- `avg_players_7d`, which feeds `pct_player_strength`: the percentile of ln(1 + players).
- `retention_4w_ratio` = 7-day average players ÷ the 7-day average 4 weeks earlier. **NULL until there are 28 days of history.**
- `momentum_wow` = this week's average ÷ last week's average − 1. **NULL until there are 14 days of history.**
- `hours_per_dollar` = SteamSpy median playtime (estimate) ÷ price. NULL for free games.
- `composite_score` = a weighted mean of the percentile components: quality 0.35, player strength 0.25, retention 0.15, value 0.15, momentum 0.10. Weights are renormalised over the components that are not null. `composite_has_history` flags when retention and momentum are included.

## Tests
`pytest` runs offline tests of loader idempotency and the rate-limit and refresh policy. `dbt build` runs schema tests (unique, not_null, relationships, accepted_values, unique key combinations) plus custom tests: non-negative players, owner ranges in order, review counts that add up, and scores within [0, 1].

## Known limits
- The universe is the top ~1,000 most-owned games, so brand-new releases enter only if they reach that list. `first_seen` is measured within this universe.
- Concurrent players are point samples, not true daily peaks.
- GitHub Actions runners are ephemeral. The workflow caches `data/`, and durable history needs MotherDuck or a data branch (Phase 2).

Data: Valve Steam Web API and store endpoints; SteamSpy (steamspy.com). This project is not affiliated with Valve.
