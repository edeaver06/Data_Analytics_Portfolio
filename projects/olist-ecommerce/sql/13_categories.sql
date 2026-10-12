-- Q4: categories (item grain for revenue, order grain for late/score).
CREATE OR REPLACE TABLE mart_categories AS
WITH cat_orders AS (
    SELECT category, order_id, SUM(price) AS gmv,
           ANY_VALUE(is_late) AS is_late, ANY_VALUE(is_delivered) AS is_delivered,
           ANY_VALUE(review_score) AS review_score
    FROM fct_order_items GROUP BY category, order_id
)
SELECT category, COUNT(*) AS orders, ROUND(SUM(gmv), 2) AS gmv,
       ROUND(SUM(gmv) / COUNT(*), 2) AS aov,
       ROUND(100.0 * AVG(is_late::INT) FILTER (WHERE is_delivered), 2) AS late_rate_pct,
       ROUND(AVG(review_score), 3) AS avg_score,
       RANK() OVER (ORDER BY SUM(gmv) DESC) AS gmv_rank
FROM cat_orders GROUP BY category ORDER BY gmv DESC;
