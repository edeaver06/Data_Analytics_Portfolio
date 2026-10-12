# Tableau Public build guide: Steam Pulse

All CSVs come from Code Builder's dbt marts (`marts.*`, read-only). Regenerate them with `.venv/bin/python scripts/make_viz.py`. Connect each CSV as its own data source
(Tableau Public can't connect live to DuckDB). Palette: Okabe-Ito (Free-to-play #E69F00, Paid #0072B2, accent #009E73, muted #8C8C8C).
Every dashboard needs a footer text box: "Source: Steam Web API concurrent players (snapshot 2026-10-12 14:03 UTC), SteamSpy owner estimates (bucketed) & prices, Steam store details."

| CSV | Grain |
|---|---|
| games.csv | 1 row per game (1,000) |
| hero_top15.csv | top 15 games by concurrent players |
| launch_decay.csv | months since launch x segment (All / Free-to-play / Paid): median share of launch-month peak, games (Data Analyst history, n=383) |
| age_xsec_today.csv | today's cross-section: players per 1k owners by game age |
| f2p_vs_paid.csv | 2 rows of pre-aggregated values |
| sales_impact.csv | discount event study by depth: pct lift, n, plus all-sales lift and 95% CI (2019-20 data, association) |
| discount_today.csv | games' current store discount (cross-section) |
| daily_players.csv | appid x UTC day (only 1 day so far) |
| game_labels.csv | marts.bridge_game_category: appid x kind (genre/category/tag) x label (+ tag_votes). Tags cover 300 games, genres/categories about 448 |
| game_scores.csv | from marts.mart_game_scores (port of best_score.py, verified identical): scored rows plus excluded rows (software, no reviews, no player count; see `excluded_reason`); score, rank, 3 components, 3 weighted parts |

## Sheet 1: Hero (games.csv)
Rows: `game_name` sorted by SUM(`concurrent_players`) descending. Columns: SUM(`concurrent_players`). Color: `pricing`. Filter: **Top N** parameter (integer 5-25, default 15) applied through a Top filter on game_name.
Calculated field `Share of total` = `SUM([concurrent_players]) / TOTAL(SUM([concurrent_players]))` for the label and tooltip.
Title: build it from the data, e.g. "Three free-to-play games hold <top-3 share> of players across <N> tracked games". Check the top 3 are all free-to-play before using that wording.

## Sheet 2: KPIs (games.csv)
BANs for: COUNT(`appid`) where concurrent_players isn't null, SUM(`concurrent_players`), and `F2P player share` = `SUM(IF [pricing]="Free-to-play" THEN [concurrent_players] END)/SUM([concurrent_players])`.

## Sheet 3: Launch decay (launch_decay.csv)
Line chart: X = `months_since_launch` (discrete: 0,1,2,3,6,12,24), Y = `median_share_of_launch_peak` (format %), Color = `segment` (All #8C8C8C thick, Free-to-play #E69F00, Paid #0072B2). Tooltip: `games`.
Title: "Games keep <month-1 share> of launch-month players after one month, <month-6> by month 6 and <month-24> by month 24" (read the values from the All segment). Caption: "<games> of today's tracked games with an observed launch (SteamCharts), survivors only". Say free-to-play holds better only if its curve is above paid.

## Sheet 4: F2P vs paid (games.csv)
Measures: `Share of games` = `COUNT([appid])/TOTAL(COUNT([appid]))`, `Share of players` (as above), MEDIAN(`concurrent_players`), MEDIAN(`positive_review_share`). Exclude pricing = Unknown.

## Sheet 5: Sales impact (sales_impact.csv)
Bars: `depth` x `pct` (label "+{pct}% (n)"), reference line at `all_sales_pct` (+39.4%), and a band from `ci_low` to `ci_high`.
Title: "The first week of a sale goes with +<all_sales_pct>% players, and deeper discounts with bigger lifts". Required subtitle: "Association, not causation: difference-in-differences over <n_events> sale starts, 2019-20 data."

## Sheet 6: Game lookup (games.csv)
Parameter **Game** (string list from game_name). Filter: `[game_name] = [Game]`. Show a KPI text sheet plus the daily_players line (blend on appid).
URL action "Open on Steam": `https://store.steampowered.com/app/<appid>`.

## Sheet 7: Game Finder (game_scores.csv, joined to games.csv and game_labels.csv on appid)
Use **Data Analyst's composite score** as materialized in `marts.mart_game_scores` (a verified port of `analysis/src/best_score.py`). Don't recompute it in Tableau; use the `score` column. Software rows have no score; filter `excluded_reason` is null. Values match `analysis/best_score_results.json` (top 15 checked on each refresh).
- **Score breakdown:** the three weighted parts, `review_bayes_part` (0.45 x Bayesian review share percentile), `player_strength_part` (0.35 x log-CCU percentile) and `value_per_dollar_part` (0.20 x value-per-dollar percentile). They add up to `score`. Show them as a stacked bar per game (Measure Names as color: #0072B2 / #E69F00 / #009E73).
- **Parameter Rank by** (string list): Composite score (default), Positive reviews, Concurrent players. Calculated field `Rank metric` = `CASE [Rank by] WHEN "Composite score" THEN [score] WHEN "Positive reviews" THEN [positive_review_share] ELSE [concurrent_players] END`, then `RANK(MAX([Rank metric]))`.
- **Filters:** calculated fields `Genre` = `IF [kind]="genre" THEN [label] END` and `Category` = `IF [kind]="category" THEN [label] END` as multi-select filters (store details now cover nearly every game). Add a price range on `steamspy_price_usd` and a range on YEAR(`release_date`).
- **Software:** already excluded from `game_scores.csv` by Data Analyst's rule (8 apps, including Wallpaper Engine and Blender). Add a caption saying so. The mart doesn't score software, so software rows appear only as unscored rows. Add an `app_type` filter (default "game"); it's now filled in for nearly every game. Note that Steam labels Wallpaper Engine `app_type="game"`.
- **Tags:** calculated field `Tag` = `IF [kind]="tag" THEN [label] END`, as a multi-select filter. Size by `tag_votes` if you add a tag cloud.
- **Steam Deck:** a multi-select filter on `deck_status` in games.csv (Verified / Playable / Unsupported / Unknown).
- **Coverage caption** (update the numbers on each refresh): "Tags cover ~300 games and Deck status ~200 of 1,000; both fill in every 6 hours."
- **Feature flags:** use `has_local_coop`, `has_split_screen` and `full_controller_support` from marts.dim_game if you add them to games.csv.
- **Actions:** a URL action to `https://store.steampowered.com/app/<appid>`, and a filter action from the ranked list to a comparison sheet (rows: the score and its parts; columns: game_name).

## Sheet 8: Category leaderboards and gap heatmap (game_labels.csv + game_scores.csv)
- **Leaderboard:** rows `label` and `game_name`, sorted by MAX(`score`), with the table-calc filter `INDEX() <= [Top N]` computed along game_name inside each label. Only include labels with 5 or more games.
- **Gap heatmap:** rows `label`; columns Measure Names, using `Scarcity` = `1 - RANK_PERCENTILE(COUNTD([appid]))`, RANK_PERCENTILE(MEDIAN([score])) and RANK_PERCENTILE(MEDIAN([concurrent_players])). Color: cividis sequential.

## Dashboards
1. Overview: KPIs + Hero. 2. Retention & pricing: Sheets 3-5. 3. Finder: Sheets 6-8 with filter actions.

## F2P vs paid sheet note
Use Steam store `is_free` (Data Analyst's definition) and read the Mann-Whitney p from `analysis/results.json`. If p >= 0.05, the title must say there's no clear player difference. Don't write "paid games are busier".
