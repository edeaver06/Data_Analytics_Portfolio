import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.olist import RAW_DIR, build  # noqa: E402


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    """Build a fresh warehouse in a temp file so tests never depend on stale state."""
    return build(tmp_path_factory.mktemp("db") / "test.duckdb")


@pytest.fixture(scope="session")
def raw():
    import pandas as pd
    read = lambda n: pd.read_csv(RAW_DIR / f"olist_{n}_dataset.csv")  # noqa: E731
    return {n: read(n) for n in ["orders", "order_items", "order_reviews", "products", "customers"]} | {
        "translation": pd.read_csv(RAW_DIR / "product_category_name_translation.csv")}
