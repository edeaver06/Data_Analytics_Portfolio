-- Q1: how strongly is lateness associated with bad reviews? Dose-response by days-late bucket.
CREATE OR REPLACE TABLE mart_delivery_vs_reviews AS
WITH delivered AS (
    SELECT *,
           CASE WHEN days_late IS NULL THEN '0. unknown'   -- no estimate date; 0 rows in the Olist data
                WHEN days_late <= -1 THEN '1. early'
                WHEN days_late =  0  THEN '2. on estimate day (on time)'
                WHEN days_late <= 3  THEN '3. 1-3 days late'
                WHEN days_late <= 7  THEN '4. 4-7 days late'
                WHEN days_late <= 14 THEN '5. 8-14 days late'
                ELSE                      '6. 15+ days late' END AS late_bucket
    FROM fct_orders
    WHERE is_delivered AND review_score IS NOT NULL
)
SELECT late_bucket,
       COUNT(*)                                          AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_orders,
       ROUND(AVG(review_score), 3)                       AS avg_score,
       ROUND(100.0 * AVG((review_score <= 2)::INT), 2)   AS pct_1_2_star,
       ROUND(100.0 * AVG((review_score = 5)::INT), 2)    AS pct_5_star
FROM delivered GROUP BY late_bucket ORDER BY late_bucket;

CREATE OR REPLACE TABLE mart_late_vs_ontime AS
SELECT CASE WHEN is_late THEN 'late' ELSE 'on time' END AS delivery,
       COUNT(*) AS orders,
       ROUND(AVG(review_score), 3) AS avg_score,
       ROUND(100.0 * AVG((review_score <= 2)::INT), 2) AS pct_1_2_star
FROM fct_orders WHERE is_delivered AND review_score IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- Same comparison split by review timing: was the review written before or after the parcel arrived?
CREATE OR REPLACE TABLE mart_late_vs_ontime_by_timing AS
SELECT CASE WHEN is_late THEN 'late' ELSE 'on time' END AS delivery,
       CASE WHEN reviewed_before_delivery THEN 'before delivery' ELSE 'after delivery' END AS review_timing,
       COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY delivery), 2) AS pct_of_group,
       ROUND(AVG(review_score), 3) AS avg_score,
       ROUND(100.0 * AVG((review_score <= 2)::INT), 2) AS pct_1_2_star
FROM fct_orders WHERE is_delivered AND review_score IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 2;

-- Q7: estimate accuracy -- is the promise padded?
CREATE OR REPLACE TABLE mart_estimate_accuracy AS
SELECT COUNT(*)                                     AS delivered_orders,
       ROUND(AVG(promised_days), 1)                 AS avg_promised_days,
       ROUND(AVG(delivery_days), 1)                 AS avg_actual_days,
       ROUND(MEDIAN(-days_late), 1)                 AS median_days_early,
       ROUND(100.0 * AVG(is_late::INT), 2)          AS late_rate_pct
FROM fct_orders WHERE is_delivered;
