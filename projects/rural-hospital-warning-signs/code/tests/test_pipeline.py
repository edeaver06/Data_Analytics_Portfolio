import sqlite3, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pipeline as p

def toy():
    base = dict(ccn="1", name="A", city="X", state="SD", county="C", rural_urban="R", facility_type="CAH",
                control=2, fy_begin=pd.Timestamp("2023-01-01"), fy_end=pd.Timestamp("2023-12-31"), beds=25,
                days_medicare=500, days_medicaid=100, days_total=1000, net_patient_revenue=10e6,
                operating_expense=11e6, operating_income=-1e6, other_income=0.5e6, net_income=-0.5e6,
                depreciation=0.05e6*365/365, cash=0.5e6, temp_investments=0, current_assets=2e6,
                current_liabilities=3e6, fund_balance=-1, uncompensated_care=0)
    return pd.DataFrame([base, {**base, "ccn": "2", "facility_type": "PH"}])

def test_filters_to_acute_and_cah():
    assert set(p.clean(toy())["facility_type"]) == {"CAH"}

def test_metrics():
    r = p.clean(toy()).iloc[0]
    assert abs(r.patient_margin - (-0.1)) < 1e-9
    assert abs(r.total_margin - (-0.5 / 10.5)) < 1e-9
    assert abs(r.medicaid_share - 0.1) < 1e-9
    assert abs(r.days_cash - 0.5e6 / ((11e6 - 0.05e6) / 365)) < 1e-6

def test_score_points():
    r = p.clean(toy()).iloc[0]
    # neg total margin, low cash, current ratio<1, neg equity, top-quartile Medicaid (only row) ; deep loss no (-10% not < -10%)
    assert r.warning_score == 5 and r.warning_tier == "Many warning signs"

def test_db_matches_csv():
    with sqlite3.connect(ROOT / "data/hospitals.db") as con:
        n = con.execute("select count(*) from hospitals where analysis_ok=1").fetchone()[0]
        dup = con.execute("select count(*)-count(distinct ccn) from hospitals").fetchone()[0]
    csv = pd.read_csv(ROOT / "data/clean/hospitals_fy2023.csv")
    assert n == int(csv.analysis_ok.sum()) and dup == 0

def test_scored_ranges():
    d = pd.read_csv(ROOT / "data/clean/hospitals_fy2023.csv").query("analysis_ok")
    assert d.warning_score.between(0, 6).all()
    assert d.medicaid_share.between(0, 1).all()
    assert d.total_margin.between(-1, 1).all()
    assert set(d.warning_tier) <= {"Few warning signs", "Some warning signs", "Many warning signs"}
