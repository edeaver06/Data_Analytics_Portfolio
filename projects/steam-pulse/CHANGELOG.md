# Changelog: Steam Pulse

## Oct 23, 2026: stopped review redirects from stalling snapshots
- Steam's review-summary endpoint began answering with a 302 redirect to the store homepage. The pipeline retried each app up to 5 times with long backoff, so a snapshot run could hang for hours.
- I changed `code/steam_pulse/http.py` and `code/steam_pulse/ingest.py`:
  - Review calls no longer follow redirects. A redirect, or HTML where JSON was expected, is not retried; that app is recorded as `ok=False`.
  - Every retry wait is capped at 30 seconds (`MAX_BACKOFF`), even if the server asks for longer.
  - Reviews get a 180-second time budget per run; remaining apps are skipped and logged.
  - Circuit breaker: if the first 5 review calls all redirect, reviews are skipped for that run.
- Added `code/tests/test_reviews_guard.py` and updated `analysis/tests/test_analysis.py` for duckdb 2.0 (`Relation.fetchone` removed).
- A real run now finishes in 6 min 18 s end to end, and player counts are still collected.

## Known issues
- Steam is still redirecting review requests, so review data stays stale until that stops. Player counts are unaffected.
- `analysis/src/backfill_build.py` still uses `c.sql(...).fetchone()`, which duckdb 2.0 removed; it needs the same fix.
