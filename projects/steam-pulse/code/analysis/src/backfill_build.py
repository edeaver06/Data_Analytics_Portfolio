"""Parse raw backfill responses into parquet tables in data/backfill/tables/. Pure parsing, no imputation."""
import re, json, pathlib, zipfile, io, datetime as dt
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]; B = ROOT / "data" / "backfill"; T = B / "tables"

ROW = re.compile(r'<td class="month-cell left">\s*([A-Za-z]+ \d{4})\s*</td>\s*<td class="right num-f">([\d.]+)</td>.*?<td class="right num">(\d+)</td>', re.S)

def parse_steamcharts(html: str, appid: int) -> pd.DataFrame:
    rows = [(appid, pd.to_datetime(m, format="%B %Y").date(), float(a), int(p)) for m, a, p in ROW.findall(html)]
    return pd.DataFrame(rows, columns=["appid", "month", "avg_players", "peak_players"])

def parse_reviews(js: str, appid: int) -> pd.DataFrame:
    """Steam returns rollup_type 'month' (most apps) or 'week' (young apps, 7-day non-overlapping buckets keyed by week start).
    Weekly buckets are SUMMED into the month of their start date (a week straddling a month boundary is attributed to its start month)."""
    cols = ["appid", "month", "up", "down", "n_buckets", "rollup_type"]
    try: r = json.loads(js)["results"]
    except Exception: return pd.DataFrame(columns=cols)
    rows = [(appid, dt.datetime.fromtimestamp(x["date"], dt.UTC).date().replace(day=1), x["recommendations_up"], x["recommendations_down"]) for x in r.get("rollups", [])]
    d = pd.DataFrame(rows, columns=["appid", "month", "up", "down"])
    if d.empty: return pd.DataFrame(columns=cols)
    d = d.groupby(["appid", "month"], as_index=False).agg(up=("up", "sum"), down=("down", "sum"), n_buckets=("up", "size"))
    d["rollup_type"] = r.get("rollup_type"); return d

def build_mendeley():
    """Mendeley ycy3sy3vj2 (CC BY 4.0). Unzips to mendeley/x/ and aggregates hourly -> daily with DuckDB."""
    import duckdb, subprocess
    M = B / "mendeley"; X = M / "x"; X.mkdir(exist_ok=True)
    for z in ["PriceHistory.zip", "PlayerCountHistoryPart1.zip", "PlayerCountHistoryPart2.zip"]:
        if (M / z).exists() and not (X / z.replace(".zip", "")).exists(): subprocess.run(["unzip", "-q", "-o", str(M / z), "-d", str(X)], check=True)
    c = duckdb.connect()
    c.execute(f"""copy (select cast(regexp_extract(filename, '(\\d+)\\.csv', 1) as int) appid, "Date"::date date, Initialprice initialprice, Finalprice finalprice, Discount discount
        from read_csv('{X}/PriceHistory/*.csv', filename=true, header=true, delim=',', columns={{'Date':'VARCHAR','Initialprice':'DOUBLE','Finalprice':'DOUBLE','Discount':'DOUBLE'}}, ignore_errors=true, strict_mode=false)) to '{T}/mendeley_price_daily.parquet'""")
    c.execute(f"""copy (select cast(regexp_extract(filename, '(\\d+)\\.csv', 1) as int) appid, cast("Time" as timestamp)::date date,
        avg(Playercount) avg_players, max(Playercount) peak_players, count(*) n_obs
        from read_csv('{X}/PlayerCountHistoryPart*/*.csv', filename=true, header=true, delim=',', columns={{'Time':'VARCHAR','Playercount':'DOUBLE'}}, ignore_errors=true, strict_mode=false) group by all)
        to '{T}/mendeley_players_daily.parquet'""")
    pd.read_csv(M / "applicationInformation.csv", encoding="latin-1").to_parquet(T / "mendeley_app_info.parquet")
    return {k: c.sql(f"select count(*), count(distinct appid), min(date), max(date) from '{T}/{k}.parquet'").fetchone() for k in ["mendeley_price_daily", "mendeley_players_daily"]}

def main():
    T.mkdir(exist_ok=True)
    sc = pd.concat([parse_steamcharts(f.read_text(), int(f.stem)) for f in (B / "steamcharts").glob("*.html") if f.stat().st_size])
    sc.to_parquet(T / "steamcharts_monthly.parquet")
    rv = pd.concat([parse_reviews(f.read_text(), int(f.stem)) for f in (B / "reviews").glob("*.json") if f.stat().st_size])
    rv.to_parquet(T / "reviews_monthly.parquet")
    import sys
    if "--mendeley" in sys.argv: print(build_mendeley()); return
    print({"sc_rows": len(sc), "sc_apps": sc.appid.nunique(), "rv_rows": len(rv), "rv_apps": rv.appid.nunique()})

if __name__ == "__main__": main()
