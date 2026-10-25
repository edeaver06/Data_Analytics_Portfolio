"""Modeling stage: explain state-level residential (RES) price change,
2021 average -> Aug 2025-Jul 2026 average, n=49 (CO, NM excluded: incomplete RES months).

Associations only, NOT causal. Small n -> wide intervals; read results cautiously.
Inputs:
  data/clean/state_price_sales_change.csv   (from src/eda.py)
  data/raw/eia_gen_mix_2021.json            (from src/fetch_covariates.py, EIA API v2)
Census regions: hard-coded from the US Census Bureau's official four-region definitions
  (https://www2.census.gov/geo/pdfs/maps-data/maps/reference/us_regdiv.pdf).
Outputs: data/clean/model_dataset.csv, reports/model_results.json, figures/06-08_*.png
Run: .venv/bin/python src/model.py   (seed 42, no API key needed)
"""
import json
import numpy as np, pandas as pd
import statsmodels.formula.api as smf
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import RepeatedKFold, LeaveOneOut, cross_val_predict
from sklearn.dummy import DummyRegressor
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.inspection import permutation_importance

SEED = 42
CENSUS = {  # Census Bureau regions
 "Northeast": "CT ME MA NH RI VT NJ NY PA",
 "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
 "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
 "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA"}
REGION = {s: r for r, ss in CENSUS.items() for s in ss.split()}

# ---- 1. Build modeling dataset -------------------------------------------
df = pd.read_csv("data/clean/state_price_sales_change.csv")
gen = pd.DataFrame(json.load(open("data/raw/eia_gen_mix_2021.json"))["response"]["data"])
gen["generation"] = pd.to_numeric(gen["generation"], errors="coerce")
gen = gen.pivot_table(index="location", columns="fueltypeid", values="generation", aggfunc="sum")
gen["gas_share_2021_pct"] = 100 * gen["NG"].fillna(0) / gen["ALL"]
df = df.merge(gen[["gas_share_2021_pct"]], left_on="state", right_index=True, how="left")
df["census_region"] = df["state"].map(REGION)
df = df[~df["state"].isin(["CO", "NM"])].dropna(subset=["res_price_chg_nominal_pct"])
assert len(df) == 49 and df["census_region"].notna().all()
assert df["gas_share_2021_pct"].notna().all(), "missing gas share"
cols = ["state", "census_region", "res_price_chg_nominal_pct", "res_price_chg_real_pct",
        "com_sales_chg_pct", "all_sales_chg_pct", "res_price_2021", "gas_share_2021_pct"]
df[cols].to_csv("data/clean/model_dataset.csv", index=False)
Y = "res_price_chg_nominal_pct"
out = {"n": len(df), "target": Y, "note": "associations only, not causal", "seed": SEED}

# ---- 2. OLS with HC3 robust SEs (HC3 suits small n) ----------------------
specs = {
 "m1_com_only": f"{Y} ~ com_sales_chg_pct",
 "m2_com_controls": f"{Y} ~ com_sales_chg_pct + res_price_2021 + gas_share_2021_pct + C(census_region)",
 "m3_total_controls": f"{Y} ~ all_sales_chg_pct + res_price_2021 + gas_share_2021_pct + C(census_region)",
}
out["ols"] = {}
for name, f in specs.items():
    m = smf.ols(f, data=df).fit(cov_type="HC3")
    ci = m.conf_int()
    out["ols"][name] = {"formula": f, "r2": m.rsquared, "adj_r2": m.rsquared_adj,
        "coef": {k: {"b": m.params[k], "lo": ci.loc[k, 0], "hi": ci.loc[k, 1], "p": m.pvalues[k]}
                 for k in m.params.index}}
# influence check on m2: drop DC (largest change, also not a state)
m = smf.ols(specs["m2_com_controls"], data=df[df.state != "DC"]).fit(cov_type="HC3")
out["ols"]["m2_without_DC"] = {"r2": m.rsquared, "coef": {k: {"b": m.params[k],
    "lo": m.conf_int().loc[k, 0], "hi": m.conf_int().loc[k, 1], "p": m.pvalues[k]} for k in m.params.index}}

# ---- 3. Random forest vs mean baseline (CV) ------------------------------
feats = ["com_sales_chg_pct", "all_sales_chg_pct", "res_price_2021", "gas_share_2021_pct"]
X = pd.concat([df[feats], pd.get_dummies(df["census_region"], prefix="reg", dtype=float)], axis=1)
y = df[Y].values
rf = RandomForestRegressor(n_estimators=500, min_samples_leaf=3, random_state=SEED)
base = DummyRegressor()
out["cv"] = {}
# LOO: one pooled prediction per state
for nm, est in [("rf", rf), ("baseline_mean", base)]:
    p = cross_val_predict(est, X, y, cv=LeaveOneOut())
    out["cv"][f"loo_{nm}"] = {"r2": r2_score(y, p), "mae": mean_absolute_error(y, p)}
# repeated 5-fold x 20: distribution of fold scores
rkf = RepeatedKFold(n_splits=5, n_repeats=20, random_state=SEED)
res = {"rf": [], "baseline_mean": []}
for tr, te in rkf.split(X):
    for nm, est in [("rf", rf), ("baseline_mean", base)]:
        p = est.fit(X.iloc[tr], y[tr]).predict(X.iloc[te])
        res[nm].append((r2_score(y[te], p), mean_absolute_error(y[te], p)))
for nm, v in res.items():
    a = np.array(v)
    out["cv"][f"rkf5x20_{nm}"] = {"r2_mean": a[:, 0].mean(), "r2_sd": a[:, 0].std(),
                                  "mae_mean": a[:, 1].mean(), "mae_sd": a[:, 1].std()}
# permutation importance, computed out-of-fold (on held-out folds) to avoid in-sample bias
imp = {c: [] for c in X.columns}
for tr, te in RepeatedKFold(n_splits=5, n_repeats=4, random_state=SEED).split(X):
    rf.fit(X.iloc[tr], y[tr])
    pi = permutation_importance(rf, X.iloc[te], y[te], n_repeats=10, random_state=SEED,
                                scoring="neg_mean_absolute_error")
    for c, v in zip(X.columns, pi.importances_mean): imp[c].append(v)
out["perm_importance_mae_increase"] = {c: {"mean": float(np.mean(v)), "sd": float(np.std(v))}
                                       for c, v in sorted(imp.items(), key=lambda kv: -np.mean(kv[1]))}

# ---- 4. Figures ----------------------------------------------------------
c = out["ols"]["m2_com_controls"]["coef"]
keys = [k for k in c if k != "Intercept"]
fig, ax = plt.subplots(figsize=(7, 4))
ax.errorbar([c[k]["b"] for k in keys], range(len(keys)),
            xerr=[[c[k]["b"] - c[k]["lo"] for k in keys], [c[k]["hi"] - c[k]["b"] for k in keys]],
            fmt="o", capsize=3)
ax.axvline(0, color="grey", ls="--"); ax.set_yticks(range(len(keys))); ax.set_yticklabels(keys)
ax.set_xlabel("Coefficient (pp of RES price change), 95% CI, HC3")
ax.set_title(f"OLS m2: RES price change 2021->Aug25-Jul26 (n={len(df)})")
fig.tight_layout(); fig.savefig("figures/06_ols_coefficients.png", dpi=150); plt.close(fig)

pim = out["perm_importance_mae_increase"]
fig, ax = plt.subplots(figsize=(7, 4))
ks = list(pim)[::-1]
ax.barh(ks, [pim[k]["mean"] for k in ks], xerr=[pim[k]["sd"] for k in ks], capsize=3)
ax.axvline(0, color="grey", ls="--")
ax.set_xlabel("MAE increase when shuffled (pp), out-of-fold")
ax.set_title("Random forest permutation importance (small n: noisy)")
fig.tight_layout(); fig.savefig("figures/07_rf_permutation_importance.png", dpi=150); plt.close(fig)

p = cross_val_predict(rf, X, y, cv=LeaveOneOut())
fig, ax = plt.subplots(figsize=(5, 5))
ax.scatter(y, p); [ax.annotate(s, (a, b), fontsize=7) for s, a, b in zip(df.state, y, p)]
lim = [min(y.min(), p.min()) - 3, max(y.max(), p.max()) + 3]; ax.plot(lim, lim, "k--", lw=1)
ax.axhline(y.mean(), color="grey", lw=1, label="baseline (mean)")
ax.set_xlabel("Actual RES price change %"); ax.set_ylabel("RF LOO predicted %"); ax.legend()
ax.set_title("Random forest LOO predictions"); fig.tight_layout()
fig.savefig("figures/08_rf_loo_pred_vs_actual.png", dpi=150); plt.close(fig)

json.dump(out, open("reports/model_results.json", "w"), indent=2, default=float)
print(json.dumps(out, indent=1, default=lambda x: round(float(x), 3)))
