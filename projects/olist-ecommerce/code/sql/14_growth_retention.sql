-- Q5: monthly growth and repeat customers. Excludes canceled/unavailable orders from GMV.
CREATE OR REPLACE TABLE mart_monthly AS
WITH m AS (
    SELECT purchase_month, COUNT(*) AS orders, SUM(gmv) AS gmv
    FROM fct_orders
    WHERE order_status NOT IN ('canceled', 'unavailable') AND gmv IS NOT NULL
      -- 2016 and Sep-2018 are sparse ramp-up / cut-off months; keep the 20 full months
      AND purchase_month BETWEEN DATE '2017-01-01' AND DATE '2018-08-01'
    GROUP BY 1
)
SELECT purchase_month, orders, gmv,
       ROUND(100.0 * (gmv / LAG(gmv) OVER (ORDER BY purchase_month) - 1), 1) AS gmv_mom_pct,
       SUM(gmv) OVER (ORDER BY purchase_month) AS running_gmv
FROM m ORDER BY purchase_month;

CREATE OR REPLACE TABLE mart_repeat_customers AS
WITH per_customer AS (
    SELECT customer_unique_id, COUNT(DISTINCT order_id) AS n_orders
    FROM fct_orders WHERE order_status NOT IN ('canceled', 'unavailable')
    GROUP BY 1
)
SELECT COUNT(*) AS customers,
       SUM((n_orders > 1)::INT) AS repeat_customers,
       ROUND(100.0 * AVG((n_orders > 1)::INT), 2) AS repeat_rate_pct
FROM per_customer;

-- Cohort retention: share of each first-purchase cohort that buys again in month k.
CREATE OR REPLACE TABLE mart_cohorts AS
WITH o AS (
    SELECT customer_unique_id, purchase_month
    FROM fct_orders WHERE order_status NOT IN ('canceled', 'unavailable')
),
first AS (SELECT customer_unique_id, MIN(purchase_month) AS cohort FROM o GROUP BY 1),
activity AS (
    SELECT DISTINCT f.cohort, o.customer_unique_id,
           date_diff('month', f.cohort, o.purchase_month) AS month_offset
    FROM o JOIN first f USING (customer_unique_id)
)
SELECT cohort, month_offset, COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / FIRST_VALUE(COUNT(*)) OVER (PARTITION BY cohort ORDER BY month_offset), 2) AS retention_pct
FROM activity GROUP BY 1, 2 ORDER BY 1, 2;
