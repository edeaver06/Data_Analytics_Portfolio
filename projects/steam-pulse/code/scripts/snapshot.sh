#!/usr/bin/env bash
# Take one Steam Pulse snapshot (ingest -> raw files -> DuckDB -> dbt build). Safe to schedule; overlapping runs exit.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs data
{
  echo "=== $(date -u +%FT%TZ) snapshot start"
  .venv/bin/python -m steam_pulse.ingest "$@"
  (cd dbt && ../.venv/bin/dbt build --profiles-dir . --quiet)
  echo "=== $(date -u +%FT%TZ) snapshot done"
} 2>&1 | tee -a logs/snapshot.log
