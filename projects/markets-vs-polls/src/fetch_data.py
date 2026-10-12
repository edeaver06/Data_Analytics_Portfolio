"""Download all public raw data into data/raw/. Re-runnable; no API keys needed.
Sources: Polymarket Gamma + CLOB price history, Kalshi public API (historical candlesticks),
FiveThirtyEight 2024 president polls (Internet Archive snapshot), MIT Election Data + Science Lab (Harvard Dataverse)."""
import json, time, urllib.request, csv
from pathlib import Path
RAW = Path(__file__).resolve().parents[1] / "data/raw"
STATES = {"AL":"alabama","AK":"alaska","AZ":"arizona","AR":"arkansas","CA":"california","CO":"colorado","CT":"connecticut","DE":"delaware","DC":"district-of-columbia","FL":"florida","GA":"georgia","HI":"hawaii","ID":"idaho","IL":"illinois","IN":"indiana","IA":"iowa","KS":"kansas","KY":"kentucky","LA":"louisiana","ME":"maine","MD":"maryland","MA":"massachusetts","MI":"michigan","MN":"minnesota","MS":"mississippi","MO":"missouri","MT":"montana","NE":"nebraska","NV":"nevada","NH":"new-hampshire","NJ":"new-jersey","NM":"new-mexico","NY":"new-york","NC":"north-carolina","ND":"north-dakota","OH":"ohio","OK":"oklahoma","OR":"oregon","PA":"pennsylvania","RI":"rhode-island","SC":"south-carolina","SD":"south-dakota","TN":"tennessee","TX":"texas","UT":"utah","VT":"vermont","VA":"virginia","WA":"washington","WV":"west-virginia","WI":"wisconsin","WY":"wyoming"}
START, END = 1727740800, 1730851200  # 2024-10-01 .. 2024-11-06 UTC

def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "portfolio-research"}), timeout=60) as r:
                return r.read()
        except Exception as e:
            if i == 3: print("FAIL", url, e); return None
            time.sleep(2 * (i + 1))

def fetch_files():
    for name, url in {"polls_538_2024.csv": "https://web.archive.org/web/2024id_/https://projects.fivethirtyeight.com/polls/data/president_polls.csv",
                      "mit_president_1976_2024.csv": "https://dataverse.harvard.edu/api/access/datafile/13887042"}.items():
        if not (RAW / name).exists(): (RAW / name).write_bytes(get(url))

def fetch_markets():
    rows, log = [], []
    for st, slug in STATES.items():
        # Polymarket: "Will a Republican win <State>?" YES token
        ev = json.loads(get(f"https://gamma-api.polymarket.com/events?slug={slug}-presidential-election-winner") or b"[]")
        pm = [m for e in ev for m in e["markets"] if "Republican win" in m["question"]]
        if pm:
            tok = json.loads(pm[0]["clobTokenIds"])[0]
            h = json.loads(get(f"https://clob.polymarket.com/prices-history?market={tok}&interval=max&fidelity=1440") or b"{}").get("history", [])
            rows += [("polymarket", st, p["t"], p["p"]) for p in h if START <= p["t"] <= END]
        log.append(("polymarket", st, bool(pm)))
        # Kalshi: PRESPARTY<ST>-24-R (Republican wins state)
        k = json.loads(get(f"https://api.elections.kalshi.com/trade-api/v2/historical/markets/PRESPARTY{st}-24-R/candlesticks?start_ts={START}&end_ts={END}&period_interval=1440") or b"{}").get("candlesticks", [])
        rows += [("kalshi", st, c["end_period_ts"], float(c["price"]["close"])) for c in k if c["price"]["close"] is not None]
        log.append(("kalshi", st, bool(k)))
        time.sleep(0.3)
    with open(RAW / "market_prices_daily.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["source", "state_po", "ts", "p_rep"]); w.writerows(rows)
    with open(RAW / "market_coverage.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["source", "state_po", "found"]); w.writerows(log)

if __name__ == "__main__":
    fetch_files(); fetch_markets()
