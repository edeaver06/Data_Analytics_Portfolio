-- Q2: seller scorecard (item/seller grain, delivered orders, >= 30 orders).
-- Multi-seller orders (1.3%) carry one order-level is_late flag, shared by every seller on the order.
CREATE OR REPLACE TABLE seller_orders AS        -- one row per (seller, order) to avoid item fan-out
SELECT seller_id, order_id, ANY_VALUE(purchase_month) AS purchase_month,
       SUM(price) AS gmv, ANY_VALUE(is_late) AS is_late, ANY_VALUE(review_score) AS review_score
FROM fct_order_items WHERE is_delivered
GROUP BY seller_id, order_id;

CREATE OR REPLACE TABLE mart_sellers AS
WITH agg AS (
    SELECT seller_id, COUNT(*) AS orders, SUM(gmv) AS gmv,
           AVG(is_late::INT) AS late_rate, AVG(review_score) AS avg_score
    FROM seller_orders GROUP BY seller_id
    HAVING COUNT(*) >= 30
)
SELECT a.*, s.state AS seller_state,
       RANK() OVER (ORDER BY late_rate DESC) AS late_rank   -- descriptive only; not used for tiers
FROM agg a JOIN stg_sellers s USING (seller_id);

-- Out-of-sample seller tiers. Ranking sellers on their late rate and then reporting that same
-- late rate is circular (it guarantees a big spread even if lateness were pure noise). Instead:
--   1. rank on 2017 orders, with the rate shrunk toward the 2017 mean (Beta prior, k = 50 pseudo-orders)
--      so small sellers with a lucky/unlucky streak are not pushed to the extremes;
--   2. measure late rate and review score on the SAME sellers' 2018 orders.
-- Both periods require >= 30 delivered orders.
CREATE OR REPLACE TABLE mart_seller_tiers_oos AS
WITH prior AS (SELECT AVG(is_late::INT) AS p FROM seller_orders WHERE purchase_month < DATE '2018-01-01'),
rank_period AS (
    SELECT seller_id, COUNT(*) AS n_2017, AVG(is_late::INT) AS raw_late_2017,
           (SUM(is_late::INT) + 50 * (SELECT p FROM prior)) / (COUNT(*) + 50) AS shrunk_late_2017
    FROM seller_orders WHERE purchase_month < DATE '2018-01-01'
    GROUP BY 1 HAVING COUNT(*) >= 30
),
measure_period AS (
    SELECT seller_id, COUNT(*) AS n_2018, AVG(is_late::INT) AS late_2018, AVG(review_score) AS score_2018
    FROM seller_orders WHERE purchase_month >= DATE '2018-01-01'
    GROUP BY 1 HAVING COUNT(*) >= 30
)
SELECT r.*, m.n_2018, m.late_2018, m.score_2018, s.state AS seller_state,
       NTILE(4) OVER (ORDER BY r.shrunk_late_2017, r.seller_id) AS tier_2017   -- 1 = most reliable in 2017
FROM rank_period r JOIN measure_period m USING (seller_id) JOIN stg_sellers s USING (seller_id);

CREATE OR REPLACE TABLE mart_seller_tiers AS
SELECT tier_2017 AS late_quartile, COUNT(*) AS sellers, SUM(n_2018) AS orders_2018,
       ROUND(100.0 * SUM(shrunk_late_2017 * n_2017) / SUM(n_2017), 2) AS ranked_late_2017_pct,
       ROUND(100.0 * SUM(late_2018 * n_2018) / SUM(n_2018), 2)        AS late_rate_pct,   -- 2018, out of sample
       ROUND(SUM(score_2018 * n_2018) / SUM(n_2018), 3)               AS avg_score,       -- 2018
       ROUND(100.0 * AVG((seller_state = 'SP')::INT), 1)              AS pct_sp_sellers
FROM mart_seller_tiers_oos GROUP BY 1 ORDER BY 1;

CREATE OR REPLACE TABLE mart_worst_sellers AS
SELECT seller_id, seller_state, orders, ROUND(100*late_rate,1) AS late_rate_pct,
       ROUND(avg_score,2) AS avg_score, late_rank
FROM mart_sellers
QUALIFY ROW_NUMBER() OVER (ORDER BY late_rate DESC, orders DESC, seller_id) <= 10;
-- Pareto: cumulative GMV share by seller (all sellers, all orders with items).
CREATE OR REPLACE TABLE mart_seller_pareto AS
WITH g AS (SELECT seller_id, SUM(price) AS gmv FROM stg_order_items GROUP BY 1),
c AS (
    SELECT seller_id, gmv,
           ROW_NUMBER() OVER (ORDER BY gmv DESC)                     AS seller_rank,
           SUM(gmv) OVER (ORDER BY gmv DESC ROWS UNBOUNDED PRECEDING) / SUM(gmv) OVER () AS cum_share,
           COUNT(*) OVER ()                                          AS n_sellers
    FROM g
)
SELECT * FROM c ORDER BY seller_rank;
