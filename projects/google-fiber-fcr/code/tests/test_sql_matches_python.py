import sys
from pathlib import Path
import duckdb, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import fcr

def _sql_results():
    import os; os.chdir(ROOT)
    con = duckdb.connect()
    stmts = [s for s in (ROOT / "sql/fcr_metrics.sql").read_text().split(";") if s.strip() and
             any(l.strip() and not l.strip().startswith("--") for l in s.splitlines())]
    con.execute(stmts[0])
    return [con.execute(s).df() for s in stmts[1:]]

def test_rows_and_dates():
    d = fcr.preprocess(fcr.load_data())
    assert len(d) == 1350
    assert str(d.date.min().date()) == "2022-01-01" and str(d.date.max().date()) == "2022-03-31"

def test_key_numbers():
    s = fcr.summary_by_category(fcr.preprocess(fcr.load_data())).set_index("problem_category")
    b = s.loc["Account Management & Billing"]
    assert (b.first_calls, b.repeat_calls, b.repeat_rate_pct) == (3553, 2400, 67.5)
    sc = s.loc["Scheduling"]
    assert (sc.repeat_calls, sc.repeat_rate_pct) == (1469, 60.6)
    assert s.repeat_rate_pct.idxmax() == "Account Management & Billing"
    share = s.loc[["Wi-Fi & Internet", "Technical Troubleshooting"], "repeat_calls"].sum() / s.repeat_calls.sum()
    assert 0.80 < share < 0.81

def test_sql_matches_python():
    d = fcr.preprocess(fcr.load_data())
    cat, mkt, mc, wk = _sql_results()
    py = fcr.summary_by_category(d).set_index("problem_category")
    for _, r in cat.iterrows():
        p = py.loc[r.problem_category]
        assert (int(r.first_calls), int(r.repeat_calls), r.repeat_rate_pct) == (p.first_calls, p.repeat_calls, p.repeat_rate_pct)
    pm = fcr.summary_by_market(d).set_index("market")
    for _, r in mkt.iterrows():
        assert (int(r.first_calls), int(r.repeat_calls)) == (pm.loc[r.market].first_calls, pm.loc[r.market].repeat_calls)
    pw = fcr.weekly_trend(d)
    assert list(wk.first_calls.astype(int)) == list(pw.first_calls)
    assert list(wk.repeat_calls.astype(int)) == list(pw.repeat_calls)
