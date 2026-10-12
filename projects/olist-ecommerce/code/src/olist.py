"""Build the Olist DuckDB warehouse: raw views -> staging -> facts -> marts."""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "olist.duckdb"

RAW_FILES = [
    "olist_customers_dataset.csv", "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv", "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv", "olist_orders_dataset.csv",
    "olist_products_dataset.csv", "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def check_raw(raw_dir: Path = RAW_DIR) -> None:
    missing = [f for f in RAW_FILES if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing raw CSVs in {raw_dir}: {missing}. Run `python src/download_data.py`."
        )


def build(db_path: Path | str = DB_PATH, raw_dir: Path = RAW_DIR) -> duckdb.DuckDBPyConnection:
    """Run every sql/*.sql file in order and return an open connection."""
    check_raw(raw_dir)
    con = duckdb.connect(str(db_path))
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        con.execute(sql_file.read_text().replace("{raw}", raw_dir.as_posix()))
    return con


def connect(db_path: Path | str = DB_PATH) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True)
