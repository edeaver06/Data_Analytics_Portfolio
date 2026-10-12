# Steam Pulse — Analysis Layer

Owned by Data Analyst. Read-only over Code Builder's `data/steam_pulse.duckdb` (attached `read_only`); no pipeline or mart files were edited.
Run: `analysis/.venv/bin/python analysis/src/steam_analysis.py && (cd analysis/src && ../.venv/bin/python best_score.py)`; tests: `analysis/.venv/bin/python -m pytest analysis/tests` (8 pass).
Outputs: `results.json`, `best_score_results.json`, `figures/*.png`.

## Headline: the data can't answer the time-series questions yet
The DB holds **one snapshot** (2026-10-12 08:03 CST / 14:03 UTC): 1,000 games (SteamSpy top list), 999 with a concurrent-player (CCU) reading, **148** with store details (genres/categories/release date). Releases span 1998-11-19 to 2026-09-09; **0 games released in the last 30 days**. The dbt marts (`dim_game`, `fct_daily_players`) are defined but **not materialized**, so `sql/00_views.sql` mirrors their logic over `raw.*`.
Because of this, launch decay/retention, the price event study, the sentiment lead/lag, rank stability over time, and the 30-day launch model are **blocked**. `readiness()` refuses to run them. The methods are implemented and unit-tested on synthetic fixtures only (DiD recovers a planted +50% effect; lead/lag finds a planted 2-day lead; backtest is expanding-window by release date against train-median and day-1-carry baselines). **No results are reported from synthetic data.**

## What the single snapshot does show (cross-sectional, correlation only)
- **Concentration:** 6.50M concurrent players total; the top 10 games hold **42.3%**.
- **F2P vs paid:** paid median CCU **551** vs free **135** (n=764/235, Mann-Whitney p≈5e-11). Paid games also have more positive reviews (median 90.2% vs 79.1%). This is about the top-1,000 list only; survivorship applies.
- **Discounts:** on-sale paid games median CCU 463 vs full price 564 (p=0.98): **no difference visible**. This is NOT an elasticity estimate. You need before/after panels for that.
- **Sentiment vs players:** Spearman ρ=**0.22** (n=995, ≥100 reviews). The link is weak and has no direction.
- **Genre** (148 detailed games only): RPG median CCU 18.3k, Simulation 12.0k, Strategy 11.1k, Adventure 10.3k; Sports 970 and Free To Play 1.7k are lowest. Sports also has the worst review share (57.9%).
- **Age:** the oldest surviving games still draw players, but this is a survivor cross-section, not a decay curve (`figures/age_xsec.png`).

## "Best game" composite score (`src/best_score.py`)
Each part is converted to a percentile rank, then combined as a weighted mean:

| component | weight | definition |
|---|---|---|
| review_bayes | 0.45 | (pos + 1000·μ)/(pos+neg+1000), where μ = global positive share (shrinks games with few reviews) |
| player_strength | 0.35 | log(1+CCU) at the snapshot |
| value_per_dollar | 0.20 | review_bayes·log(1+CCU)/max(price, $1). Free games are floored at $1 |
| retention | 0 (pending) | needs daily panel |
| momentum | 0 (pending) | needs ≥2 snapshots |

**Validation** (n=999):
- Weight sensitivity: 200 Dirichlet draws around the weights give a median Spearman of **0.96** vs. the base ranking (5th percentile 0.87), and top-20 overlap is **80%**.
- Bootstrap (resampling games plus binomial resampling of reviews): median top-20 retention is **100%**.
- Prior strength: setting n=100 or n=5000 instead of 1000 gives ρ>0.998.
- Alternative rankings: ρ=0.79 vs raw review share, 0.69 vs CCU alone, 0.60 vs review count.
- Rank stability over time: **not possible yet** (one snapshot).

**Top overall:** Wallpaper Engine, Terraria, Stardew Valley, Blender, Left 4 Dead 2. Caveat: SteamSpy has no app-type field, so software (Wallpaper Engine, Blender, Soundpad) gets in. It should be filtered on `app_type='game'` once the store details cover all games.

**Best by category:**
- <$10: Wallpaper Engine, Terraria, L4D2
- $10–30: Stardew Valley, Isaac Rebirth, ETS2
- $30+: RimWorld, Baldur's Gate 3, RE4
- Free: Blender, Supermarket Together, HoloCure
- Split-screen co-op: Stardew Valley, Project Zomboid, It Takes Two
- Online co-op / full controller: Terraria, Stardew, L4D2
- Strategy: Schedule I, Don't Starve Together, BG3

**Price-tier outperformance:** <$10 has the highest median score (0.56), then $10–30 (0.54), $30+ (0.48), free (0.45). Value-per-dollar favours cheap games by design.

**Category lift and demand/supply gaps** (148 detailed games; gap_index = engagement index ÷ supply share; see `figures/category_gap.png`):
- Highest score lift: Early Access (+0.21; 9 games, median CCU 21k), LAN Co-op (+0.19), Remote Play Together (+0.16), Steam Input API (+0.13).
- Under-supplied and highly engaged: Early Access, Steam Input API (13 games, 3.0× median CCU), VR, LAN PvP, RPG (2.2×).
- **Local/split-screen co-op is not a gap in this sample.** 12 games and 0.73× median CCU: the reviews are good (+0.06 lift) but engagement is below median.
- Online co-op is common (51%) and 2.2× engaged.
- Every category result here comes from a sample biased toward popular games, with n≥5 per category. Treat them as hypotheses.

## Caveats
SteamSpy owner counts are bucketed estimates and were not used for any headline. The sample is a top-1,000 list, so survivorship bias is heavy. Store details cover 148/1,000 games and are not a random subset. CCU is a single instantaneous reading, so time of day and day of week are confounded. Everything here is correlation, not causation.

## Schema requests for Code Builder
1. **Recurring snapshots**: hourly (or at least daily) `raw.player_counts`, plus materialized `fct_daily_players`. This unblocks decay, momentum, retention, event study and lead/lag. The model and over-time stability need ≥60 days.
2. **appdetails for all 1,000 games** (currently 150), and a `dim_game.app_type` filter so software can be excluded.
3. **New releases tracked from day 0**: add a feed of upcoming/new releases (e.g. store "new releases" or a release-date watcher), with first-seen date. Without it there are no launch curves and no 30-day target.
4. **Daily price/discount history**: `fct_daily_price(appid, date, price, initial_price, discount_pct)` from repeated SteamSpy/appdetails pulls. This gives sale start/end events for the DiD.
5. **Daily review counts** (`positive`, `negative` per day, or the appreviews API) for the sentiment lead/lag and momentum.
6. **Category flags in `dim_game`**: `categories` list, or booleans `has_online_coop`, `has_local_coop`, `has_split_screen`, `full_controller_support`, `remote_play_together`. They're in the raw payload; I parse them myself for now.
7. **Not available at all (needs a new source):** **Steam Deck compatibility** (not in appdetails; needs the Deck verified endpoint) and **user tags** (needs SteamSpy `appdetails` per app, which returns `tags`). I did not invent either.
8. Optional: `release_date_text` fallbacks ("Coming soon", quarters) and `metacritic_score` exposed in a mart.

## Charts for Viz Specialist
`figures/category_gap.png` (lead chart), `f2p_vs_paid.png`, `sentiment_vs_ccu.png`, `genre_median_ccu.png`, `age_xsec.png` (title must keep the "survivors only" warning).
