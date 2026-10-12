"""Can You Beat the Closing Line? Analysis helpers (DuckDB SQL + Python stats)."""
from pathlib import Path
import duckdb, numpy as np, pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/games.csv"
BREAKEVEN = 110 / 210  # 52.38%

def connect(raw=RAW):
    con = duckdb.connect()
    con.execute(f"CREATE TABLE raw_games AS SELECT * FROM read_csv_auto('{raw}', all_varchar=false)")
    con.execute((ROOT / "sql/closing_line.sql").read_text())
    return con

def ml_prob(ml):
    ml = np.asarray(ml, float)
    return np.where(ml < 0, -ml / (-ml + 100), 100 / (ml + 100))

def efficiency(g):
    """OLS result ~ spread_line (efficient: intercept 0, slope 1); total likewise."""
    out = {}
    for y, x in [("result", "spread_line"), ("total", "total_line")]:
        m = sm.OLS(g[y], sm.add_constant(g[x])).fit(cov_type="HC1")
        out[y] = dict(intercept=m.params["const"], slope=m.params[x],
                      slope_ci=tuple(m.conf_int().loc[x]), mean_err=(g[y] - g[x]).mean(),
                      mae=(g[y] - g[x]).abs().mean(), n=len(g))
    return out

def moneyline_calibration(g):
    d = g.dropna(subset=["home_moneyline", "away_moneyline"]).query("result != 0 and abs(home_moneyline) >= 100 and abs(away_moneyline) >= 100").copy()
    ph, pa = ml_prob(d.home_moneyline), ml_prob(d.away_moneyline)
    d["overround"] = ph + pa - 1
    d["p_home"] = ph / (ph + pa)  # proportional vig removal
    d["home_win"] = (d.result > 0).astype(int)
    d["bin"] = pd.cut(d.p_home, np.linspace(0, 1, 11))
    cal = d.groupby("bin", observed=True).agg(n=("home_win", "size"), pred=("p_home", "mean"), actual=("home_win", "mean"))
    brier = ((d.p_home - d.home_win) ** 2).mean()
    return d, cal, brier

def test_strategies(summary, alpha=0.05):
    s = summary.copy()
    s["p_vs_50"] = [stats.binomtest(int(w), int(n), 0.5).pvalue for w, n in zip(s.wins, s.bets)]
    s["p_beats_vig"] = [stats.binomtest(int(w), int(n), BREAKEVEN, alternative="greater").pvalue for w, n in zip(s.wins, s.bets)]
    lo, hi = proportion_confint(s.wins, s.bets, method="wilson")
    s["ci_low"], s["ci_high"] = lo, hi
    s["p_vs_50_holm"] = multipletests(s.p_vs_50, method="holm")[1]
    s["p_beats_vig_holm"] = multipletests(s.p_beats_vig, method="holm")[1]
    s["sig_bias_holm"] = s.p_vs_50_holm < alpha
    return s

def walk_forward(con, split=2015):
    """Pick strategies that beat break-even in-sample (< split), report out-of-sample record."""
    df = con.execute("SELECT * FROM strategy_bets WHERE win IS NOT NULL").df()
    ins, oos = df[df.season < split], df[df.season >= split]
    a = ins.groupby("strategy").win.mean().rename("in_sample_rate")
    b = oos.groupby("strategy").win.agg(["mean", "size"]).rename(columns={"mean": "oos_rate", "size": "oos_bets"})
    r = pd.concat([a, b], axis=1)
    r["picked"] = r.in_sample_rate > BREAKEVEN
    r["oos_roi"] = r.oos_rate * (100 / 110) - (1 - r.oos_rate)
    return r.sort_values("in_sample_rate", ascending=False)

def pnl_curve(con, strategy):
    d = con.execute("SELECT b.season, b.win FROM strategy_bets b WHERE strategy=? AND win IS NOT NULL", [strategy]).df()
    d["units"] = np.where(d.win == 1, 100 / 110, -1.0)
    return d.groupby("season").units.sum().cumsum()
