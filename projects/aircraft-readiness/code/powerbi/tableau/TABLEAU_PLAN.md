# Tableau Public plan: Aircraft Readiness

Tableau Public can't read parquet, so use the tidy CSVs in this folder. Each one is denormalized, so no joins are needed. **The CSVs are gitignored.** Rebuild them with `cd code && .venv/bin/python powerbi/build_powerbi.py`.

| File | Grain | Rows | Status |
|---|---|---|---|
| sdr_reports.csv | one FAA SDR, with aircraft, operator, ATA, part, stage and precaution labels joined (no narrative). Includes `precaution_label_basis` and `precaution_label_unverified` | 34,350 | real |
| tail_intervals.csv | consecutive reporting days on a tail, plus model | 13,355 | approximated |
| gao_mc_benchmark.csv | fleet x fiscal year, GAO-22-104533 Table 1 | 56 | real (verified) |
| engine_runs.csv | simulated engine (NASA C-MAPSS) | 709 | NASA simulation |
| SIMULATED_status_daily.csv | simulated tail x day | 7,300 | **synthetic** |
| SIMULATED_work_orders.csv | simulated work order | 256 | **synthetic** |
| SIMULATED_requisitions.csv | simulated requisition | 321 | **synthetic** |
| SIMULATED_backlog_daily.csv | day, fleet-level open and overdue requisitions | 365 | **synthetic** |

Add each file as its own data source. Relate the SIMULATED_* files only to each other (on Tail Id), and never to the real files.
Unknown members appear as `<UNKNOWN>` in n_number, operator_code and part_name. Exclude them from top-N rankings, but keep them in totals.

## Calculated fields
sdr_reports:
- `Reports` = `COUNTD([Sdr Id])`
- `Op Interruptions` = `SUM(INT([Is Operational Interruption]))`
- `Op Interruption Rate` = `[Op Interruptions] / [Reports]`
- `Unverified Interruptions` = `SUM(IIF([Is Operational Interruption] AND [Precaution Label Unverified], 1, 0))`
- `Unverified Share` = `[Unverified Interruptions] / [Op Interruptions]` (use it in footnotes)
- `Precaution Display` = `[Precaution Code] + " " + [Precaution Label] + IIF([Precaution Label Unverified], " †", "")`
- `Op Repeat Rate (30d)` = `SUM(INT([Is Repeat 30d])) / SUM(INT([Is In Operation]))`
- `Median Report Lag` = `MEDIAN([Report Lag Days])`
- `Lag > 3 Days %` = `SUM(IIF([Report Lag Days] > 3, 1, 0)) / [Reports]`
- `Known Aircraft` = `[N Number] != "<UNKNOWN>"` (filter for aircraft counts and rankings)
- `Date Basis` parameter (Difficulty / Submission), with `Report Date` = `IIF([Date Basis] = "Difficulty", [Difficulty Date], [Submission Date])`

tail_intervals (filter `Is Valid` = True on the data source):
- `Mean Hours Between Reports (approx MTBF)` = `SUM([Hours Between]) / COUNT([Hours Between])`
- `Hours per Op Interruption (approx)` = `SUM([Hours Between]) / SUM(INT([Ends In Interruption]))`

gao_mc_benchmark:
- `MC Rate` = `AVG([Mc Rate Pct]) / 100`, `Goal` = `AVG([Mc Goal Pct]) / 100`, `Gap pts` = `AVG([Gap To Goal Pts])`
- `Is B-1B` = `[Aircraft] = "B-1B"` (highlight color)

engine_runs: `Mean Cycles to Failure` = `AVG([Cycles To Failure])`, `Cycles CV` = `STDEV([Cycles To Failure]) / AVG([Cycles To Failure])`

SIMULATED_* (every field name starts with SIM):
- `SIM MC Rate` = `SUM(INT([Is Mission Capable])) / COUNT([Tail Id])`
- `SIM NMCM %` = `SUM(IIF([Status] = "NMCM", 1, 0)) / COUNT([Tail Id])`, and the same pattern for `SIM NMCS %`
- `SIM MTTR (h)` = `AVG(IIF([Work Type] = "Unscheduled repair", [Repair Hours], NULL))`
- `SIM MTBF (h)` = `TOTAL(SUM([Flight Hours]))` from status_daily / unscheduled work orders. Compute it as two BANs, or use the value from kpi_values.json (35.5).
- `SIM Late %` = `SUM(IIF([Backorder Days] > 0, 1, 0)) / COUNT([Requisition Id])`
- `SIM Backlog Age (weighted)` = `SUM([Open Requisitions] * [Avg Age Days]) / SUM([Open Requisitions])` (backlog_daily)

## Sheets
1. **KPI tiles**: Reports, Op Interruptions†, Op Interruption Rate†, Op Repeat Rate, Mean Hours Between Reports*, Median Report Lag. Add a caption with the † and * footnotes.
2. **Monthly trend**: Reports as bars and Op Interruptions as a line on a dual axis.
3. **Interruptions by ATA**: top 10 chapters.
4. **Interruptions by precaution code**: Precaution Display, colored by `Precaution Label Unverified` (inferred #0072B2, unverified #56B4E9).
5. **ATA trend**: top 5 chapters by month.
6. **Repeat rate by ATA**: In-op reports >= 100.
7. **Hours between reports by model**: >= 100 intervals.
8. **Top parts**: top 15, `<UNKNOWN>` excluded.
9. **Report lag by operator**: median and P90, top 10.
10. **SIM status mix**: monthly 100% stacked MC/NMCM/NMCS. Title starts with "SIMULATED:".
11. **SIM backlog over time**: area chart from SIMULATED_backlog_daily, with Open Requisitions and Overdue Requisitions. Title starts with "SIMULATED:".
12. **GAO FY2021 MC vs goal**: bars with a goal reference mark per row, B-1B highlighted, and a reference line at 60.4% labeled "simulated fleet". Title: "Real-world context: GAO fleet MC rates (real)".
13. **Engine life histogram**: bins of 15 cycles, colored by dataset.

## Dashboards (1280 x 720, Okabe-Ito colors: #0072B2, #E69F00, #009E73, #CC79A7, #56B4E9, #D55E00)
- **D1 Fleet reliability overview**: sheets 1, 2, 3, 4. Clicking an ATA bar filters sheet 2.
- **D2 Failure trends**: sheets 5, 6, 7, 8.
- **D3 Parts and components**: sheets 8, 9.
- **D4 Simulated fleet (demo data) and real-world context**: the yellow "SIMULATED DATA" banner and SIM tiles over sheets 10 and 11 on the left. Sheet 12 sits in a blue-bordered "Real-world context (real data)" container on the right.
- **D5 Engine health (optional)**: sheet 13.
- Footer on every dashboard: `Source: FAA SDR, FAA Registry, NASA C-MAPSS; analysis by Evan Deaver`. D4 adds "Simulated fleet: src/synthetic.py, seed 42 | Real-world context: GAO-22-104533".
- To publish, use **File > Save to Tableau Public**. The files are far below the 15M-row limit.
