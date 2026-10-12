# Star schema, KPI definitions and Power BI hand-off

Paths are relative to `code/`. Warehouse: `data/aircraft_readiness.duckdb`, schema `mart` (staging in `stg`, raw loads in `raw`).
Model-ready exports: `data/export/<table>.parquet` (all tables) and `.csv` (all except `fct_discrepancy.csv`, which is gitignored at 15 MB; use the parquet).
DDL: `sql/01_staging.sql` → `sql/02_dims.sql` → `sql/03_facts.sql` → `sql/04_kpis.sql`; synthetic layer in `src/synthetic.py`. The SQL is plain DuckDB. The Postgres-incompatible bits are `DISTINCT ON` (Postgres has it too), `strptime`/`try_strptime` (use `to_date`), `arg_max` (use `DISTINCT ON`), `UNPIVOT` (use `UNION ALL`), `median`/`quantile_cont` (use `percentile_cont`), and `range()` (use `generate_series`).

## Diagram
```
                 dim_date (date_key)
                    │   ▲ submission_date_key (inactive relationship)
                    │ difficulty_date_key
dim_aircraft ──< fct_discrepancy >── dim_ata (ata_key = 4-digit JASC; ata_chapter = 2-digit ATA)
 (aircraft_key)     │        │
                    │        └──── dim_part (part_key)
              dim_operator (operator_key)

dim_aircraft ──< fct_tail_interval >── dim_date (to_date_key)
fct_engine_run            (stand-alone, NASA C-MAPSS)
fct_mc_rate_benchmark     (stand-alone, GAO; join on fiscal_year to dim_date.us_fiscal_year if wanted)
syn_dim_tail ──< syn_fct_status_daily / syn_fct_work_order / syn_fct_requisition   (SYNTHETIC, tail_id)
syn_fct_status_daily.date_key ── dim_date only overlaps for 2025 dates
dim_stage (stage_code) ──< fct_discrepancy >── dim_precaution (precaution_code)
syn_fct_backlog_daily (SYNTHETIC, one row per day: open / overdue requisitions)
```

### Unknown members
Every fact foreign key is non-null. Reports with no N-number (175) point to `dim_aircraft.aircraft_key = -1`, reports with no operator (578) to `dim_operator.operator_key = -1`, and reports with no part name to `dim_part.part_key = -1`. These members are labelled `<UNKNOWN>`, with angle brackets so they can't collide with a literal "UNKNOWN" typed on a report. Missing JASC codes use `dim_ata.ata_key = 'UNK'` and missing stage or precaution codes use `'-1'`. Filter on `aircraft_key <> -1` when a visual needs real aircraft only.

### Code lookups
`dim_stage` (unique on `stage_code`) and `dim_precaution` (unique on `precaution_code`, with `is_operational_interruption`) are the dimensions to relate. `dim_sdr_code` is a reference list unique on `code_key` (`stage:IN`, `precaution:K`, …). Labels for precaution codes B, F, G and H are inferred from report text but unverified against an FAA code list. I, J and L are labelled `Unknown` (87 reports across F–L). `label_basis` records this.

Power BI relationships: all one-to-many, single direction, dim → fact. Make `difficulty_date_key` the active date relationship; `submission_date_key` inactive (use `USERELATIONSHIP` for a "by submission date" view). Do **not** relate synthetic tables to `dim_aircraft`; they are a separate fleet (`SIM-01`…`SIM-20`).

## What each requested measure is built from

| Requested measure | Status | How |
|---|---|---|
| Aircraft status with time in status (MC / NMC) | **Synthetic only** | No public source publishes tail-level status. `syn_fct_status_daily` (one row per simulated tail per day: `status` MC/NMCM/NMCS, `reason_ata_chapter` ('05' = phase inspection), `reason_type`, `flight_hours`). Calibrated to MC ≈ 60% (GAO FY2021 range 32–71%). Fleet-level **real** MC rates are in `fct_mc_rate_benchmark` (GAO, annual, 8 fleets FY2015–21). |
| NMCM vs NMCS reason codes | **Synthetic only** | NMCS = days waiting for a simulated part, NMCM = hands-on repair days. Reason = ATA chapter, drawn from the **real** mix of ATA chapters behind SDR operational interruptions. |
| Failure events + flight hours for MTBF | **Approximated (real data)** | SDRs carry aircraft total hours and cycles at each report. `fct_tail_interval` = hours/cycles flown between consecutive reporting days on the same tail. "MTBR" = Σ hours_between / count of intervals (valid only). Caveat: an SDR is a *reportable* difficulty, not every failure, so this is mean time between **reported** difficulties, an upper bound on true MTBF. Real engine MTBF in cycles: `fct_engine_run` (C-MAPSS simulation). Synthetic MTBF: `syn_kpi_fleet.mtbf_flight_hours`. |
| Work-order open/close for MTTR | **Unavailable in public data → synthetic** | SDRs have no repair start/finish. `syn_fct_work_order` (`opened_at`, `closed_at`, `awaiting_parts_days`, `hands_on_days`, `repair_hours`). MTTR = avg(repair_hours). |
| Requisition dates, due/receipt, backlog age, backorder days | **Unavailable in public data → synthetic** | DLA requisition data is not public. `syn_fct_requisition` (≈320 rows: `priority` MICAP/Routine, `requisition_date`, `due_date`, `receipt_date`, `lead_time_days`, `backorder_days`). `syn_fct_backlog_daily` precomputes open / overdue requisitions and average age per day (open = requisition_date ≤ D < receipt_date). The closest **real** proxies: `kpi_top_parts` (which parts fail most = demand signal) and `kpi_report_lag` (event → FAA submission days, a reporting backlog). |
| Repeat discrepancies | **Real** | `fct_discrepancy.is_repeat_30d`: a report that arose in operation (stage ≠ inspection) with an earlier in-operation report on the same tail and same ATA chapter in the previous 30 days. `is_repeat_30d_any` includes inspection findings (inflated by multi-day heavy checks; don't headline it). |
| Operational interruptions (readiness impact proxy) | **Real, codes inferred** | `is_operational_interruption` = precautionary procedure code not K (none) or O (other): unscheduled landing, aborted takeoff, return to gate, engine shutdown. Code meanings are **inferred from narratives**; the FAA's published layout doesn't decode them (`dim_sdr_code.label_basis`). |

## Sources per table
| Table | Source | Licence / access |
|---|---|---|
| `fct_discrepancy`, `fct_tail_interval`, `dim_operator`, `dim_part` | FAA Service Difficulty Reporting System (sdrs.faa.gov public query, 1 Jan – 29 Jun 2025) | US Government work, public domain. No bulk file; the query returns ≤1,500 rows, so `src/fetch_sdrs.py` downloads 5-day windows |
| `dim_aircraft` | SDRS + FAA Aircraft Registry (`ReleasableAircraft.zip`: MASTER, ACFTREF; snapshot 9 Oct 2026) | Public domain; ~73 MB zip |
| `dim_ata` | FAA JASC code table (sdrs.faa.gov/documents/JASC_Code.doc) → `data/ref/jasc_codes.csv` | Public domain |
| `dim_sdr_code` | Hand-built from narrative samples → `data/ref/sdr_code_labels.csv` | Inferred, flagged per row |
| `fct_engine_run` | NASA C-MAPSS Turbofan Engine Degradation Simulation (train FD001–FD004) | NASA open data; simulation, not field data |
| `fct_mc_rate_benchmark` | GAO-22-104533 Table 1 → `data/ref/gao_mission_capable_rates.csv` | Public. All 8 goals and 56 rates checked against the report PDF on 12 Oct 2026; raw extract in `data/ref/gao_22_104533_table1_extract.txt`. Goal = FY2021 goal |
| `syn_*` | `src/synthetic.py`, seed 42 | **Synthetic.** Every row has `is_synthetic = TRUE`; assumptions in `syn_assumptions` |

Considered and not used: **NTSB** accident database (Access `.mdb`, accidents only, too rare for KPIs); **DLA** requisition / backorder data (not public at line level); **DoD MC rates** beyond GAO tables (the Air Force stopped publishing tail-level rates; only GAO / press summaries).

## KPI definitions (DAX-ready)
| KPI | Definition | Table |
|---|---|---|
| Reports | COUNTROWS(fct_discrepancy) | real |
| Operational interruption rate | % of reports with is_operational_interruption | real |
| Operational repeat rate | SUM(is_repeat_30d) / SUM(is_in_operation) | real |
| MTBR (hours) | SUM(hours_between) / COUNTROWS, filtered is_valid = TRUE | real, approximation of MTBF |
| Hours per operational interruption | SUM(hours_between) / SUM(ends_in_interruption), is_valid | real, approximation |
| Median report lag | MEDIAN(report_lag_days) | real |
| Engine mean cycles to failure | AVERAGE(fct_engine_run.cycles_to_failure) | real simulation |
| MC rate vs goal | mc_rate_pct − mc_goal_pct | real benchmark (GAO) |
| MC / NMCM / NMCS % | share of syn_fct_status_daily rows by status | **synthetic** |
| MTTR (hours) | AVERAGE(syn_fct_work_order.repair_hours) | **synthetic** |
| Parts backlog / backorder days | open requisitions per day; AVERAGE(backorder_days) | **synthetic** |

Dashboard guidance: put synthetic visuals on their own page titled "Simulated fleet (demo data)", with a visible banner.

## Columns (generated from the warehouse)

#### `dim_date` (624 rows)
`date_key INTEGER`, `date DATE`, `year BIGINT`, `quarter BIGINT`, `month BIGINT`, `year_month VARCHAR`, `day_of_week BIGINT`, `day_name VARCHAR`, `us_fiscal_year BIGINT`

#### `dim_aircraft` (6,522 rows)
`aircraft_key BIGINT`, `n_number VARCHAR`, `make VARCHAR`, `model VARCHAR`, `fleet_class VARCHAR`, `serial VARCHAR`, `max_reported_hours DOUBLE`, `max_reported_cycles DOUBLE`, `year_mfr INTEGER`, `ref_mfr VARCHAR`, `ref_model VARCHAR`, `n_engines INTEGER`, `n_seats INTEGER`, `weight_class VARCHAR`, `registrant_state VARCHAR`, `in_current_registry BOOLEAN`

#### `dim_ata` (548 rows)
`ata_key VARCHAR`, `jasc_description VARCHAR`, `ata_chapter VARCHAR`, `ata_chapter_name VARCHAR`

#### `dim_operator` (165 rows)
`operator_key BIGINT`, `operator_code VARCHAR`, `sdr_count_total BIGINT`

#### `dim_part` (992 rows)
`part_key BIGINT`, `part_name VARCHAR`

#### `dim_stage` (14 rows)
`stage_code VARCHAR`, `stage_label VARCHAR`, `label_basis VARCHAR`, `is_in_operation BOOLEAN`

#### `dim_precaution` (13 rows)
`precaution_code VARCHAR`, `precaution_label VARCHAR`, `label_basis VARCHAR`, `is_operational_interruption BOOLEAN`

#### `dim_sdr_code` (23 rows)
`code_key VARCHAR`, `code_type VARCHAR`, `code VARCHAR`, `label VARCHAR`, `label_basis VARCHAR`

#### `fct_discrepancy` (34,350 rows)
`sdr_id VARCHAR`, `difficulty_date_key INTEGER`, `submission_date_key INTEGER`, `aircraft_key BIGINT`, `operator_key BIGINT`, `part_key BIGINT`, `ata_key VARCHAR`, `difficulty_date DATE`, `submission_date DATE`, `report_lag_days BIGINT`, `is_date_anomaly BOOLEAN`, `aircraft_total_hours DOUBLE`, `aircraft_total_cycles DOUBLE`, `stage_code VARCHAR`, `precaution_code VARCHAR`, `nature_code VARCHAR`, `discovered_code VARCHAR`, `part_condition VARCHAR`, `is_in_operation BOOLEAN`, `is_operational_interruption BOOLEAN`, `is_repeat_30d_any BOOLEAN`, `is_repeat_30d BOOLEAN`, `days_since_prev_same_ata BIGINT`, `discrepancy_text VARCHAR`, `is_synthetic BOOLEAN`

#### `fct_tail_interval` (13,355 rows)
`aircraft_key BIGINT`, `from_date DATE`, `to_date DATE`, `to_date_key INTEGER`, `hours_between DOUBLE`, `cycles_between DOUBLE`, `days_between BIGINT`, `ends_in_interruption BOOLEAN`, `is_valid BOOLEAN`

#### `fct_engine_run` (709 rows)
`dataset VARCHAR`, `unit BIGINT`, `cycles_to_failure BIGINT`, `is_synthetic_data_source BOOLEAN`

#### `fct_mc_rate_benchmark` (56 rows)
`aircraft VARCHAR`, `service VARCHAR`, `mc_goal_pct BIGINT`, `fiscal_year INTEGER`, `mc_rate_pct DOUBLE`, `gap_to_goal_pts DOUBLE`, `met_goal BOOLEAN`, `source VARCHAR`

#### `syn_dim_tail` (20 rows)
`tail_id VARCHAR`, `is_synthetic BOOLEAN`

#### `syn_fct_status_daily` (7,300 rows)
`tail_id VARCHAR`, `date_key BIGINT`, `date DATE`, `status VARCHAR`, `is_mission_capable BOOLEAN`, `reason_ata_chapter VARCHAR`, `reason_type VARCHAR`, `flight_hours DOUBLE`, `is_synthetic BOOLEAN`

#### `syn_fct_work_order` (256 rows)
`work_order_id BIGINT`, `tail_id VARCHAR`, `ata_chapter VARCHAR`, `work_type VARCHAR`, `opened_at TIMESTAMP_NS`, `closed_at TIMESTAMP_NS`, `awaiting_parts_days DOUBLE`, `hands_on_days DOUBLE`, `repair_hours DOUBLE`, `is_synthetic BOOLEAN`

#### `syn_fct_requisition` (321 rows)
`requisition_id BIGINT`, `work_order_id BIGINT`, `tail_id VARCHAR`, `ata_chapter VARCHAR`, `priority VARCHAR`, `requisition_date DATE`, `due_date DATE`, `receipt_date DATE`, `lead_time_days DOUBLE`, `backorder_days DOUBLE`, `is_synthetic BOOLEAN`

#### `syn_fct_backlog_daily` (365 rows)
`date_key BIGINT`, `date DATE`, `open_requisitions BIGINT`, `overdue_requisitions BIGINT`, `avg_age_days DOUBLE`, `is_synthetic BOOLEAN`

#### `syn_assumptions` (14 rows)
`parameter VARCHAR`, `value VARCHAR`, `note VARCHAR`

#### `syn_kpi_fleet` (1 rows)
`data_flag VARCHAR`, `mc_rate_pct DOUBLE`, `nmcm_pct DOUBLE`, `nmcs_pct DOUBLE`, `total_flight_hours DOUBLE`, `mtbf_flight_hours DOUBLE`, `mttr_hours DOUBLE`, `work_orders BIGINT`, `requisitions BIGINT`, `mean_parts_lead_days DOUBLE`, `pct_requisitions_late DOUBLE`, `avg_open_requisitions DOUBLE`, `is_synthetic BOOLEAN`

#### `kpi_mtbr_by_model` (77 rows)
`make VARCHAR`, `model VARCHAR`, `intervals BIGINT`, `tails BIGINT`, `mtbr_hours DOUBLE`, `median_hours_between DOUBLE`, `mean_cycles_between DOUBLE`, `hours_per_operational_interruption DOUBLE`

#### `kpi_repeat_by_ata` (34 rows)
`ata_chapter VARCHAR`, `ata_chapter_name VARCHAR`, `reports BIGINT`, `repeats_any HUGEINT`, `repeat_rate_any_pct DOUBLE`, `in_operation_reports HUGEINT`, `operational_repeats HUGEINT`, `operational_repeat_rate_pct DOUBLE`, `interruption_rate_pct DOUBLE`

#### `kpi_monthly` (6 rows)
`year_month VARCHAR`, `reports BIGINT`, `tails_reporting BIGINT`, `operational_interruptions HUGEINT`, `operational_repeat_rate_pct DOUBLE`, `median_report_lag_days DOUBLE`

#### `kpi_report_lag` (36 rows)
`operator_code VARCHAR`, `reports BIGINT`, `median_lag_days DOUBLE`, `p90_lag_days DOUBLE`, `pct_over_3_days DOUBLE`

#### `kpi_top_parts` (50 rows)
`part_name VARCHAR`, `reports BIGINT`, `tails BIGINT`, `most_common_condition VARCHAR`, `interruption_rate_pct DOUBLE`

#### `kpi_engine_mtbf` (4 rows)
`dataset VARCHAR`, `engines BIGINT`, `mean_cycles_to_failure DOUBLE`, `min_cycles BIGINT`, `max_cycles BIGINT`, `coeff_variation DOUBLE`
