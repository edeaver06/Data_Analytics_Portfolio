"""One command for the whole pipeline:  python src/run_pipeline.py [--skip-fetch]

--skip-fetch reuses the cached raw JSON in data/raw/ instead of calling the API.
"""
import sys

import clean
import fetch_eia
import load_sqlite
import quality_checks

if __name__ == "__main__":
    if "--skip-fetch" not in sys.argv:
        fetch_eia.main()
    df = clean.main()
    counts = load_sqlite.load(df, clean.load_regions())
    print("SQLite row counts:", counts)
    failed = 0
    for name, ok, detail in quality_checks.run_checks(load_sqlite.DB_FILE):
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        failed += not ok
    sys.exit(1 if failed else 0)
