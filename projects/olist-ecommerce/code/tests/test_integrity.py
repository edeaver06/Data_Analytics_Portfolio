"""Grain, uniqueness and no-double-counting checks."""


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_row_counts_match_published_dataset(con, need_real):
    assert one(con, "SELECT COUNT(*) FROM stg_orders") == 99_441
    assert one(con, "SELECT COUNT(*) FROM stg_order_items") == 112_650
    assert one(con, "SELECT COUNT(*) FROM stg_customers") == 99_441


def test_staging_keeps_every_raw_row(con):
    for stg, raw in [("stg_orders", "raw_orders"), ("stg_order_items", "raw_order_items"), ("stg_customers", "raw_customers")]:
        assert one(con, f"SELECT COUNT(*) FROM {stg}") == one(con, f"SELECT COUNT(*) FROM {raw}") > 0


def test_fct_orders_one_row_per_order(con):
    assert one(con, "SELECT COUNT(*) FROM fct_orders") == one(con, "SELECT COUNT(*) FROM stg_orders")
    assert one(con, "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM fct_orders") == 0


def test_fct_order_items_one_row_per_item(con):
    n = one(con, "SELECT COUNT(*) FROM stg_order_items")
    assert one(con, "SELECT COUNT(*) FROM fct_order_items") == n
    assert one(con, "SELECT COUNT(*) FROM (SELECT DISTINCT order_id, order_item_id FROM fct_order_items)") == n


def test_reviews_deduped_to_one_per_order(con):
    assert one(con, "SELECT MAX(c) FROM (SELECT COUNT(*) c FROM stg_reviews GROUP BY order_id)") == 1
    # raw data really does contain duplicates, so the dedupe is doing work
    assert one(con, "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM raw_reviews") > 0


def test_geolocation_one_row_per_zip(con):
    assert one(con, "SELECT COUNT(*) - COUNT(DISTINCT zip_prefix) FROM stg_geolocation") == 0


def test_no_gmv_fan_out(con):
    """Joining payments/reviews must not inflate revenue."""
    fct = one(con, "SELECT SUM(gmv) FROM fct_orders")
    items = one(con, "SELECT SUM(price) FROM stg_order_items")
    assert fct == items
    assert one(con, "SELECT SUM(price) FROM fct_order_items") == items


def test_no_payment_fan_out(con):
    assert one(con, "SELECT SUM(paid) FROM fct_orders") == one(con, "SELECT SUM(payment_value) FROM stg_payments")


def test_category_gmv_sums_to_total(con):
    assert one(con, "SELECT SUM(gmv) FROM mart_categories") == one(con, "SELECT SUM(price) FROM stg_order_items")


def test_is_late_consistent_with_dates(con):
    assert one(con, "SELECT COUNT(*) FROM fct_orders WHERE is_delivered AND is_late <> (days_late > 0)") == 0


def test_no_negative_delivery_days(con):
    assert one(con, "SELECT COUNT(*) FROM fct_orders WHERE is_delivered AND delivery_days < 0") == 0


def test_seller_tiers_partition_sellers(con):
    assert one(con, "SELECT COALESCE(SUM(sellers), 0) FROM mart_seller_tiers") == one(con, "SELECT COUNT(*) FROM mart_seller_tiers_oos")


def test_seller_tiers_are_out_of_sample(con):
    """Tiers are ranked on 2017 orders and measured on 2018 orders only."""
    assert one(con, "SELECT COUNT(*) FROM mart_seller_tiers_oos WHERE n_2017 < 30 OR n_2018 < 30") == 0


def test_review_timing_split_covers_all_reviewed_deliveries(con):
    assert one(con, "SELECT SUM(orders) FROM mart_late_vs_ontime_by_timing") == one(
        con, "SELECT COUNT(*) FROM fct_orders WHERE is_delivered AND review_score IS NOT NULL")
    assert one(con, "SELECT COUNT(*) FROM mart_sellers WHERE orders < 30") == 0


def test_pareto_ends_at_100pct(con):
    assert abs(one(con, "SELECT MAX(cum_share) FROM mart_seller_pareto") - 1) < 1e-9
