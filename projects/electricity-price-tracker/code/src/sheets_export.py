"""Build the compact tables loaded into the Google Sheets dashboard.

Reads data/electricity.db (and the cached FRED CPI file) and writes
data/clean/sheets/{annual_state_sector,states_summary,cpi_annual}.csv.
Annual prices are sales-weighted: sum(revenue) / sum(sales) * 100 (cents/kWh),
using only months where both values are reported. No API key is read.
Run: .venv/bin/python src/sheets_export.py
"""
from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "clean" / "sheets"
L12 = ("2025-08-01", "2026-07-01")   # latest 12 complete months (same window as the EDA)


def wprice(df):
    ok = df.dropna(subset=["revenue_million_usd", "sales_million_kwh"])
    return round(ok.revenue_million_usd.sum() / ok.sales_million_kwh.sum() * 100, 2) if len(ok) else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ROOT / "data" / "electricity.db")
    m = pd.read_sql("select * from retail_sales_monthly", con)
    reg = pd.read_sql("select state, primary_region, multi_region from state_region", con)
    m["year"] = m.month.str[:4].astype(int)
    us = m.copy(); us["state"] = "US"; us["state_name"] = "United States (51 total)"
    allm = pd.concat([m, us])

    rows = []
    for (yr, st), g in allm.groupby(["year", "state"]):
        r = {"Year": yr, "State": st}
        for sec in ["RES", "COM", "ALL"]:
            r[f"{sec} price (c/kWh)"] = wprice(g[g.sector == sec])
        res = g[g.sector == "RES"].dropna(subset=["revenue_million_usd", "sales_million_kwh"])
        r["RES sales (GWh)"] = round(res.sales_million_kwh.sum(), 1)
        r["RES months reported"] = len(res) if st != "US" else res.month.nunique()
        rows.append(r)
    ann = pd.DataFrame(rows).merge(reg, left_on="State", right_on="state", how="left").drop(columns="state")
    ann["primary_region"] = ann.primary_region.fillna("US total")
    ann = ann.rename(columns={"primary_region": "Grid region (primary)"})
    ann = ann[["Year", "State", "Grid region (primary)", "RES price (c/kWh)", "COM price (c/kWh)",
               "ALL price (c/kWh)", "RES sales (GWh)", "RES months reported"]]
    ann.to_csv(OUT / "annual_state_sector.csv", index=False)

    res = allm[allm.sector == "RES"]
    srows = []
    for st, g in res.groupby("state"):
        l12 = g[(g.month >= L12[0]) & (g.month <= L12[1])]
        l12ok = l12.dropna(subset=["revenue_million_usd", "sales_million_kwh"])
        nmonths = l12ok.month.nunique() if st != "US" else 12
        latest = g[g.month == L12[1]]
        srows.append({
            "State": st, "State name": g.state_name.iloc[0],
            "RES 2001 avg (c/kWh)": wprice(g[g.year == 2001]),
            "RES 2021 avg (c/kWh)": wprice(g[g.year == 2021]),
            "RES latest-12 avg (c/kWh)": wprice(l12),
            "RES latest month 2026-07 (c/kWh)": (wprice(latest) if st == "US" else latest.price_cents_per_kwh.iloc[0]),
            "Latest-12 months complete": "yes" if nmonths == 12 else f"no ({nmonths}/12)",
        })
    s = pd.DataFrame(srows).merge(reg, left_on="State", right_on="state", how="left").drop(columns="state")
    s["primary_region"] = s.primary_region.fillna("US total")
    s["multi_region"] = s.multi_region.map({1: "yes", 0: "no"}).fillna("n/a")
    s = s.rename(columns={"primary_region": "Grid region (primary)", "multi_region": "Split across regions"})
    s.to_csv(OUT / "states_summary.csv", index=False)

    cpi = pd.read_csv(ROOT / "data" / "raw" / "cpi_cpiaucsl.csv")
    cpi.columns = ["date", "cpi"]
    cpi["cpi"] = pd.to_numeric(cpi.cpi, errors="coerce")
    cpi = cpi.set_index(pd.to_datetime(cpi.date)).cpi.resample("MS").mean().interpolate()  # Oct-2025 gap
    out = [{"Period": str(y), "CPI-U avg": round(cpi[str(y)].mean(), 3)} for y in range(2001, 2026)]
    out.append({"Period": "2026 YTD (Jan-Jul)", "CPI-U avg": round(cpi["2026-01":"2026-07"].mean(), 3)})
    out.append({"Period": "Latest-12 (2025-08..2026-07)", "CPI-U avg": round(cpi["2025-08":"2026-07"].mean(), 3)})
    pd.DataFrame(out).to_csv(OUT / "cpi_annual.csv", index=False)
    print(len(ann), len(s), len(out))


if __name__ == "__main__":
    main()
