#!/usr/bin/env bash
# Reproduce everything from the raw Synthea CSVs (see reports/data-sources.md to regenerate them).
set -euo pipefail
cd "$(dirname "$0")"
Rscript src/01_ingest.R      # raw CSV -> SQLite staging (identifiers dropped)
Rscript src/02_build.R       # measures, KPI marts, worklist, SQL views
Rscript src/03_figures.R     # images/*.png
Rscript src/04_dashboard.R   # app/dashboard.html
bash src/05_screenshot.sh    # images/05_dashboard_screenshot.png
Rscript -e 'testthat::test_dir("tests", stop_on_failure = TRUE)'
python3 src/audit.py         # independent SQL recompute of every KPI
