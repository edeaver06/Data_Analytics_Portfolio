"""Recompute headline metrics independently in pandas and compare with SQL."""
import pandas as pd
import pytest


@pytest.fixture(scope="module")
def pd_orders(raw):
    o = raw["orders"].copy()
    for c in ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        o[c] = pd.to_datetime(o[c])
    r = raw["order_reviews"].copy()
    r["ts"] = pd.to_datetime(r.review_answer_timestamp)
    r = r.sort_values(["order_id", "ts", "review_id"], ascending=[True, False, True]).drop_duplicates("order_id")
    o = o.merge(r[["order_id", "review_score"]], on="order_id", how="left")
    d = o[(o.order_status == "delivered") & o.order_delivered_customer_date.notna()].copy()
    d["is_late"] = d.order_delivered_customer_date.dt.normalize() > d.order_estimated_delivery_date.dt.normalize()
    return d


def test_late_rate_parity(con, pd_orders):
    sql = con.execute("SELECT AVG(is_late::INT) FROM fct_orders WHERE is_delivered").fetchone()[0]
    assert sql == pytest.approx(pd_orders.is_late.mean(), abs=1e-12)


def test_late_vs_ontime_score_gap_parity(con, pd_orders):
    sql = dict(con.execute("""SELECT is_late, AVG(review_score) FROM fct_orders
                              WHERE is_delivered AND review_score IS NOT NULL GROUP BY 1""").fetchall())
    g = pd_orders.dropna(subset=["review_score"]).groupby("is_late").review_score.mean()
    assert sql[True] == pytest.approx(g[True], abs=1e-9)
    assert sql[False] == pytest.approx(g[False], abs=1e-9)


def test_top_category_gmv_parity(con, raw):
    items = raw["order_items"].merge(raw["products"], on="product_id", how="left").merge(
        raw["translation"], on="product_category_name", how="left")
    items["category"] = items.product_category_name_english.fillna(items.product_category_name).fillna("unknown")
    pd_top = items.groupby("category").price.sum().sort_values(ascending=False)
    sql_top = con.execute("SELECT category, gmv FROM mart_categories ORDER BY gmv DESC LIMIT 1").fetchone()
    assert sql_top[0] == pd_top.index[0]
    assert float(sql_top[1]) == pytest.approx(pd_top.iloc[0], abs=0.01)


def test_repeat_rate_parity(con, raw):
    o = raw["orders"].merge(raw["customers"], on="customer_id")
    o = o[~o.order_status.isin(["canceled", "unavailable"])]
    n = o.groupby("customer_unique_id").order_id.nunique()
    sql = con.execute("SELECT repeat_customers, customers FROM mart_repeat_customers").fetchone()
    assert (int(sql[0]), int(sql[1])) == (int((n > 1).sum()), len(n))
