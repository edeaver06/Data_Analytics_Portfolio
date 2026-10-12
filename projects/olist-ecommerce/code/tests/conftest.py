import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.olist import RAW_DIR, build  # noqa: E402

# The real Olist CSVs are CC BY-NC-SA and gitignored; download them from Kaggle into data/raw.
# Without them (e.g. CI), the pipeline runs on a tiny SYNTHETIC fixture instead, so the
# integrity and parity tests still execute. README-number tests need the real data and skip.
SYNTHETIC_DIR = ROOT / "tests" / "fixtures" / "synthetic_olist"
REAL = (RAW_DIR / "olist_orders_dataset.csv").exists()
DATA_DIR = RAW_DIR if REAL else SYNTHETIC_DIR


@pytest.fixture(scope="session")
def using_real_data():
    return REAL


@pytest.fixture
def need_real():
    if not REAL:
        pytest.skip("needs the real Olist CSVs in data/raw (running on the synthetic fixture)")


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    """Build a fresh warehouse in a temp file so tests never depend on stale state."""
    return build(tmp_path_factory.mktemp("db") / "test.duckdb", raw_dir=DATA_DIR)


@pytest.fixture(scope="session")
def raw():
    import pandas as pd
    read = lambda n: pd.read_csv(DATA_DIR / f"olist_{n}_dataset.csv")  # noqa: E731
    return {n: read(n) for n in ["orders", "order_items", "order_reviews", "products", "customers"]} | {
        "translation": pd.read_csv(DATA_DIR / "product_category_name_translation.csv")}
