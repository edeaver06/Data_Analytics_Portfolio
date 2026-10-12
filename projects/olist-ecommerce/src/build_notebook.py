"""Generates notebooks/olist_story.ipynb (kept as code so the notebook is reproducible)."""
from pathlib import Path
import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
md("""# When the parcel is late, the stars fall
A short walk through the business story using the DuckDB marts built by `src/run_pipeline.py`.
**Question:** how strongly are late deliveries associated with worse reviews, and who or where are they concentrated?

**Limitations up front:** observational data (association, not causation); 84% of late-order reviews were written before the parcel arrived; 646 delivered orders have no review and reviewers self-select; multi-seller orders (1.3%) share one lateness flag."""),
code("""import sys
from pathlib import Path
from IPython.display import Image, display
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))
from src.olist import build
con = build()  # rebuilds data/olist.duckdb from data/raw (about 5 s)
q = lambda sql: con.execute(sql).fetchdf()
FIG = ROOT / "images"
q("SELECT COUNT(*) AS orders, ROUND(SUM(gmv)) AS gmv_brl, MIN(purchased_at) AS first, MAX(purchased_at) AS last FROM fct_orders")"""),
md("""## 1. The data, and the grain traps
`fct_orders` has exactly one row per order. Items are aggregated *before* joining payments and reviews, so revenue isn't double-counted:"""),
code("""q(\"\"\"SELECT (SELECT SUM(gmv) FROM fct_orders) AS fct_gmv,
          (SELECT SUM(price) FROM stg_order_items) AS item_gmv,
          (SELECT COUNT(*) FROM (SELECT order_id FROM raw_reviews GROUP BY 1 HAVING COUNT(*) > 1)) AS orders_with_multiple_reviews,
          (SELECT COUNT(*) FROM (SELECT review_id FROM raw_reviews GROUP BY 1 HAVING COUNT(DISTINCT order_id) > 1)) AS review_ids_shared_across_orders\"\"\")"""),
md("""## 2. Primary comparison: reviews written after delivery
Olist sends the survey around the estimated date, so most late-order reviews are written before the parcel arrives. The fair comparison is late vs on time **among reviews written after delivery**."""),
code('display(q("SELECT * FROM mart_late_vs_ontime_by_timing")); display(Image(FIG / "08_review_timing.png"))'),
code("""import sys; sys.path.insert(0, str(ROOT / "src"))
from run_pipeline import headline_metrics
m = headline_metrics(con)
print(f"PRIMARY  after delivery: {m['late_after_delivery_score']:.2f} vs {m['ontime_after_delivery_score']:.2f}, gap {m['gap_after_delivery']:+.2f} "
      f"(Welch 95% CI {m['gap_after_t_ci']}, bootstrap {m['gap_after_boot_ci']}); stratified {m['gap_after_stratified_state_items']:+.2f}")
print(f"SECONDARY before delivery: {m['pct_late_reviews_before_delivery']:.0f}% of late reviews, {m['late_before_delivery_score']:.2f} stars, gap {m['gap_before_delivery']:+.2f}")
print(f"Pooled: gap {m['gap_all']:+.2f} (CI {m['gap_all_t_ci']}); stratified by state and item count {m['gap_stratified_state_items']:+.2f}")"""),
md("## 3. All reviews pooled, by days late ('on estimate day' counts as on time)"),
code('q("SELECT * FROM mart_late_vs_ontime")'),
code('display(q("SELECT * FROM mart_delivery_vs_reviews")); display(Image(FIG / "01_late_vs_reviews.png"))'),
md("## 4. Promises are padded, yet still missed"),
code('q("SELECT * FROM mart_estimate_accuracy")'),
md("""## 5. Sellers, out of sample\nRanked on 2017 late rate (shrunk toward the mean), measured on 2018 orders. Ranking and reporting on the same data would be circular."""),
code('display(q("SELECT * FROM mart_seller_tiers")); display(Image(FIG / "02_seller_tiers.png"))'),
code('q("SELECT * FROM mart_worst_sellers")'),
md("## 6. Where? States and lanes\nSão Paulo sellers shipping to the North-East (AL, MA, SE, PI) are the worst lanes."),
code('display(q("SELECT * FROM mart_lanes LIMIT 10")); print("SP->AL Wilson 95% CI (%):", m["worst_lane_wilson_ci_pct"]); display(Image(FIG / "06_lane_heatmap.png"))'),
code('display(Image(FIG / "04_state_late_rate.png"))'),
md("## 7. Categories"),
code('display(q("SELECT * FROM mart_categories LIMIT 10")); display(Image(FIG / "05_category_matrix.png"))'),
md("## 8. Growth is strong, but retention is near zero"),
code('display(q("SELECT * FROM mart_repeat_customers")); display(Image(FIG / "03_monthly_gmv.png"))'),
code('display(Image(FIG / "07_cohort_retention.png"))'),
md("## 9. Payments"),
code('display(q("SELECT * FROM mart_payments")); display(q("SELECT * FROM mart_installments"))'),
md("""## Takeaways
1. Reviewed after delivery, late orders score **3.78★ vs 4.29★** on time (gap −0.51★, 95% CI −0.60 to −0.43).
2. **84%** of late-order reviews are written before the parcel arrives and average **1.97★**, so not having the order yet goes hand in hand with 1★ reviews.
3. Out of sample, 2017's least reliable seller quartile is only about **1.4x** as late in 2018 (9.6% vs 6.9%), and it is 89% São Paulo sellers: lanes matter as much as sellers.
4. SP → North-East lanes miss their estimates 15–24% of the time (SP→AL 24%, 95% CI 19–30%), even though estimates are padded by about 12 days.
5. Only **3%** of customers buy twice, so fixing first deliveries is also a retention play.

*Observational data: lateness is associated with worse reviews; this doesn't prove causation.*"""),
]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
nbf.write(nb, Path(__file__).parents[1] / "notebooks" / "olist_story.ipynb")
