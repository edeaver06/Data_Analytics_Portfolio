"""Data-center footprint vs. state electricity prices (supersedes src/model.py sales-growth proxy).

Question: do states with more estimated data-center electricity use (from facility
square footage) have higher OR lower power prices / price changes? Two-sided tests;
no direction assumed. Results are cross-state ASSOCIATIONS, not causal effects.

Inputs
  data/raw/im3_open_source_data_center_atlas_v2026.02.09.csv  PNNL IM3 Open Source Data
      Center Atlas, doi:10.57931/3017294, (c) OpenStreetMap contributors, ODbL 1.0.
  data/clean/retail_sales_monthly.csv        EIA retail sales RES/COM/ALL (src/clean.py)
  data/raw/retail_sales_ind_2021_2026.json   EIA retail sales IND (src/fetch_ind.py)
  data/raw/cpi_cpiaucsl.csv, data/raw/eia_gen_mix_2021.json
Power-density scenarios (watts per sq ft of atlas footprint, treated as average draw):
  low  33  W/ft2  LBNL, Mitchell-Jackson et al. 2001 "Data center power requirements:
                  measurements from Silicon Valley" (measured total computer-room density)
  mid  50  W/ft2  LBNL "High-Performance Data Centers: A Research Roadmap" (typical actual
                  30-55 W/ft2; 50 commonly adopted)
  high 151 W/ft2  arXiv 2606.05420 (2026) hyperscale facility CAPACITY / floor area
                  -> upper bound: assumes running at full capacity 8760 h
Run: .venv/bin/python src/dc_analysis.py   (seed 42; no API key needed)
"""
import json
import numpy as np, pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import spearmanr
from statsmodels.stats.multitest import multipletests
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = 42; rng = np.random.default_rng(SEED)
DENS = {"low": 33, "mid": 50, "high": 151}
CENSUS = {"Northeast": "CT ME MA NH RI VT NJ NY PA", "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
          "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
          "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA"}
REGION = {s: r for r, ss in CENSUS.items() for s in ss.split()}
out = {"note": "associations only; atlas is a 2026 snapshot, crowd-sourced, incomplete", "seed": SEED,
       "density_w_per_sqft": DENS}

# ---- 1. Atlas -> facilities (avoid campus/building double counting) -------------
a = pd.read_csv("data/raw/im3_open_source_data_center_atlas_v2026.02.09.csv")
out["atlas_rows"] = len(a)
a = a.drop_duplicates(["id", "type"])            # county-straddling rows repeat the same facility
out["atlas_rows_after_county_dedup"] = len(a)
camp, bld, pt = (a[a.type == t].copy() for t in ("campus", "building", "point"))
def hav_m(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    h = np.sin((lat2-lat1)*p/2)**2 + np.cos(lat1*p)*np.cos(lat2*p)*np.sin((lon2-lon1)*p/2)**2
    return 12_742_000 * np.arcsin(np.sqrt(h))
# a building/point whose centroid lies within a campus's equivalent-circle radius is treated
# as part of that campus (campus footprint is kept, the inner item dropped). Approximation:
# no polygons in the CSV.
camp["r_m"] = np.sqrt(camp.sqft * 0.0929 / np.pi)
def inside_campus(df):
    if df.empty: return np.zeros(0, bool)
    d = hav_m(df.lat.values[:, None], df.lon.values[:, None], camp.lat.values[None], camp.lon.values[None])
    return (d <= camp.r_m.values[None]).any(axis=1)
bld["in_campus"] = inside_campus(bld); pt["in_campus"] = inside_campus(pt)
out["buildings_inside_campus_dropped"] = int(bld.in_campus.sum())
out["points_inside_campus_dropped"] = int(pt.in_campus.sum())
fac = pd.concat([camp, bld[~bld.in_campus], pt[~pt.in_campus]])[["id", "state_abb", "operator", "type", "sqft"]]
fac["sqft_missing"] = fac.sqft.isna()
out["facilities"] = len(fac); out["facilities_missing_sqft"] = int(fac.sqft_missing.sum())
# impute missing (all are 'point' features) with state median of facilities with sqft,
# falling back to the national median. Flagged; sensitivity run without imputation.
st_med = fac.groupby("state_abb").sqft.median(); nat_med = fac.sqft.median()
fac["sqft_imputed"] = fac.sqft.fillna(fac.state_abb.map(st_med)).fillna(nat_med)
out["national_median_sqft"] = float(nat_med)

# ---- 2. Prices: 2021 vs latest 12 months, 4 sectors ---------------------------
m = pd.read_csv("data/clean/retail_sales_monthly.csv", parse_dates=["month"])
m = m[["state", "sector", "month", "sales_million_kwh", "revenue_million_usd"]]
ind = pd.DataFrame(json.load(open("data/raw/retail_sales_ind_2021_2026.json"))["response"]["data"])
ind = pd.DataFrame({"state": ind.stateid, "sector": "IND", "month": pd.to_datetime(ind.period),
                    "sales_million_kwh": pd.to_numeric(ind.sales, errors="coerce"),
                    "revenue_million_usd": pd.to_numeric(ind.revenue, errors="coerce")})
m = pd.concat([m, ind]).dropna(subset=["sales_million_kwh", "revenue_million_usd"])
cpi = pd.read_csv("data/raw/cpi_cpiaucsl.csv", parse_dates=["observation_date"])
cpi = cpi.rename(columns={"observation_date": "month", "CPIAUCSL": "cpi"})
cpi["cpi"] = pd.to_numeric(cpi.cpi, errors="coerce").interpolate(limit_area="inside")
BASE = ("2021-01-01", "2021-12-01"); LAT = ("2025-08-01", "2026-07-01")
def window(w):
    d = m[(m.month >= w[0]) & (m.month <= w[1])]
    g = d.groupby(["state", "sector"]).agg(rev=("revenue_million_usd", "sum"),
                                           sales=("sales_million_kwh", "sum"), n=("month", "count"))
    g["price"] = g.rev / g.sales * 100
    return g[g.n == 12].price.unstack()      # require all 12 months
p21, plat = window(BASE), window(LAT)
c = cpi.set_index("month").cpi
cpi_ratio = c[LAT[0]:LAT[1]].mean() / c[BASE[0]:BASE[1]].mean()
out["cpi_change_pct"] = float((cpi_ratio - 1) * 100)
st = pd.DataFrame(index=sorted(REGION))
for s in ["RES", "COM", "IND", "ALL"]:
    st[f"{s.lower()}_price_2021"] = p21[s]; st[f"{s.lower()}_price_latest"] = plat[s]
    st[f"{s.lower()}_chg_nominal_pct"] = (plat[s] / p21[s] - 1) * 100
    st[f"{s.lower()}_chg_real_pct"] = (plat[s] / cpi_ratio / p21[s] - 1) * 100
# denominator: total retail sales, calendar 2025 (all 12 months)
tot25 = m[(m.sector == "ALL") & (m.month.dt.year == 2025)].groupby("state").sales_million_kwh.agg(["sum", "count"])
st["all_sales_2025_gwh"] = tot25["sum"].where(tot25["count"] == 12)

# ---- 3. State aggregates and estimated DC load --------------------------------
g = fac.groupby("state_abb")
st["dc_facilities"] = g.size(); st["dc_facilities_missing_sqft"] = g.sqft_missing.sum()
st["dc_sqft_known"] = g.sqft.sum(); st["dc_sqft_imputed"] = g.sqft_imputed.sum()
st[["dc_facilities", "dc_facilities_missing_sqft", "dc_sqft_known", "dc_sqft_imputed"]] = \
    st[["dc_facilities", "dc_facilities_missing_sqft", "dc_sqft_known", "dc_sqft_imputed"]].fillna(0)
for k, w in DENS.items():
    st[f"dc_gwh_{k}"] = st.dc_sqft_imputed * w * 8760 / 1e9          # W*h -> GWh
    st[f"dc_share_{k}_pct"] = 100 * st[f"dc_gwh_{k}"] / st.all_sales_2025_gwh
st["dc_share_mid_noimpute_pct"] = 100 * st.dc_sqft_known * 50 * 8760 / 1e9 / st.all_sales_2025_gwh
gen = pd.DataFrame(json.load(open("data/raw/eia_gen_mix_2021.json"))["response"]["data"])
gen["generation"] = pd.to_numeric(gen.generation, errors="coerce")
gen = gen.pivot_table(index="location", columns="fueltypeid", values="generation", aggfunc="sum")
st["gas_share_2021_pct"] = 100 * gen.NG.reindex(st.index).fillna(0) / gen.ALL.reindex(st.index)
st["census_region"] = pd.Series(REGION)
st.index.name = "state"
nat = {k: float(st[f"dc_gwh_{k}"].sum() / 1000) for k in DENS}
out["national_est_twh"] = nat
out["national_est_twh_noimpute_mid"] = float(st.dc_sqft_known.sum() * 50 * 8760 / 1e12)
out["lbnl_2023_twh"] = 176
out["national_total_sqft_imputed"] = float(st.dc_sqft_imputed.sum())
out["top10_share_mid"] = st.dc_share_mid_pct.sort_values(ascending=False).head(10).round(2).to_dict()
out["states_with_zero_facilities"] = st.index[st.dc_facilities == 0].tolist()

# ---- 4. Spearman (two-sided) with bootstrap CI, Holm across 12 outcomes --------
def sp_ci(x, y, B=5000):
    r = spearmanr(x, y)
    bs = [spearmanr(x[i], y[i])[0] for i in (rng.integers(0, len(x), len(x)) for _ in range(B))]
    return r[0], r[1], *np.nanpercentile(bs, [2.5, 97.5])
OUTS = [f"{s}_{k}" for s in ["res", "com", "ind", "all"] for k in ["price_latest", "chg_nominal_pct", "chg_real_pct"]]
def run_spearman(expo):
    res = {}
    for o in OUTS:
        d = st[[expo, o]].dropna()
        rho, p, lo, hi = sp_ci(d[expo].values, d[o].values)
        res[o] = {"n": len(d), "rho": rho, "lo": lo, "hi": hi, "p": p}
    adj = multipletests([v["p"] for v in res.values()], method="holm")[1]
    for v, pa in zip(res.values(), adj): v["p_holm"] = pa
    return res
# shares under low/mid/high differ only by a constant factor -> identical ranks; so Spearman
# is run on the mid share (imputed) and, as sensitivity, on the non-imputed share.
out["spearman_mid_imputed"] = run_spearman("dc_share_mid_pct")
out["spearman_mid_noimpute"] = run_spearman("dc_share_mid_noimpute_pct")
# sensitivity 3: campus polygons are LAND area (parking, open ground), which likely inflates
# load. Recompute using building footprints only (all buildings, incl. those inside campuses).
bsq = a[a.type == "building"].groupby("state_abb").sqft.sum().reindex(st.index).fillna(0)
st["dc_sqft_buildings_only"] = bsq
st["dc_share_mid_buildings_only_pct"] = 100 * bsq * 50 * 8760 / 1e9 / st.all_sales_2025_gwh
out["national_est_twh_buildings_only"] = {k: float(bsq.sum() * w * 8760 / 1e12) for k, w in DENS.items()}
out["spearman_mid_buildings_only"] = run_spearman("dc_share_mid_buildings_only_pct")

st.round(4).to_csv("data/clean/dc_state_estimates.csv")

# ---- 5. OLS, HC3, controls --------------------------------------------------
# exposure: log10(share% + 0.01) because shares are very right-skewed; coefficient = pp of
# outcome per 10x higher share. Controls: gas share 2021, census region, and (for change
# outcomes) the sector's own 2021 price level.
st["log10_dc_share"] = np.log10(st.dc_share_mid_pct + 0.01)
out["ols"] = {}
for o in OUTS:
    s = o.split("_")[0]
    f = f"{o} ~ log10_dc_share + gas_share_2021_pct + C(census_region)"
    if "chg" in o: f += f" + {s}_price_2021"
    d = st.dropna(subset=[o, "log10_dc_share", f"{s}_price_2021"])
    r = smf.ols(f, data=d).fit(cov_type="HC3"); ci = r.conf_int().loc["log10_dc_share"]
    out["ols"][o] = {"formula": f, "n": int(r.nobs), "r2": r.rsquared, "b_log10_share": r.params["log10_dc_share"],
                     "lo": ci[0], "hi": ci[1], "p": r.pvalues["log10_dc_share"]}
adj = multipletests([v["p"] for v in out["ols"].values()], method="holm")[1]
for v, pa in zip(out["ols"].values(), adj): v["p_holm"] = pa

# ---- 6. Figures --------------------------------------------------------------
NOTE = "Source: PNNL IM3 Data Center Atlas (OSM, ODbL) v2026.02.09; EIA retail sales. Association, not causation."
top = st.dc_share_mid_pct.sort_values().tail(20)
fig, ax = plt.subplots(figsize=(7, 6))
ax.barh(top.index, top.values, xerr=[top.values - st.loc[top.index, "dc_share_low_pct"],
        st.loc[top.index, "dc_share_high_pct"] - top.values], capsize=2, color="#4C72B0")
ax.set_xlabel("Estimated data-center share of 2025 retail sales, % (bar = 50 W/ft2; whiskers 33-151)")
ax.set_title("Top 20 states: estimated data-center share of load"); fig.text(0.01, 0.01, NOTE, fontsize=6)
fig.tight_layout(rect=(0, .03, 1, 1)); fig.savefig("figures/09_dc_share_by_state.png", dpi=150); plt.close(fig)
for i, kind in enumerate(["price_latest", "chg_nominal_pct"]):
    fig, axs = plt.subplots(2, 2, figsize=(10, 8))
    for ax, s in zip(axs.flat, ["res", "com", "ind", "all"]):
        o = f"{s}_{kind}"; d = st[["log10_dc_share", o]].dropna(); r = out["spearman_mid_imputed"][o]
        ax.scatter(d.log10_dc_share, d[o], s=14)
        for nm, (x, y) in d.iterrows(): ax.annotate(nm, (x, y), fontsize=6)
        ax.set_title(f"{s.upper()}: rho {r['rho']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}], Holm p {r['p_holm']:.2f}", fontsize=9)
        ax.set_xlabel("log10(est. DC share % + 0.01)")
        ax.set_ylabel("price, c/kWh (Aug25-Jul26)" if kind == "price_latest" else "% change 2021 -> Aug25-Jul26")
    fig.text(0.01, 0.005, NOTE, fontsize=6); fig.tight_layout(rect=(0, .02, 1, 1))
    fig.savefig(f"figures/{10+i}_dc_share_vs_{kind}.png", dpi=150); plt.close(fig)
fig, ax = plt.subplots(figsize=(7, 6))
ks = OUTS[::-1]; o = out["ols"]
ax.errorbar([o[k]["b_log10_share"] for k in ks], range(len(ks)),
            xerr=[[o[k]["b_log10_share"] - o[k]["lo"] for k in ks], [o[k]["hi"] - o[k]["b_log10_share"] for k in ks]], fmt="o", capsize=3)
ax.axvline(0, color="grey", ls="--"); ax.set_yticks(range(len(ks))); ax.set_yticklabels(ks, fontsize=8)
ax.set_xlabel("OLS coef per 10x higher est. DC share (95% CI, HC3)"); ax.set_title("Controls: gas share, region, 2021 price (change models)")
fig.text(0.01, 0.01, NOTE, fontsize=6); fig.tight_layout(rect=(0, .03, 1, 1))
fig.savefig("figures/12_dc_ols_coefficients.png", dpi=150); plt.close(fig)

json.dump(out, open("reports/dc_analysis_results.json", "w"), indent=2, default=float)
r = lambda x: round(float(x), 3)
print(json.dumps({k: v for k, v in out.items() if k not in ("ols", "spearman_mid_imputed", "spearman_mid_noimpute")}, default=r, indent=1))
for k in ("spearman_mid_buildings_only",):
    print(k); print(pd.DataFrame(out[k]).T.drop(columns=["formula"], errors="ignore").astype(float).round(3).to_string())
print(st[["dc_facilities","dc_facilities_missing_sqft","dc_share_mid_pct"]].describe().round(2))
