# Code: diabetes care-gap tracker (R)

## Run
1. Generate the data (about 10 minutes, needs Java 17+): see `../data-sources.md` for the exact Synthea command. Put the CSV folder at `data/raw/synthea_csv/`.
2. Install R 4.5 and the packages in `r_package_versions.txt` (dplyr, readr, tidyr, lubridate, DBI, RSQLite, ggplot2, testthat, rmarkdown, flexdashboard, gt).
3. From this folder: `./run_all.sh`

## Layout
| Path | What |
|---|---|
| `src/00_config.R` | paths, code lists, measurement years, illustrative targets |
| `src/01_ingest.R` | raw CSV → SQLite staging tables (`stg_*`), direct identifiers dropped |
| `src/measures.R` | pure measure functions (denominator, numerators, KPI rates, worklist) |
| `src/02_build.R` | builds `member_measures`, `kpi`, `worklist_2026`, runs `sql/*.sql` |
| `src/03_figures.R` | PNG figures → `images/` |
| `src/05_screenshot.sh` | headless-Chromium screenshot of the dashboard → `images/` |
| `src/04_dashboard.R`, `app/dashboard.Rmd` | static flexdashboard → `app/dashboard.html` |
| `src/audit.py` | recomputes every KPI with SQL only and scans text for personal data / secrets |
| `sql/01_views.sql` | SQL version of each measure (`v_sql_member`), `v_kpi_overall`, `v_worklist_top50` |
| `tests/` | testthat: measure edge cases + data-quality checks |
| `data/clean/` | `kpi.csv`, `kpi_overall.csv`, `worklist_2026.csv` (the SQLite file is rebuilt, not committed) |

## Grain
- `member_measures`: one row per patient per measurement year (2017-2026), only patients in the denominator.
- `kpi`: one row per year × breakdown (overall, age_band, sex, payer_group) × group × measure, with denominator, numerator, rate.
- `worklist_2026`: one row per patient with ≥1 open gap in MY2026 year to date, ranked by priority, then longest since last visit, then ID. `patient_id` is the first 8 characters of the synthetic Synthea ID (full IDs never leave the database).
