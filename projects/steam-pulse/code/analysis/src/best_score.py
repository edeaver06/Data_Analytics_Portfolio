"""Transparent composite 'best game' score + validation. Components needing time series get weight 0 until data exists."""
import json, numpy as np, pandas as pd
from scipy import stats
import steam_analysis as sa

WEIGHTS = {"review_bayes": 0.45, "player_strength": 0.35, "value_per_dollar": 0.20, "retention": 0.0, "momentum": 0.0}
PRIOR_N = 1000  # pseudo-reviews at the global mean
SOFTWARE_GENRES = {"Utilities", "Software", "Design & Illustration", "Animation & Modeling", "Audio Production",
                   "Video Production", "Photo Editing", "Web Publishing", "Game Development", "Education"}
# 'Casual' deliberately omitted: Steam tags Wallpaper Engine Casual + Utilities, so including it would let it through.
GAME_GENRES = {"Action", "Adventure", "RPG", "Strategy", "Simulation", "Sports", "Racing"}
EXCL_CSV = sa.ROOT.parent / "dbt" / "seeds" / "software_exclusions.csv"  # single copy, shared with dbt

def is_software(genres, appid, curated):
    if appid in curated: return True
    if not isinstance(genres, (list, tuple, np.ndarray)): return False
    g = set(genres); return bool(g & SOFTWARE_GENRES) and not (g & GAME_GENRES)

def filter_software(df, include_software=False):
    curated = set(pd.read_csv(EXCL_CSV).appid)
    flag = np.array([is_software(g, a, curated) for g, a in zip(df.genres, df.appid)], bool)
    return (df if include_software else df[~flag]), df[flag]

def bayes_review(pos, neg, prior_n=PRIOR_N, mu=None):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    mu = pos.sum() / (pos + neg).sum() if mu is None else mu
    return (pos + prior_n * mu) / (pos + neg + prior_n)

def pct(s): return s.rank(pct=True)

def score(df, w=WEIGHTS, prior_n=PRIOR_N):
    d = df.copy()
    d["review_bayes"] = bayes_review(d.positive, d.negative, prior_n)
    d["player_strength"] = np.log1p(d.player_count)
    # value: quality-weighted engagement per dollar; free games get price floor $1 (documented)
    d["value_per_dollar"] = d.review_bayes * np.log1p(d.player_count) / np.maximum(d.price_usd.fillna(0), 1.0)
    comps = [k for k, v in w.items() if v > 0]
    d["score"] = sum(w[k] * pct(d[k]) for k in comps) / sum(w[k] for k in comps)
    return d.sort_values("score", ascending=False)

def price_tier(p):
    return pd.cut(p.fillna(0), [-0.01, 0, 10, 30, 1e9], labels=["free", "<$10", "$10-30", "$30+"]).astype(str)

def validate(df, n=200, seed=0):
    rng = np.random.default_rng(seed); base = score(df); top = set(base.appid[:20]); r0 = base.set_index("appid").score
    wsens, boot = [], []
    keys = ["review_bayes", "player_strength", "value_per_dollar"]
    for _ in range(n):
        w = dict(zip(keys, rng.dirichlet([4.5, 3.5, 2.0])))
        s = score(df, w).set_index("appid").score
        wsens.append((stats.spearmanr(r0, s.loc[r0.index])[0], len(top & set(s.nlargest(20).index)) / 20))
        b = df.sample(len(df), replace=True, random_state=int(rng.integers(1e9))).drop_duplicates("appid")
        tot = (b.positive + b.negative).clip(lower=0)
        b = b.assign(positive=rng.binomial(tot.astype(int), (b.positive / tot.replace(0, 1)).clip(0, 1)))
        b = b.assign(negative=tot - b.positive)
        sb = score(b); boot.append(len(top & set(sb.appid[:20])) / len(top & set(b.appid)) if top & set(b.appid) else np.nan)
    ws = np.array(wsens)
    alt = {"raw_pos_share": stats.spearmanr(base.score, base.positive / (base.positive + base.negative).replace(0, np.nan), nan_policy="omit")[0],
           "ccu_only": stats.spearmanr(base.score, base.player_count)[0],
           "review_count": stats.spearmanr(base.score, base.positive + base.negative)[0]}
    prior = {pn: stats.spearmanr(r0, score(df, prior_n=pn).set_index("appid").score.loc[r0.index])[0] for pn in (100, 5000)}
    return {"weight_perturb_spearman_median": float(np.median(ws[:, 0])), "weight_perturb_spearman_p5": float(np.percentile(ws[:, 0], 5)),
            "weight_perturb_top20_overlap_median": float(np.median(ws[:, 1])),
            "bootstrap_top20_retained_median": float(np.nanmedian(boot)), "alt_ranking_spearman": alt, "prior_n_spearman": prior,
            "rank_stability_over_time": "see history_results.json rank_stability"}

def categories(c, g):
    cats = c.sql("select appid, categories from a_store_cats").df()
    gen = c.sql("select appid, genres from a_store").df()
    s = score(g)
    s["tier"] = price_tier(s.price_usd)
    out = {"by_price_tier": s.groupby("tier").agg(n=("appid", "size"), med_score=("score", "median"), med_ccu=("player_count", "median")).reset_index().to_dict("records")}
    best = {f"tier:{t}": grp.head(3)[["name", "score"]].round(3).to_dict("records") for t, grp in s.groupby("tier")}
    long = []
    for frame, col, pre in [(cats, "categories", "cat:"), (gen, "genres", "genre:")]:
        for _, r in frame.dropna().iterrows():
            for v in r[col]: long.append((r.appid, pre + v))
    L = pd.DataFrame(long, columns=["appid", "cat"]).merge(s, on="appid")
    sub = s[s.appid.isin(L.appid)]
    agg = L.groupby("cat").agg(n=("appid", "nunique"), med_score=("score", "median"), ccu_per_game=("player_count", "median")).reset_index()
    agg = agg[agg.n >= 5]
    agg["score_lift_vs_detailed_median"] = agg.med_score - sub.score.median()
    agg["supply_share"] = agg.n / sub.appid.nunique()
    agg["engagement_index"] = agg.ccu_per_game / sub.player_count.median()
    agg["gap_index"] = agg.engagement_index / agg.supply_share  # high = engaged but under-supplied (within top-sample only)
    for k in ["cat:Shared/Split Screen Co-op", "cat:Online Co-op", "cat:Full controller support", "genre:RPG", "genre:Strategy"]:
        sel = L[L.cat == k].sort_values("score", ascending=False)
        if len(sel): best[k] = sel.head(3)[["name", "score"]].round(3).to_dict("records")
    out["categories"] = agg.sort_values("gap_index", ascending=False).round(3).to_dict("records")
    out["best_by_category"] = best
    out["n_with_category_flags"] = int(sub.appid.nunique())
    return out

def main(include_software=False):
    c = sa.connect()
    g, sw = filter_software(c.sql("select * from a_game where player_count is not null and positive+negative>0").df(), include_software)
    s = score(g)
    res = {"include_software": include_software, "excluded_software": sw[["appid", "name"]].to_dict("records"), "weights": WEIGHTS, "prior_n": PRIOR_N, "n": len(g), "top15": s.head(15)[["name", "score", "review_bayes", "player_count", "price_usd"]].round(3).to_dict("records"),
           "validation": validate(g), **categories(c, g)}
    (sa.ROOT / "best_score_results.json").write_text(json.dumps(res, indent=1, default=str))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    a = pd.DataFrame(res["categories"]); fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(a.supply_share, a.engagement_index)
    for _, r in a.iterrows(): ax.annotate(r["cat"].split(":")[1][:22], (r.supply_share, r.engagement_index), fontsize=6)
    ax.set_xlabel("share of detailed games in category (supply)"); ax.set_ylabel("median CCU / overall median (engagement)")
    ax.set_title("Demand vs supply by category (148 top games excl. software, 1 snapshot)"); fig.tight_layout(); fig.savefig(sa.ROOT / "figures" / "category_gap.png", dpi=120)
    return res

if __name__ == "__main__":
    import sys; r = main("--include-software" in sys.argv); print(json.dumps({k: r[k] for k in ["top15", "validation", "by_price_tier", "n_with_category_flags"]}, indent=1, default=str))
    for x in r["categories"][:8] + r["categories"][-4:]: print(x)
    print(json.dumps(r["best_by_category"], indent=0))
