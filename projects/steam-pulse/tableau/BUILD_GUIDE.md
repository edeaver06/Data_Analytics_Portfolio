# Tableau Public build guide: Steam Pulse

Regenerate the CSVs with `.venv/bin/python scripts/make_viz.py`. Connect each CSV as its own data source
(Tableau Public can't connect live to DuckDB). Palette: Okabe-Ito (Free-to-play #E69F00, Paid #0072B2, accent #009E73, muted #8C8C8C).
Every dashboard needs a footer text box: "Source: Steam Web API concurrent players (snapshot 2026-10-12 14:03 UTC), SteamSpy owner estimates (bucketed) & prices, Steam store details."

| CSV | Grain |
|---|---|
| games.csv | 1 row per game (1,000) |
| hero_top15.csv | top 15 games by concurrent players |
| launch_decay.csv | games with a release date and players per 1k owners > 0 (147) |
| f2p_vs_paid.csv | 2 rows of pre-aggregated values |
| sales_impact.csv | paid games with an owner estimate |
| daily_players.csv | appid x UTC day (only 1 day so far) |
| game_labels.csv | bridge: appid x kind (genre/category) x label, 150 games |
| game_scores.csv | 999 scored games: composite score, rank, 3 components and 3 weighted parts |

## Sheet 1: Hero (games.csv)
Rows: `game_name` sorted by SUM(`concurrent_players`) descending. Columns: SUM(`concurrent_players`). Color: `pricing`. Filter: **Top N** parameter (integer 5-25, default 15) applied through a Top filter on game_name.
Calculated field `Share of total` = `SUM([concurrent_players]) / TOTAL(SUM([concurrent_players]))` for the label and tooltip.
Title: "3 free-to-play games hold 33% of all players in the top 1,000".

## Sheet 2: KPIs (games.csv)
BANs for: COUNT(`appid`) where concurrent_players isn't null, SUM(`concurrent_players`), and `F2P player share` = `SUM(IF [pricing]="Free-to-play" THEN [concurrent_players] END)/SUM([concurrent_players])`.

## Sheet 3: Launch decay proxy (launch_decay.csv)
Scatter with X = `years_since_release` and Y = `players_per_1k_owners` (log axis). Color: `pricing`. Add a reference line or a second sheet of MEDIAN by `age_bucket`.
Subtitle: "Cross-sectional proxy, one snapshot. Per-game decay needs daily history." Once daily_players has more than 7 days, add a line chart of `peak_players_sampled` by `snapshot_date_utc` with a `game_name` filter.

## Sheet 4: F2P vs paid (games.csv)
Measures: `Share of games` = `COUNT([appid])/TOTAL(COUNT([appid]))`, `Share of players` (as above), MEDIAN(`concurrent_players`), MEDIAN(`positive_review_share`). Exclude pricing = Unknown.

## Sheet 5: Sales impact (sales_impact.csv)
Bars: `discount_band` x MEDIAN(`players_per_1k_owners`), with labels showing COUNT(`appid`). Parameter **Min discount** (0-100) feeds the calculated field `[discount_pct] >= [Min discount]` used as a filter on the detail table.
Caption: association only, not a before/after effect.

## Sheet 6: Game lookup (games.csv)
Parameter **Game** (string list from game_name). Filter: `[game_name] = [Game]`. Show a KPI text sheet plus the daily_players line (blend on appid).
URL action "Open on Steam": `https://store.steampowered.com/app/<appid>`.

## Sheet 7: Game Finder (game_scores.csv, joined to games.csv and game_labels.csv on appid)
Use **Data Analyst's composite score** (`analysis/src/best_score.py`, method in `analysis/README.md`). Don't recompute it in Tableau; use the `score` column. Values match `analysis/best_score_results.json` (top 15 checked).
- **Score breakdown:** the three weighted parts, `review_bayes_part` (0.45 x Bayesian review share percentile), `player_strength_part` (0.35 x log-CCU percentile) and `value_per_dollar_part` (0.20 x value-per-dollar percentile). They add up to `score`. Show them as a stacked bar per game (Measure Names as color: #0072B2 / #E69F00 / #009E73).
- **Parameter Rank by** (string list): Composite score (default), Positive reviews, Concurrent players. Calculated field `Rank metric` = `CASE [Rank by] WHEN "Composite score" THEN [score] WHEN "Positive reviews" THEN [positive_review_share] ELSE [concurrent_players] END`, then `RANK(MAX([Rank metric]))`.
- **Filters:** calculated fields `Genre` = `IF [kind]="genre" THEN [label] END` and `Category` = `IF [kind]="category" THEN [label] END` as multi-select filters (they only cover the 150 games with store details). Add a price range on `steamspy_price_usd` and a range on YEAR(`release_date`).
- **App type:** add an `app_type` filter (default "game") only once it's filled in for every game. Today it covers 150 of 1,000, so add a caption: "Software such as Wallpaper Engine and Blender can't be excluded until Code Builder adds app_type."
- **No tags or Steam Deck filters:** there's no data for either.
- **Actions:** a URL action to `https://store.steampowered.com/app/<appid>`, and a filter action from the ranked list to a comparison sheet (rows: the score and its parts; columns: game_name).

## Sheet 8: Category leaderboards and gap heatmap (game_labels.csv + game_scores.csv)
- **Leaderboard:** rows `label` and `game_name`, sorted by MAX(`score`), with the table-calc filter `INDEX() <= [Top N]` computed along game_name inside each label. Only include labels with 5 or more games.
- **Gap heatmap:** rows `label`; columns Measure Names, using `Scarcity` = `1 - RANK_PERCENTILE(COUNTD([appid]))`, RANK_PERCENTILE(MEDIAN([score])) and RANK_PERCENTILE(MEDIAN([concurrent_players])). Color: cividis sequential.

## Dashboards
1. Overview: KPIs + Hero. 2. Retention & pricing: Sheets 3-5. 3. Finder: Sheets 6-8 with filter actions.
