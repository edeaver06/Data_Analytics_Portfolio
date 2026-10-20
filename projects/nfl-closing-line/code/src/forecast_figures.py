"""Render figures 03 and 04 as forecast-accuracy charts (no betting/profit framing).
Inputs: data/clean/strategy_tests.csv and data/clean/findings.json only.
Usage: python forecast_figures.py OUT_DIR [OUT_DIR ...]   (default: ../images relative to code/)
"""
import sys, json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
C = ROOT / "data/clean"
F = json.load(open(C / "findings.json"))
s = pd.read_csv(C / "strategy_tests.csv")
REF = 110 / 210  # 52.38%: accuracy needed to break even against standard -110 pricing

# Okabe-Ito palette
BLUE, ORANGE, GREEN, VERM, SKY, PURPLE, GREY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#8C8C8C"
plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#444", "axes.grid": True,
    "grid.color": "#e6e6e6", "grid.linewidth": .8, "axes.axisbelow": True, "font.size": 10.5})
S0, S1 = F["seasons"]
SRC = f"Source: nflverse games data, {S0}-{S1} seasons ({F['games']:,} games with closing lines); analysis by Evan Deaver"

def label(x):  # neutral strategy names
    x = x.removeprefix("Bet ").replace(" ATS", " vs spread")
    return x[0].upper() + x[1:]
s["name"] = s.strategy.map(label)
is_wind = lambda r: "wind" in r.strategy
s = s.sort_values("win_rate").reset_index(drop=True)
outs = [Path(p) for p in sys.argv[1:]] or [ROOT.parent / "images"]

def finish(fig, title, sub, name):
    fig.suptitle(title, x=0.01, ha="left", fontsize=14.5, fontweight="bold", y=1.04)
    fig.text(0.01, 0.955, sub, ha="left", va="bottom", fontsize=10.5, color="#444")
    fig.text(0.01, -0.10, SRC, ha="left", va="top", fontsize=8, color=GREY)
    for d in outs:
        d.mkdir(parents=True, exist_ok=True); fig.savefig(d / name, dpi=200, bbox_inches="tight"); print("wrote", d / name)
    plt.close(fig)

# 03: forecast hit rate per strategy vs 50% (coin flip), 95% Wilson CI, Holm-corrected significance
fig, ax = plt.subplots(figsize=(10, 6))
for i, r in s.iterrows():
    c = BLUE if is_wind(r) else GREY
    ax.plot([r.ci_low, r.ci_high], [i, i], color=c, lw=2.2, alpha=.7); ax.plot(r.win_rate, i, "o", color=c, ms=8)
    ax.text(r.ci_high + .004, i, f"{r.win_rate:.1%}  (n={int(r.bets):,} games)", va="center", fontsize=8.8)
ax.set_yticks(range(len(s))); ax.set_yticklabels(s.name); ax.grid(axis="y", visible=False)
ax.axvline(.5, color="#333", lw=1); ax.text(.502, len(s) - .4, "50% = coin flip", color="#333", fontsize=9)
ax.set_xticks(np.arange(.44, .661, .02)); ax.set(xlim=(.44, .66), xlabel="Forecast hit rate (bars/lines = 95% range)")
ax.xaxis.set_major_formatter("{x:.0%}")
w = s[s.strategy.str.contains("wind")].iloc[0]
ax.text(0, -0.11, f"Blue = only strategy that differs from 50% after accounting for 10 tests (p = {w.p_vs_50_holm:.4f}).\n"
        "n = decided games (pushes excluded).", transform=ax.transAxes, ha="left", va="top", fontsize=8.8, bbox=dict(fc="white", ec="#ccc"))
finish(fig, f"The closing line is hard to beat: only windy-game unders ({w.win_rate:.1%}) beat a coin flip",
       f"{len(s)} rule-based strategies tested against closing lines; wind 15+ mph unders hit {w.win_rate:.1%}", "03_forecast_hit_rate.png")

# 04: hit rate per strategy vs the 52.38% reference
fig, ax = plt.subplots(figsize=(10, 6))
y = np.arange(len(s))
cols = [BLUE if is_wind(r) else GREY for r in s.itertuples()]
ax.barh(y, s.win_rate, color=cols, height=.6, alpha=.9)
ax.errorbar(s.win_rate, y, xerr=[s.win_rate - s.ci_low, s.ci_high - s.win_rate], fmt="none", ecolor="#333", elinewidth=1.2, capsize=3)
for i, r in s.iterrows():
    ax.text(r.ci_high + .004, i, f"{r.win_rate:.1%}  (n={int(r.bets):,} games)", va="center", fontsize=8.8)
ax.axvline(REF, color=VERM, ls="--", lw=1.6)
ax.text(REF + .002, len(s) - .35, "52.38% accuracy needed to cover\nthe sportsbook's margin", color=VERM, fontsize=8.8, va="bottom")
ax.set_yticks(y); ax.set_yticklabels(s.name); ax.grid(axis="y", visible=False)
ax.set_xticks(np.arange(.44, .661, .02)); ax.set(xlim=(.44, .66), ylim=(-.6, len(s) + .5), xlabel="Forecast hit rate (bars/lines = 95% range)")
ax.xaxis.set_major_formatter("{x:.0%}")
n_above = int((s.win_rate >= REF).sum())
ax.text(0, -0.11, f"Wind 15+ unders: 95% CI {w.ci_low:.1%}-{w.ci_high:.1%} sits above 52.38% before correction,\n"
        f"but it is not statistically reliable once {len(s)} tests are accounted for (p = {w.p_beats_vig_holm:.2f}).\n"
        "n = decided games (pushes excluded).", transform=ax.transAxes, ha="left", va="top", fontsize=8.8, bbox=dict(fc="white", ec="#ccc"))
finish(fig, "No strategy clearly clears the 52.38% accuracy bar",
       f"{n_above} of {len(s)} strategies have a point estimate above 52.38%, but none is significant after correction", "04_forecast_accuracy_vs_breakeven.png")
