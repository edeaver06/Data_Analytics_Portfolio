"""Regenerate portfolio-ready charts (README/STORY charts -> ../images/, others -> figures/; drafts in data/clean/draft_charts/).
Run: .venv/bin/python src/polish_figures.py"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd
from clv import connect, pnl_curve, BREAKEVEN

C = ROOT / "data/clean"
# Charts shown in README/STORY live in the project-root images/; the rest go to code/figures/.
MAIN = {"03_strategy_win_rates.png", "02_cover_rate_by_spread.png", "04_backtest_pnl.png", "01_moneyline_calibration.png"}
def fig_path(name):
    d = (ROOT.parent / "images") if name in MAIN else (ROOT / "figures")
    d.mkdir(parents=True, exist_ok=True)
    return d / name
F = json.load(open(C / "findings.json"))
cal = pd.read_csv(C / "ml_calibration.csv"); buckets = pd.read_csv(C / "spread_buckets.csv")
summ = pd.read_csv(C / "strategy_tests.csv")
# Okabe-Ito colorblind-safe palette
BLUE, ORANGE, GREEN, VERM, SKY, PURPLE, GREY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#8C8C8C"
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#444", "axes.grid": True,
    "grid.color": "#e6e6e6", "grid.linewidth": .8, "axes.axisbelow": True, "font.size": 10.5})
S0, S1 = F["seasons"]
SRC = f"Source: nflverse games data, {S0}-{S1} seasons ({F['games']:,} games with closing lines). Breakeven at -110 = 52.38%."

def finish(fig, title, sub, name):
    fig.suptitle(title, x=0.01, ha="left", fontsize=14.5, fontweight="bold", y=1.04)
    fig.text(0.01, 0.955, sub, ha="left", va="bottom", fontsize=10.5, color="#444")
    fig.text(0.01, -0.02, SRC, ha="left", va="top", fontsize=8, color=GREY)
    out = fig_path(name); fig.savefig(out, dpi=200, bbox_inches="tight"); plt.close(fig); print("wrote", out)

def be_line(ax, vertical=False):
    kw = dict(color=VERM, ls="--", lw=1.4)
    (ax.axvline if vertical else ax.axhline)(BREAKEVEN, **kw)

# 01 calibration
fig, ax = plt.subplots(figsize=(7, 6.4))
ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1, label="Perfect calibration")
ax.scatter(cal.pred, cal.actual, s=cal.n / 3, color=BLUE, alpha=.85, edgecolor="white", label="Games per bin (bubble size)")
for _, r in cal.iterrows():
    if r.n >= 100: ax.annotate(f"{r.actual:.0%}", (r.pred, r.actual), xytext=(8, -12), textcoords="offset points", fontsize=8.5, color="#333")
ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Vig-free implied probability of home win", ylabel="Actual home win rate")
ax.xaxis.set_major_formatter("{x:.0%}"); ax.yaxis.set_major_formatter("{x:.0%}"); ax.legend(loc="upper left", frameon=False, fontsize=9)
ax.text(.97, .05, f"Brier score {F['brier']:.3f}\n(coin flip = 0.250)\n{F['ml_games']:,} games", transform=ax.transAxes, ha="right", fontsize=9.5,
        bbox=dict(fc="white", ec="#ccc"))
finish(fig, "Closing moneylines are well calibrated", "Implied win probabilities track actual outcomes closely across every probability bin", "01_moneyline_calibration.png")

# 02 cover rate by spread bucket
b = buckets.copy(); b["label"] = b.bucket.str[3:].str.replace("home ", "Home ").str.replace("pick'em", "Pick'em").str.replace(r" (?=[\d])", "\n", regex=True)
fig, ax = plt.subplots(figsize=(9.5, 5))
cols = [ORANGE if "dog" in x else (GREY if "pick" in x else BLUE) for x in b.bucket]
bars = ax.bar(b.label, b.home_cover_rate, color=cols, width=.65)
for bar, r in zip(bars, b.itertuples()):
    ax.text(bar.get_x() + bar.get_width() / 2, r.home_cover_rate + .006, f"{r.home_cover_rate:.1%}\nn={r.games:,}", ha="center", fontsize=8.5)
ax.axhline(.5, color="#333", lw=1); be_line(ax)
ax.text(len(b) - .5, BREAKEVEN + .004, "52.38% breakeven", color=VERM, ha="right", fontsize=9)
ax.set_yticks(np.arange(.40, .621, .02)); ax.set(ylim=(.40, .62), ylabel="Home team cover rate (ATS)"); ax.yaxis.set_major_formatter("{x:.0%}")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=ORANGE, label="Home underdog"), Patch(color=BLUE, label="Home favorite")], frameon=False, loc="upper right", fontsize=9)
finish(fig, "Home teams cover close to 50% in most spread buckets",
       "Most buckets sit below the 52.38% breakeven; the 7+ point home-dog bucket is one subgroup, not a tested edge", "02_cover_rate_by_spread.png")

# 03 strategy win rates
s = summ.sort_values("win_rate").reset_index(drop=True)
fig, ax = plt.subplots(figsize=(10, 6))
for i, r in s.iterrows():
    c = GREEN if r.sig_bias_holm else (BLUE if r.win_rate >= .5 else GREY)
    ax.plot([r.ci_low, r.ci_high], [i, i], color=c, lw=2.2, alpha=.7); ax.plot(r.win_rate, i, "o", color=c, ms=8)
    ax.text(r.ci_high + .004, i, f"{r.win_rate:.1%}  (n={int(r.bets):,})", va="center", fontsize=8.8)
ax.set_yticks(range(len(s))); ax.set_yticklabels(s.strategy); ax.grid(axis="y", visible=False)
ax.axvline(.5, color="#333", lw=1); be_line(ax, True)
ax.text(BREAKEVEN + .002, len(s) - .4, "52.38% breakeven", color=VERM, fontsize=9)
ax.set_xticks(np.arange(.44, .661, .02)); ax.set(xlim=(.44, .66), xlabel="Win rate with 95% Wilson confidence interval"); ax.xaxis.set_major_formatter("{x:.0%}")
w = s[s.strategy.str.contains("wind")].iloc[0]
ax.text(.995, .03, f"Green = differs from 50% after Holm correction.\nWind 15+ unders: 57.0%, but beating the vig is not\nsignificant after correction (Holm p = {w.p_beats_vig_holm:.2f}).",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8.8, bbox=dict(fc="white", ec="#ccc"))
finish(fig, "Only high-wind unders stand out, and that's not proven profitable",
       "Home dogs (50.5%) and primetime overs (48.7%) fall short of the 52.38% breakeven; 10 strategies tested", "03_strategy_win_rates.png")

# 04 backtest P&L
con = connect()
fig, ax = plt.subplots(figsize=(10, 5))
for st, lab, c, dy in [("Bet home underdogs ATS", "Home underdogs ATS", ORANGE, 9), ("Bet primetime overs", "Primetime overs", PURPLE, -9),
                      ("Bet all overs", "All overs", SKY, 0), ("Bet favorites ATS", "Favorites ATS", BLUE, 0)]:
    cv = pnl_curve(con, st); ax.plot(cv.index, cv.values, color=c, lw=2)
    ax.annotate(f"{lab}: {cv.values[-1]:+.0f}u", (cv.index[-1], cv.values[-1]),
                xytext=(6, dy), textcoords="offset points", va="center", fontsize=9, color=c, fontweight="bold")
ax.axhline(0, color="#333", lw=1)
ax.set(xlabel="Season", ylabel="Cumulative units (1 unit per bet at -110)"); ax.set_xlim(right=S1 + 8); ax.set_xticks(range(2000, S1 + 1, 5))
finish(fig, "Naive betting strategies lose money to the vig over time",
       "Cumulative profit/loss betting 1 unit per game at -110; every curve finishes below zero", "04_backtest_pnl.png")

# 05 spread error histogram
g = con.execute("SELECT * FROM games").df()
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.hist(g.ats_margin, bins=range(-50, 51, 2), color=BLUE, edgecolor="white")
m = F["efficiency"]["result"]
ax.axvline(0, color="#333", lw=1); ax.axvline(m["mean_err"], color=ORANGE, lw=2, ls="--")
ax.text(m["mean_err"] - 1.5, ax.get_ylim()[1] * .92,  f"Mean error {m['mean_err']:+.2f} pts", color=ORANGE, fontsize=9.5, fontweight="bold", ha="right")
ax.text(.98, .95, f"Slope of result on spread: {m['slope']:.2f}\n95% CI [{m['slope_ci'][0]:.2f}, {m['slope_ci'][1]:.2f}] includes 1.0\nMean absolute error {m['mae']:.1f} pts",
        transform=ax.transAxes, ha="right", va="top", fontsize=9, bbox=dict(fc="white", ec="#ccc"))
ax.set(xlabel="Actual home margin minus closing spread (points)", ylabel="Games"); ax.grid(axis="x", visible=False)
finish(fig, "Closing spreads are unbiased: errors center on zero",
       "Individual games miss by ~10 points on average, but the misses don't lean toward either side", "05_spread_error_hist.png")
