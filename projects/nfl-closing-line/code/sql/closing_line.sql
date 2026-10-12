-- Builds analysis tables from nflverse games (raw_games registered by Python).
-- Conventions: result = home_score - away_score; spread_line = expected home margin (positive = home favored).
CREATE OR REPLACE TABLE games AS
WITH base AS (
  SELECT *,
    CAST(substr(CAST(gametime AS VARCHAR),1,2) AS INT) AS kick_hour
  FROM raw_games
  WHERE result IS NOT NULL AND spread_line IS NOT NULL AND total_line IS NOT NULL
),
flags AS (
  SELECT game_id, season, game_type, week, weekday, home_team, away_team,
    result, total, spread_line, total_line, home_moneyline, away_moneyline,
    div_game, roof, wind, home_rest, away_rest,
    result - spread_line                         AS ats_margin,      -- >0 home covers
    total - total_line                           AS ou_margin,       -- >0 over
    CASE WHEN result - spread_line > 0 THEN 1 WHEN result - spread_line < 0 THEN 0 END AS home_cover,
    CASE WHEN total - total_line > 0 THEN 1 WHEN total - total_line < 0 THEN 0 END       AS over_hit,
    (weekday IN ('Monday','Thursday') OR (weekday='Sunday' AND kick_hour >= 20)) AND game_type='REG' AS primetime,
    spread_line < 0                               AS home_dog,
    abs(spread_line) >= 7                         AS big_spread,
    location = 'Neutral'                          AS neutral
  FROM base
)
SELECT * FROM flags;

-- Each candidate bias as "the side you would bet": win=1, loss=0, push=NULL
CREATE OR REPLACE TABLE strategy_bets AS
WITH s AS (
  SELECT 'Bet home team ATS' AS strategy, season, home_cover AS win FROM games WHERE NOT neutral
  UNION ALL SELECT 'Bet home underdogs ATS', season, home_cover FROM games WHERE home_dog AND NOT neutral
  UNION ALL SELECT 'Bet favorites ATS', season, CASE WHEN spread_line>0 THEN home_cover ELSE 1-home_cover END FROM games WHERE spread_line<>0
  UNION ALL SELECT 'Bet underdogs of 7+ ATS', season, CASE WHEN spread_line>0 THEN 1-home_cover ELSE home_cover END FROM games WHERE big_spread
  UNION ALL SELECT 'Bet divisional underdogs ATS', season, CASE WHEN spread_line>0 THEN 1-home_cover ELSE home_cover END FROM games WHERE div_game=1 AND spread_line<>0
  UNION ALL SELECT 'Bet all overs', season, over_hit FROM games
  UNION ALL SELECT 'Bet primetime overs', season, over_hit FROM games WHERE primetime
  UNION ALL SELECT 'Bet unders, wind 15+ mph', season, 1-over_hit FROM games WHERE wind >= 15 AND roof IN ('outdoors','open')
  UNION ALL SELECT 'Bet team with rest edge ATS', season, CASE WHEN home_rest>away_rest THEN home_cover ELSE 1-home_cover END FROM games WHERE home_rest - away_rest >= 3 OR away_rest - home_rest >= 3
  UNION ALL SELECT 'Bet playoff underdogs ATS', season, CASE WHEN spread_line>0 THEN 1-home_cover ELSE home_cover END FROM games WHERE game_type<>'REG' AND spread_line<>0
)
SELECT * FROM s;

CREATE OR REPLACE VIEW strategy_summary AS
WITH graded AS (
  SELECT strategy, count(*) AS games, count(win) AS bets, sum(win) AS wins
  FROM strategy_bets GROUP BY strategy
)
SELECT strategy, games, bets, wins, bets - wins AS losses,
  wins::DOUBLE / bets AS win_rate,
  (wins * (100.0/110) - (bets - wins)) / bets AS roi_per_unit   -- -110 pricing
FROM graded ORDER BY win_rate DESC;

CREATE OR REPLACE VIEW spread_buckets AS
WITH b AS (
  SELECT CASE WHEN spread_line <= -7 THEN 'a) home dog 7+'
              WHEN spread_line < -3 THEN 'b) home dog 3.5-6.5'
              WHEN spread_line < 0 THEN 'c) home dog 0.5-3'
              WHEN spread_line = 0 THEN 'd) pick''em'
              WHEN spread_line <= 3 THEN 'e) home fav 0.5-3'
              WHEN spread_line < 7 THEN 'f) home fav 3.5-6.5'
              ELSE 'g) home fav 7+' END AS bucket, *
  FROM games
)
SELECT bucket, count(*) AS games, avg(spread_line) AS avg_line, avg(result) AS avg_result,
  avg(home_cover) AS home_cover_rate, avg(CASE WHEN result>0 THEN 1.0 WHEN result<0 THEN 0 ELSE 0.5 END) AS home_win_rate
FROM b GROUP BY bucket ORDER BY bucket;
