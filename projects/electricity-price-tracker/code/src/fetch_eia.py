"""Step 1: download monthly retail electricity sales from the EIA API v2.

Plain English: EIA only returns 5,000 rows per request, so we ask for page 1
(offset 0), then page 2 (offset 5000), and so on, until we have every row EIA
says exists ("total"). The raw pages are saved untouched under data/raw/.
The API key comes from the EIA_API_KEY environment variable and is never
printed or saved.
"""
import json
import os
import re
import time
from pathlib import Path

import requests

from states import STATES, SECTORS

URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"
PAGE_SIZE = 5000          # EIA's maximum rows per JSON response
START = "2001-01"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def redact(text: str) -> str:
    """Hide the API key if it ever appears in a URL or error message."""
    return re.sub(r"api_key=[^&\s]+", "api_key=REDACTED", str(text))


def build_params(api_key, offset, length=PAGE_SIZE):
    """Query parameters for one page. Sorting makes paging stable (no gaps/dupes)."""
    params = [("api_key", api_key), ("frequency", "monthly"), ("start", START),
              ("offset", offset), ("length", length)]
    for i, col in enumerate(["price", "sales", "revenue", "customers"]):
        params.append((f"data[{i}]", col))
    for s in STATES:
        params.append(("facets[stateid][]", s))
    for s in SECTORS:
        params.append(("facets[sectorid][]", s))
    for i, col in enumerate(["period", "stateid", "sectorid"]):
        params += [(f"sort[{i}][column]", col), (f"sort[{i}][direction]", "asc")]
    return params


def _get_with_retry(get, params, tries=3):
    """EIA sometimes times out; try up to 3 times before giving up."""
    for attempt in range(1, tries + 1):
        try:
            resp = get(URL, params=params, timeout=120)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt == tries:
                raise RuntimeError(redact(e)) from None
            time.sleep(5 * attempt)


def fetch_all(api_key, get=requests.get, page_size=PAGE_SIZE):
    """Page through the API. Returns (rows, reported_total, pages).

    `get` can be swapped for a fake in tests so no network is needed.
    """
    rows, pages, offset, total = [], [], 0, None
    while True:
        resp = _get_with_retry(get, build_params(api_key, offset, page_size))
        body = resp.json()["response"]
        total = int(body["total"])          # EIA sends total as a string
        batch = body["data"]
        pages.append(body)
        rows.extend(batch)
        offset += len(batch)
        if not batch or offset >= total:
            break
    if len(rows) != total:
        raise RuntimeError(f"Row count mismatch: got {len(rows)}, EIA reported {total}")
    return rows, total, pages


def main():
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        raise SystemExit("EIA_API_KEY is not set. Get a free key at https://www.eia.gov/opendata/register.php")
    rows, total, pages = fetch_all(api_key)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(pages):
        page = {k: v for k, v in page.items() if k != "request"}  # drop echoed params
        (RAW_DIR / f"retail_sales_page_{i:02d}.json").write_text(json.dumps(page))
    (RAW_DIR / "retail_sales_all.json").write_text(json.dumps(rows))
    print(f"Fetched {len(rows)} rows in {len(pages)} pages (EIA reported total {total}).")


if __name__ == "__main__":
    main()
