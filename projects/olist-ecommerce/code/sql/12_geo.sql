-- Q3: geography -- customer states and seller->customer lanes.
CREATE OR REPLACE TABLE mart_customer_states AS
SELECT customer_state, COUNT(*) AS orders,
       ROUND(100.0 * AVG(is_late::INT), 2) AS late_rate_pct,
       MEDIAN(delivery_days)               AS median_delivery_days,
       ROUND(AVG(review_score), 3)         AS avg_score
FROM fct_orders WHERE is_delivered
GROUP BY 1 ORDER BY late_rate_pct DESC;

CREATE OR REPLACE TABLE mart_lanes AS
SELECT seller_state, customer_state, COUNT(*) AS orders,
       ROUND(100.0 * AVG(is_late::INT), 2)               AS late_rate_pct,
       QUANTILE_CONT(delivery_days, 0.5)                 AS median_delivery_days,
       ROUND(AVG(review_score), 3)                       AS avg_score
FROM fct_orders WHERE is_delivered AND n_sellers = 1
GROUP BY 1, 2 HAVING COUNT(*) >= 100
ORDER BY late_rate_pct DESC;
