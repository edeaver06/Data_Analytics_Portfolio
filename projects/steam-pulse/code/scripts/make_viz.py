"""Regenerate Steam Pulse extra static figures (code/figures/viz/, git-ignored) and Tableau CSV exports (app/tableau/, git-ignored; archived outside the repo).
Usage: .venv/bin/python scripts/make_viz.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import os
# Render from the committed parquet extract (app/data), never the live DB.
os.environ["STEAM_PULSE_DB"] = str(ROOT / "data" / "__render_from_extract__.duckdb")
sys.path.insert(0, str(ROOT / "app"))
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from marts import load, enrich, add_score

BLUE, ORANGE, GREEN, GREY, VERM = "#0072B2", "#E69F00", "#009E73", "#8C8C8C", "#D55E00"
OUT = ROOT / "figures" / "viz"; OUT.mkdir(parents=True, exist_ok=True)
TAB = ROOT / "app" / "tableau"; TAB.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
                     "figure.dpi": 150, "axes.grid": True, "grid.alpha": .25})

dim, fct, snaps, src_label = load(); g = add_score(enrich(dim, fct))
snap = pd.to_datetime(snaps.snapshot_ts.iloc[-1]).strftime("%Y-%m-%d %H:%M UTC")
SRC = "Source: Steam Web API, SteamSpy; analysis by Evan Deaver"
def note(fig, extra=""):
    fig.text(0.01, 0.01, (extra + "\n" if extra else "") + SRC, fontsize=7, color=GREY, ha="left", va="bottom")
def fmt(n): return f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.0f}K" if n >= 1e3 else f"{n:.0f}"

# ---------- hero: top 15 games by concurrent players, coloured by pricing ----------
top = g.nlargest(15, "last_players").iloc[::-1]
total = g.last_players.sum(); top3 = g.nlargest(3, "last_players").last_players.sum()
fig, ax = plt.subplots(figsize=(10, 6.2))
sw_ids = set(add_score(enrich(dim, fct)).query("is_software").appid)
cols = [GREY if a in sw_ids else ORANGE if p == "Free-to-play" else BLUE for a, p in zip(top.appid, top.pricing)]
ax.barh(top.game_name, top.last_players, color=cols)
for y, v in enumerate(top.last_players): ax.text(v, y, " " + fmt(v), va="center", fontsize=8)
t3 = g.nlargest(3, "last_players"); n_f2p3 = int((t3.pricing == "Free-to-play").sum())
lead3 = "Three free-to-play games" if n_f2p3 == 3 else f"The top 3 games ({n_f2p3} free-to-play)"
ax.set_title(f"{lead3} hold {top3/total:.0%} of all tracked players", pad=22)
ax.text(0, 1.02, f"Concurrent players, {fmt(total)} total across {int(g.last_players.notna().sum()):,} games",
        transform=ax.transAxes, fontsize=9, color="#444")
ax.xaxis.set_major_formatter(lambda v, _: fmt(v)); ax.grid(axis="y", visible=False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=ORANGE, label="Free-to-play"), Patch(color=BLUE, label="Paid"), Patch(color=GREY, label="Software (excluded from game score)")], loc="lower right", frameon=False)
fig.tight_layout(rect=(0, .05, 1, 1)); note(fig); fig.savefig(OUT / "hero.png"); plt.close(fig)

# ---------- launch decay: real curves from the analysis layer's history (analysis/history_results.json) ----------
import json
H = json.loads((ROOT / "analysis" / "history_results.json").read_text())
# cross-sectional frame kept for the Tableau CSV only
d = g.dropna(subset=["years_since_release", "players_per_1k_owners"]); d = d[d.players_per_1k_owners > 0]
d = d.assign(age_bucket=pd.cut(d.years_since_release, [0, 1, 2, 5, 10, 30], labels=["<1 yr", "1-2", "2-5", "5-10", "10+"]))
ret = pd.concat([pd.DataFrame(H["retention"][k]).assign(segment=k) for k in ["all", "free", "paid"]])
RA = ret[ret.segment == "all"].set_index("m"); RF = ret[ret.segment == "free"].set_index("m"); RP = ret[ret.segment == "paid"].set_index("m")
CHECKS = []
def check(label, got, want, tol):
    if abs(float(got) - float(want)) > tol: CHECKS.append(f"MISMATCH {label}: data={got} expected={want}")
check("retention n", H["retention_n"], 600, 0); check("retention m1", RA.loc[1, "median"], .56, .005); check("retention m6", RA.loc[6, "median"], .25, .005)
fig, ax = plt.subplots(figsize=(10, 5.8))
for seg, lab, cl, lw in [("all", f"All games (n={H['retention_n']})", GREY, 3), ("free", f"Free-to-play (n={RF.loc[0,'count']})", ORANGE, 2.2), ("paid", f"Paid (n={RP.loc[0,'count']})", BLUE, 2.2)]:
    r = ret[ret.segment == seg]; ax.plot(r.m, r["median"], marker="o", color=cl, lw=lw, label=lab)
for m_ in [1, 6, 24]:
    ax.annotate(f"{RA.loc[m_,'median']:.3f}", (m_, RA.loc[m_, "median"]), textcoords="offset points", xytext=(14, 8), ha="left", fontsize=9, color="#333", fontweight="bold")
ax.annotate(f"F2P {RF.loc[6,'median']:.3f} vs paid {RP.loc[6,'median']:.3f} at month 6", (6, RF.loc[6, "median"]), textcoords="offset points", xytext=(30, 25), fontsize=8.5, color=ORANGE, arrowprops=dict(arrowstyle="-", color=GREY, lw=.6))
ax.set_xticks(RA.index); ax.set_ylim(0, 1.05); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
ax.set_xlabel("Months since launch"); ax.set_ylabel("Median share of launch-month peak players")
ax.set_title(f"Games keep {RA.loc[1,'median']:.0%} of launch-month players after one month,\n{RA.loc[6,'median']:.0%} by month 6 and {RA.loc[24,'median']:.0%} by month 24", pad=22)
ax.text(0, 1.02, "Monthly average players / launch-month peak; " + ("free-to-play holds better than paid" if RF.loc[6, "median"] > RP.loc[6, "median"] else "paid holds as well as or better than free-to-play"), transform=ax.transAxes, fontsize=9, color="#444")
ax.legend(frameon=False)
fig.tight_layout(rect=(0, .07, 1, 1))
note(fig, f"History: analysis/history_results.json, SteamCharts monthly players for {H['retention_n']} of today's tracked games with an observed launch (survivors only).")
fig.savefig(OUT / "launch_decay.png"); plt.close(fig)

# ---------- f2p vs paid ----------
k = g[g.pricing.isin(["Free-to-play", "Paid"])]
s = k.groupby("pricing").agg(games=("appid", "size"), players=("last_players", "sum"),
      median_players=("last_players", "median"), median_review=("positive_review_share", "median"),
      median_p1k=("players_per_1k_owners", "median")).reindex(["Free-to-play", "Paid"])
s["player_share"] = s.players / s.players.sum(); s["game_share"] = s.games / s.games.sum()
fig, axs = plt.subplots(1, 4, figsize=(12, 4.6))
panels = [("game_share", "Share of games", lambda v: f"{v:.0%}"), ("player_share", "Share of players", lambda v: f"{v:.0%}"),
          ("median_players", "Median concurrent players", lambda v: f"{v:,.0f}"), ("median_review", "Median positive reviews", lambda v: f"{v:.0%}")]
for ax, (c, t, f) in zip(axs, panels):
    ax.bar(s.index, s[c], color=[ORANGE, BLUE]); ax.set_title(t, fontsize=10, loc="center")
    for i, v in enumerate(s[c]): ax.text(i, v, f(v), ha="center", va="bottom", fontsize=9)
    ax.set_yticks([]); ax.grid(False); ax.spines["left"].set_visible(False)
Rj = json.loads((ROOT / "analysis" / "results.json").read_text())
fj = {r["segment"]: r for r in Rj["f2p"]}; pv = Rj["f2p_mwu_p"]
check("f2p free median (vs results.json)", s.loc["Free-to-play", "median_players"], fj["free"]["med_ccu"], 0)
check("f2p paid median (vs results.json)", s.loc["Paid", "median_players"], fj["paid"]["med_ccu"], 0)
if pv >= 0.05:
    t = (f"No clear difference in typical players between free-to-play and paid\n(median {fj['free']['med_ccu']:,.0f} vs "
         f"{fj['paid']['med_ccu']:,.0f}, p = {pv:.2f})" + ("; paid games review better" if fj["paid"]["med_pos_share"] > fj["free"]["med_pos_share"] else ""))
else:
    hi, lo = ("free", "paid") if fj["free"]["med_ccu"] > fj["paid"]["med_ccu"] else ("paid", "free")
    t = f"The typical {hi} game has more players than the typical {lo} game (p = {pv:.1e})"
fig.suptitle(t, x=.01, ha="left", fontweight="bold", fontsize=12)
fig.tight_layout(rect=(0, .06, 1, .88)); note(fig, "Free-to-play = Steam store is_free. Medians are per game; p from Mann-Whitney in analysis/results.json.")
fig.savefig(OUT / "f2p_vs_paid.png"); plt.close(fig)

# ---------- sales impact: discount event study (DiD) from analysis/history_results.json ----------
D = H["discount_did"]
check("did events", D["n_events"], 10756, 0); check("did pct", D["did_pct"], 39.4, .05); check("did ci low", D["ci95_pct"][0], 37.6, .05); check("did ci high", D["ci95_pct"][1], 41.3, .05)
dep = pd.DataFrame([{"depth": k, **v} for k, v in D["by_depth"].items()])
paid = g[(g.pricing == "Paid") & g.players_per_1k_owners.notna() & g.discount_pct.notna()].copy()  # today's cross-section, CSV only
paid["discount_band"] = pd.cut(paid.discount_pct.fillna(0), [-1, 0, 25, 50, 75, 100], labels=["Full price", "1-25%", "26-50%", "51-75%", "76-100%"])
fig, ax = plt.subplots(figsize=(10, 5.6))
ax.bar(dep.depth, dep.pct, color=GREEN)
for i, r in dep.iterrows(): ax.text(i, r.pct, f"+{r.pct:.0f}%\n(n={r.n:,})", ha="center", va="bottom", fontsize=9)
ax.axhline(D["did_pct"], color=VERM, ls="--", lw=1.4)
ax.text(-.45, D["did_pct"] + .8, f"all sales +{D['did_pct']:.0f}% (95% CI {D['ci95_pct'][0]:.1f}-{D['ci95_pct'][1]:.1f}%)", color=VERM, fontsize=8.5, ha="left", va="bottom")
ax.set_ylabel("Players in first week of sale vs. controls"); ax.yaxis.set_major_formatter(lambda v, _: f"+{v:.0f}%"); ax.set_xlabel("Discount depth")
ax.set_ylim(0, dep.pct.max() * 1.25); ax.grid(axis="x", visible=False)
ax.set_title(f"The first week of a sale goes with +{D['did_pct']:.0f}% players, and deeper discounts with bigger lifts", pad=22)
ax.text(0, 1.02, f"Association, not causation: difference-in-differences over {D['n_events']:,} sale starts in {D['n_games']:,} games, 2019-20 data", transform=ax.transAxes, fontsize=9, color="#444")
fig.tight_layout(rect=(0, .1, 1, 1))
note(fig, f"History: analysis/history_results.json; Mendeley CC BY 4.0 2019-20 price/player panel, not today's tracked games.\nPre-trend days -7..-1: {D['pretrend_days_-7_-1_pct']:+.1f}%. Sale timing is chosen by publishers, so read as association.")
fig.savefig(OUT / "sales_impact.png"); plt.close(fig)

# ---------- Tableau CSVs (one per view) ----------
keep = ["appid", "game_name", "developer", "publisher", "primary_genre", "release_date", "years_since_release", "pricing",
        "price_usd", "initial_price_usd", "discount_pct", "on_sale", "owners_estimate_range", "owners_estimate_low",
        "owners_estimate_high", "owners_mid", "positive", "negative", "positive_review_share", "metacritic_score",
        "last_players", "deck_status", "n_tags", "has_local_coop", "has_split_screen", "full_controller_support", "players_per_1k_owners", "has_store_details"]
g[keep].rename(columns={"last_players": "concurrent_players"}).to_csv(TAB / "games.csv", index=False)
top.iloc[::-1][["appid", "game_name", "pricing", "last_players"]].rename(columns={"last_players": "concurrent_players"}).to_csv(TAB / "hero_top15.csv", index=False)
ret.rename(columns={"m": "months_since_launch", "median": "median_share_of_launch_peak", "count": "games"}).to_csv(TAB / "launch_decay.csv", index=False)
d[["appid", "game_name", "pricing", "release_date", "years_since_release", "age_bucket", "last_players", "owners_mid", "players_per_1k_owners"]].to_csv(TAB / "age_xsec_today.csv", index=False)
s.reset_index().to_csv(TAB / "f2p_vs_paid.csv", index=False)
paid[["appid", "game_name", "discount_pct", "discount_band", "price_usd", "initial_price_usd", "last_players", "owners_mid", "players_per_1k_owners"]].to_csv(TAB / "discount_today.csv", index=False)
dep.assign(all_sales_pct=D["did_pct"], ci_low=D["ci95_pct"][0], ci_high=D["ci95_pct"][1], n_events=D["n_events"], data_years="2019-20").to_csv(TAB / "sales_impact.csv", index=False)
fct.merge(dim[["appid", "game_name"]], on="appid").to_csv(TAB / "daily_players.csv", index=False)

print("data:", src_label); print("total players", total, "top3 share", round(top3 / total, 4))
print(s.round(4).to_string()); print("\n".join(CHECKS) or "no mismatches")

# ---------- Game Finder / leaderboard CSVs ----------
from marts import load_bridge
b = load_bridge()
b.merge(g[["appid", "game_name"]], on="appid").to_csv(TAB / "game_labels.csv", index=False)  # bridge: appid x genre/category

# composite score per game from marts.mart_game_scores (port of the analysis layer's best_score.py)
g[["appid", "game_name", "app_type", "is_software", "score_price_usd", "positive", "negative", "last_players", "score", "score_rank", "excluded_reason",
   "review_bayes", "player_strength", "value_per_dollar", "review_bayes_part", "player_strength_part", "value_per_dollar_part"]
  ].dropna(subset=["score"]).sort_values("score", ascending=False).to_csv(TAB / "game_scores.csv", index=False)
