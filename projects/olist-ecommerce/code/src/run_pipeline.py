"""Build the warehouse, export every mart to data/outputs/, run the stats test and
write data/outputs/headline_metrics.json (the numbers quoted in the README)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.olist import build  # noqa: E402

OUT = ROOT / "data" / "outputs"


def mean_diff_ci(a, b, n_boot: int = 2000, seed: int = 42):
    """Mean(a) - mean(b) with a Welch t 95% CI and a percentile bootstrap 95% CI."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a.mean() - b.mean()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    df = se**4 / ((a.var(ddof=1) / len(a)) ** 2 / (len(a) - 1) + (b.var(ddof=1) / len(b)) ** 2 / (len(b) - 1))
    t = stats.t.ppf(0.975, df)
    rng = np.random.default_rng(seed)
    boots = np.array([rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return d, (d - t * se, d + t * se), (lo, hi)


def wilson_ci(k: int, n: int, z: float = 1.959964):
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def headline_metrics(con) -> dict:
    q = lambda sql: con.execute(sql).fetchone()  # noqa: E731
    lo = {r[0]: r for r in con.execute("SELECT * FROM mart_late_vs_ontime").fetchall()}
    est = con.execute("SELECT * FROM mart_estimate_accuracy").fetchdf().iloc[0]
    buckets = con.execute("SELECT * FROM mart_delivery_vs_reviews").fetchdf()
    tiers = con.execute("SELECT * FROM mart_seller_tiers").fetchdf()
    pareto_80 = q("SELECT MIN(seller_rank), MAX(n_sellers) FROM mart_seller_pareto WHERE cum_share >= 0.8")
    rep = con.execute("SELECT * FROM mart_repeat_customers").fetchdf().iloc[0]
    yoy = q("""SELECT SUM(gmv) FILTER (WHERE year(purchase_month)=2018) /
                      SUM(gmv) FILTER (WHERE year(purchase_month)=2017 AND month(purchase_month)<=8) - 1
               FROM mart_monthly""")[0]
    top_cat = q("SELECT category, gmv FROM mart_categories ORDER BY gmv DESC LIMIT 1")
    worst_state = q("SELECT customer_state, late_rate_pct FROM mart_customer_states WHERE orders >= 300 ORDER BY late_rate_pct DESC LIMIT 1")
    worst_lane = q("SELECT seller_state, customer_state, late_rate_pct, orders FROM mart_lanes ORDER BY late_rate_pct DESC LIMIT 1")
    cc = q("SELECT pct_orders FROM mart_payments WHERE payment_type='credit_card'")[0]
    inst = {r[0]: r[2] for r in con.execute("SELECT * FROM mart_installments").fetchall()}
    totals = q("SELECT COUNT(*), SUM(gmv) FILTER (WHERE is_delivered), SUM(gmv) FROM fct_orders")
    timing = {(r[0], r[1]): r for r in con.execute("SELECT * FROM mart_late_vs_ontime_by_timing").fetchall()}
    strat_sql = """WITH d AS (SELECT * FROM fct_orders WHERE is_delivered AND review_score IS NOT NULL {extra}),
        s AS (SELECT customer_state, n_items > 1 AS multi_item,
                     AVG(review_score) FILTER (WHERE is_late) - AVG(review_score) FILTER (WHERE NOT is_late) AS gap,
                     COUNT(*) FILTER (WHERE is_late) AS n_late
              FROM d GROUP BY 1, 2 HAVING n_late >= 20)
        SELECT SUM(gap * n_late) / SUM(n_late) FROM s"""
    strat = q(strat_sql.format(extra=""))[0]
    strat_after = q(strat_sql.format(extra="AND NOT reviewed_before_delivery"))[0]
    lane_k = q("""SELECT SUM(is_late::INT), COUNT(*) FROM fct_orders
                  WHERE is_delivered AND n_sellers = 1 AND seller_state = 'SP' AND customer_state = 'AL'""")
    misc = q("""SELECT (SELECT COUNT(*) FROM fct_orders WHERE is_delivered AND review_score IS NULL),
                       (SELECT COUNT(*) FROM (SELECT order_id FROM raw_reviews GROUP BY 1 HAVING COUNT(*) > 1)),
                       (SELECT COUNT(*) FROM (SELECT order_id FROM raw_reviews GROUP BY 1
                                              HAVING COUNT(*) > 1 AND MIN(review_score) <> MAX(review_score))),
                       (SELECT COUNT(*) FROM (SELECT review_id FROM raw_reviews GROUP BY 1 HAVING COUNT(DISTINCT order_id) > 1)),
                       (SELECT COUNT(*) FILTER (WHERE n_sellers > 1) FROM fct_orders)""")

    scores = con.execute("""SELECT is_late, reviewed_before_delivery AS before, review_score
                            FROM fct_orders WHERE is_delivered AND review_score IS NOT NULL""").fetchdf()
    late, ontime = scores[scores.is_late].review_score, scores[~scores.is_late].review_score
    late_after = scores[scores.is_late & ~scores.before.astype(bool)].review_score
    ontime_after = scores[~scores.is_late & ~scores.before.astype(bool)].review_score
    late_before = scores[scores.is_late & scores.before.astype(bool)].review_score
    d_all, t_all, b_all = mean_diff_ci(late, ontime)
    d_aft, t_aft, b_aft = mean_diff_ci(late_after, ontime_after)   # PRIMARY: both reviewed after delivery
    d_bef, _, b_bef = mean_diff_ci(late_before, ontime)
    u, p = stats.mannwhitneyu(late, ontime, alternative="less")   # kept for reference only
    lane_lo, lane_hi = wilson_ci(int(lane_k[0]), int(lane_k[1]))

    b = buckets.set_index("late_bucket")
    return {
        "orders": int(totals[0]),
        "gmv_brl_delivered": float(totals[1]),
        "gmv_brl_all_statuses": float(totals[2]),
        "late_rate_pct": float(est.late_rate_pct),
        "late_avg_score": float(lo["late"][2]),
        "ontime_avg_score": float(lo["on time"][2]),
        "late_pct_1_2_star": float(lo["late"][3]),
        "ontime_pct_1_2_star": float(lo["on time"][3]),
        "score_8_14_days_late": float(b.loc["5. 8-14 days late", "avg_score"]),
        "pct_1_2_star_8_14_days_late": float(b.loc["5. 8-14 days late", "pct_1_2_star"]),
        "pct_late_reviews_before_delivery": float(timing[("late", "before delivery")][3]),
        "pct_ontime_reviews_before_delivery": float(timing[("on time", "before delivery")][3]),
        "late_before_delivery_score": float(timing[("late", "before delivery")][4]),
        "late_after_delivery_score": float(timing[("late", "after delivery")][4]),
        "ontime_after_delivery_score": float(timing[("on time", "after delivery")][4]),
        "ontime_after_pct_1_2_star": float(timing[("on time", "after delivery")][5]),
        "late_before_delivery_n": int(timing[("late", "before delivery")][2]),
        "late_after_delivery_n": int(timing[("late", "after delivery")][2]),
        "late_after_pct_1_2_star": float(timing[("late", "after delivery")][5]),
        "late_before_pct_1_2_star": float(timing[("late", "before delivery")][5]),
        "gap_all": round(float(d_all), 3),
        "gap_all_t_ci": [round(float(x), 3) for x in t_all],
        "gap_all_boot_ci": [round(float(x), 3) for x in b_all],
        "gap_after_delivery": round(float(d_aft), 3),
        "gap_after_t_ci": [round(float(x), 3) for x in t_aft],
        "gap_after_boot_ci": [round(float(x), 3) for x in b_aft],
        "gap_before_delivery": round(float(d_bef), 3),
        "gap_before_boot_ci": [round(float(x), 3) for x in b_bef],
        "gap_stratified_state_items": round(float(strat), 3),
        "gap_after_stratified_state_items": round(float(strat_after), 3),
        "mannwhitney_p": float(p),
        "delivered_without_review": int(misc[0]),
        "orders_with_multiple_reviews": int(misc[1]),
        "multi_review_orders_conflicting_scores": int(misc[2]),
        "review_ids_shared_across_orders": int(misc[3]),
        "multi_seller_orders": int(misc[4]),
        "avg_promised_days": float(est.avg_promised_days),
        "avg_actual_days": float(est.avg_actual_days),
        "median_days_early": float(est.median_days_early),
        "seller_q4_late_pct": float(tiers.iloc[-1].late_rate_pct),
        "seller_q1_late_pct": float(tiers.iloc[0].late_rate_pct),
        "seller_q4_score": float(tiers.iloc[-1].avg_score),
        "seller_tier_sellers_each": int(tiers.iloc[0].sellers),
        "seller_q4_pct_sp": float(tiers.iloc[-1].pct_sp_sellers),
        "seller_q1_pct_sp": float(tiers.iloc[0].pct_sp_sellers),
        "seller_q1_score": float(tiers.iloc[0].avg_score),
        "sellers_for_80pct_gmv": int(pareto_80[0]),
        "sellers_total": int(pareto_80[1]),
        "repeat_rate_pct": float(rep.repeat_rate_pct),
        "gmv_yoy_jan_aug_2018_pct": round(100 * float(yoy), 1),
        "top_category": top_cat[0], "top_category_gmv": float(top_cat[1]),
        "worst_state": worst_state[0], "worst_state_late_pct": float(worst_state[1]),
        "worst_lane": f"{worst_lane[0]}->{worst_lane[1]}", "worst_lane_late_pct": float(worst_lane[2]),
        "worst_lane_orders": int(worst_lane[3]),
        "worst_lane_wilson_ci_pct": [round(100 * float(lane_lo), 1), round(100 * float(lane_hi), 1)],
        "credit_card_pct": float(cc),
        "aov_single_installment": float(inst["1 (single)"]), "aov_7plus_installments": float(inst["7+"]),
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    con = build()
    marts = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'mart_%' ORDER BY 1").fetchall()]
    for t in marts:
        con.execute(f"COPY {t} TO '{(OUT / t).as_posix()}.csv' (HEADER)")
    m = headline_metrics(con)
    (OUT / "headline_metrics.json").write_text(json.dumps(m, indent=2))
    print(f"Built {len(marts)} marts -> {OUT}")
    for k, v in m.items():
        print(f"  {k:30s} {v}")


if __name__ == "__main__":
    main()
