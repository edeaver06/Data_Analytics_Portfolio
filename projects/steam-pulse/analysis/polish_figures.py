"""Polished versions of the Steam Pulse analysis figures -> analysis/figures/polished/ (originals untouched).
Numbers come from results.json / best_score_results.json; per-game distributions (f2p hist, sentiment scatter)
are re-read read-only from data/steam_pulse.duckdb with the same filters as src/steam_analysis.py and
cross-checked against results.json (mismatches are printed, never "fixed").
Usage: ../.venv/bin/python polish_figures.py   (from analysis/)"""
import json, sys, pathlib
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

A = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(A / "src"))
OUT = A / "figures" / "polished"; OUT.mkdir(parents=True, exist_ok=True)
R = json.loads((A / "results.json").read_text()); B = json.loads((A / "best_score_results.json").read_text())

BLUE, ORANGE, GREEN, GREY, VERM, SKY = "#0072B2", "#E69F00", "#009E73", "#8C8C8C", "#D55E00", "#56B4E9"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
                     "figure.dpi": 150, "axes.grid": True, "grid.alpha": .25, "figure.facecolor": "white", "axes.facecolor": "white"})
snap = R["coverage"]["last_snapshot"]
SRC = f"Source: Steam Web API concurrent players (single snapshot {snap}), SteamSpy reviews & prices, Steam store details. Steam Pulse / Evan Deaver."
def note(fig, extra=""): fig.text(0.01, 0.01, (extra + "\n" if extra else "") + SRC, fontsize=7, color=GREY, ha="left", va="bottom")
def sub(ax, t): ax.text(0, 1.02, t, transform=ax.transAxes, fontsize=9, color="#444")
def fmt(n): return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.1f}K" if n >= 1e3 else f"{n:.0f}"
MISMATCH = []
def check(label, got, want, tol=1e-6):
    if abs(float(got) - float(want)) > tol * max(1, abs(float(want))): MISMATCH.append(f"{label}: data={got} vs results.json={want}")

# ---------- per-game data (read-only, same filters as steam_analysis.main) ----------
g = x = None
try:
    import steam_analysis as sa
    c = sa.connect(); g = c.sql("select * from a_game where player_count is not null").df()
    x = g.dropna(subset=["pos_share"]); x = x[(x.positive + x.negative) >= 100]
    f2p = {r["segment"]: r for r in R["f2p"]}
    for seg, m in [("free", g.f2p_steamspy), ("paid", ~g.f2p_steamspy)]:
        check(f"f2p {seg} n", m.sum(), f2p[seg]["n"]); check(f"f2p {seg} med_ccu", g[m].player_count.median(), f2p[seg]["med_ccu"])
    from scipy import stats
    rho = stats.spearmanr(x.pos_share, x.player_count)[0]
    check("sentiment n", len(x), R["sentiment_spearman"]["n"]); check("sentiment rho", rho, R["sentiment_spearman"]["rho"], 1e-4)
except Exception as e:
    MISMATCH.append(f"could not load per-game data from duckdb ({e}); f2p/sentiment drawn from summary only")

# ---------- 1. category_gap (lead) ----------
cat = pd.DataFrame(B["categories"]); ndet = B["n_with_category_flags"]
cat["kind"] = cat.cat.str.split(":").str[0]; cat["label"] = cat.cat.str.split(":", n=1).str[1]
fig, ax = plt.subplots(figsize=(11, 6.8))
xs = np.linspace(0.02, 0.9, 200)
for gi, ls in [(10, ":"), (30, "--")]: ax.plot(xs, gi * xs, color=GREY, lw=.9, ls=ls); ax.text(3.25/gi, 3.25, f"gap index = {gi} ", fontsize=7, color=GREY, ha="right", va="top", rotation=0)
ax.axhline(1, color=GREY, lw=.8); ax.text(0.9, 1.02, "overall median engagement", fontsize=7, color=GREY, ha="right", va="bottom")
col = cat.kind.map({"cat": BLUE, "genre": ORANGE})
ax.scatter(cat.supply_share, cat.engagement_index, s=18 + cat.n * 2.2, c=col, alpha=.7, edgecolor="white", lw=.6)
top = cat.nlargest(8, "gap_index"); low = cat.nsmallest(3, "gap_index")
POS = {"Steam Input API Support": (.17, 3.12), "HDR available": (.17, 2.78), "Early Access": (.14, 2.45), "LAN Co-op": (.14, 2.33),
       "LAN PvP": (.14, 1.97), "Tracked Controller Support": (.14, 1.62), "VR Supported": (.14, 1.50), "Gamepad Recommended": (.14, 1.38),
       "Family Sharing": (.62, .62), "Action": (.62, .50), "Free To Play": (.31, .12)}
for _, r in pd.concat([top, low]).iterrows():
    tx, ty = POS.get(r.label, (r.supply_share + .02, r.engagement_index + .1))
    ax.annotate(f"{r.label}  (gap {r.gap_index:.0f}, n={r.n})", (r.supply_share, r.engagement_index), xytext=(tx, ty), fontsize=7.5,
                color="#222", va="center", arrowprops=dict(arrowstyle="-", color=GREY, lw=.5, shrinkA=0, shrinkB=3))
ax.set_xlabel(f"Supply: share of the {ndet} store-detail games in the category"); ax.set_ylabel("Engagement: median CCU / overall median")
ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}"); ax.set_ylim(0, 3.3)
ax.set_title("Controller, LAN and Early Access games draw ~2-3x typical players\nfrom a small slice of supply", pad=22)
sub(ax, f"Category demand vs supply, {len(cat)} categories/genres with n>=5; labels show gap index (engagement / supply) and game count")
ax.legend(handles=[Patch(color=BLUE, label="Steam category"), Patch(color=ORANGE, label="Genre"),
                   Line2D([], [], marker="o", ls="", color=GREY, label="bubble size = games")], frameon=False, loc="upper right")
fig.tight_layout(rect=(0, .06, 1, 1))
note(fig, "Gap index is relative within the top-player store-detail sample only; small categories (n=5) are noisy. Not a market-wide demand estimate.")
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
fig.suptitle(f"The typical paid game has {f['paid']['med_ccu']/f['free']['med_ccu']:.1f}x the players of a free-to-play game ({f['paid']['med_ccu']:,.0f} vs {f['free']['med_ccu']:,.0f})",
             x=.01, ha="left", fontweight="bold", fontsize=13)
fig.text(.01, .9, f"Top-1,000 Steam games by players, one snapshot; Mann-Whitney p = {R['f2p_mwu_p']:.1e}", fontsize=9, color="#444")
fig.tight_layout(rect=(0, .06, 1, .89)); note(fig, "Free-to-play = SteamSpy flag. Per-game medians; a few F2P giants dominate total players (see hero chart).")
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
ax.legend(handles=[Patch(color=BLUE, label="n >= 15"), Patch(color=GREY, label="n < 15 (noisy)"), Patch(color=VERM, label="Highest median (Early Access, n=9)")], frameon=False, loc="lower right")
fig.tight_layout(rect=(0, .05, 1, 1)); note(fig); fig.savefig(OUT / "genre_median_ccu.png"); plt.close(fig)

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
ax.set_title("Age vs players (survivors only, NOT a decay curve):\nolder games still in the top 1,000 keep thousands of players", pad=22, fontsize=12)
sub(ax, f"Median CCU by whole years since release, {age.n.sum()} games with store details, one snapshot; dead games are absent by construction")
fig.tight_layout(rect=(0, .06, 1, 1)); note(fig, "Survivorship bias: only games still popular today are sampled. Real launch decay needs daily per-game snapshots.")
fig.savefig(OUT / "age_xsec.png"); plt.close(fig)

# ---------- cross-checks on summary numbers ----------
if B["n_with_category_flags"] != R["coverage"]["games_with_store_details"]:
    MISMATCH.append(f"best_score n_with_category_flags={B['n_with_category_flags']} vs results.json games_with_store_details={R['coverage']['games_with_store_details']} (original category_gap title says 148)")
print("wrote:", *sorted(p.name for p in OUT.glob("*.png")))
print("MISMATCHES:" if MISMATCH else "no mismatches", *MISMATCH, sep="\n  ")
