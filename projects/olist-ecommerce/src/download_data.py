"""Download the 9 Olist CSVs from Olist's own public GitHub repo (no Kaggle auth needed)
and verify row counts against the published Kaggle figures."""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.olist import RAW_DIR, RAW_FILES  # noqa: E402

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"
EXPECTED_ROWS = {
    "olist_customers_dataset.csv": 99_441, "olist_geolocation_dataset.csv": 1_000_163,
    "olist_order_items_dataset.csv": 112_650, "olist_order_payments_dataset.csv": 103_886,
    "olist_order_reviews_dataset.csv": 99_224, "olist_orders_dataset.csv": 99_441,
    "olist_products_dataset.csv": 32_951, "olist_sellers_dataset.csv": 3_095,
    "product_category_name_translation.csv": 71,
}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in RAW_FILES:
        dest = RAW_DIR / name
        if not dest.exists():
            print(f"downloading {name} ...")
            urllib.request.urlretrieve(f"{BASE}/{name}", dest)
        n = duckdb.sql(f"SELECT COUNT(*) FROM read_csv_auto('{dest.as_posix()}', header=true)").fetchone()[0]
        status = "OK" if n == EXPECTED_ROWS[name] else f"MISMATCH (expected {EXPECTED_ROWS[name]:,})"
        print(f"{name:45s} {n:>10,} rows  {status}")
        if n != EXPECTED_ROWS[name]:
            sys.exit(1)


if __name__ == "__main__":
    main()
