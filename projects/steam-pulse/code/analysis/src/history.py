"""Gated time-series analyses on backfilled history. Results -> history_results.json."""
import json, pathlib, numpy as np, pandas as pd
from scipy import stats
import steam_analysis as sa, best_score as bs
T = sa.ROOT / "data" / "backfill" / "tables"; F = sa.ROOT / "figures"
SC_START = pd.Timestamp("2012-07-01")  # SteamCharts collection start

def load():
    sc = pd.read_parquet(T / "steamcharts_monthly.parquet"); sc["month"] = pd.to_datetime(sc.month)
    rv = pd.read_parquet(T / "reviews_monthly.parquet"); rv["month"] = pd.to_datetime(rv.month)
    c = sa.connect(); g = c.sql("select * from a_game").df()
    _, sw = bs.filter_software(g.dropna(subset=["appid"]))
    g = g[~g.appid.isin(sw.appid)]
    return sc[sc.appid.isin(g.appid)], rv[rv.appid.isin(g.appid)], g

def launch_panel(sc, rv, today=pd.Timestamp("2026-10-01")):
    """Launch month = first SteamCharts month, only when it is after collection start AND reviews start same/next month."""
    first = sc.groupby("appid").month.min().rename("launch")
    first_rv = rv[(rv.up + rv.down) > 0].groupby("appid").month.min().rename("rv_first")
    L = pd.concat([first, first_rv], axis=1).dropna()
    L = L[(L.launch > SC_START + pd.DateOffset(months=1)) & ((L.launch - L.rv_first).dt.days.abs() <= 62)]
    p = sc.merge(L.reset_index(), on="appid")
    p["m"] = (p.month.dt.year - p.launch.dt.year) * 12 + (p.month.dt.month - p.launch.dt.month)
    p = p[p.month < today]  # drop current partial month
    return p, L

def retention(p, g, max_m=24):
    base = p[p.m <= 1].groupby("appid").avg_players.max().rename("base")
    q = p.join(base, on="appid"); q = q[q.base >= 50]; q["idx"] = q.avg_players / q.base
    q = q.merge(g[["appid", "f2p_steamspy", "primary_genre"]], on="appid", how="left")
    def curve(d): 
        c = d[d.m <= max_m].groupby("m").idx.agg(["median", "count"]).reset_index(); return c
    out = {"all": curve(q)}
    out["free"] = curve(q[q.f2p_steamspy == True]); out["paid"] = curve(q[q.f2p_steamspy == False])
    q["cohort"] = np.where(q.launch >= "2020-01-01", "2020+", "2012-2019")
    for k in ["2012-2019", "2020+"]: out[k] = curve(q[q.cohort == k])
    return q, out

def stacked_did(price, players, pre=14, post=14, min_disc=10):
    """Sale start = first day discount>=min_disc after >=pre days at 0. Controls: paid games with no discount in the window, same calendar window."""
    price = price.sort_values(["appid", "date"]).copy(); price["date"] = pd.to_datetime(price.date)
    players = players.copy(); players["date"] = pd.to_datetime(players.date)
    price["on"] = price.discount >= min_disc
    events = []
    for a, d in price.groupby("appid"):
        on = d.on.values; dates = d.date.values
        for i in range(pre, len(d) - post):
            if on[i] and not on[i - pre:i].any(): events.append((a, dates[i]))
    ev = pd.DataFrame(events, columns=["appid", "event_d"])
    disc_days = price[price.on].groupby("appid").date.apply(set).to_dict()
    paid = set(price.appid)
    rows = []
    pl = players.set_index(["appid", "date"]).avg_players
    rng = np.random.default_rng(0)
    for k, (a, e) in enumerate(ev.itertuples(index=False)):
        win = pd.date_range(e - pd.Timedelta(days=pre), e + pd.Timedelta(days=post))
        ctrl = [c for c in rng.permutation(list(paid - {a}))[:60] if not (disc_days.get(c, set()) & set(win))][:5]
        for unit, tr in [(a, True)] + [(c, False) for c in ctrl]:
            try: s = pl.loc[unit].reindex(win)
            except KeyError: continue
            if s.isna().mean() > 0.2: continue
            rows.append(pd.DataFrame({"stack": k, "appid": unit, "treated": tr, "rel": range(-pre, post + 1), "players": s.values}))
    P = pd.concat(rows, ignore_index=True).dropna()
    P["l"] = np.log1p(P.players)
    base = P[P.rel < 0].groupby(["stack", "appid"]).l.mean().rename("base")
    P = P.join(base, on=["stack", "appid"]); P["lr"] = P.l - P.base
    es = P.groupby(["rel", "treated"]).lr.mean().unstack(); es["did"] = es[True] - es[False]
    post_eff = P[P.rel.between(0, 7)].groupby(["stack", "treated"]).lr.mean().unstack().dropna()
    d = post_eff[True] - post_eff[False]
    gid = ev.appid.reindex(d.index).values; games = np.unique(gid); by = {g_: d.values[gid == g_] for g_ in games}
    rng2 = np.random.default_rng(1)
    boot = [np.concatenate([by[x] for x in rng2.choice(games, len(games))]).mean() for _ in range(500)]  # cluster bootstrap by game
    depth = price.set_index(["appid", "date"]).discount
    dep = np.array([depth.get((a, e), np.nan) for a, e in ev.reindex(d.index).itertuples(index=False)])
    bins = pd.cut(dep, [9, 33, 50, 75, 100], labels=["10-33%", "34-50%", "51-75%", "76%+"])
    by_depth = {}
    for k in bins.categories:  # empty depth bins report n=0 and pct=None instead of a NaN mean (RuntimeWarning)
        sel = d.values[bins == k]
        by_depth[str(k)] = {"n": int(sel.size), "pct": float(np.expm1(sel.mean()) * 100) if sel.size else None}
    pre_eff = P[P.rel.between(-7, -1)].groupby(["stack", "treated"]).lr.mean().unstack().dropna(); pd_ = pre_eff[True] - pre_eff[False]
    return es.reset_index(), {"n_events": int(len(d)), "n_games": int(ev.appid.nunique()), "did_days0_7_log": float(d.mean()),
        "did_pct": float(np.expm1(d.mean()) * 100), "ci95_pct": [float(np.expm1(np.percentile(boot, 2.5)) * 100), float(np.expm1(np.percentile(boot, 97.5)) * 100)],
        "pretrend_days_-7_-1_pct": float(np.expm1(pd_.mean()) * 100), "by_depth": by_depth}

def lead_lag_panel(sc, rv, max_lag=3):
    """Within-game monthly changes: corr(Δpositive_share_t, Δlog players_{t+k}). Pooled with game de-meaning."""
    m = sc.merge(rv, on=["appid", "month"]); m = m[(m.up + m.down) >= 30].sort_values(["appid", "month"])
    m["pos"] = m.up / (m.up + m.down); m["lp"] = np.log1p(m.avg_players); m["lrev"] = np.log1p(m.up + m.down)
    out = {}
    for x in ["pos", "lrev"]:
        res = []
        for k in range(-max_lag, max_lag + 1):
            d = m.copy(); d["dx"] = d.groupby("appid")[x].diff(); d["dy"] = d.groupby("appid").lp.diff().groupby(d.appid).shift(-k)
            d = d.dropna(subset=["dx", "dy"]); r, pval = stats.pearsonr(d.dx, d.dy); res.append({"lag": k, "corr": float(r), "p": float(pval), "n": len(d)})
        out[x] = res
    return out, int(m.appid.nunique()), int(len(m))

def model_30d(p, L, g):
    """Target: log avg players in month 1 (≈days 30-60). Launch-time features only: price, f2p, launch month-of-year, dev prior hit."""
    t = p[p.m == 1][["appid", "avg_players"]].rename(columns={"avg_players": "p30"})
    df = L.reset_index().merge(t, on="appid").merge(g[["appid", "price_usd", "f2p_steamspy", "name"]], on="appid")
    own = sa.connect().sql("select appid, developer from a_owners").df(); df = df.merge(own, on="appid", how="left")
    df = df.sort_values("launch").reset_index(drop=True)
    df["dev_prior_hit"] = [int(((df.developer == r.developer) & (df.launch < r.launch)).any()) if isinstance(r.developer, str) else 0 for r in df.itertuples()]
    df["log_p30"] = np.log1p(df.p30); df["log_price"] = np.log1p(df.price_usd.fillna(0)); df["f2p"] = df.f2p_steamspy.astype(float)
    df["q4"] = (df.launch.dt.month >= 10).astype(float); df["post2020"] = (df.launch.dt.year >= 2020).astype(float)
    df = df.rename(columns={"launch": "release_date"})
    feats = ["log_price", "f2p", "dev_prior_hit", "q4", "post2020"]
    m0 = p[p.m == 0][["appid", "peak_players"]].rename(columns={"peak_players": "p0peak"})
    df = df.merge(m0, on="appid", how="left"); df["log_p1"] = np.log1p(df.p0peak)  # launch-MONTH peak: post-launch info, used only in variant B / naive carry
    bt = sa.time_backtest(df, feats, n_folds=4)
    btB = sa.time_backtest(df.dropna(subset=["log_p1"]), feats + ["log_p1"], n_folds=4)
    df.attrs["btB"] = btB
    # extra baseline: same-year median
    return df, bt, feats

def rank_stability(sc, rv, g, years=(2022, 2023, 2024, 2025)):
    """Score at end of each year using cumulative reviews to date and that December's avg players (price = current, documented)."""
    ranks = {}
    for y in years:
        cut = pd.Timestamp(f"{y}-12-01")
        r = rv[rv.month <= cut].groupby("appid")[["up", "down"]].sum().rename(columns={"up": "positive", "down": "negative"})
        pl = sc[sc.month == cut].set_index("appid").avg_players.rename("player_count")
        d = r.join(pl, how="inner").reset_index().merge(g[["appid", "price_usd"]], on="appid")
        d = d[(d.positive + d.negative) > 0]
        ranks[y] = bs.score(d).set_index("appid").score
    out = []
    for a, b in zip(years[:-1], years[1:]):
        common = ranks[a].index.intersection(ranks[b].index)
        out.append({"from": a, "to": b, "n": len(common), "spearman": float(stats.spearmanr(ranks[a][common], ranks[b][common])[0]),
                    "top20_overlap": len(set(ranks[a][common].nlargest(20).index) & set(ranks[b][common].nlargest(20).index)) / 20})
    return out

def main():
    sc, rv, g = load(); res = {}
    res["coverage"] = {"steamcharts_apps": int(sc.appid.nunique()), "steamcharts_months": [str(sc.month.min().date()), str(sc.month.max().date())],
        "apps_with_24m_plus": int((sc.groupby("appid").size() >= 24).sum()), "apps_with_12m_plus": int((sc.groupby("appid").size() >= 12).sum()),
        "review_apps": int(rv.appid.nunique()), "review_months": [str(rv.month.min().date()), str(rv.month.max().date())]}
    p, L = launch_panel(sc, rv); q, curves = retention(p, g)
    res["launch_n"] = int(L.shape[0]); res["retention_n"] = int(q.appid.nunique())
    res["retention"] = {k: v[v.m.isin([0, 1, 2, 3, 6, 12, 24])].round(3).to_dict("records") for k, v in curves.items()}
    res["lead_lag"], res["lead_lag_apps"], res["lead_lag_rows"] = lead_lag_panel(sc, rv)
    df, bt, feats = model_30d(p, L, g); res["model"] = {"n": len(df), "features": feats, "backtest": bt.round(3).to_dict("records"),
        "mean_mae": {k: float(bt[k].mean()) for k in ["mae_model", "mae_train_median"]},
        "variant_B_with_launch_month_peak": {"backtest": df.attrs["btB"].round(3).to_dict("records"), "mean_mae": {k: float(df.attrs["btB"][k].mean()) for k in ["mae_model", "mae_train_median", "mae_day1_carry"]}},
        "launch_years": df.release_date.dt.year.value_counts().sort_index().to_dict()}
    res["rank_stability"] = rank_stability(sc, rv, g)
    if (T / "mendeley_price_daily.parquet").exists() and (T / "mendeley_players_daily.parquet").exists():
        es, res["discount_did"] = stacked_did(pd.read_parquet(T / "mendeley_price_daily.parquet"), pd.read_parquet(T / "mendeley_players_daily.parquet"))
        es.to_csv(sa.ROOT / "data" / "backfill" / "tables" / "event_study.csv", index=False)
    else: res["discount_did"] = "NOT RUN: Mendeley price/player files missing"
    figs(curves, res, locals().get("es"))
    (sa.ROOT / "history_results.json").write_text(json.dumps(res, indent=1, default=str)); return res

def figs(curves, res, es):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    for k in ["all", "free", "paid", "2012-2019", "2020+"]:
        c = curves[k]; ax.plot(c.m, c["median"], label=f"{k}")
    ax.set_yscale("log"); ax.set_xlabel("months since launch"); ax.set_ylabel("avg players / launch peak month (median)"); ax.legend(); ax.set_title("Retention (today's top-1000 survivors)")
    fig.savefig(F / "retention_curves.png", dpi=120); plt.close(fig)
    if es is not None:
        fig, ax = plt.subplots(); ax.plot(es.rel, np.expm1(es.did) * 100, "o-"); ax.axvline(-0.5, ls="--", c="gray"); ax.axhline(0, c="k", lw=.5)
        ax.set_xlabel("days from sale start"); ax.set_ylabel("treated - control (% vs pre)"); ax.set_title("Discount event study (Mendeley 2019-20)"); fig.savefig(F / "discount_event_study.png", dpi=120); plt.close(fig)
    fig, ax = plt.subplots()
    for x, l in [("pos", "Δ positive share"), ("lrev", "Δ log review volume")]:
        d = pd.DataFrame(res["lead_lag"][x]); ax.plot(d.lag, d["corr"], "o-", label=l)
    ax.axhline(0, c="k", lw=.5); ax.set_xlabel("lag k (x leads players by k months)"); ax.set_ylabel("corr with Δ log players"); ax.legend(); fig.savefig(F / "sentiment_lead_lag.png", dpi=120); plt.close(fig)

if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
