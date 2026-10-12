"""Steam Pulse analysis layer. Read-only over ../data/steam_pulse.duckdb."""
from __future__ import annotations
import json, pathlib
import duckdb, numpy as np, pandas as pd
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT.parent / "data" / "steam_pulse.duckdb"

def connect(db=DB):
    c = duckdb.connect()
    c.execute(f"attach '{db}' as sp (read_only)")
    c.execute((ROOT / "sql" / "00_views.sql").read_text())
    return c

def q(c, name):
    return c.sql((ROOT / "sql" / f"{name}.sql").read_text()).df()

# ---- readiness gates: refuse to run time-series analyses without the data ----
def readiness(cov: dict) -> dict:
    days, recent = cov["n_days"], cov["released_last_30d"]
    return {
        "launch_decay": days >= 30 and recent >= 10,
        "price_event_study": days >= 28,
        "sentiment_lead_lag": days >= 28,
        "model_30d": days >= 60 and recent >= 30,
        "cross_sectional": cov["games_with_players"] > 0,
    }

# ---- methods (ready for panel data; unit-tested on synthetic fixtures) ----
def retention_curve(panel: pd.DataFrame) -> pd.DataFrame:
    """panel: appid, day_since_launch, players. Returns median players indexed to day 0..7 peak."""
    base = panel[panel.day_since_launch <= 7].groupby("appid").players.max().rename("base")
    p = panel.join(base, on="appid")
    p["idx"] = p.players / p.base
    return p.groupby("day_since_launch").idx.median().reset_index()

def event_study_did(panel: pd.DataFrame, window=7) -> pd.DataFrame:
    """panel: appid, d, players, treated(bool game), event_d (sale start for treated; matched pseudo-date for controls).
    Returns per relative day: mean log-ratio vs pre-period (treated - control)."""
    p = panel.copy()
    p["rel"] = (pd.to_datetime(p.d) - pd.to_datetime(p.event_d)).dt.days
    p = p[p.rel.between(-window, window)]
    pre = p[p.rel < 0].groupby("appid").players.mean().rename("pre")
    p = p.join(pre, on="appid")
    p["lr"] = np.log1p(p.players) - np.log1p(p.pre)
    g = p.groupby(["rel", "treated"]).lr.mean().unstack()
    return (g[True] - g[False]).rename("did").reset_index()

def lead_lag(x: pd.Series, y: pd.Series, max_lag=7) -> pd.DataFrame:
    """corr(x_t, y_{t+k}); positive k = x leads y."""
    return pd.DataFrame({"lag": range(-max_lag, max_lag + 1),
        "corr": [x.corr(y.shift(-k)) for k in range(-max_lag, max_lag + 1)]})

def time_backtest(df: pd.DataFrame, feats, target="log_p30", date="release_date", n_folds=3):
    """Expanding-window backtest by release date. Compares OLS vs naive baselines (MAE in log space)."""
    df = df.sort_values(date).reset_index(drop=True)
    cuts = np.linspace(0.4, 1.0, n_folds + 1)
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        tr, te = df.iloc[: int(a * len(df))], df.iloc[int(a * len(df)): int(b * len(df))]
        X = np.c_[np.ones(len(tr)), tr[feats]]; beta = np.linalg.lstsq(X, tr[target], rcond=None)[0]
        pred = np.c_[np.ones(len(te)), te[feats]] @ beta
        out.append({"fold_end": str(te[date].max()), "n_test": len(te),
            "mae_model": float(np.abs(pred - te[target]).mean()),
            "mae_train_median": float(np.abs(tr[target].median() - te[target]).mean()),
            "mae_day1_carry": float(np.abs(te["log_p1"] - te[target]).mean()) if "log_p1" in te else np.nan})
    return pd.DataFrame(out)

def main():
    c = connect()
    cov = q(c, "10_coverage").iloc[0].to_dict()
    res = {"coverage": cov, "readiness": readiness(cov)}
    g = c.sql("select * from a_game where player_count is not null").df()
    f2p = q(c, "20_f2p_vs_paid"); disc = q(c, "30_discount_xsec"); gen = q(c, "40_genre"); age = q(c, "50_age_xsec")
    x = g.dropna(subset=["pos_share"]); x = x[(x.positive + x.negative) >= 100]
    rho, p = stats.spearmanr(x.pos_share, x.player_count)
    paid = g[~g.f2p_steamspy]
    mw = stats.mannwhitneyu(paid[paid.discount_pct > 0].player_count, paid[paid.discount_pct == 0].player_count)
    ff = stats.mannwhitneyu(g[g.f2p_steamspy].player_count, g[~g.f2p_steamspy].player_count)
    res.update(f2p=f2p.to_dict("records"), f2p_mwu_p=float(ff.pvalue), discount=disc.to_dict("records"),
               discount_mwu_p=float(mw.pvalue), genre=gen.to_dict("records"), age=age.to_dict("records"),
               sentiment_spearman={"rho": float(rho), "p": float(p), "n": int(len(x))},
               top10_share_of_ccu=float(g.player_count.nlargest(10).sum() / g.player_count.sum()),
               total_ccu=int(g.player_count.sum()))
    figs(g, gen, age, x)
    (ROOT / "results.json").write_text(json.dumps(res, indent=2, default=str))
    return res

def figs(g, gen, age, x):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    F = ROOT / "figures"
    fig, ax = plt.subplots(); [ax.hist(np.log10(g[g.f2p_steamspy == k].player_count + 1), bins=30, alpha=.6, label=l) for k, l in [(True, "free"), (False, "paid")]]
    ax.set_xlabel("log10(concurrent players + 1)"); ax.legend(); ax.set_title("F2P vs paid, single snapshot"); fig.savefig(F / "f2p_vs_paid.png", dpi=120); plt.close(fig)
    fig, ax = plt.subplots(); ax.scatter(x.pos_share, np.log10(x.player_count + 1), s=6); ax.set_xlabel("SteamSpy positive review share"); ax.set_ylabel("log10 CCU"); ax.set_title("Sentiment vs players (cross-section)"); fig.savefig(F / "sentiment_vs_ccu.png", dpi=120); plt.close(fig)
    fig, ax = plt.subplots(); ax.barh(gen.genre, gen.med_ccu); ax.set_xlabel("median CCU (games with store details)"); fig.tight_layout(); fig.savefig(F / "genre_median_ccu.png", dpi=120); plt.close(fig)
    fig, ax = plt.subplots(); ax.plot(age.bucket_years, age.med_ccu, "o-"); ax.set_yscale("log"); ax.set_xlabel("years since release"); ax.set_ylabel("median CCU"); ax.set_title("Age vs players (survivors only, NOT a decay curve)"); fig.savefig(F / "age_xsec.png", dpi=120); plt.close(fig)

if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
