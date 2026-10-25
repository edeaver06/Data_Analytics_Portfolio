# Code: Rural Hospital Financial Warning Signs
- `src/pipeline.py`: reads the CMS FY2023 cost report CSV (`data/raw/cr2023.csv`), keeps STH/CAH hospitals with one full-year report each, computes margins, days cash, current ratio and payer mix, scores six warning signs (0-6), and writes `data/hospitals.db` (SQLite) and `data/clean/*.csv`.
- `sql/views.sql`: `state_summary` view.
- `tests/test_pipeline.py`: 5 pytest checks (run after the pipeline builds the database).

Generated `data/` is not committed. See the project [README](../README.md) for the download and run steps.
