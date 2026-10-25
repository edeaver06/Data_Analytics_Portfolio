# STATUS: Steam Pulse

**Last updated:** 2026-10-25 (Portfolio Manager)
**Stage:** Published; maintenance fix committed locally, awaiting Evan's OK to push.

## Latest change (2026-10-23, Code Builder): review-stall fix
- Problem: Steam's review-summary endpoint started answering with a 302 redirect to the store homepage. The pipeline retried each app up to 5 times with long backoff, so a snapshot run could hang for hours.
- Fix (`code/steam_pulse/http.py`, `code/steam_pulse/ingest.py`):
  - Review calls no longer follow redirects. A redirect, or HTML where JSON was expected, is not retried; that app is recorded as `ok=False`.
  - Every retry wait is capped at 30 seconds (`MAX_BACKOFF`), even if the server asks for longer.
  - Reviews get a 180-second time budget per run; remaining apps are skipped and logged.
  - Circuit breaker: if the first 5 review calls all redirect, reviews are skipped for that run.
- Tests: new `code/tests/test_reviews_guard.py`; `analysis/tests/test_analysis.py` updated for duckdb 2.0 (`Relation.fetchone` removed).
- Verified on a real run: 6 min 18 s end to end (previously hung), player counts still collected.

## Open items
- Steam is still redirecting review requests, so review data stays stale until that stops. Player counts are unaffected.
- `analysis/src/backfill_build.py` uses `c.sql(...).fetchone()`, which duckdb 2.0 removed; it will need the same fix.
- CI workflow for Steam Pulse exists only as an uncommitted draft in another worktree; not part of this change.

## Next step
- Evan reviews this change; on his OK, push to main.
