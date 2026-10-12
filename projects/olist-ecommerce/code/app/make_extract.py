"""Copy aggregate mart tables (no order-, customer- or seller-level rows) into app/data.
Run from code/ after the dbt/analysis pipeline: python app/make_extract.py
The Olist data is CC BY-NC-SA 4.0, so only these summaries ship with the app."""
import shutil
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "data" / "outputs"
OUT = Path(__file__).parent / "data"; OUT.mkdir(exist_ok=True)
AGGREGATES = ["mart_delivery_vs_reviews", "mart_late_vs_ontime_by_timing", "mart_seller_tiers", "mart_lanes",
              "mart_customer_states", "mart_monthly", "mart_cohorts", "mart_categories", "mart_payments"]
for name in AGGREGATES:
    shutil.copy(SRC / f"{name}.csv", OUT / f"{name}.csv")
shutil.copy(SRC / "headline_metrics.json", OUT / "headline_metrics.json")
