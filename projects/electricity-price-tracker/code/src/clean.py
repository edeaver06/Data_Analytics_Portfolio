"""Step 2: turn raw EIA rows into a tidy table with proper types and units.

Decisions (also in README):
- EIA sends numbers as text; convert to numbers. Blanks stay blank (NaN) - we
  never fill in a withheld value.
- Customer counts are reported as 0 for every row before 2008-01 because EIA
  did not collect them monthly then. A 0 there means "not collected", so we
  store it as blank and flag it.
- `period` "2026-07" becomes a real date (first day of the month).
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "retail_sales_all.json"
CLEAN_FILE = ROOT / "data" / "clean" / "retail_sales_monthly.csv"
SEED_FILE = ROOT / "data" / "seed" / "state_region.csv"

RENAME = {
    "stateid": "state", "stateDescription": "state_name", "sectorid": "sector",
    "sectorName": "sector_name", "price": "price_cents_per_kwh",
    "sales": "sales_million_kwh", "revenue": "revenue_million_usd", "customers": "customers",
}
EXPECTED_UNITS = {
    "price-units": "cents per kilowatt-hour", "sales-units": "million kilowatt hours",
    "revenue-units": "million dollars", "customers-units": "number of customers",
}
VALUE_COLS = ["price_cents_per_kwh", "sales_million_kwh", "revenue_million_usd", "customers"]


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    # Stop if EIA ever changes units, so we don't silently mix them.
    for col, unit in EXPECTED_UNITS.items():
        found = set(raw[col].dropna().unique())
        if found - {unit}:
            raise ValueError(f"Unexpected units in {col}: {found}")
    df = raw[["period", *RENAME]].rename(columns=RENAME).copy()
    df["month"] = pd.to_datetime(df.pop("period"), format="%Y-%m")
    for col in VALUE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")  # text -> number; blanks stay NaN
    # Pre-2008 customer counts of 0 mean "not collected", not zero customers.
    not_collected = (df["month"] < "2008-01-01") & (df["customers"] == 0)
    df.loc[not_collected, "customers"] = pd.NA
    df["customers"] = df["customers"].astype("Int64")
    df["customers_not_collected"] = not_collected.astype(int)
    df["any_value_missing"] = df[VALUE_COLS].isna().any(axis=1).astype(int)
    df = df.drop_duplicates(["state", "month", "sector"])
    return df.sort_values(["state", "sector", "month"]).reset_index(drop=True)[
        ["state", "state_name", "sector", "sector_name", "month", *VALUE_COLS,
         "customers_not_collected", "any_value_missing"]]


def load_regions() -> pd.DataFrame:
    return pd.read_csv(SEED_FILE, dtype=str, keep_default_na=False)


def main():
    raw = pd.DataFrame(json.loads(RAW_FILE.read_text()))
    df = clean(raw)
    CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_FILE, index=False, date_format="%Y-%m-%d")
    print(f"raw rows: {len(raw)} -> clean rows: {len(df)} (dropped {len(raw) - len(df)})")
    return df


if __name__ == "__main__":
    main()
