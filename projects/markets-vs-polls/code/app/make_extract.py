"""Copy the saved, state-level results into app/data. Run from code/: python app/make_extract.py"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).parent / "data"; OUT.mkdir(exist_ok=True)
for f in ["scores.csv", "matched_panel.csv", "findings.json"]:
    shutil.copy(ROOT / "data" / "clean" / f, OUT / f)
