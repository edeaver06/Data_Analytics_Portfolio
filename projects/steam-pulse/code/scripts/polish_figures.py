"""Polished versions of the Steam Pulse analysis figures -> analysis/figures/polished/ (the drafts written by analysis/src are git-ignored).
Numbers come from results.json / best_score_results.json / history_results.json; per-game distributions (f2p hist,
sentiment scatter) are re-read from the committed parquet extract in app/data/ with the same filters as src/steam_analysis.py and
cross-checked against results.json (mismatches are printed, never "fixed").
Usage: python scripts/polish_figures.py   (from projects/steam-pulse/)"""
import json, sys, pathlib
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

A = pathlib.Path(__file__).resolve().parents[1] / "analysis"
sys.path.insert(0, str(A / "src"))
OUT = A / "figures" / "polished"; OUT.mkdir(parents=True, exist_ok=True)
R = json.loads((A / "results.json").read_text()); B = json.loads((A / "best_score_results.json").read_text())

BLUE, ORANGE, GREEN, GREY, VERM, SKY = "#0072B2", "#E69F00", "#009E73", "#8C8C8C", "#D55E00", "#56B4E9"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
                     "figure.dpi": 150, "axes.grid": True, "grid.alpha": .25, "figure.facecolor": "white", "axes.facecolor": "white"})
snap = R["coverage"]["last_snapshot"]
SRC = "Source: Steam Web API, SteamSpy; analysis by Evan Deaver"
def note(fig, extra=""): fig.text(0.01, 0.01, (extra + "\n" if extra else "") + SRC, fontsize=7, color=GREY, ha="left", va="bottom")
def sub(ax, t): ax.text(0, 1.02, t, transform=ax.transAxes, fontsize=9, color="#444")
def fmt(n): return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.1f}K" if n >= 1e3 else f"{n:.0f}"
MISMATCH = []
def check(label, got, want, tol=1e-6):
    if abs(float(got) - float(want)) > tol * max(1, abs(float(want))): MISMATCH.append(f"{label}: data={got} vs results.json={want}")

# ---------- per-game data: committed parquet extract (app/data), not the live DB ----------
g = x = None
try:
    P = A.parent / "app" / "data"
    dim = pd.read_parquet(P / "dim_game.parquet"); si = pd.read_parquet(P / "score_inputs.parquet")
    fct = pd.read_parquet(P / "fct_daily_players.parquet")
    lp = fct.sort_values("snapshot_date_utc").groupby("appid").tail(1)[["appid", "last_players"]]
    g = dim.merge(si, on="appid", how="left").merge(lp, on="appid", how="left").rename(columns={"last_players": "player_count"})
    g = g[g.player_count.notna()].copy()
    g["f2p_steamspy"] = g.is_free.astype("boolean").fillna(g.price_usd.eq(0)).astype(bool)  # same rule as sql/00_views.sql a_game
    g["pos_share"] = (g.positive / (g.positive + g.negative)).where((g.positive + g.negative) > 0)
    x = g.dropna(subset=["pos_share"]); x = x[(x.positive + x.negative) >= 100]
    f2p = {r["segment"]: r for r in R["f2p"]}
    for seg, m in [("free", g.f2p_steamspy), ("paid", ~g.f2p_steamspy)]:
        check(f"f2p {seg} n", m.sum(), f2p[seg]["n"]); check(f"f2p {seg} med_ccu", g[m].player_count.median(), f2p[seg]["med_ccu"])
    from scipy import stats
    rho = stats.spearmanr(x.pos_share, x.player_count)[0]
    check("sentiment n", len(x), R["sentiment_spearman"]["n"]); check("sentiment rho", rho, R["sentiment_spearman"]["rho"], 1e-4)
except Exception as e:
    MISMATCH.append(f"could not load per-game data from the parquet extract ({e}); f2p/sentiment drawn from summary only")

# ---------- 1. category_gap (lead) ----------
cat = pd.DataFrame(B["categories"]); ndet = B["n_with_category_flags"]
cat["kind"] = cat.cat.str.split(":").str[0]; cat["label"] = cat.cat.str.split(":", n=1).str[1]
C = cat.set_index("label"); E, S, N = C.engagement_index, C.supply_share, C.n
# Lead categories as named in analysis/README.md ("clearest gaps"); every number below is read from the JSON.
LEAD = [l for l in ["Steam Input API Support", "Save Anytime"] if l in C.index]
NICE = {"Steam Input API Support": "Steam Input API", "Shared/Split Screen Co-op": "Split-screen co-op"}
SS, EA = "Shared/Split Screen Co-op", "Early Access"
check("category_gap n", ndet, B["n"] - 1)  # store-detail games with CCU, software excluded
check("Steam Input API engagement", round(E["Steam Input API Support"], 1), 9.7); check("Steam Input API n", N["Steam Input API Support"], 31)
check("Save Anytime engagement", round(E["Save Anytime"], 1), 5.9); check("split-screen co-op engagement", round(E[SS], 2), 1.05)
is_gap = lambda l: l in C.index and E[l] >= 2 and S[l] <= 0.10 and N[l] >= 10
fig, ax = plt.subplots(figsize=(11, 6.8))
big = cat[cat.n >= 10]; small = cat[cat.n < 10]
ax.scatter(small.supply_share, small.engagement_index, s=14, facecolor="white", edgecolor=GREY, lw=.7)
ax.scatter(big.supply_share, big.engagement_index, s=18 + big.n * .35, c=big.kind.map({"cat": BLUE, "genre": ORANGE}), alpha=.7, edgecolor="white", lw=.6)
ax.axhline(1, color=GREY, lw=.8); ax.text(.99, 1.03, "overall median players", fontsize=7, color=GREY, ha="right", va="bottom", transform=ax.get_yaxis_transform())
for l in LEAD:
    ax.scatter([S[l]], [E[l]], s=220, facecolor="none", edgecolor=VERM, lw=2.2, zorder=5)
    ax.annotate(f"{NICE.get(l, l)}: {E[l]:.1f}x players, {S[l]:.0%} of games (n={N[l]})", (S[l], E[l]), textcoords="offset points",
                xytext=(14, 6), fontsize=8.5, color=VERM, fontweight="bold")
others = [SS, EA, "Adjustable Text Size", "Online Co-op", "RPG", "Free To Play"]
for l in others:
    if l in C.index and N[l] >= 10:
        extra = "  (no longer a gap)" if l == SS and not is_gap(SS) else ""
        ax.annotate(f"{NICE.get(l, l)} ({E[l]:.1f}x, n={N[l]}){extra}", (S[l], E[l]), textcoords="offset points", xytext=(8, -12 if l in (EA, SS) else 4), fontsize=7.5, color="#222")
ax.set_yscale("log"); ax.yaxis.set_major_formatter(lambda v, _: f"{v:g}x")
ax.set_xlabel(f"Supply: share of the {ndet:,} store-detail games in the category"); ax.set_ylabel("Players: median CCU / overall median (log)")
ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
title = " and ".join(f"{NICE.get(l, l)} ({E[l]:.1f}x)" for l in LEAD) + " are the clearest gaps:\nfew games, many more players than the typical game"
ax.set_title(title, pad=22)
sub(ax, f"Based on {ndet:,} popular games; correlation only.")
ax.legend(handles=[Patch(color=BLUE, label="Steam category"), Patch(color=ORANGE, label="Genre"),
                   Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=GREY, label="n < 10 (ignore)")], frameon=False, loc="lower right")
fig.tight_layout(rect=(0, .06, 1, 1))
note(fig, (f"Split-screen co-op is {E[SS]:.2f}x with {S[SS]:.0%} of games, so not a gap at full coverage (it was 2.5x at 444 games). " if not is_gap(SS) else "")
          + (f"Early Access is {E[EA]:.1f}x from {S[EA]:.0%} of games. " if EA in C.index else "") + "Software excluded.")
print("category_gap title:", ax.get_title(loc="left").replace("\n", " | "))
print("  top by engagement (n>=20):", ", ".join(f"{l} {E[l]:.1f}x" for l in C[C.n >= 20].engagement_index.nlargest(3).index))
fig.savefig(OUT / "category_gap.png"); plt.close(fig)

# ---------- 2. f2p_vs_paid ----------
f = {r["segment"]: r for r in R["f2p"]}
fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1.6, 1]})
if g is not None:
    bins = np.linspace(0, np.log10(g.player_count.max() + 1), 31)
    for k, lab, cl in [(True, "Free-to-play", ORANGE), (False, "Paid", BLUE)]:
        v = np.log10(g[g.f2p_steamspy == k].player_count + 1)
        a1.hist(v, bins=bins, alpha=.6, color=cl, label=f"{lab} (n={len(v)})", density=True)
        m = f["free" if k else "paid"]["med_ccu"]; a1.axvline(np.log10(m + 1), color=cl, lw=2, ls="--")
        a1.text(np.log10(m + 1), a1.get_ylim()[1] * (.92 if k else .82), f" median {m:,.0f}", color=cl, fontsize=8, fontweight="bold")
    a1.set_xticks(range(0, 7)); a1.set_xticklabels(["1", "10", "100", "1K", "10K", "100K", "1M"])
    a1.set_xlabel("Concurrent players (log scale)"); a1.set_ylabel("Share of games (density)"); a1.legend(frameon=False)
a1.set_title("Distribution of concurrent players", fontsize=10)
mets = [("med_ccu", "Median CCU", lambda v: f"{v:,.0f}"), ("med_pos_share", "Median positive\nreview share", lambda v: f"{v:.1%}")]
for j, (k, t, fm) in enumerate(mets):
    for i, (seg, cl) in enumerate([("free", ORANGE), ("paid", BLUE)]):
        val = f[seg][k] / (f["paid"][k]); y = j * 3 + i
        a2.barh(y, val, color=cl); a2.text(val, y, " " + fm(f[seg][k]), va="center", fontsize=9)
a2.set_yticks([0.5, 3.5]); a2.set_yticklabels([m[1] for m in mets]); a2.invert_yaxis(); a2.set_xticks([]); a2.grid(False)
a2.spines["bottom"].set_visible(False); a2.set_xlim(0, 1.35); a2.set_title("Medians (bar length relative to paid)", fontsize=10)
pv = R["f2p_mwu_p"]
if pv >= 0.05:
    ft = f"No clear player difference between free-to-play and paid games (median {f['free']['med_ccu']:,.0f} vs {f['paid']['med_ccu']:,.0f}, p = {pv:.2f})"
else:
    hi, lo = ("free", "paid") if f["free"]["med_ccu"] > f["paid"]["med_ccu"] else ("paid", "free")
    ft = f"The typical {hi} game has {f[hi]['med_ccu']/f[lo]['med_ccu']:.1f}x the players of a {lo} game ({f[hi]['med_ccu']:,.0f} vs {f[lo]['med_ccu']:,.0f})"
fig.suptitle(ft, x=.01, ha="left", fontweight="bold", fontsize=13)
print("f2p title:", ft)
fig.text(.01, .9, f"{R['coverage']['games_with_players']:,} tracked Steam games, latest snapshot; Mann-Whitney p = {R['f2p_mwu_p']:.2f}", fontsize=9, color="#444")
fig.tight_layout(rect=(0, .06, 1, .89)); note(fig, "Free-to-play = Steam store is_free (SteamSpy price $0 as fallback). Per-game medians; a few F2P giants dominate total players (see hero chart).")
fig.savefig(OUT / "f2p_vs_paid.png"); plt.close(fig)

# ---------- 3. sentiment_vs_ccu ----------
ss = R["sentiment_spearman"]
fig, ax = plt.subplots(figsize=(10, 6))
if x is not None:
    ax.scatter(x.pos_share, x.player_count + 1, s=9, color=BLUE, alpha=.35, edgecolor="none", label="Game")
    xb = pd.cut(x.pos_share, np.arange(0, 1.0001, .1)); med = x.groupby(xb, observed=True).player_count.agg(["median", "size"])
    mids = [iv.mid for iv in med.index]
    ax.plot(mids, med["median"] + 1, color=VERM, marker="o", lw=2.2, label="Median per 10-pt band")
    for m_, (_, r) in zip(mids, med.iterrows()):
        if r["size"] >= 10: ax.annotate(f"{fmt(r['median'])}\n(n={int(r['size'])})", (m_, r["median"] + 1), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=7.5, color=VERM)
ax.set_yscale("log"); ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
ax.set_xlabel("Positive review share (SteamSpy)"); ax.set_ylabel("Concurrent players + 1 (log)"); ax.legend(frameon=False, loc="upper left")
ax.set_title("Better-reviewed games tend to have more players, but only weakly", pad=22)
sub(ax, f"Spearman rho = {ss['rho']:.2f} (p = {ss['p']:.1e}, n = {ss['n']:,} games with >=100 reviews); cross-section, not causal")
fig.tight_layout(rect=(0, .05, 1, 1)); note(fig); fig.savefig(OUT / "sentiment_vs_ccu.png"); plt.close(fig)

# ---------- 4. genre_median_ccu ----------
gen = pd.DataFrame(R["genre"]).sort_values("med_ccu")
fig, ax = plt.subplots(figsize=(10, 6))
cols = [VERM if v == gen.med_ccu.max() else (GREY if n < 15 else BLUE) for v, n in zip(gen.med_ccu, gen.n)]
ax.barh(gen.genre, gen.med_ccu, color=cols)
for y, (v, n) in enumerate(zip(gen.med_ccu, gen.n)): ax.text(v, y, f" {v:,.0f}  (n={n})", va="center", fontsize=8.5)
ax.xaxis.set_major_formatter(lambda v, _: fmt(v)); ax.grid(axis="y", visible=False); ax.set_xlim(0, gen.med_ccu.max() * 1.25)
best = gen[gen.n >= 15].iloc[-1]
ax.set_title(f"{best.genre} has the highest median players among well-sampled genres ({best.med_ccu:,.0f})", pad=22)
sub(ax, f"Median concurrent players by genre, {R['coverage']['games_with_store_details']} games with store details; a game can have several genres")
ax.legend(handles=[Patch(color=BLUE, label="n >= 15"), Patch(color=GREY, label="n < 15 (noisy)"), Patch(color=VERM, label=f"Highest median ({gen.iloc[-1].genre}, n={gen.iloc[-1].n})")], frameon=False, loc="lower right")
fig.tight_layout(rect=(0, .05, 1, 1)); note(fig); fig.savefig(OUT / "genre_median_ccu.png"); plt.close(fig)

if g is not None and "genres_any" in g:
    rpg = g[g.genres_any.apply(lambda v: isinstance(v, (list, np.ndarray)) and "RPG" in list(v))].player_count.median()
    check("RPG median ccu (duckdb)", rpg, gen.set_index("genre").med_ccu["RPG"])
print("RPG median CCU:", gen.set_index("genre").med_ccu["RPG"], "| genre title:", ax.get_title(loc="left"))

gm = gen.set_index("genre").med_ccu
for gname, want in [("Racing", 1096), ("RPG", 711.5), ("Early Access", 685)]: check(f"genre {gname} median", gm[gname], want)

# ---------- 5. age_xsec ----------
age = pd.DataFrame(R["age"])
fig, ax = plt.subplots(figsize=(10, 5.8))
ok = age.n >= 5
ax.plot(age.bucket_years, age.med_ccu, color=GREY, lw=1, zorder=1)
ax.scatter(age.bucket_years[ok], age.med_ccu[ok], s=age.n[ok] * 8, color=BLUE, zorder=2, label="n >= 5")
ax.scatter(age.bucket_years[~ok], age.med_ccu[~ok], s=age.n[~ok] * 8 + 10, facecolor="white", edgecolor=GREY, zorder=2, label="n < 5 (noisy)")
for i, (_, r) in enumerate(age.iterrows()):
    ax.annotate(f"{fmt(r.med_ccu)}\nn={int(r.n)}", (r.bucket_years, r.med_ccu), textcoords="offset points", xytext=(0, 9 if i % 2 else -22), ha="center", fontsize=6.5, color="#333" if r.n >= 5 else GREY)
ax.set_yscale("log"); ax.set_xlabel("Years since release"); ax.set_ylabel("Median concurrent players (log)")
ax.yaxis.set_major_formatter(lambda v, _: fmt(v)); ax.legend(frameon=False, loc="lower left")
ax.set_title("Age vs players (survivors only, NOT a decay curve):\nolder games still among today's popular games keep players", pad=22, fontsize=12)
sub(ax, f"Median CCU by whole years since release, {age.n.sum()} games with store details, one snapshot; dead games are absent by construction")
fig.tight_layout(rect=(0, .06, 1, 1)); note(fig, "Survivorship bias: only games still popular today are sampled. Real launch decay needs daily per-game snapshots.")
fig.savefig(OUT / "age_xsec.png"); plt.close(fig)

# ---------- 6-8. history charts (history_results.json) ----------
Hp = A / "history_results.json"
if Hp.exists():
    H = json.loads(Hp.read_text())
    # 6. retention_curves
    ret = {k: pd.DataFrame(H["retention"][k]).set_index("m") for k in ["all", "free", "paid", "2012-2019", "2020+"]}
    check("retention n", H["retention_n"], 600)
    for m_, want in [(1, .56), (6, .25)]: check(f"retention all m{m_}", round(ret["all"].loc[m_, "median"], 2), want)
    fig, ax = plt.subplots(figsize=(10, 5.8))
    for k, lab, cl, ls, lw in [("all", "All", GREY, "-", 3), ("free", "Free-to-play", ORANGE, "-", 2), ("paid", "Paid", BLUE, "-", 2),
                               ("2020+", "Launched 2020+", VERM, "--", 1.6)]:
        r = ret[k]; ax.plot(r.index, r["median"], marker="o", color=cl, ls=ls, lw=lw, label=f"{lab} (n={int(r['count'].iloc[0])})")
    ax.set_xticks(ret["all"].index); ax.set_ylim(0, 1.05); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Months since launch"); ax.set_ylabel("Median share of launch-month peak players"); ax.legend(frameon=False)
    a6 = ret["all"]["median"]
    ax.set_title(f"Players drop {1 - a6[1]:.0%} after the first month, then level off; free-to-play holds better", pad=22)
    sub(ax, f"Median monthly players / launch-month peak, {H['retention_n']} of today's tracked games with an observed launch (SteamCharts)")
    fig.tight_layout(rect=(0, .06, 1, 1)); note(fig, f"History: SteamCharts monthly players via history_results.json. Survivors only. 2020+ launches are a small group (n={int(ret['2020+']['count'].iloc[0])}).")
    print("retention_curves title:", ax.get_title(loc="left")); fig.savefig(OUT / "retention_curves.png"); plt.close(fig)
    # 7. discount_event_study
    D = H["discount_did"]; dep = pd.DataFrame([{"depth": k, **v} for k, v in D["by_depth"].items()])
    check("did n_events", D["n_events"], 10756); check("did pct", round(D["did_pct"], 1), 39.4)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.bar(dep.depth, dep.pct, color=GREEN)
    for i, r in dep.iterrows(): ax.text(i, r.pct, f"+{r.pct:.0f}%\n(n={r.n:,})", ha="center", va="bottom", fontsize=9)
    ax.axhline(D["did_pct"], color=VERM, ls="--", lw=1.4)
    ax.text(-.45, D["did_pct"] + .8, f"all sales +{D['did_pct']:.1f}% (95% CI {D['ci95_pct'][0]:.1f} to {D['ci95_pct'][1]:.1f}%)", color=VERM, fontsize=8.5)
    ax.set_ylim(0, dep.pct.max() * 1.25); ax.yaxis.set_major_formatter(lambda v, _: f"+{v:.0f}%"); ax.grid(axis="x", visible=False)
    ax.set_xlabel("Discount depth"); ax.set_ylabel("Players, first week of sale vs. controls")
    ax.set_title(f"Sales go with +{D['did_pct']:.0f}% players in their first week; deeper discounts, bigger lifts", pad=22)
    sub(ax, f"Association from 2019-20 data: difference-in-differences, {D['n_events']:,} sale starts in {D['n_games']:,} games; pre-trend {D['pretrend_days_-7_-1_pct']:+.1f}%")
    fig.tight_layout(rect=(0, .07, 1, 1)); note(fig, "History: Mendeley CC BY 4.0 2019-20 panel via history_results.json, not today's tracked games. Publishers choose sale timing; not causal.")
    print("discount_event_study title:", ax.get_title(loc="left")); fig.savefig(OUT / "discount_event_study.png"); plt.close(fig)
    # 8. sentiment_lead_lag
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for k, lab, cl in [("pos", "Change in positive-review share", BLUE), ("lrev", "Change in log review volume", ORANGE)]:
        d = pd.DataFrame(H["lead_lag"][k]); ax.plot(d.lag, d["corr"], marker="o", color=cl, lw=2.2, label=lab)
        if k == "pos": mx = d["corr"].abs().max()
        else: r0 = d.set_index("lag")["corr"][0]
    ax.axhline(0, color=GREY, lw=.8); ax.axhspan(-.05, .05, color=GREY, alpha=.12, lw=0)
    ax.annotate(f"same month r = {r0:.2f}", (0, r0), textcoords="offset points", xytext=(10, -4), fontsize=8.5, color=ORANGE)
    ax.set_xticks(range(-3, 4)); ax.set_xlabel("Lag k in months (positive k: reviews lead players by k months)")
    ax.set_ylabel("Correlation with change in log players")
    ax.set_title("Review sentiment doesn't lead player counts; review volume just moves with players", pad=22)
    sub(ax, f"Within-game monthly changes, {H['lead_lag_apps']} games, {H['lead_lag_rows']:,} game-months; sentiment |r| <= {mx:.2f} at every lag")
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout(rect=(0, .06, 1, 1)); note(fig, "History: SteamCharts monthly players + review history via history_results.json. Shaded band = |r| < 0.05. Correlation only.")
    print("sentiment_lead_lag title:", ax.get_title(loc="left")); fig.savefig(OUT / "sentiment_lead_lag.png"); plt.close(fig)
else:
    MISMATCH.append("history_results.json missing: retention/discount/lead-lag charts skipped")

# ---------- cross-checks on summary numbers ----------
if B["n_with_category_flags"] != R["coverage"]["games_with_store_details"]:
    print(f"note: category_gap uses {B['n_with_category_flags']} games (store-detail games with category flags, software excluded) vs {R['coverage']['games_with_store_details']} with store details")
print("wrote:", *sorted(p.name for p in OUT.glob("*.png")))
print("MISMATCHES:" if MISMATCH else "no mismatches", *MISMATCH, sep="\n  ")
