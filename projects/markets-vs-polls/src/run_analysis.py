"""python src/run_analysis.py -> findings, data/clean/*.csv, images/*.png"""
import sys; sys.path.insert(0, "src")
import json, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from forecast_scoring import *
con = connect(); d = matched_panel(con); s = score(d)
(ROOT/"data/clean").mkdir(exist_ok=True); d.to_csv(ROOT/"data/clean/matched_panel.csv", index=False); s.to_csv(ROOT/"data/clean/scores.csv", index=False)
pd.set_option("display.width", 200); print(s.round(4).to_string())
boot = {}
for h, g in d.groupby("days_before"):
    boot[int(h)] = {f"{a}_minus_{b}": paired_bootstrap(g[a], g[b], g.rep_won) for a, b in [("polymarket","polls"),("kalshi","polls"),("polymarket","kalshi")]}
print(json.dumps(boot, indent=1))
sens = pd.DataFrame([dict(sigma=sg, brier_polls_T1=brier(poll_prob(d[d.days_before==1].poll_margin_2p, sg), d[d.days_before==1].rep_won)) for sg in [3,4,5,6,7,8]])
print(sens.round(4))
g1 = d[d.days_before == 1].copy(); g1["poll_error"] = g1.actual_margin_2p - g1.poll_margin_2p
print(g1[["state_po","polymarket","kalshi","polls","poll_margin_2p","actual_margin_2p","rep_won","n_pollsters"]].round(3).sort_values("poll_margin_2p").to_string())
miss = d.groupby("days_before").apply(lambda g: g.loc[((g[["polymarket","kalshi","polls"]] > .5).ne(g.rep_won.astype(bool), axis=0)).any(axis=1), "state_po"].tolist())
print(miss)
cov = dict(markets=pd.read_csv(RAW/"market_coverage.csv").groupby("source").found.sum().to_dict(), states_matched=d.groupby("days_before").size().to_dict(),
           mean_poll_error_T1=float(g1.poll_error.mean()), sd_poll_error_T1=float(g1.poll_error.std()))
json.dump(dict(coverage=cov, bootstrap=boot, sigma_sensitivity=sens.to_dict("records")), open(ROOT/"data/clean/findings.json","w"), indent=2, default=float)
print(cov)
F = ROOT/"images"
fig, ax = plt.subplots(figsize=(7,4))
for src in ["polymarket","kalshi","polls"]:
    x = s[s.source==src]; ax.plot(x.days_before, x.brier, marker="o", label=src)
ax.invert_xaxis(); ax.set(xlabel="Days before Nov 5, 2024", ylabel="Brier score (lower = better)", title="State-level forecast accuracy at matched time points"); ax.legend()
fig.savefig(F/"01_brier_by_horizon.png", dpi=120, bbox_inches="tight")
fig, ax = plt.subplots(figsize=(6,6)); ax.plot([0,1],[0,1],"k--",lw=1)
for src in ["polymarket","kalshi","polls"]: ax.scatter(g1[src], g1.rep_won + np.random.default_rng(1).uniform(-.03,.03,len(g1)), alpha=.6, label=src)
ax.set(xlabel="Forecast P(Republican wins state), 1 day out", ylabel="Outcome (jittered)", title="Forecasts vs outcomes, T-1"); ax.legend()
fig.savefig(F/"02_forecast_vs_outcome_T1.png", dpi=120, bbox_inches="tight")
fig, ax = plt.subplots(figsize=(6,6)); ax.scatter(g1.poll_margin_2p, g1.actual_margin_2p); ax.plot([-40,40],[-40,40],"k--",lw=1)
for _, r in g1.iterrows(): ax.annotate(r.state_po, (r.poll_margin_2p, r.actual_margin_2p), fontsize=7)
ax.set(xlabel="Poll average two-party margin (R-D, pts), T-1", ylabel="Actual margin (R-D, pts)", title="Poll average vs result")
fig.savefig(F/"03_poll_margin_vs_actual.png", dpi=120, bbox_inches="tight")
