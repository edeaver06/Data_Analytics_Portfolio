"""EDA: residential electricity prices vs. sales growth by state (EIA retail-sales).

Reproduce:  .venv/bin/python src/eda.py
Inputs : data/electricity.db (built by src/run_pipeline.py), data/raw/cpi_cpiaucsl.csv
         (FRED CPIAUCSL, downloaded automatically if missing; no key needed).
Outputs: data/clean/state_price_sales_change.csv, data/clean/national_res_price_monthly.csv,
         figures/0*.png, reports/eda_quality.json
No API key is read or used here. Descriptive only: no causal claims.
"""
import json, sqlite3, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DB, FIG, CLEAN, REP = ROOT/"data/electricity.db", ROOT/"figures", ROOT/"data/clean", ROOT/"reports"
CPI = ROOT/"data/raw/cpi_cpiaucsl.csv"
SRC = "Source: EIA Open Data API v2, electricity/retail-sales (monthly); CPI: BLS CPI-U via FRED CPIAUCSL"
rng = np.random.default_rng(42)
FIG.mkdir(exist_ok=True); CLEAN.mkdir(exist_ok=True)

# ---- load ---------------------------------------------------------------------
con = sqlite3.connect(DB)
df = pd.read_sql("SELECT state, sector, month, price_cents_per_kwh AS price, "
                 "sales_million_kwh AS sales, revenue_million_usd AS revenue FROM retail_sales_monthly", con)
view_rows = con.execute("SELECT COUNT(*) FROM v_residential_price").fetchone()[0]
df["month"] = pd.to_datetime(df["month"])

# ---- data quality ---------------------------------------------------------------
q = {"rows": len(df), "view_v_residential_price_rows": view_rows,
     "states": int(df.state.nunique()), "sectors": sorted(df.sector.unique()),
     "first_month": str(df.month.min().date()), "last_month": str(df.month.max().date()),
     "duplicates_state_sector_month": int(df.duplicated(["state", "sector", "month"]).sum())}
months = pd.date_range(df.month.min(), df.month.max(), freq="MS")
q["expected_rows"] = len(months) * q["states"] * len(q["sectors"])
q["missing_state_sector_months"] = q["expected_rows"] - len(df)
q["null_counts"] = {c: int(df[c].isna().sum()) for c in ["price", "sales", "revenue"]}
q["null_rows_detail"] = (df[df[["price", "sales", "revenue"]].isna().any(axis=1)]
    .assign(m=lambda d: d.month.dt.strftime("%Y-%m")).groupby(["state", "sector"])["m"]
    .agg(lambda s: f"{len(s)} rows ({s.min()}..{s.max()})").to_dict())
q["null_rows_detail"] = {f"{k[0]}-{k[1]}": v for k, v in q["null_rows_detail"].items()}
# Unit check: price (c/kWh) should equal revenue($M)/sales(MkWh)*100
chk = df.dropna(subset=["price", "sales", "revenue"]).query("sales > 0")
implied = chk.revenue / chk.sales * 100
q["price_vs_revenue_over_sales_median_abs_diff_cents"] = round(float((implied - chk.price).abs().median()), 3)
q["price_vs_implied_gt_1cent_rows"] = int(((implied - chk.price).abs() > 1).sum())
# Outliers: month-over-month RES price jump > 30% within a state
res = df[df.sector == "RES"].sort_values(["state", "month"]).copy()
res["mom"] = res.groupby("state").price.pct_change(fill_method=None)
out = res[res.mom.abs() > 0.30]
q["res_price_mom_jumps_gt_30pct"] = [f"{r.state} {r.month:%Y-%m} {r.mom:+.0%}" for r in out.itertuples()]
complete = df[["price", "sales"]].notna().all(axis=1).groupby(df.month).sum()
full = len(q["sectors"]) * q["states"]
q["latest_fully_complete_month"] = str(complete[complete == full].index.max().date())
q["latest_month_with_all_51_res_prices"] = str(res.dropna(subset=["price"]).groupby("month").state.nunique()
                                              .loc[lambda s: s == 51].index.max().date())

# ---- CPI (inflation adjustment) ------------------------------------------------
if not CPI.exists():
    urllib.request.urlretrieve("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL", CPI)
cpi = pd.read_csv(CPI, parse_dates=["observation_date"]).rename(columns={"observation_date": "month", "CPIAUCSL": "cpi"})
# BLS did not publish CPI for Oct 2025 (federal shutdown); FRED leaves it blank.
# Fill such gaps by linear interpolation between neighbouring months and record them.
q["cpi_months_interpolated"] = [f"{m:%Y-%m}" for m in cpi.loc[cpi.cpi.isna(), "month"]]
cpi["cpi"] = cpi.cpi.interpolate(limit_area="inside")
df = df.merge(cpi, on="month", how="left")
assert df.cpi.notna().all(), "CPI missing for some months"

# ---- windows: 2021 calendar year vs latest 12 months (same 12 calendar months seasonally balanced) ----
last = df.month.max()
LATEST = (last - pd.DateOffset(months=11), last)          # 2025-08..2026-07
BASE = (pd.Timestamp("2021-01-01"), pd.Timestamp("2021-12-01"))
q["windows"] = {"base": "2021-01..2021-12", "latest": f"{LATEST[0]:%Y-%m}..{LATEST[1]:%Y-%m}"}
def win(d, w): return d[(d.month >= w[0]) & (d.month <= w[1])]

def window_stats(d):
    """Sales-weighted price (= revenue/sales), total sales, mean CPI for a window."""
    g = d.groupby(["state", "sector"]).agg(rev=("revenue", "sum"), sales=("sales", "sum"),
                                           n=("sales", "count"), cpi=("cpi", "mean"))
    g["price"] = g.rev / g.sales * 100
    return g
b, l = window_stats(win(df, BASE)), window_stats(win(df, LATEST))
w = b.join(l, lsuffix="_2021", rsuffix="_latest").reset_index()
w = w[(w.n_2021 == 12) & (w.n_latest == 12)]               # require 12 non-null months in both windows
cpi_ratio = l.cpi.mean() / b.cpi.mean()
q["cpi_change_pct"] = round((cpi_ratio - 1) * 100, 2)
w["price_chg_nominal_pct"] = (w.price_latest / w.price_2021 - 1) * 100
w["price_chg_real_pct"] = (w.price_latest / cpi_ratio / w.price_2021 - 1) * 100
w["sales_chg_pct"] = (w.sales_latest / w.sales_2021 - 1) * 100
wide = w.pivot(index="state", columns="sector",
               values=["price_2021", "price_latest", "price_chg_nominal_pct", "price_chg_real_pct",
                       "sales_2021", "sales_latest", "sales_chg_pct"])
wide.columns = [f"{s.lower()}_{m}" for m, s in wide.columns]
reg = pd.read_sql("SELECT state, primary_region, multi_region FROM state_region", con)
wide = wide.reset_index().merge(reg, on="state", how="left").round(3)
q["states_dropped_from_comparison"] = {s: sorted(set(df.state) - set(w[w.sector == s].state)) for s in q["sectors"]}
wide.to_csv(CLEAN/"state_price_sales_change.csv", index=False)

# National residential (sales-weighted across states)
nat = (df[df.sector == "RES"].dropna(subset=["revenue", "sales"]).groupby("month")
       .agg(rev=("revenue", "sum"), sales=("sales", "sum"), cpi=("cpi", "first")))
nat["price_nominal"] = nat.rev / nat.sales * 100
nat["price_real_latest_dollars"] = nat.price_nominal * cpi.set_index("month").cpi.loc[last] / nat.cpi
nat["price_nominal_12mo_avg"] = nat.price_nominal.rolling(12).mean()
nat.reset_index()[["month", "price_nominal", "price_real_latest_dollars", "price_nominal_12mo_avg", "sales"]] \
   .round(4).to_csv(CLEAN/"national_res_price_monthly.csv", index=False)
us = w.groupby("sector")[["rev_2021", "sales_2021", "rev_latest", "sales_latest"]].sum()
us_price = {s: (us.loc[s, "rev_latest"] / us.loc[s, "sales_latest"]) / (us.loc[s, "rev_2021"] / us.loc[s, "sales_2021"]) for s in us.index}
q["national"] = {s: {"price_2021": round(us.loc[s, "rev_2021"] / us.loc[s, "sales_2021"] * 100, 2),
                     "price_latest": round(us.loc[s, "rev_latest"] / us.loc[s, "sales_latest"] * 100, 2),
                     "price_chg_nominal_pct": round((us_price[s] - 1) * 100, 1),
                     "price_chg_real_pct": round((us_price[s] / cpi_ratio - 1) * 100, 1),
                     "sales_chg_pct": round((us.loc[s, "sales_latest"] / us.loc[s, "sales_2021"] - 1) * 100, 1)}
                 for s in us.index}

# ---- correlations: sales growth (proxy) vs residential price change -------------
def spearman_ci(x, y, n_boot=5000):
    m = x.notna() & y.notna(); x, y = x[m].to_numpy(), y[m].to_numpy()
    rho, p = stats.spearmanr(x, y)
    boots = [stats.spearmanr(x[i], y[i])[0] for i in (rng.integers(0, len(x), len(x)) for _ in range(n_boot))]
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return {"n": int(len(x)), "rho": round(float(rho), 3), "p": round(float(p), 4),
            "ci95_bootstrap": [round(float(lo), 3), round(float(hi), 3)]}
q["spearman"] = {f"{px}_vs_{sx}_sales_growth": spearman_ci(wide[f"{sx}_sales_chg_pct"], wide[f"res_price_chg_{px}_pct"])
                 for sx in ["com", "all"] for px in ["nominal", "real"]}
q["top10_com_sales_growth"] = wide.nlargest(10, "com_sales_chg_pct")[["state", "com_sales_chg_pct", "all_sales_chg_pct", "res_price_chg_nominal_pct"]].round(1).to_dict("records")
q["top10_all_sales_growth"] = wide.nlargest(10, "all_sales_chg_pct")[["state", "all_sales_chg_pct", "res_price_chg_nominal_pct"]].round(1).to_dict("records")
q["top10_res_price_chg_nominal"] = wide.nlargest(10, "res_price_chg_nominal_pct")[["state", "res_price_chg_nominal_pct", "res_price_chg_real_pct", "com_sales_chg_pct"]].round(1).to_dict("records")
q["bottom5_res_price_chg_nominal"] = wide.nsmallest(5, "res_price_chg_nominal_pct")[["state", "res_price_chg_nominal_pct", "res_price_chg_real_pct"]].round(1).to_dict("records")
q["res_price_chg_nominal_median"] = round(float(wide.res_price_chg_nominal_pct.median()), 1)
q["res_price_chg_real_median"] = round(float(wide.res_price_chg_real_pct.median()), 1)
q["states_res_real_price_fell"] = int((wide.res_price_chg_real_pct < 0).sum())
# Robustness: same correlation excluding CA/HI/AK (wildfire/isolated-grid confounders)
sub = wide[~wide.state.isin(["CA", "HI", "AK"])]
q["spearman_excl_CA_HI_AK_com_nominal"] = spearman_ci(sub.com_sales_chg_pct, sub.res_price_chg_nominal_pct)
# Group comparison: top-quintile COM growth vs rest (descriptive)
wd = wide.dropna(subset=["res_price_chg_nominal_pct"])  # CO, NM lack 12 RES months
cut = wd.com_sales_chg_pct.quantile(0.8)
hi_g, lo_g = wd[wd.com_sales_chg_pct >= cut], wd[wd.com_sales_chg_pct < cut]
mw = stats.mannwhitneyu(hi_g.res_price_chg_nominal_pct, lo_g.res_price_chg_nominal_pct)
q["top_quintile_com_growth_vs_rest"] = {"n_top": len(hi_g), "n_rest": len(lo_g), "cut_pct": round(float(cut), 1),
    "median_res_price_chg_top": round(float(hi_g.res_price_chg_nominal_pct.median()), 1),
    "median_res_price_chg_rest": round(float(lo_g.res_price_chg_nominal_pct.median()), 1),
    "mannwhitney_p": round(float(mw.pvalue), 4)}
# Fuel-spike context: national RES annual nominal price by year
yr = nat.groupby(nat.index.year).apply(lambda g: g.rev.sum() / g.sales.sum() * 100)
q["national_res_price_by_year"] = {int(k): round(float(v), 2) for k, v in yr.loc[2019:].items()}

# ---- figures --------------------------------------------------------------------
def foot(ax, extra=""):
    ax.figure.text(0.01, 0.01, SRC + extra, fontsize=7, color="#555")
BLUE, ORANGE, GRAY = "#0072B2", "#E69F00", "#999999"

fig, ax = plt.subplots(figsize=(10, 5.5))
ax.plot(nat.index, nat.price_nominal_12mo_avg, color=BLUE, label="Nominal (12-mo avg)")
ax.plot(nat.index, nat.price_real_latest_dollars.rolling(12).mean(), color=ORANGE, ls="--",
        label=f"Inflation-adjusted, {last:%b %Y} dollars (12-mo avg)")
real12 = nat.price_real_latest_dollars.rolling(12).mean()
q["national_real_12mo_latest"] = round(float(real12.iloc[-1]), 2)
q["national_real_12mo_prior_peak"] = {"month": f"{real12.iloc[:-36].idxmax():%Y-%m}", "value": round(float(real12.iloc[:-36].max()), 2)}
ax.set_title(f"US residential price: {nat.price_nominal_12mo_avg.iloc[-1]:.1f} c/kWh nominal; inflation-adjusted it is the "
             f"highest since 2001\n({real12.iloc[-1]:.1f} c vs prior peak {real12.iloc[:-36].max():.1f} c in {real12.iloc[:-36].idxmax():%Y}, {last:%b %Y} dollars)", fontsize=11)
ax.set_ylabel("Cents per kWh (sales-weighted, 50 states + DC)"); ax.set_xlabel("Month")
ax.legend(); ax.grid(alpha=.3); fig.subplots_adjust(bottom=.15); foot(ax)
fig.savefig(FIG/"01_national_res_price_trend.png", dpi=150); plt.close(fig)

s = wide.sort_values("res_price_chg_nominal_pct")
fig, ax = plt.subplots(figsize=(8, 12))
ax.barh(s.state, s.res_price_chg_nominal_pct, color=GRAY, label="Nominal")
ax.scatter(s.res_price_chg_real_pct, s.state, color=BLUE, s=14, zorder=3, label="Inflation-adjusted")
ax.axvline(0, color="k", lw=.8); ax.axvline(q["cpi_change_pct"], color=ORANGE, ls=":", label=f"CPI change ({q['cpi_change_pct']:.1f}%)")
ax.set_title(f"Residential price change, 2021 avg -> {q['windows']['latest']}\nmedian state +{q['res_price_chg_nominal_median']}% nominal, {q['res_price_chg_real_median']:+}% real", fontsize=11)
ax.set_xlabel("% change in sales-weighted residential price"); ax.tick_params(axis="y", labelsize=7)
ax.legend(loc="lower right", fontsize=8); fig.subplots_adjust(bottom=.06, left=.1); foot(ax)
fig.savefig(FIG/"02_state_res_price_change.png", dpi=150); plt.close(fig)

for sx, fname in [("com", "03_com_sales_growth_vs_res_price.png"), ("all", "04_total_sales_growth_vs_res_price.png")]:
    r = q["spearman"][f"nominal_vs_{sx}_sales_growth"]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.scatter(wide[f"{sx}_sales_chg_pct"], wide.res_price_chg_nominal_pct, color=BLUE, alpha=.75)
    for t in wide.itertuples():
        ax.annotate(t.state, (getattr(t, f"{sx}_sales_chg_pct"), t.res_price_chg_nominal_pct), fontsize=7, xytext=(3, 2), textcoords="offset points")
    lab = "Commercial" if sx == "com" else "Total (all-sector)"
    ax.set_title(f"{lab} sales growth vs residential price change by state\n"
                 f"Spearman rho = {r['rho']:+.2f} (95% CI {r['ci95_bootstrap'][0]:+.2f} to {r['ci95_bootstrap'][1]:+.2f}), n = {r['n']}: association, not cause", fontsize=11)
    ax.set_xlabel(f"{lab} sales change, % (2021 -> {q['windows']['latest']}); PROXY for data-center load")
    ax.set_ylabel("Residential price change, % nominal"); ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6); ax.grid(alpha=.3)
    fig.subplots_adjust(bottom=.13); foot(ax, " | sales growth is a proxy, not measured data-center load")
    fig.savefig(FIG/fname, dpi=150); plt.close(fig)

t = wide.nlargest(15, "com_sales_chg_pct").sort_values("com_sales_chg_pct")
fig, ax = plt.subplots(figsize=(8, 6))
ax.barh(t.state, t.com_sales_chg_pct, color=BLUE)
ax.set_title(f"15 states with the fastest commercial sales growth, 2021 -> {q['windows']['latest']}")
ax.set_xlabel("% change in commercial electricity sales (million kWh)"); fig.subplots_adjust(bottom=.13); foot(ax)
fig.savefig(FIG/"05_top_com_sales_growth.png", dpi=150); plt.close(fig)
(REP/"eda_quality.json").write_text(json.dumps(q, indent=2, default=str))
print("wrote", REP/"eda_quality.json")
