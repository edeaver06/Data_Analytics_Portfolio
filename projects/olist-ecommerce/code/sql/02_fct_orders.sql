-- One row per order. Every child table is aggregated to order grain BEFORE joining,
-- so item revenue is never multiplied by payment or review rows.
CREATE OR REPLACE TABLE fct_orders AS
WITH items AS (
    SELECT order_id,
           SUM(price)                AS gmv,
           SUM(freight)              AS freight,
           COUNT(*)                  AS n_items,
           COUNT(DISTINCT seller_id) AS n_sellers,
           MIN(seller_id)            AS first_seller_id   -- deterministic pick for the 1.3% multi-seller orders
    FROM stg_order_items GROUP BY order_id
),
payments AS (
    SELECT order_id,
           SUM(payment_value)        AS paid,
           MAX(payment_installments) AS installments,
           -- main payment type = the one carrying the most value
           FIRST(payment_type ORDER BY payment_value DESC, payment_sequential) AS payment_type
    FROM stg_payments GROUP BY order_id
)
SELECT o.order_id, o.order_status, o.purchased_at,
       date_trunc('month', o.purchased_at)::DATE           AS purchase_month,
       c.customer_unique_id, c.state                       AS customer_state,
       s.state                                             AS seller_state,
       i.gmv, i.freight, i.n_items, i.n_sellers,
       p.paid, p.installments, p.payment_type,
       r.review_score,
       r.created_at                                        AS review_created_at,
       -- Olist sends the review survey on the ESTIMATED date, so most late orders are reviewed
       -- before the parcel arrives. Those reviews rate "not received", not the delivered product.
       CASE WHEN r.created_at IS NULL OR o.delivered_at IS NULL THEN NULL
            ELSE r.created_at < o.delivered_at END         AS reviewed_before_delivery,
       date_diff('day', o.purchased_at, o.delivered_at)    AS delivery_days,
       date_diff('day', o.estimated_at, o.delivered_at)    AS days_late,   -- negative = early
       date_diff('day', o.purchased_at, o.estimated_at)    AS promised_days,
       CASE WHEN o.delivered_at IS NULL THEN NULL
            ELSE o.delivered_at::DATE > o.estimated_at::DATE END AS is_late,
       (o.order_status = 'delivered' AND o.delivered_at IS NOT NULL) AS is_delivered
FROM stg_orders o
LEFT JOIN stg_customers c USING (customer_id)
LEFT JOIN items    i USING (order_id)
LEFT JOIN payments p USING (order_id)
LEFT JOIN stg_reviews r USING (order_id)
LEFT JOIN stg_sellers s ON s.seller_id = i.first_seller_id;

-- Item/seller grain fact for seller & category metrics (an order can span sellers).
CREATE OR REPLACE TABLE fct_order_items AS
SELECT oi.order_id, oi.order_item_id, oi.seller_id, oi.product_id, pr.category,
       oi.price, oi.freight, f.purchase_month, f.customer_state, f.review_score,
       f.is_late, f.is_delivered, f.days_late, f.delivery_days
FROM stg_order_items oi
JOIN fct_orders f USING (order_id)
LEFT JOIN stg_products pr USING (product_id);
