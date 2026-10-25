# Audit results

Run: `python3 src/audit.py`

- PASS: All KPI rows recomputed in SQL match R (denominator and numerator) - 770 KPI rows, 0 mismatches
- PASS: Patient-level flags identical in R and SQL - 0 flag diffs, 0 membership diffs
- PASS: Worklist size (patients with >=1 open gap, MY2026 YTD) matches SQL - SQL 672 vs R 672
- PASS: Every % in README/STORY traces to a computed rate or stated threshold
- PASS: No phone in project text files
- PASS: No address in project text files
- PASS: No banned-descriptor word in project text files
- PASS: No secret in project text files
- PASS: No SSN in project text files
