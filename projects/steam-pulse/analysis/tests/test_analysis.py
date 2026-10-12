import sys, pathlib, numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import steam_analysis as sa
import pytest

def _need_db():
    if not sa.DB.exists(): pytest.skip(f"{sa.DB} missing (clean checkout; run the pipeline first)")

def test_coverage_and_views():
    _need_db()
    c = sa.connect(); cov = sa.q(c, "10_coverage").iloc[0]
    assert cov.games >= 1000 and cov.games_with_players >= 999 and cov.n_snapshots >= 1
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

def test_software_rule():
    cur = {365670}
    assert bs.is_software(["Casual", "Indie", "Utilities", "Photo Editing"], 431960, cur)  # Wallpaper Engine
    assert not bs.is_software(["Action", "Utilities"], 1, cur)
    assert not bs.is_software(["Indie", "RPG"], 2, cur)
    assert bs.is_software(None, 365670, cur) and not bs.is_software(None, 3, cur)

def test_default_excludes_software():
    _need_db()
    c = sa.connect(); g = c.sql("select * from a_game where player_count is not null and positive+negative>0").df()
    kept, sw = bs.filter_software(g); all_, _ = bs.filter_software(g, include_software=True)
    assert {431960, 365670, 629520} <= set(sw.appid) and not set(sw.appid) & set(kept.appid) and len(all_) == len(g)

import backfill_build as bb, history as hi
def test_parse_steamcharts_row():
    html = '''<td class="month-cell left">
        September 2026
    </td>
    <td class="right num-f">7962.19</td><td class="right num-p gainorloss">4.86</td><td class="right gainorloss">+0.06%</td><td class="right num">13252</td>'''
    d = bb.parse_steamcharts(html, 1); assert len(d) == 1 and d.avg_players[0] == 7962.19 and d.peak_players[0] == 13252
    assert str(d.month[0]) == "2026-09-01"

def test_parse_reviews_and_bad_json():
    d = bb.parse_reviews('{"results":{"rollups":[{"date":1788220800,"recommendations_up":5,"recommendations_down":1}]}}', 7)
    assert d.up[0] == 5 and str(d.month[0]) == "2026-09-01"
    assert bb.parse_reviews("<html>", 7).empty

def test_stacked_did_on_planted_effect():  # synthetic fixture: +50% during sale, controls flat
    dates = pd.date_range("2020-01-01", periods=60); price, pl = [], []
    for a in range(12):
        sale = a < 4
        for i, d in enumerate(dates):
            on = sale and 30 <= i < 37
            price.append((a, d, 10, 5 if on else 10, 50 if on else 0)); pl.append((a, d, 1000 * (1.5 if on else 1.0)))
    P = pd.DataFrame(price, columns=["appid", "date", "initialprice", "finalprice", "discount"]); Q = pd.DataFrame(pl, columns=["appid", "date", "avg_players"])
    es, r = hi.stacked_did(P, Q, pre=14, post=14)
    assert r["n_events"] == 4 and abs(r["pretrend_days_-7_-1_pct"]) < 1e-6
    assert 25 < r["did_pct"] < 50  # days 0-7 average: 7 of 8 days at +50%

def test_launch_panel_excludes_pre_collection_games():
    sc = pd.DataFrame({"appid": [1, 1, 2, 2], "month": pd.to_datetime(["2012-07-01", "2012-08-01", "2018-03-01", "2018-04-01"]), "avg_players": [1, 1, 100, 50], "peak_players": [1, 1, 200, 80]})
    rv = pd.DataFrame({"appid": [1, 2], "month": pd.to_datetime(["2010-01-01", "2018-03-01"]), "up": [5, 5], "down": [0, 0]})
    p, L = hi.launch_panel(sc, rv); assert list(L.index) == [2] and p[p.appid == 2].m.tolist() == [0, 1]

def test_weekly_review_buckets_summed_to_unique_months():
    js = '{"results":{"rollup_type":"week","rollups":[{"date":1732060800,"recommendations_up":10,"recommendations_down":1},{"date":1732665600,"recommendations_up":5,"recommendations_down":2},{"date":1733270400,"recommendations_up":3,"recommendations_down":0}]}}'
    d = bb.parse_reviews(js, 9)
    assert len(d) == 2 and not d.duplicated(["appid", "month"]).any()
    nov = d[d.month.astype(str) == "2024-11-01"].iloc[0]; assert (nov.up, nov.down, nov.n_buckets) == (15, 3, 2)
