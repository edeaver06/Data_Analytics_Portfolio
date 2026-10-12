"""Polite backfill fetcher. Raw responses saved verbatim; parsing happens in backfill_build.py.
SteamCharts: no robots.txt (404) and no terms page as of 2026-10-12; 1 request / 1.5 s, identifying UA.
Steam appreviewhistogram: public store endpoint, 1 request / 1.2 s."""
import sys, time, pathlib, json, duckdb, requests
ROOT = pathlib.Path(__file__).resolve().parents[1]; OUT = ROOT / "data" / "backfill"
UA = {"User-Agent": "SteamPulse-portfolio-research/0.1 (contact via github; 1 req per 1.5s)"}
SRC = {"steamcharts": ("https://steamcharts.com/app/{}", "html", 1.5),
       "reviews": ("https://store.steampowered.com/appreviewhistogram/{}?l=english&review_score_preference=0", "json", 1.2)}

def appids():
    c = duckdb.connect(); c.execute(f"attach '{ROOT.parent / 'data' / 'steam_pulse.duckdb'}' as sp (read_only)")
    return [r[0] for r in c.sql("select distinct appid from steam_pulse.marts.dim_game order by appid").fetchall()]

def run(src):
    url, ext, delay = SRC[src]; s = requests.Session(); s.headers.update(UA)
    for a in appids():
        f = OUT / src / f"{a}.{ext}"
        if f.exists(): continue
        for attempt in range(3):
            try:
                r = s.get(url.format(a), timeout=30)
                if r.status_code == 429: time.sleep(60 * (attempt + 1)); continue
                f.write_text(r.text if r.ok else ""); break
            except requests.RequestException: time.sleep(10)
        time.sleep(delay)
    print("done", src)

if __name__ == "__main__": run(sys.argv[1])
