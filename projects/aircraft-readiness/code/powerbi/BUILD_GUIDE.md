# Build guide: Aircraft Readiness in Power BI Desktop (Windows)

## What's in `code/powerbi/`
| File | What it is |
|---|---|
| BUILD_GUIDE.md | This guide: import, model, measures, 5 pages, drill-through, publish |
| MODEL_SPEC.md | Star schema: tables, relationships, cardinality, date tables, unknown members |
| measures.dax | Every DAX measure, each with its definition and data status |
| theme.json | Colorblind-safe (Okabe-Ito) report theme |
| kpi_values.json | Expected KPI values, computed from the warehouse, for checking the build |
| mockups/ | **Design mockups** rendered with matplotlib from the real data. These are not Power BI screenshots |
| tableau/ | TABLEAU_PLAN.md plus tidy CSVs (gitignored; rebuilt by the script) |
| build_powerbi.py | Rebuilds tableau/*.csv, kpi_values.json and mockups/ from `code/data/aircraft_readiness.duckdb` (read-only) |

Run `cd code && .venv/bin/python powerbi/build_powerbi.py` after `src/build.py` refreshes the warehouse. The script checks its synthetic KPIs against `mart.syn_kpi_fleet`.

You'll need Power BI Desktop (free, from the Microsoft Store) and the folder `code/data/export/` copied to the PC. Allow about 2 to 3 hours.

## 1. Import the data
1. Copy `code/data/export/` to the PC, for example `C:\aircraft-readiness\export\`.
2. Create a text parameter `ExportFolder` (Transform data > Manage parameters) set to that path. Build each source path as `ExportFolder & "fct_discrepancy.parquet"` so the folder is easy to move.
3. Go to **Get data > Parquet** (or **Text/CSV**) and load these tables. Use parquet for fct_discrepancy.
   - dim_date, dim_aircraft, dim_ata, dim_operator, dim_part, dim_stage, dim_precaution
   - fct_discrepancy, fct_tail_interval, fct_mc_rate_benchmark, fct_engine_run
   - kpi_engine_mtbf, kpi_mtbr_by_model, kpi_top_parts, kpi_repeat_by_ata, kpi_report_lag, kpi_monthly
   - syn_dim_tail, syn_fct_status_daily, syn_fct_work_order, syn_fct_requisition, syn_fct_backlog_daily, syn_assumptions, syn_kpi_fleet
   - `dim_sdr_code` is optional, as a reference list only. Don't relate it. `dim_stage` and `dim_precaution` are already unique, so no Power Query split is needed.
4. In Power Query, check the types:
   - `*_date` columns: Date
   - `opened_at` and `closed_at`: Date/Time
   - `is_*` columns: True/False
   - numeric keys: Whole Number
   - `ata_key`, `stage_code` and `precaution_code`: Text. Missing values are `'UNK'` and `'-1'`, which are text.
5. Optional: remove `fct_discrepancy[discrepancy_text]` to save size. Then **Close & Apply**.

## 2. Build the model (Model view)
1. Delete any relationships that autodetect created, then create the ones listed in `MODEL_SPEC.md`. Set all of them to single direction and many-to-one.
2. Make `dim_date[date_key] → fct_discrepancy[difficulty_date_key]` **active** and `→ submission_date_key` **inactive**.
3. **Modeling > New table:**
   ```DAX
   Sim Date = ADDCOLUMNS ( CALENDAR ( DATE(2025,1,1), DATE(2025,12,31) ), "Month", FORMAT ( [Date], "yyyy-mm" ) )
   ```
   Relate `'Sim Date'[Date]` to `syn_fct_status_daily[date]` and to `syn_fct_backlog_daily[date]` (1:*).
4. **Do not** relate any `syn_*` table to `dim_aircraft` or `dim_date`. Leave `fct_mc_rate_benchmark` unrelated.
5. Mark `dim_date` (on `date`) and `'Sim Date'` (on `Date`) as date tables. Hide the fact-side keys and the `is_synthetic` columns.

## 3. Add the measures
1. Go to **Home > Enter data**, name the table `_Measures`, and load it. You'll hide its column later.
2. For each block in `measures.dax`, choose **New measure** and paste one measure, from its name to the end of its expression. Set the display folder to the section name.
3. Set the formats: `%` measures as Percentage with 1 decimal place, hours and days as 0 to 1 decimal places, counts as whole numbers with a thousands separator.
4. Check the values against `kpi_values.json`. At the time of writing:
   - **Real SDR:**
     - Reports: 34,350
     - Aircraft Reporting: 6,521
     - Operational Interruptions: 2,521, a rate of 7.3%
     - Interruptions Unverified Code: 262 (10.4%)
     - Operational Repeat Rate: 7.1%
     - Median Report Lag: 3 days
   - **Approximated:** Mean Hours Between Reports 277.0; Hours per Op. Interruption 2,087
   - **Engine (C-MAPSS):** 226.2 mean cycles
   - **GAO:** 0 of 8 fleets met their goal in FY2021; B-1B at 40.7%
   - **SIM:**

     | Measure | Value |
     |---|---|
     | MC | 60.4% |
     | NMCM | 19.5% |
     | NMCS | 20.0% |
     | MTBF | 35.5 h |
     | MTTR | 272.6 h |
     | Requisitions | 321 |
     | Late | 56.1% |
     | Avg open per day | 10.1 |
     | Backlog age | 12.0 days |

## 4. Apply the theme
Go to **View > Themes > Browse for themes** and pick `theme.json`, which uses the Okabe-Ito palette. Blue is the primary color, orange the secondary, and vermillion is for alerts or overdue. Set simulated card values to grey (#7F7F7F) manually.

## 5. Report pages
Canvas: 16:9, 1280 x 720. Each page gets a title, a subtitle stating the data status, and this footer text box:
`Source: FAA SDR, FAA Registry, NASA C-MAPSS; analysis by Evan Deaver` (page 4 adds `| Simulated fleet: src/synthetic.py, seed 42 | Real-world context: GAO-22-104533, Table 1`).

### Page 1: Fleet reliability overview (real)
Mockup: `mockups/page1_fleet_reliability_overview.png`
- **Cards:**
  - Reports, Aircraft Reporting
  - Operational Interruptions†, Operational Interruption Rate %†
  - Operational Repeat Rate %
  - Mean Hours Between Reports (approx MTBF)*, Hours per Operational Interruption (approx)*
  - Median Report Lag (days)
- **Line and clustered column chart:** dim_date[year_month] on the axis, Reports as columns, Operational Interruptions as the line.
- **Bar chart:** dim_ata[ata_chapter_name] with Operational Interruptions, top 10. Tooltip: Operational Interruption Rate %.
- **Bar chart: interruptions by precaution code.**
  - Axis: dim_precaution[precaution_code] and [precaution_label]. Value: Operational Interruptions. Visual filter: dim_precaution[is_operational_interruption] = True.
  - Conditional formatting: under Bars > Color > fx, use rules on `Precaution Label Status`: Unverified = #56B4E9, Inferred = #0072B2.
  - Add † to the unverified labels with a calculated column, `Precaution Display = dim_precaution[precaution_code] & " " & dim_precaution[precaution_label] & IF ( CONTAINSSTRING ( dim_precaution[label_basis], "unverified" ), " †" )`.
- **Footnotes:**
  - A card showing `Unverified Code Footnote`.
  - A text box: "* Approximation from real data: mean hours between consecutive SDR reporting days. Upper bound on true MTBF. Aircraft count excludes <UNKNOWN>."
- **Slicers:** dim_date[date] (between), dim_aircraft[fleet_class], dim_aircraft[make], dim_operator[operator_code].

### Page 2: Failure trends (real)
Mockup: `mockups/page2_failure_trends.png`
- Line chart: year_month with Operational Interruptions, and dim_ata[ata_chapter_name] as the legend (top 5 by Operational Interruptions).
- Bar chart: ata_chapter_name with Operational Repeat Rate %. Filter: In-Operation Reports >= 100.
- Bar chart: dim_aircraft[model] with Mean Hours Between Reports (approx MTBF). Filters: Valid Intervals >= 100 and aircraft_key <> -1.
- Bar chart: dim_part[part_name] with Reports, top 10. Filter: part_key <> -1.
- Footnote card: `Unverified Code Footnote`.
- Slicers: date, fleet_class, make/model, dim_stage[stage_label], dim_precaution[precaution_label].

### Page 3: Parts and components (real)
Mockup: `mockups/page3_parts_and_components.png`
- Bar chart: part_name with Reports, top 15, filtered to part_key <> -1. Tooltip: Operational Interruption Rate %.
- Bar chart: fct_discrepancy[part_condition] with Reports, top 8.
- Clustered bar: operator_code with Median and P90 Report Lag, top 10 by Reports, filtered to operator_key <> -1. Card: Reports Unknown Operator.
- Subtitle: "Parts demand signal and reporting backlog (real). Supply backlog is on page 4 (simulated)."

### Page 4: Simulated fleet (demo data) and real-world context
Mockup: `mockups/page4_simulated_fleet_and_real_context.png`

**Left 70%: simulated (SYNTHETIC)**
- A yellow (#F0E442) banner across the top: "SIMULATED DATA: synthetic demo fleet SIM-01 to SIM-20 (is_synthetic = TRUE). Not real aircraft status, work orders or requisitions."
- Cards with grey values, each card title ending in "(simulated)":
  - SIM MC Rate %, SIM NMCM Rate %, SIM NMCS Rate %
  - SIM MTBF (flight hours), SIM MTTR (hours)
  - SIM Avg Open Requisitions per Day, SIM Requisitions Late %
- 100% stacked column: 'Sim Date'[Month] with SIM MC Rate %, SIM NMCM Rate %, SIM NMCS Rate %.
- **Backlog over time:** area chart with 'Sim Date'[Date] on the axis, plus:
  - Values: SIM Open Requisitions (Backlog) (sky blue) and SIM Overdue Requisitions (vermillion)
  - Tooltip: SIM Backlog Avg Age (days)
  - A card beside it: SIM Peak Open Requisitions
- Optional table: syn_fct_requisition with priority, requisition_date, due_date, receipt_date and backorder_days. Color backorder_days > 0 vermillion.
- Slicers: syn_dim_tail[tail_id] and 'Sim Date'[Date] only. The backlog line is fleet-level, so the tail slicer doesn't filter it. Add a note saying so.

**Right 30%: Real-world context (REAL, GAO-22-104533), in a box with a blue border**
- A card for `GAO FY2021 Headline` and a card for `GAO B-1B MC Rate FY2021 %` (subtitle "B-1B, Ellsworth AFB, goal 52%").
- Bar chart: fct_mc_rate_benchmark[aircraft] with GAO MC Rate %, filtered to fiscal_year = 2021. Highlight the B-1B bar in vermillion.
  - Show the goal as error bars (GAO MC Goal %) or as a tooltip.
  - Add a constant X-axis line at the SIM MC Rate % value (Analytics pane), labeled "simulated fleet".
- Optional: a line chart of GAO MC Rate % by fiscal_year FY2015–21 with aircraft as the legend.
- Title the box "Real-world context (real data)" so it's never mistaken for the simulation.

### Page 5 (optional): Engine health (NASA C-MAPSS simulation)
Mockup: `mockups/page5_engine_health.png`
- Cards: Engines, Mean Cycles to Failure, Min Cycles, Max Cycles.
- Histogram: bins of 15 cycles, with dataset as the legend.
- Column chart: dataset with mean cycles, plus CV in the tooltip.
- Subtitle: "NASA run-to-failure simulation, not field data."

## 6. Drill-through
1. **Aircraft detail** (hidden page): drill-through on dim_aircraft[n_number], with a page filter aircraft_key <> -1.
   - Cards: Reports, Operational Interruptions, Mean Hours Between Reports, plus make, model and year_mfr.
   - Table: difficulty_date, ata_chapter_name, part_name, part_condition, stage_label, precaution_label (with †), is_repeat_30d, report_lag_days.
2. **ATA chapter detail** (hidden page): drill-through on dim_ata[ata_chapter_name].
   - Shows Reports by month, the top parts, the top models and Operational Repeat Rate %.
3. Right-click any ATA, model or tail bar on Pages 1 to 3 to drill through. Page 4 has no drill-through into real tails.

## 7. Slicer sync
Use **View > Sync slicers**. Sync the date, fleet_class and make slicers across Pages 1 to 3 only. Page 4 keeps its own Sim Date and tail slicers.

## 8. Publish or export screenshots
- **Screenshots:** in reading view, set Fit to page, then capture each page at 1280 x 720 or larger (Win+Shift+S). Save them as `images/powerbi_page1_overview.png` and so on. Real screenshots replace the mockups in the README. Never present a mockup as a Power BI screenshot.
- **PDF:** go to **File > Export > Export to PDF**.
- **Publish to the web (optional):** **Home > Publish** to My workspace, then in the Service use **File > Embed report > Publish to web (public)**. Only do this once every synthetic visual is labeled, because anyone can see it.
- **Save:** use **File > Save as** `aircraft_readiness.pbix`. Keep it under 100 MB for GitHub.
