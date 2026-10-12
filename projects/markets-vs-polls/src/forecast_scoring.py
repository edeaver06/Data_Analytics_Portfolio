"""Markets vs Polls scoring. Calibration/Brier logic mirrors nfl-closing-line/src/clv.py
(moneyline_calibration); the American-odds helper is reused directly where needed."""
import sys
from pathlib import Path
import duckdb, numpy as np, pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "nfl-closing-line/src"))
try:
    from clv import ml_prob  # noqa: F401  (reused: American odds -> implied probability)
except Exception:  # keep this project runnable on its own
    def ml_prob(ml):
        ml = np.asarray(ml, float); return np.where(ml < 0, -ml / (-ml + 100), 100 / (ml + 100))

RAW = ROOT / "data/raw"
HORIZONS = [28, 21, 14, 7, 1]
SIGMA = 5.0   # fixed a priori: assumed SD (pts) of state poll-average error on two-party margin; NOT fit to 2024 results

ABBR = dict(zip(
 ["Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware","District of Columbia","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada","New Hampshire","New Jersey","New Mexico","New York","North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia","Wisconsin","Wyoming"],
 "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()))

def poll_prob(margin, sigma=SIGMA):
    return norm.cdf(np.asarray(margin, float) / sigma)

def brier(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float); return float(np.mean((p - y) ** 2))

def log_loss(p, y, eps=1e-3):
    p = np.clip(np.asarray(p, float), eps, 1 - eps); y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

def calibration_table(p, y, bins=5):
    d = pd.DataFrame({"p": p, "y": y}); d["bin"] = pd.cut(d.p, np.linspace(0, 1, bins + 1), include_lowest=True)
    return d.groupby("bin", observed=True).agg(n=("y", "size"), pred=("p", "mean"), actual=("y", "mean"))

def paired_bootstrap(a, b, y, n=10000, seed=0):
    """CI for Brier(a) - Brier(b), resampling states. Negative = a better."""
    rng = np.random.default_rng(seed); a, b, y = map(np.asarray, (a, b, y)); k = len(y)
    idx = rng.integers(0, k, (n, k))
    diff = ((a[idx] - y[idx]) ** 2).mean(1) - ((b[idx] - y[idx]) ** 2).mean(1)
    return float(np.mean((a - y) ** 2 - (b - y) ** 2)), tuple(np.percentile(diff, [2.5, 97.5]))

def connect():
    con = duckdb.connect()
    con.execute(f"CREATE TABLE raw_polls AS SELECT * FROM read_csv_auto('{RAW/'polls_538_2024.csv'}', all_varchar=true)")
    con.execute("ALTER TABLE raw_polls ALTER pct TYPE DOUBLE; ALTER TABLE raw_polls ALTER hypothetical TYPE BOOLEAN")
    con.execute(f"CREATE TABLE raw_mit AS SELECT * FROM read_csv_auto('{RAW/'mit_president_1976_2024.csv'}')")
    con.execute(f"CREATE TABLE raw_markets AS SELECT * FROM read_csv_auto('{RAW/'market_prices_daily.csv'}')")
    con.execute("CREATE TABLE horizons AS SELECT unnest(?) AS days_before", [HORIZONS])
    con.execute((ROOT / "sql/forecasts.sql").read_text())
    return con

def matched_panel(con, sigma=SIGMA):
    """One row per (horizon, state) where Polymarket, Kalshi AND a poll average all exist."""
    m = con.execute("SELECT * FROM market_at_horizon").df().pivot_table(index=["days_before","state_po"], columns="source", values="p_rep").reset_index()
    p = con.execute("SELECT * FROM poll_avg").df(); p["state_po"] = p.state.map(ABBR); p = p.dropna(subset=["state_po"])
    o = con.execute("SELECT * FROM outcomes").df()
    d = m.merge(p[["days_before","state_po","n_pollsters","poll_margin_2p"]], on=["days_before","state_po"]).merge(o, on="state_po")
    d = d.dropna(subset=["polymarket","kalshi","poll_margin_2p"])
    d["polls"] = poll_prob(d.poll_margin_2p, sigma)
    return d

def score(d):
    rows = []
    for h, g in d.groupby("days_before"):
        for src in ["polymarket", "kalshi", "polls"]:
            rows.append(dict(days_before=h, source=src, states=len(g), brier=brier(g[src], g.rep_won),
                             log_loss=log_loss(g[src], g.rep_won), correct=int(((g[src] > .5) == g.rep_won).sum())))
    return pd.DataFrame(rows)
