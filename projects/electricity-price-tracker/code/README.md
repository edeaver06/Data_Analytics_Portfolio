# Electricity Price Tracker

**Question:** Are AI data centers driving up state residential electricity prices?
This repo is the data pipeline: monthly EIA retail electricity data for all 50 states + DC, 2001-01 to the latest month, cleaned and loaded into SQLite, analyzed in Python, and summarized in a Google Sheets dashboard. Any link to data centers will be reported as association, not cause.

## Data
| Source | What | License |
|---|---|---|
| [EIA API v2 `electricity/retail-sales`](https://api.eia.gov/v2/electricity/retail-sales/) (forms EIA-826/861/861M) | Monthly price, sales, revenue and customers by state and sector (RES, COM, ALL) | US government, public domain |
| `data/seed/state_region.csv` (hand-built) | Each state's dominant ISO/RTO or regional grouping | Built for this project from public ISO/RTO footprint maps. No PUDL data is copied in yet; if PUDL balancing-authority codes are added, credit Catalyst Cooperative's PUDL (CC-BY-4.0). |
| EPRI *Powering Intelligence* | State data-center load estimates | **Copyrighted. No EPRI data is stored in this repo.** EPRI figures appear only as cited numbers in the write-up. |

Pulled 2026-10-21: 46,971 rows (51 states x 3 sectors x 307 months, 2001-01 to 2026-07). That matches the API's reported total.

### Data-center atlas (ODbL)
`data/raw/im3_open_source_data_center_atlas_v2026.02.09.csv` comes from the PNNL IM3 Open Source Data Center Atlas v2026.02.09 (https://doi.org/10.57931/3017294; record https://data.msdlive.org/records/p147s-4h760). Data-center locations are © OpenStreetMap contributors. It is available under the **Open Database License (ODbL) 1.0** (http://opendatacommons.org/licenses/odbl/1.0/). `data/clean/dc_state_estimates.csv` is a derived database and is shared under the ODbL.

## Pipeline
```
EIA API --(src/fetch_eia.py, pages of 5,000)--> data/raw/*.json (cached, gitignored)
        --(src/clean.py)--> data/clean/retail_sales_monthly.csv
        --(src/load_sqlite.py + sql/schema.sql)--> data/electricity.db
        --(src/quality_checks.py)--> PASS/FAIL report
```

## Tables (data/electricity.db)
**retail_sales_monthly**: one row per state + month + sector (primary key).
| column | type | unit / meaning |
|---|---|---|
| state, state_name | text | 2-letter code, 50 states + DC |
| sector, sector_name | text | RES residential, COM commercial, ALL all sectors |
| month | text date | first of month, YYYY-MM-DD |
| price_cents_per_kwh | real | average retail price, cents per kWh |
| sales_million_kwh | real | million kWh sold |
| revenue_million_usd | real | million US dollars |
| customers | integer | number of customers (NULL before 2008 or when withheld) |
| customers_not_collected | 0/1 | 1 = pre-2008 row where EIA reported 0 because it did not collect monthly counts |
| any_value_missing | 0/1 | 1 = at least one value blank |

**state_region**: one row per state (51). The columns are `primary_region`, `region_type` (ISO/RTO, non-RTO, isolated), `other_regions` and `multi_region`.
**v_residential_price**: a view with RES rows joined to the region tag.

## Cleaning decisions
- Numbers arrive as text and are converted. Blank or withheld values stay blank. Nothing is filled in.
- Customer counts of 0 before 2008-01 (12,852 rows) are recoded to NULL and flagged.
- 41 rows have other blank values. Most are Alaska in 2016 (RES sales/revenue/customers, and RES price for 2016-08 and 2016-09). The rest are RI COM 2024-11, plus NM RES 2026-04/05/06 and CO RES 2026-05 sales. They stay blank.
- If EIA ever changes the units, the pipeline stops rather than mix them.

## Google Sheets dashboard
`src/sheets_export.py` writes `data/clean/sheets/` (sales-weighted annual prices per state and year, a state summary, and CPI). Those feed a Google Sheet with a state dropdown driving XLOOKUP KPIs (latest price, change since 2001 in nominal and CPI-adjusted terms, rank of 51), a line chart, a ranked table with conditional formatting, and a region summary built with QUERY. Every KPI was checked against `data/electricity.db` (0 mismatches across 52 rows).

## Limitations
- Grid regions don't follow state lines. 19 states are flagged `multi_region` (e.g., IL = PJM + MISO; TX = ERCOT + SPP + MISO), and the primary region is a judgment call.
- MD RES 2026-03 is 35.85 c/kWh (+79% vs Feb, back to 22.07 in Apr). The live EIA API confirms that value, so it is kept and flagged.
- 2026 covers Jan-Jul only. CO (2026-05) and NM (2026-04..06) lack RES sales, so their 2026 averages leave those months out.
- EIA's commercial sector includes data centers but doesn't break them out. There is no official monthly state data-center series.

## Reproduce
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export EIA_API_KEY=...            # free key: https://www.eia.gov/opendata/register.php (or put it in .env; .env is gitignored)
.venv/bin/python src/run_pipeline.py          # add --skip-fetch to reuse cached raw JSON
.venv/bin/python -m pytest tests              # offline tests, no key needed
```

## Layout
`src/` Python steps · `sql/` schema · `data/seed/` region map · `data/clean/` clean CSV · `tests/` pytest · `notebooks/`, `app/` (placeholders) · `figures/` charts · `reports/` source research
