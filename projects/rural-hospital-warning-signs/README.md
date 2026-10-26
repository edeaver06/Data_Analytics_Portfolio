# Rural Hospital Financial Warning Signs (Upper Midwest)

This project screens 4,284 US short-term and critical access hospitals using CMS FY2023 cost reports, with a focus on SD, ND, MN, NE, MT, WY and IA (485 hospitals).
A Python + SQLite pipeline computes margins, days cash, current ratio and payer mix, then counts six financial warning signs (0-6). A [Google Sheets dashboard](https://docs.google.com/spreadsheets/d/1QoG2l-5s70JOvz15ZmdtHULTPSygrQUXWIPyah5qBbo/edit) filters by state and lists hospitals by name.

Tiers: 0-1 Few warning signs, 2-3 Some warning signs, 4-6 Many warning signs.

> **Caveat:** Hospitals in larger health systems (e.g. Sanford, Monument, Avera) may show low cash because the parent system holds it. This is a screening score from public CMS FY2023 cost reports, not a prediction or a judgment of any hospital.

Findings (FY2023): Focus-state hospitals had a median total margin of 5.9% vs 4.3% elsewhere, and 6.6% showed many warning signs (4+ of 6) vs 14.0% elsewhere. Wyoming stood out: 46% of its hospitals had a negative total margin and 19% showed many warning signs. Medicaid share showed essentially no relationship with total margin (Spearman -0.06).

See data-sources.md for sources and license.
Links: [Google Sheet](https://docs.google.com/spreadsheets/d/1QoG2l-5s70JOvz15ZmdtHULTPSygrQUXWIPyah5qBbo/edit) · [Story](STORY.md) · [Code](code/README.md) · [Data sources](data-sources.md)

## Run
Download the raw CMS file (not committed) to `code/data/raw/cr2023.csv`:
```
mkdir -p code/data/raw && curl -L -o code/data/raw/cr2023.csv "https://data.cms.gov/sites/default/files/2026-01/3c39f483-c7e0-4025-8396-4df76942e10f/CostReport_2023_Final.csv"
```
Then:
```
python code/src/pipeline.py && pytest code/tests
```
