"""Write the app's small extract: saved result tables plus season-by-season profit per strategy.
Run from code/ (after src/run_analysis.py): python app/make_extract.py"""
import shutil, sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clv import connect  # noqa: E402

OUT = Path(__file__).parent / "data"; OUT.mkdir(exist_ok=True)
for f in ["strategy_tests.csv", "spread_buckets.csv", "ml_calibration.csv", "walk_forward.csv", "findings.json"]:
    shutil.copy(ROOT / "data" / "clean" / f, OUT / f)
con = connect()
d = con.execute("SELECT strategy, season, win FROM strategy_bets WHERE win IS NOT NULL").df()
d["units"] = d.win.map({1: 100 / 110, 0: -1.0})
s = d.groupby(["strategy", "season"], as_index=False).agg(bets=("win", "size"), wins=("win", "sum"), units=("units", "sum"))
s.to_csv(OUT / "strategy_by_season.csv", index=False)
print(len(s), "strategy-season rows")
