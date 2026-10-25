"""Step 3: load the clean table and the region seed into SQLite (data/electricity.db).

Rerunning drops and rebuilds the tables, so it never creates duplicates.
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_FILE = ROOT / "data" / "electricity.db"
SCHEMA = ROOT / "sql" / "schema.sql"


def load(df: pd.DataFrame, regions: pd.DataFrame, db_path=DB_FILE) -> dict:
    out = df.copy()
    out["month"] = out["month"].dt.strftime("%Y-%m-%d")
    regions = regions.copy()
    regions["multi_region"] = regions["multi_region"].astype(int)
    with sqlite3.connect(db_path) as con:
        con.executescript(SCHEMA.read_text())
        out.to_sql("retail_sales_monthly", con, if_exists="append", index=False)
        regions.to_sql("state_region", con, if_exists="append", index=False)
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("retail_sales_monthly", "state_region", "v_residential_price")}
    return counts
