"""Write the app's small data extract (daily totals per market and problem type) from data/raw.
Run from code/: python app/make_extract.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fcr import load_data, preprocess  # noqa: E402

d = preprocess(load_data())
out = (d.groupby(["date", "market", "problem_category"], as_index=False)
         .agg(first_calls=("contacts_n", "sum"), repeat_calls=("repeat_calls", "sum")))
out["first_calls"] = out.first_calls.astype(int); out["repeat_calls"] = out.repeat_calls.astype(int)
(Path(__file__).parent / "data").mkdir(exist_ok=True)
out.to_csv(Path(__file__).parent / "data" / "daily_calls.csv", index=False)
print(len(out), "rows")
