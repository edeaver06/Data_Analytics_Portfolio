"""Rural hospital financial warning signs pipeline: CMS Hospital Provider Cost Report (FY2023) -> SQLite -> clean CSVs."""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cr2023.csv"
DB = ROOT / "data/hospitals.db"
CLEAN = ROOT / "data/clean"
FOCUS = ["SD", "ND", "MN", "NE", "MT", "WY", "IA"]

COLS = {
    "Provider CCN": "ccn", "Hospital Name": "name", "City": "city", "State Code": "state",
    "County": "county", "Rural Versus Urban": "rural_urban", "CCN Facility Type": "facility_type",
    "Type of Control": "control", "Fiscal Year Begin Date": "fy_begin", "Fiscal Year End Date": "fy_end",
    "Number of Beds": "beds", "Total Days Title XVIII": "days_medicare", "Total Days Title XIX": "days_medicaid",
    "Total Days (V + XVIII + XIX + Unknown)": "days_total", "Net Patient Revenue": "net_patient_revenue",
    "Less Total Operating Expense": "operating_expense", "Net Income from Service to Patients": "operating_income",
    "Total Other Income": "other_income", "Net Income": "net_income", "Depreciation Cost": "depreciation",
    "Cash on Hand and in Banks": "cash", "Temporary Investments": "temp_investments",
    "Total Current Assets": "current_assets", "Total Current Liabilities": "current_liabilities",
    "Total Fund Balances": "fund_balance", "Cost of Uncompensated Care": "uncompensated_care",
}

def load_raw(path=RAW):
    df = pd.read_csv(path, low_memory=False, usecols=list(COLS)).rename(columns=COLS)
    df["ccn"] = df["ccn"].astype(str).str.zfill(6)
    for c in ["fy_begin", "fy_end"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def clean(df):
    df = df[df["facility_type"].isin(["STH", "CAH"])].copy()  # general acute + critical access
    df["fy_days"] = (df["fy_end"] - df["fy_begin"]).dt.days + 1
    # one report per hospital: keep the longest, then latest, period
    df = df.sort_values(["ccn", "fy_days", "fy_end"]).drop_duplicates("ccn", keep="last")
    df["full_year"] = df["fy_days"].between(350, 380)
    df["valid_financials"] = (df["net_patient_revenue"] >= 1_000_000) & (df["operating_expense"] > 0)
    npr = df["net_patient_revenue"].where(df["valid_financials"])
    df["patient_margin"] = df["operating_income"] / npr
    df["total_margin"] = df["net_income"] / (npr + df["other_income"].fillna(0))
    daily_exp = (df["operating_expense"] - df["depreciation"].fillna(0)) / df["fy_days"]
    liquid = df["cash"].fillna(0) + df["temp_investments"].fillna(0)
    df["days_cash"] = (liquid / daily_exp).where(df["valid_financials"] & (daily_exp > 0))
    df["current_ratio"] = (df["current_assets"] / df["current_liabilities"]).where((df["current_liabilities"] > 0) & (df["current_assets"] >= 0))
    tot = df["days_total"].where(df["days_total"] > 0)
    df["medicaid_share"] = df["days_medicaid"].fillna(0) / tot
    df["medicare_share"] = df["days_medicare"].fillna(0) / tot
    df["is_cah"] = df["facility_type"].eq("CAH")
    df["is_rural"] = df["rural_urban"].eq("R")
    df["focus_state"] = df["state"].isin(FOCUS)
    df["analysis_ok"] = (df["valid_financials"] & df["full_year"] & df["medicaid_share"].between(0, 1)
                        & df["patient_margin"].between(-1, 1) & df["total_margin"].between(-1, 1))
    return score(df)

def score(df):
    """Transparent 0-6 point rule score. Not a prediction of closure."""
    ok = df["analysis_ok"]
    p75 = df.loc[ok, "medicaid_share"].quantile(0.75)
    pts = pd.DataFrame(index=df.index)
    pts["pt_neg_total_margin"] = df["total_margin"] < 0
    pts["pt_deep_patient_loss"] = df["patient_margin"] < -0.10
    pts["pt_low_cash"] = df["days_cash"] < 30
    pts["pt_current_ratio"] = df["current_ratio"] < 1
    pts["pt_neg_equity"] = df["fund_balance"] < 0
    pts["pt_high_medicaid"] = df["medicaid_share"] >= p75
    for c in pts:
        df[c] = pts[c].astype(int)
    df["warning_score"] = pts.sum(axis=1).where(ok)
    df["warning_tier"] = pd.cut(df["warning_score"], [-1, 1, 3, 6], labels=["Few warning signs", "Some warning signs", "Many warning signs"]).astype(object)
    df.attrs["medicaid_p75"] = p75
    return df

OUT = ["ccn", "name", "city", "state", "county", "facility_type", "is_cah", "is_rural", "control", "beds",
       "fy_end", "net_patient_revenue", "patient_margin", "total_margin", "days_cash", "current_ratio",
       "medicaid_share", "medicare_share", "pt_neg_total_margin", "pt_deep_patient_loss", "pt_low_cash", "pt_current_ratio",
       "pt_neg_equity", "pt_high_medicaid", "warning_score", "warning_tier", "analysis_ok", "focus_state"]

def run():
    df = clean(load_raw())
    out = df[OUT].copy()
    out["fy_end"] = out["fy_end"].dt.date.astype(str)
    with sqlite3.connect(DB) as con:
        out.to_sql("hospitals", con, if_exists="replace", index=False)
        con.executescript((ROOT / "sql/views.sql").read_text())
        st = pd.read_sql("SELECT * FROM state_summary", con)
    CLEAN.mkdir(parents=True, exist_ok=True)
    out.to_csv(CLEAN / "hospitals_fy2023.csv", index=False)
    out[out.focus_state & out.analysis_ok].to_csv(CLEAN / "focus_hospitals.csv", index=False)
    st.to_csv(CLEAN / "state_summary.csv", index=False)
    print(len(out), "hospitals;", int(out.analysis_ok.sum()), "scored; medicaid p75 =", round(df.attrs["medicaid_p75"], 4))
    return out

if __name__ == "__main__":
    run()
