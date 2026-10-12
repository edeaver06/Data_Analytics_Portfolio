"""Google Fiber FCR metrics: loading, cleaning, and summary tables (pandas)."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
MARKETS = ["market_1", "market_2", "market_3"]
REPEAT_COLS = [f"contacts_n_{i}" for i in range(1, 8)]

# Category mapping. The case-study data only ships anonymized codes (type_1..type_5);
# these labels follow the Google Data Analytics certificate case-study brief.
PROBLEM_MAP = {
    "type_1": "Account Management & Billing",
    "type_2": "Technical Troubleshooting",
    "type_3": "Scheduling",
    "type_4": "Construction",
    "type_5": "Wi-Fi & Internet",
}


def load_data(data_dir=RAW_DIR):
    """Load market_1..3 CSVs. Raises FileNotFoundError if any is missing (no fallback data)."""
    data_dir = Path(data_dir)
    missing = [m for m in MARKETS if not (data_dir / f"{m}.csv").exists()]
    if missing:
        raise FileNotFoundError(f"Missing raw CSVs in {data_dir}: {missing}. "
                                "Place market_1.csv, market_2.csv, market_3.csv there.")
    return pd.concat([pd.read_csv(data_dir / f"{m}.csv") for m in MARKETS], ignore_index=True)


def preprocess(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date_created"])
    df["market"] = df["new_market"]
    df["problem_category"] = df["new_type"].map(PROBLEM_MAP)
    if df["problem_category"].isna().any():
        raise ValueError(f"Unmapped types: {df.loc[df.problem_category.isna(), 'new_type'].unique()}")
    df[["contacts_n"] + REPEAT_COLS] = df[["contacts_n"] + REPEAT_COLS].fillna(0)
    df["repeat_calls"] = df[REPEAT_COLS].sum(axis=1)
    return df


def _rates(g):
    g["repeat_rate_pct"] = (g["repeat_calls"] / g["first_calls"] * 100).round(1)
    g["fcr_pct"] = (100 - g["repeat_rate_pct"]).round(1)
    return g


def summary_by_category(df):
    g = df.groupby("problem_category").agg(first_calls=("contacts_n", "sum"),
                                           repeat_calls=("repeat_calls", "sum")).astype(int).reset_index()
    g = _rates(g)
    g["pct_of_total_repeats"] = (g["repeat_calls"] / g["repeat_calls"].sum() * 100).round(1)
    return g.sort_values("repeat_rate_pct", ascending=False).reset_index(drop=True)


def summary_by_market(df, by_category=False):
    keys = ["market", "problem_category"] if by_category else ["market"]
    g = df.groupby(keys).agg(first_calls=("contacts_n", "sum"),
                             repeat_calls=("repeat_calls", "sum")).astype(int).reset_index()
    return _rates(g)


def weekly_trend(df):
    w = df.assign(week=df["date"].dt.to_period("W-SUN").dt.start_time).groupby("week").agg(
        first_calls=("contacts_n", "sum"), repeat_calls=("repeat_calls", "sum")).astype(int).reset_index()
    w = _rates(w)
    w["wow_repeat_rate_change_pts"] = w["repeat_rate_pct"].diff().round(1)
    return w


if __name__ == "__main__":
    d = preprocess(load_data())
    print(len(d), d.date.min().date(), d.date.max().date())
    print(summary_by_category(d).to_string(index=False))
    print(summary_by_market(d).to_string(index=False))
