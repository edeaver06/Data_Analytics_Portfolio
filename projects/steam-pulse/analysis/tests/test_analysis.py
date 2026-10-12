import sys, pathlib, numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import steam_analysis as sa

def test_coverage_and_views():
    c = sa.connect(); cov = sa.q(c, "10_coverage").iloc[0]
    assert cov.games == 1000 and cov.games_with_players == 999 and cov.n_snapshots >= 1
    assert c.sql("select count(*) from a_game").fetchone()[0] == c.sql("select count(distinct appid) from a_game").fetchone()[0]
    g = sa.q(c, "40_genre"); assert not g.genre.str.contains('"').any()

def test_readiness_blocks_timeseries_on_one_snapshot():
    r = sa.readiness({"n_days": 1, "released_last_30d": 0, "games_with_players": 999})
    assert not r["model_30d"] and not r["price_event_study"] and r["cross_sectional"]

def test_did_recovers_synthetic_effect():  # synthetic fixture for method validation only
    rows = []
    for a in range(40):
        t = a < 20
        for k in range(-7, 8):
            rows.append(dict(appid=a, treated=t, d=pd.Timestamp("2026-01-10") + pd.Timedelta(days=k),
                event_d=pd.Timestamp("2026-01-10"), players=1000 * (1 + 0.01 * k) * (1.5 if t and k >= 0 else 1)))
    did = sa.event_study_did(pd.DataFrame(rows)).set_index("rel").did
    assert abs(did.loc[3] - np.log(1.5)) < 0.02 and abs(did.loc[-3]) < 0.01

def test_lead_lag_detects_lead():
    x = pd.Series(np.random.default_rng(0).normal(size=200)); y = x.shift(2).fillna(0)
    ll = sa.lead_lag(x, y); assert ll.loc[ll["corr"].idxmax(), "lag"] == 2

def test_backtest_is_time_ordered_and_beats_median_on_signal():
    rng = np.random.default_rng(1); n = 300
    df = pd.DataFrame({"release_date": pd.date_range("2024-01-01", periods=n), "log_p1": rng.normal(8, 1, n)})
    df["log_p30"] = df.log_p1 - 1 + rng.normal(0, .2, n)
    bt = sa.time_backtest(df, ["log_p1"])
    assert (bt.mae_model < bt.mae_train_median).all() and len(bt) == 3

def test_retention_index_starts_at_one():
    p = pd.DataFrame({"appid": [1]*10, "day_since_launch": range(10), "players": [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]})
    r = sa.retention_curve(p); assert r.idx.iloc[0] == 1.0 and r.idx.iloc[-1] == 0.1

import best_score as bs
def test_bayes_shrinks_small_samples():
    r = bs.bayes_review([10, 100000], [0, 0], prior_n=1000, mu=0.8)
    assert r[0] < 0.81 and r[1] > 0.99

def test_score_weights_sum_and_range():
    assert abs(sum(bs.WEIGHTS.values()) - 1) < 1e-9
    df = pd.DataFrame({"appid": [1, 2, 3], "positive": [900, 50, 10], "negative": [100, 50, 90], "player_count": [1000, 100, 10], "price_usd": [10, 10, 10]})
    s = bs.score(df); assert s.appid.iloc[0] == 1 and s.score.between(0, 1).all()
