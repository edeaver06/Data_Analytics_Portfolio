import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, pytest
from forecast_scoring import brier, log_loss, poll_prob, paired_bootstrap, connect, matched_panel, ml_prob

@pytest.fixture(scope="module")
def con(): return connect()

def test_brier_basic(): assert brier([1, 0, .5], [1, 0, 1]) == pytest.approx(0.25 / 3)
def test_log_loss_perfect_small(): assert log_loss([.999], [1]) < 0.01
def test_poll_prob_symmetric(): assert poll_prob(0) == pytest.approx(.5) and poll_prob(5) + poll_prob(-5) == pytest.approx(1)
def test_reused_ml_prob(): assert float(ml_prob([-110])[0]) == pytest.approx(110 / 210)
def test_bootstrap_sign():
    est, (lo, hi) = paired_bootstrap([1, 0, 1, 0], [.5] * 4, [1, 0, 1, 0]); assert est < 0 and hi <= 0

def test_outcomes_match_pandas(con):
    m = pd.read_csv(Path(__file__).resolve().parents[1] / "data/raw/mit_president_1976_2024.csv")
    m = m[(m.year == 2024) & m.party_simplified.isin(["DEMOCRAT", "REPUBLICAN"])].groupby(["state_po", "party_simplified"]).candidatevotes.sum().unstack()
    exp = (m.REPUBLICAN > m.DEMOCRAT).astype(int)
    got = con.execute("SELECT state_po, rep_won FROM outcomes").df().set_index("state_po").rep_won
    assert len(got) == 51 and (got.sort_index() == exp.sort_index()).all()

def test_no_lookahead(con):
    # every market price used is on/before its horizon date
    bad = con.execute("SELECT count(*) FROM market_at_horizon WHERE price_date > DATE '2024-11-05' - days_before::INT").fetchone()[0]
    assert bad == 0
    bad_p = con.execute("SELECT count(*) FROM poll_avg").fetchone()[0]; assert bad_p > 0
    d = matched_panel(con); assert d.groupby(["days_before", "state_po"]).size().max() == 1
