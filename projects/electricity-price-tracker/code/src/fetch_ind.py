"""Fetch EIA monthly retail sales, INDUSTRIAL sector (IND), 51 states, 2021-01..2026-07.
Source: EIA API v2 electricity/retail-sales (public domain). Key from env EIA_API_KEY, never saved.
Raw: data/raw/retail_sales_ind_2021_2026.json"""
import json, os, re, sys, requests
STATES = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
p = [("api_key", os.environ["EIA_API_KEY"]), ("frequency", "monthly"), ("start", "2021-01"), ("end", "2026-07"),
     ("data[]", "price"), ("data[]", "sales"), ("data[]", "revenue"), ("facets[sectorid][]", "IND"), ("length", "5000")]
p += [("facets[stateid][]", s) for s in STATES]
r = requests.get("https://api.eia.gov/v2/electricity/retail-sales/data/", params=p, timeout=90)
if r.status_code != 200: sys.exit(re.sub(r"api_key=[^&\s]+", "api_key=REDACTED", f"HTTP {r.status_code} {r.text[:200]}"))
js = r.json(); js.get("request", {}).get("params", {}).pop("api_key", None)
json.dump(js, open("data/raw/retail_sales_ind_2021_2026.json", "w"))
print("rows", len(js["response"]["data"]), "total", js["response"]["total"])
