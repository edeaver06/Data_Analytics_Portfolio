# Steam Pulse: Analysis Layer

Owned by Data Analyst. It reads Code Builder's marts (`marts.*`, `snapshots.*`, `staging.stg_player_counts` / `stg_steamspy_owners`) from `data/steam_pulse.duckdb`, attached **read-only**. No pipeline or mart files were edited. The historical backfill lives in `data/backfill/` (sources and licenses in [`data/backfill/SOURCES.md`](data/backfill/SOURCES.md); ingest spec for Code Builder in [`INGEST_SPEC.md`](INGEST_SPEC.md)).

```
analysis/.venv/bin/python analysis/src/steam_analysis.py          # snapshot cross-section -> results.json
(cd analysis/src && ../.venv/bin/python best_score.py)              # composite score -> best_score_results.json  [--include-software]
analysis/.venv/bin/python analysis/src/backfill_fetch.py steamcharts|reviews   # polite crawl (resumable)
analysis/.venv/bin/python analysis/src/backfill_build.py [--mendeley]          # parse -> data/backfill/tables
(cd analysis/src && ../.venv/bin/python history.py)                 # time-series analyses -> history_results.json
analysis/.venv/bin/python -m pytest analysis/tests                  # 15 tests; DB-dependent ones skip if the DB is absent
```

## Headline findings (history, 2012–2026)
1. **Players drop 44% after the first month and then level off.** Median monthly average players vs. the launch-peak month: **0.56 at month 1, 0.37 at month 2, 0.25 at month 6, 0.29 at month 12, 0.26 at month 24** (600 of today's top games with an observed launch). Free-to-play holds better (0.80 at month 1 → 0.40 at month 6, n=110) than paid (0.51 → 0.22, n=490). Games launched in 2020+ decay faster: 0.48 → 0.17 at month 6 (n=233) vs 0.62 → 0.31 for 2012–2019 (n=367).
2. **Discounts are associated with +39% daily players during the first week of a sale** (stacked difference-in-differences vs. same-window, non-discounted paid games; 10,756 sale starts across 1,453 games, 2019–20; game-clustered 95% CI +37.6% to +41.3%). The pre-trend over days −7 to −1 is −0.2%. The effect scales with discount depth: 10–33% off → +22%, 34–50% → +32%, 51–75% → +40%, 76%+ → +53%.
3. **Review sentiment does not lead player counts.** Within-game monthly changes in positive share correlate with player changes at |r| ≤ 0.05 at every lag from −3 to +3 months (928 games, 95k game-months). Review volume moves with players in the same month (r=0.65) and mean-reverts at the other lags (r ≈ −0.04 to −0.17).
4. **Launch-time facts barely predict players 30 days after launch.** A linear model using price, F2P, developer prior hit, Q4 and post-2020 gets a backtest MAE of **1.76** (log players) vs **2.03** for a train-median baseline (4 expanding time folds, 655 launches), about 13% better. Adding the launch-month peak (post-launch information) cuts MAE to **0.97**, vs 1.66 for naive carry-forward.
5. **"Best game" rankings are stable year to year.** Re-scored each December: Spearman **0.97–0.98** between consecutive years (2022→2025, 860–910 games). Top-20 overlap is **70–80%**, so the top of the list churns more than the whole ranking.

## Snapshot cross-section (Code Builder's current marts, correlation only)
- **Coverage:** 1,030 games (the top 1,000 plus 30 newly tracked releases; 1,029 with CCU); store details now cover **1,029**; Deck status 1,029; 4 snapshots, all on 2026-10-12.
- **Concentration:** 6.22M concurrent players; the top 10 games hold 40.1%.
- **F2P vs paid: no difference now.** Free median CCU 542 vs paid 411 (152 vs 877 games, Mann-Whitney p=0.47). The earlier "paid 551 vs free 135" used SteamSpy price=0 as the F2P flag; it now uses the store's `is_free`. Paid games still review better: 89.4% vs 80.2% positive.
- **Sentiment vs players:** Spearman ρ=0.22 (n=995).
- **On sale today:** median CCU 520 vs 403 at full price (126 vs 751 paid games). This is a cross-section; see finding 2 for the causal design.
- **Steam Deck:** Verified median CCU 877 (n=301), Playable 506 (479), Unsupported 244 (182).
- **Genres** (`genres_any`, software genres excluded): Racing 1,096 (n=29), Simulation 948 (207), Sports 847 (40), Strategy 721 (209), RPG 712 (266), Early Access 685 (32), Adventure 618 (392); lowest are Free To Play 185 (175), Indie 300 (378) and Action 343 (686). MMO (75.0%) and Free To Play (77.0%) review worst. (Earlier figures of RPG 18.3k and then 4.6k came from 148- and 449-game store-detail subsets that leaned toward popular games.)

## "Best game" composite score (`src/best_score.py`)
| component | weight | definition |
|---|---|---|
| review_bayes | 0.45 | (pos + 1000·μ)/(pos+neg+1000), with μ = global positive share |
| player_strength | 0.35 | log(1+CCU), latest `fct_daily_players` |
| value_per_dollar | 0.20 | review_bayes·log(1+CCU)/max(price,$1) |
| retention, momentum | 0 | pending ≥4 weeks of `fct_daily_players`; historical retention is in finding 1 |

Each component is a percentile rank, and the score is the weighted mean. Games without SteamSpy review counts (the 30 new releases) aren't scored.
- **Software exclusion** (default; `--include-software` turns it off): store genres ∩ {Utilities, Software, Design & Illustration, Animation & Modeling, Audio Production, Video Production, Photo Editing, Web Publishing, Game Development, Education} and no {Action, Adventure, RPG, Strategy, Simulation, Sports, Racing}. Casual is omitted because Wallpaper Engine is Casual + Utilities. The fallback list is `software_exclusions.csv`. 8 apps excluded: 431960, 365670, 629520, 431730, 1366800, 993090, 1840, 3132990.
- **Validation** (n=991):
  - Weight perturbation: Spearman median 0.96 (p5 0.84), top-20 overlap 80%.
  - Bootstrap: 100% of the top 20 retained.
  - Prior n of 100 or 5,000: ρ>0.998.
  - Alternative rankings: ρ≈0.79 vs raw share, 0.69 vs CCU, 0.61 vs review count.
  - Over time: see finding 5.
- **Top 5:** Terraria, Stardew Valley, Left 4 Dead 2, The Binding of Isaac: Rebirth, Garry's Mod.
- **Best by category:**
  - <$10: Terraria, L4D2, Garry's Mod
  - $10–30: Stardew Valley, Isaac, ETS2
  - $30+: RimWorld, RE4, Factorio
  - Free: Supermarket Together, Unturned, TF2
  - Split-screen co-op: Stardew Valley, Brotato, Portal 2
  - Online co-op / full controller: Terraria, Stardew, L4D2
  - Strategy: Schedule I, Cookie Clicker, Balatro
- **Price tiers:** median score is 0.55 under $10, 0.54 at $10–30, 0.48 at $30+ and 0.45 free.
- **Category lift and demand/supply** (990 games with category flags, software excluded; `figures/category_gap.png`):
  - **Steam Input API** (31 games, 3% of supply, 9.7× median CCU, +0.13 lift) and **Save Anytime** (86 games, 5.9×, +0.09) are the clearest gaps.
  - **Split-screen co-op is not a gap on full coverage.** 75 games (7.6%), 1.05× the median, +0.01 lift. It looked like a gap at 444 games (2.5×) and not at 148 (0.75×). It's sample-dependent, so drop it as a headline.
  - Online co-op is 31% of supply and 2.3× engaged; RPG is 26% and 1.7×; Early Access is 3% and 1.4× but scores below the median (−0.08).
  - Ignore categories with n<10.

## Data coverage
| source | apps | span | grain |
|---|---|---|---|
| Steam Pulse marts | 1,030 | 2026-10-12 (6-hourly from now on) | snapshot |
| SteamCharts monthly | **938** parsed (crawl finished: 1,000 requested; the rest returned HTTP 500 or no table); 923 have ≥24 months | 2012-07 → 2026-09 | monthly avg + peak |
| Steam review histogram | 991 (984 monthly-rollup, 16 weekly-rollup responses) | 2010-10 → 2026-10 | monthly up/down (English); weekly buckets summed to months |
| Mendeley CC BY 4.0 | 1,512 prices / 2,000 players (a 2019–20 popular set, *not* today's top 1,000) | prices 2019-04 → 2020-08; players 2017-12 → 2020-08 | daily |

**Gaps:**
- No price history from 2020-08 to 2026-10.
- Launch months are observable only for games released after 2012-08.

## Caveats
- **Survivorship:** history uses today's top games, so failed launches are missing.
- **Discount DiD:** publishers choose sale timing, and controls are a selected group of non-discounting games. Read the result as an association.
- **SteamSpy owner counts** are estimates and aren't used.
- The launch month is partial (so the baseline is the max of months 0–1).
- Review histograms: young games come back in 7-day buckets. A week that straddles a month boundary is counted in its start month.
- Everything here is correlation, not causation.

## Remaining schema requests for Code Builder
1. Ingest the backfill per `INGEST_SPEC.md` (monthly players, monthly reviews, Mendeley daily price/players, `launch_month_observed`).
2. (Done by Code Builder: store details and Deck status now cover 1,029/1,030.) Tags: confirm coverage of `snap_game_tags`.
4. `dim_game.is_software` (Steam's `app_type` calls Wallpaper Engine a game).
5. New-release tracking from day 0 (`first_seen` exists; it needs a new-releases feed) so future launches enter with daily data.
6. Optional: IsThereAnyDeal price history once Evan registers a key.

## Charts for Viz Specialist
`figures/retention_curves.png`, `discount_event_study.png`, `sentiment_lead_lag.png`, `category_gap.png` (lead), `f2p_vs_paid.png`, `sentiment_vs_ccu.png`, `genre_median_ccu.png`, `age_xsec.png` (keep the "survivors only" title).
