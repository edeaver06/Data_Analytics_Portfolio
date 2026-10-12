-- Staging: typed, cleaned, grain-safe tables.
CREATE OR REPLACE TABLE stg_orders AS
SELECT order_id, customer_id, order_status,
       CAST(order_purchase_timestamp AS TIMESTAMP)       AS purchased_at,
       CAST(order_approved_at AS TIMESTAMP)              AS approved_at,
       CAST(order_delivered_carrier_date AS TIMESTAMP)   AS shipped_at,
       CAST(order_delivered_customer_date AS TIMESTAMP)  AS delivered_at,
       CAST(order_estimated_delivery_date AS TIMESTAMP)  AS estimated_at
FROM raw_orders;

CREATE OR REPLACE TABLE stg_customers AS
SELECT customer_id, customer_unique_id, lpad(customer_zip_code_prefix, 5, '0') AS zip_prefix,
       customer_city AS city, customer_state AS state
FROM raw_customers;

CREATE OR REPLACE TABLE stg_sellers AS
SELECT seller_id, lpad(seller_zip_code_prefix, 5, '0') AS zip_prefix,
       seller_city AS city, seller_state AS state
FROM raw_sellers;

-- English category names; fall back to Portuguese, then 'unknown'.
CREATE OR REPLACE TABLE stg_products AS
SELECT p.product_id,
       COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category
FROM raw_products p
LEFT JOIN raw_category_translation t USING (product_category_name);

CREATE OR REPLACE TABLE stg_order_items AS
SELECT order_id, order_item_id, product_id, seller_id,
       CAST(price AS DECIMAL(12,2)) AS price, CAST(freight_value AS DECIMAL(12,2)) AS freight
FROM raw_order_items;

CREATE OR REPLACE TABLE stg_payments AS
SELECT order_id, payment_sequential, payment_type, payment_installments,
       CAST(payment_value AS DECIMAL(12,2)) AS payment_value
FROM raw_payments;

-- Reviews: 547 orders have several reviews (202 of them with conflicting scores), so
-- "keep the latest answered" matters. Separately, 789 review_ids are shared across orders,
-- so review_id is NOT a unique key; the grain here is order_id.
CREATE OR REPLACE TABLE stg_reviews AS
WITH ranked AS (
    SELECT order_id, review_id, review_score,
           CAST(review_creation_date AS TIMESTAMP)    AS created_at,
           CAST(review_answer_timestamp AS TIMESTAMP) AS answered_at,
           ROW_NUMBER() OVER (PARTITION BY order_id
                              ORDER BY CAST(review_answer_timestamp AS TIMESTAMP) DESC, review_id) AS rn
    FROM raw_reviews
)
SELECT order_id, review_id, review_score, created_at, answered_at FROM ranked WHERE rn = 1;

-- Geolocation has many rows per zip prefix -> average to one point per prefix.
CREATE OR REPLACE TABLE stg_geolocation AS
SELECT lpad(geolocation_zip_code_prefix, 5, '0') AS zip_prefix,
       AVG(geolocation_lat) AS lat, AVG(geolocation_lng) AS lng
FROM raw_geolocation GROUP BY 1;
