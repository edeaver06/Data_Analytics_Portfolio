-- Raw layer: one view per CSV. {raw} is replaced by the runner with the data/raw path.
CREATE OR REPLACE VIEW raw_orders      AS SELECT * FROM read_csv_auto('{raw}/olist_orders_dataset.csv', header=true);
CREATE OR REPLACE VIEW raw_customers   AS SELECT * FROM read_csv_auto('{raw}/olist_customers_dataset.csv', header=true, types={'customer_zip_code_prefix':'VARCHAR'});
CREATE OR REPLACE VIEW raw_order_items AS SELECT * FROM read_csv_auto('{raw}/olist_order_items_dataset.csv', header=true);
CREATE OR REPLACE VIEW raw_payments    AS SELECT * FROM read_csv_auto('{raw}/olist_order_payments_dataset.csv', header=true);
CREATE OR REPLACE VIEW raw_reviews     AS SELECT * FROM read_csv_auto('{raw}/olist_order_reviews_dataset.csv', header=true);
CREATE OR REPLACE VIEW raw_products    AS SELECT * FROM read_csv_auto('{raw}/olist_products_dataset.csv', header=true);
CREATE OR REPLACE VIEW raw_sellers     AS SELECT * FROM read_csv_auto('{raw}/olist_sellers_dataset.csv', header=true, types={'seller_zip_code_prefix':'VARCHAR'});
CREATE OR REPLACE VIEW raw_geolocation AS SELECT * FROM read_csv_auto('{raw}/olist_geolocation_dataset.csv', header=true, types={'geolocation_zip_code_prefix':'VARCHAR'});
CREATE OR REPLACE VIEW raw_category_translation AS SELECT * FROM read_csv_auto('{raw}/product_category_name_translation.csv', header=true);
