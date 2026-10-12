#!/usr/bin/env bash
# Full pipeline: download public data (skips files already present), build the warehouse, run checks, export, test.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
START=${SDR_START:-2025-01-01}; END=${SDR_END:-2025-06-29}
mkdir -p data/raw/registry data/raw/cmapss
if [ ! -f data/raw/registry/MASTER.txt ]; then
  curl -sL -A "Mozilla/5.0" -o data/raw/registry.zip https://registry.faa.gov/database/ReleasableAircraft.zip
  unzip -oq data/raw/registry.zip MASTER.txt ACFTREF.txt -d data/raw/registry && rm data/raw/registry.zip
fi
if [ ! -f data/raw/cmapss/train_FD001.txt ]; then
  curl -sL -o data/raw/cmapss.zip "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
  unzip -oq data/raw/cmapss.zip -d data/raw/cmapss_tmp && unzip -oq data/raw/cmapss_tmp/*/CMAPSSData.zip -d data/raw/cmapss
  rm -rf data/raw/cmapss.zip data/raw/cmapss_tmp
fi
$PY src/fetch_sdrs.py "$START" "$END"     # slow: the public SDRS query returns at most 1,500 rows per request
SDR_END=$END $PY src/build.py
$PY src/make_figures.py
$PY powerbi/build_powerbi.py >/dev/null   # Tableau CSVs + Power BI mockups
$PY -m pytest -q tests
