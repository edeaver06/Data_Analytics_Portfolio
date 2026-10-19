# Aircraft Readiness: code and engineering notes

Everything technical lives here. For the recruiter summary see the [project page](../README.md). For the plain-English walkthrough see [STORY.md](../STORY.md). Run every command below from this `code/` folder.

## How to run
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
bash scripts/run.sh     # download FAA + NASA data, build the warehouse, 22 data-quality checks, exports, charts, pytest
```
- The SDR download is slow because the public query returns at most 1,500 rows per request. Six months takes 30–90 minutes depending on the FAA server, and it resumes where it stopped. Set the window with `SDR_START=2025-01-01 SDR_END=2025-06-29 bash scripts/run.sh`.
- Without raw data, `pytest` still runs the logic tests and the dashboard smoke tests, and skips the warehouse tests.

**Dashboard** (runs on the bundled extract, no build step, deployable to Streamlit Cloud with `app/requirements.txt`):
```bash
pip install -r app/requirements.txt
streamlit run app/streamlit_app.py
```

## What's in this folder (`code/`)
| Path | What it's for |
|---|---|
| `src/fetch_sdrs.py` | FAA SDRS downloader (5-day windows, splits windows that hit the 1,500-row cap) |
| `src/build.py` | Load raw → run SQL → synthetic layer → data-quality checks → exports (`data/export/`, `app/data/`) |
| `src/synthetic.py` | Clearly flagged simulated fleet (status, work orders, requisitions, backlog) |
| `src/make_figures.py` | README charts → `../images/` |
| `sql/` | `01_staging` → `02_dims` → `03_facts` → `04_kpis`. `sql/tests/` holds 22 checks, and each must return 0 rows |
| `app/` | Streamlit dashboard, its requirements and a 300 KB parquet extract |
| `data/ref/` | JASC/ATA codes (FAA), SDR code labels (inferred), GAO rates (verified) plus the raw table extract |
| `data/export/` | Model-ready parquet (tracked) and CSV (regenerated, gitignored) for BI tools such as Tableau |
| `data/raw/`, `data/*.duckdb` | *Not in git.* Re-created by `scripts/run.sh` |
| `docs/schema.md` | Star schema, relationships, KPI definitions, real vs approximated vs synthetic, column lists |
| `tests/` | pytest: windowing, repeat and interval logic on toy data, synthetic calibration, warehouse checks, export parity, dashboard smoke test |

## Data sources (verified 12 Oct 2026)
| Source | Access | Used for |
|---|---|---|
| FAA Service Difficulty Reporting System | Public query at sdrs.faa.gov, ≤1,500 rows per query, 76 fields. Public domain | `fct_discrepancy`, `fct_tail_interval` |
| FAA Aircraft Registry | `ReleasableAircraft.zip` (73 MB, daily) | `dim_aircraft` (96.4% of SDR tails matched) |
| FAA JASC code table | sdrs.faa.gov references | `dim_ata` |
| GAO-22-104533, Table 1 | Report PDF (Wayback Machine copy of gao.gov; gao.gov blocks scripted downloads) | `fct_mc_rate_benchmark`. All 8 goals and 56 rates checked against the PDF |
| NASA C-MAPSS | 12 MB zip, open | `fct_engine_run` |
| Not used | NTSB (accidents too rare), DLA requisitions (not public) | n/a |

## Design decisions
1. **SDRS plus the registry over C-MAPSS alone.** C-MAPSS is simulated sensor data with no maintenance records. SDRS is the only public, report-level maintenance-discrepancy source with aircraft hours and cycles.
2. **Star schema with one row per report.** `fct_discrepancy` sits at the SDR level (de-duplicated by operator control number), with conformed dimensions for date, aircraft, ATA system, operator, part, stage and precaution.
3. **Unknown members (key −1) instead of nulls.** 175 reports have no N-number and 578 have no operator. They point to `<UNKNOWN>` rows (key −1; `ata_key = 'UNK'` for missing codes), so every relationship in the star schema holds and totals reconcile.
4. **Code lookups are unique.** `dim_stage` and `dim_precaution` are unique on their code and cover every code seen in the facts. `dim_sdr_code` is unique on `code_key = code_type:code`.
5. **Inferred code meanings are flagged, never hidden.** The FAA doesn't publish precautionary-procedure meanings. Labels come from reading report text, and `label_basis` says whether each is inferred, unverified or Unknown (I, J and L stay Unknown).
6. **Operational repeats exclude inspection findings.** Counting heavy-check findings inflates the repeat rate to 39%, because one check spans several days. The headline 7.1% counts only problems that came up in operation.
7. **Hours between reports is labelled an approximation.** It uses aircraft total hours on each report and drops intervals where hours don't increase or exceed 20 hours a day. It is an upper bound on MTBF because only reportable problems count.
8. **The synthetic layer is separate, flagged and calibrated.** All `syn_*` tables carry `is_synthetic = TRUE`, aren't related to real aircraft, and list every assumption in `syn_assumptions`. They are tuned so the mission-capable rate falls inside the GAO range, and a data-quality check enforces 32–75% and at least 200 requisitions.
9. **GAO stays out of the dashboard.** Its numbers are in the warehouse and README only, at the project lead's request.
10. **DuckDB, mostly Postgres-compatible.** See `docs/schema.md` for the handful of DuckDB-specific functions and their Postgres equivalents.

## Synthetic fleet (demo data)
A 20-aircraft notional fleet for 2025, seed 42. Real inputs are the SDR disruption rate per flight hour and the ATA mix behind disruptions. It assumes 6-hour sorties flown on 30% of days, a 60× grounding-defect multiplier, phase inspections every 300 flight hours (median 14 days), 55% of failures needing a part, and a 9-day median lead time with a 7-day due date. Result: **MC 60.4%, NMCM 19.5%, NMCS 20.0%, MTBF 35.5 flight hours, MTTR 273 hours, 256 work orders, 321 requisitions (56% late), mean lead time 12.9 days, about 10 open requisitions a day.** For reference, GAO's FY2021 range for the 8 fleets is 32.4–71.1%, and the B-1B NMCS rate was 6.8–10.4% in FY2015–20, so supply downtime here is deliberately higher than the B-1B's. These are not findings.

## Caveats
- SDRs are reportable difficulties (14 CFR 121.703 / 135.415), mostly from airlines and charter operators, and military aircraft aren't included. Cross-operator comparisons partly measure reporting culture.
- The window runs 1 Jan – 29 Jun 2025 (the default end date; download windows are 5 days long).
- 22 reports have a submission date before the difficulty date. They're flagged as `is_date_anomaly` and excluded from lag statistics.
- The GAO goal column is the FY2021 goal. `met_goal` for earlier years compares against that same goal.
