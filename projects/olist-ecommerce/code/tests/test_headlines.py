"""Pin every number quoted in the README, so the README cannot drift from the code."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_pipeline import headline_metrics  # noqa: E402

EXPECTED = {
    "orders": 99_441, "late_rate_pct": 6.77,
    "late_avg_score": 2.27, "ontime_avg_score": 4.29,
    "late_pct_1_2_star": 62.42, "ontime_pct_1_2_star": 9.27,
    "pct_1_2_star_8_14_days_late": 80.15,
    "avg_promised_days": 24.4, "avg_actual_days": 12.5, "median_days_early": 12.0,
    # primary comparison: reviews written AFTER delivery
    "late_after_delivery_score": 3.779, "ontime_after_delivery_score": 4.291,
    "late_after_delivery_n": 1049, "late_after_pct_1_2_star": 18.3, "ontime_after_pct_1_2_star": 9.25,
    "gap_after_delivery": -0.512, "gap_after_stratified_state_items": -0.545,
    # secondary: reviews written before the parcel arrived
    "pct_late_reviews_before_delivery": 83.56, "pct_ontime_reviews_before_delivery": 3.14,
    "late_before_delivery_score": 1.974, "late_before_delivery_n": 5332, "late_before_pct_1_2_star": 71.1,
    "gap_all": -2.02, "gap_stratified_state_items": -2.034,
    "gmv_brl_delivered": 13_220_248.93,
    "delivered_without_review": 646, "orders_with_multiple_reviews": 547,
    "multi_review_orders_conflicting_scores": 202, "review_ids_shared_across_orders": 789,
    "multi_seller_orders": 1_278,
    # out-of-sample seller tiers: ranked on 2017 (shrunk), measured on 2018
    "seller_q4_late_pct": 9.6, "seller_q1_late_pct": 6.85,
    "seller_q4_score": 3.98, "seller_q1_score": 4.129,
    "seller_tier_sellers_each": 46, "seller_q4_pct_sp": 89.1,
    "sellers_for_80pct_gmv": 544, "sellers_total": 3_095,
    "repeat_rate_pct": 3.04, "gmv_yoy_jan_aug_2018_pct": 138.3,
    "top_category": "health_beauty", "worst_state": "AL", "worst_state_late_pct": 21.41,
    "worst_lane": "SP->AL", "worst_lane_late_pct": 24.02, "worst_lane_orders": 254,
    "credit_card_pct": 75.4, "aov_single_installment": 100.91, "aov_7plus_installments": 337.08,
}


@pytest.fixture(scope="module", autouse=True)
def _real_only(using_real_data):
    if not using_real_data:
        pytest.skip("README numbers need the real Olist CSVs in data/raw")


@pytest.fixture(scope="module")
def m(con):
    return headline_metrics(con)


@pytest.mark.parametrize("key", EXPECTED)
def test_headline(m, key):
    exp = EXPECTED[key]
    assert m[key] == (pytest.approx(exp, abs=1e-6) if isinstance(exp, float) else exp)


def test_after_delivery_gap_ci_excludes_zero(m):
    """Primary result: the after-delivery gap's 95% CIs (Welch t and bootstrap) bracket it and exclude 0."""
    for key in ("gap_after_t_ci", "gap_after_boot_ci"):
        lo, hi = m[key]
        assert lo < m["gap_after_delivery"] < hi < 0
    assert m["gap_after_t_ci"] == pytest.approx([-0.595, -0.429], abs=0.002)


def test_before_delivery_gap_is_much_larger(m):
    lo, hi = m["gap_before_boot_ci"]
    assert hi < m["gap_after_boot_ci"][0]


def test_worst_lane_wilson_ci(m):
    assert m["worst_lane_wilson_ci_pct"] == [19.2, 29.6]
