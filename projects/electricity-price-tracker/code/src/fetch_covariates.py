"""Fetch 2021 state generation mix (natural-gas share) from EIA API v2.
Source: https://api.eia.gov/v2/electricity/electric-power-operational-data/
  frequency=annual, sectorid=99 (all sectors), fueltypeid in {ALL, NNG (natural gas)}, year 2021.
Raw response saved to data/raw/eia_gen_mix_2021.json with api_key never written.
Key read from env EIA_API_KEY; never printed."""
import json, os, re, sys, requests
URL = "https://api.eia.gov/v2/electricity/electric-power-operational-data/data/"
def main():
    key = os.environ["EIA_API_KEY"]
    params = [("api_key", key), ("frequency", "annual"), ("start", "2021"), ("end", "2021"),
              ("data[]", "generation"), ("facets[sectorid][]", "99"),
              ("facets[fueltypeid][]", "ALL"), ("facets[fueltypeid][]", "NG"),
              ("length", "5000")]
    r = requests.get(URL, params=params, timeout=60)
    if r.status_code != 200:
        sys.exit(re.sub(r"api_key=[^&\s]+", "api_key=REDACTED", f"HTTP {r.status_code}: {r.text[:300]}"))
    js = r.json(); js.get("request", {}).get("params", {}).pop("api_key", None)
    os.makedirs("data/raw", exist_ok=True)
    with open("data/raw/eia_gen_mix_2021.json", "w") as f: json.dump(js, f)
    print("rows:", len(js["response"]["data"]))
if __name__ == "__main__": main()
