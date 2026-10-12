-- DuckDB: FCR metrics from data/raw/market_*.csv (run from project root:  duckdb < sql/fcr_metrics.sql)
CREATE OR REPLACE VIEW calls AS
WITH raw AS (
    SELECT * FROM read_csv('data/raw/market_*.csv', header = true, nullstr = 'null')
), mapped AS (
    SELECT
        CAST(date_created AS DATE) AS call_date,
        new_market AS market,
        CASE new_type
            WHEN 'type_1' THEN 'Account Management & Billing'
            WHEN 'type_2' THEN 'Technical Troubleshooting'
            WHEN 'type_3' THEN 'Scheduling'
            WHEN 'type_4' THEN 'Construction'
            WHEN 'type_5' THEN 'Wi-Fi & Internet'
        END AS problem_category,
        COALESCE(contacts_n, 0) AS first_calls,
        COALESCE(contacts_n_1,0)+COALESCE(contacts_n_2,0)+COALESCE(contacts_n_3,0)+COALESCE(contacts_n_4,0)
          +COALESCE(contacts_n_5,0)+COALESCE(contacts_n_6,0)+COALESCE(contacts_n_7,0) AS repeat_calls
    FROM raw
)
SELECT * FROM mapped;

-- 1. By category
WITH cat AS (
    SELECT problem_category, SUM(first_calls) AS first_calls, SUM(repeat_calls) AS repeat_calls
    FROM calls GROUP BY problem_category
)
SELECT problem_category, first_calls, repeat_calls,
       ROUND(100.0 * repeat_calls / first_calls, 1) AS repeat_rate_pct,
       ROUND(100.0 * repeat_calls / SUM(repeat_calls) OVER (), 1) AS pct_of_total_repeats
FROM cat ORDER BY repeat_rate_pct DESC;

-- 2. By market
WITH mkt AS (
    SELECT market, SUM(first_calls) AS first_calls, SUM(repeat_calls) AS repeat_calls
    FROM calls GROUP BY market
)
SELECT market, first_calls, repeat_calls, ROUND(100.0 * repeat_calls / first_calls, 1) AS repeat_rate_pct
FROM mkt ORDER BY market;

-- 3. By market x category
WITH mc AS (
    SELECT market, problem_category, SUM(first_calls) AS first_calls, SUM(repeat_calls) AS repeat_calls
    FROM calls GROUP BY ALL
)
SELECT *, ROUND(100.0 * repeat_calls / NULLIF(first_calls, 0), 1) AS repeat_rate_pct
FROM mc ORDER BY market, repeat_rate_pct DESC;

-- 4. Week-over-week trend (weeks start Monday)
WITH wk AS (
    SELECT date_trunc('week', call_date) AS week, SUM(first_calls) AS first_calls, SUM(repeat_calls) AS repeat_calls
    FROM calls GROUP BY 1
), rated AS (
    SELECT *, ROUND(100.0 * repeat_calls / first_calls, 1) AS repeat_rate_pct FROM wk
)
SELECT *, ROUND(repeat_rate_pct - LAG(repeat_rate_pct) OVER (ORDER BY week), 1) AS wow_repeat_rate_change_pts
FROM rated ORDER BY week;
