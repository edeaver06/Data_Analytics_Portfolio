#!/usr/bin/env bash
# Full-page screenshot of the static dashboard (headless Chromium).
set -euo pipefail
chromium --headless=new --no-sandbox --hide-scrollbars --window-size=1500,2600 \
  --screenshot="$PWD/images/05_dashboard_screenshot.png" "file://$PWD/app/dashboard.html" 2>/dev/null
