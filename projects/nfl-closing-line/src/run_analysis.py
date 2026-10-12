"""Run everything: python src/run_analysis.py -> prints findings, writes images/ and data/clean/."""
import sys; sys.path.insert(0, "src")
import json, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from clv import *

con = connect(); g = con.execute("SELECT * FROM games").df()
(ROOT/"data/clean").mkdir(exist_ok=True, parents=True)
eff = efficiency(g)
d, cal, brier = moneyline_calibration(g)
summ = test_strategies(con.execute("SELECT * FROM strategy_summary").df())
wf = walk_forward(con)
buckets = con.execute("SELECT * FROM spread_buckets").df()
summ.to_csv(ROOT/"data/clean/strategy_tests.csv", index=False); wf.to_csv(ROOT/"data/clean/walk_forward.csv")
buckets.to_csv(ROOT/"data/clean/spread_buckets.csv", index=False); cal.to_csv(ROOT/"data/clean/ml_calibration.csv")
res = dict(seasons=[int(g.season.min()), int(g.season.max())], games=len(g), efficiency=eff, brier=brier,
           brier_coinflip=0.25, mean_overround=d.overround.mean(), ml_games=len(d),
           home_cover=float(g.home_cover.mean()), over=float(g.over_hit.mean()))
json.dump(res, open(ROOT/"data/clean/findings.json", "w"), indent=2, default=float)
pd.set_option("display.width", 220)
print(json.dumps(res, indent=1, default=float)); print(summ.round(4).to_string()); print(wf.round(4)); print(buckets.round(3)); print(cal.round(3))

F = ROOT/"data"/"clean"/"draft_charts"; F.mkdir(parents=True, exist_ok=True)
fig, ax = plt.subplots(figsize=(6,6)); ax.plot([0,1],[0,1],"k--",lw=1)
ax.scatter(cal.pred, cal.actual, s=cal.n/5); ax.set(xlabel="Vig-free implied P(home win)", ylabel="Actual home win rate", title=f"Moneyline calibration (Brier {brier:.3f})")
fig.savefig(F/"01_moneyline_calibration.png", dpi=120, bbox_inches="tight")
fig, ax = plt.subplots(figsize=(8,4)); ax.bar(buckets.bucket, buckets.home_cover_rate); ax.axhline(.5,c="k",ls="--"); ax.axhline(BREAKEVEN,c="r",ls=":",label="52.38% breakeven")
ax.set(ylabel="Home cover rate", title="Cover rate by closing spread bucket"); ax.legend(); plt.xticks(rotation=30, ha="right")
fig.savefig(F/"02_cover_rate_by_spread.png", dpi=120, bbox_inches="tight")
s = summ.sort_values("win_rate"); fig, ax = plt.subplots(figsize=(8,5))
ax.errorbar(s.win_rate, s.strategy, xerr=[s.win_rate-s.ci_low, s.ci_high-s.win_rate], fmt="o")
ax.axvline(.5,c="k",ls="--"); ax.axvline(BREAKEVEN,c="r",ls=":",label="breakeven at -110"); ax.set(xlabel="Win rate (95% Wilson CI)", title="Candidate biases vs the vig"); ax.legend()
fig.savefig(F/"03_strategy_win_rates.png", dpi=120, bbox_inches="tight")
fig, ax = plt.subplots(figsize=(8,4))
for st in ["Bet home underdogs ATS","Bet primetime overs","Bet all overs","Bet favorites ATS"]:
    c = pnl_curve(con, st); ax.plot(c.index, c.values, label=st)
ax.axhline(0,c="k",lw=1); ax.set(xlabel="Season", ylabel="Cumulative units (1u/bet, -110)", title="Backtest P&L of naive strategies"); ax.legend(fontsize=8)
fig.savefig(F/"04_backtest_pnl.png", dpi=120, bbox_inches="tight")
fig, ax = plt.subplots(figsize=(7,4)); ax.hist(g.ats_margin, bins=range(-50,51,2)); ax.set(xlabel="Actual margin minus closing spread (home)", title="Spread errors are centered near zero")
fig.savefig(F/"05_spread_error_hist.png", dpi=120, bbox_inches="tight")
