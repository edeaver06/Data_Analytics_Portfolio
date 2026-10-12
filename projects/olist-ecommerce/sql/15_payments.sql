-- Q6: payment mix and installments vs order value.
CREATE OR REPLACE TABLE mart_payments AS
SELECT payment_type, COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_orders,
       ROUND(AVG(paid), 2) AS avg_order_value,
       ROUND(AVG(installments), 2) AS avg_installments
FROM fct_orders WHERE paid IS NOT NULL
GROUP BY 1 ORDER BY orders DESC;

CREATE OR REPLACE TABLE mart_installments AS
SELECT CASE WHEN installments <= 1 THEN '1 (single)'
            WHEN installments <= 3 THEN '2-3'
            WHEN installments <= 6 THEN '4-6'
            ELSE '7+' END AS installment_band,
       COUNT(*) AS orders, ROUND(AVG(paid), 2) AS avg_order_value
FROM fct_orders WHERE payment_type = 'credit_card'
GROUP BY 1 ORDER BY 1;
