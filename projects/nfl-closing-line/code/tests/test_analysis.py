import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, pytest
from clv import connect, ml_prob, BREAKEVEN
from clv import test_strategies as run_tests

@pytest.fixture(scope="module")
def con(): return connect()

def test_breakeven(): assert abs(BREAKEVEN - 0.5238) < 1e-4

def test_ml_prob(): assert np.allclose(ml_prob([-110, 100, 200]), [110/210, 0.5, 1/3])

def test_sql_cover_matches_pandas(con):
    raw = pd.read_csv(Path(__file__).resolve().parents[1] / "data/raw/games.csv").dropna(subset=["result","spread_line","total_line"])
    m = raw.result - raw.spread_line
    sql = con.execute("SELECT sum(home_cover), count(home_cover) FROM games").fetchone()
    assert sql == ((m > 0).sum(), (m != 0).sum())

def test_roi_formula(con):
    s = con.execute("SELECT * FROM strategy_summary").df().iloc[0]
    assert abs(s.roi_per_unit - (s.wins*100/110 - s.losses)/s.bets) < 1e-12

def test_pushes_excluded(con):
    assert con.execute("SELECT count(*) FROM games WHERE ats_margin=0 AND home_cover IS NOT NULL").fetchone()[0] == 0

def test_holm_never_smaller(con):
    s = run_tests(con.execute("SELECT * FROM strategy_summary").df())
    assert (s.p_vs_50_holm >= s.p_vs_50 - 1e-12).all()
