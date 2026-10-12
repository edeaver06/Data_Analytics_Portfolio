"""Download FAA Service Difficulty Reports (public query at sdrs.faa.gov) in date windows.

The public query caps results at 1,500 rows, so windows that hit the cap are split in half.
Each window is saved as data/raw/sdrs/sdr_<from>_<to>.parquet. Re-runs skip finished windows.
"""
import sys, io, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd, requests
from bs4 import BeautifulSoup

URL = "https://sdrs.faa.gov/Query.aspx"
P = "ctl00$pageContentPlaceHolder$"
OUT = Path(__file__).resolve().parents[1] / "data/raw/sdrs"
CAP = 1500

def _form(soup, skip=("submit", "checkbox", "image")):
    return {i["name"]: i.get("value", "") for i in soup.select("input[name]") if i.get("type") not in skip}

def query(d0: dt.date, d1: dt.date) -> pd.DataFrame:
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 (portfolio research; contact via GitHub)"
    soup = BeautifulSoup(s.get(URL, timeout=120).text, "lxml")
    f = _form(soup)
    f[P + "tbDifficultyDateFrom"] = d0.strftime("%m/%d/%Y"); f[P + "tbDifficultyDateTo"] = d1.strftime("%m/%d/%Y")
    f[P + "btnQuery"] = "Query"
    soup = BeautifulSoup(s.post(URL, data=f, timeout=600).text, "lxml")
    boxes = soup.select("input[type=checkbox]")
    if len(boxes) <= 1:
        return pd.DataFrame()
    f = _form(soup)
    for b in boxes: f[b["name"]] = "on"
    f[P + "btnDownload"] = "Download"
    r = s.post(URL, data=f, timeout=900); r.raise_for_status()
    return pd.read_html(io.StringIO(r.text))[0].astype(str)

def window(d0, d1):
    out = OUT / f"sdr_{d0}_{d1}.parquet"
    if out.exists(): return
    for attempt in range(3):
        try:
            df = query(d0, d1); break
        except Exception as e:
            print("retry", d0, d1, e, flush=True); time.sleep(20)
    else:
        print("FAILED", d0, d1, flush=True); return
    if len(df) >= CAP and d0 < d1:
        mid = d0 + (d1 - d0) // 2
        window(d0, mid); window(mid + dt.timedelta(days=1), d1); return
    if len(df) >= CAP: print("WARNING single day at cap", d0, flush=True)
    df.to_parquet(out); print(d0, d1, len(df), flush=True)

def main(start="2025-01-01", end="2025-12-31", step=5, workers=3):
    OUT.mkdir(parents=True, exist_ok=True)
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    wins = []
    while a <= b:
        e = min(a + dt.timedelta(days=step - 1), b); wins.append((a, e)); a = e + dt.timedelta(days=1)
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda w: window(*w), wins))

if __name__ == "__main__":
    main(*sys.argv[1:3]) if len(sys.argv) > 2 else main()
