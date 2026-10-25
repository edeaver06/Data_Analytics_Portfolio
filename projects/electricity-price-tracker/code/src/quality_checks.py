"""Data-quality checks run against the SQLite database. Each returns (name, passed, detail)."""
import sqlite3
from datetime import date

PRICE_MIN, PRICE_MAX = 1.0, 80.0   # cents/kWh; real US prices sit roughly 4-55


def run_checks(db_path, max_lag_months=6):
    con = sqlite3.connect(db_path)
    q = lambda sql: con.execute(sql).fetchall()
    results = []
    dupes = q("SELECT COUNT(*) FROM (SELECT state, month, sector FROM retail_sales_monthly "
              "GROUP BY 1,2,3 HAVING COUNT(*) > 1)")[0][0]
    results.append(("no duplicate state/month/sector", dupes == 0, f"{dupes} duplicates"))
    n_states = q("SELECT COUNT(DISTINCT state) FROM retail_sales_monthly")[0][0]
    results.append(("51 states present (50 + DC)", n_states == 51, f"{n_states} states"))
    n_regions = q("SELECT COUNT(*) FROM state_region WHERE state IN "
                  "(SELECT DISTINCT state FROM retail_sales_monthly)")[0][0]
    results.append(("every state has a region tag", n_regions == 51, f"{n_regions} tagged"))
    bad = q(f"SELECT COUNT(*) FROM retail_sales_monthly WHERE price_cents_per_kwh IS NOT NULL "
            f"AND price_cents_per_kwh NOT BETWEEN {PRICE_MIN} AND {PRICE_MAX}")[0][0]
    results.append((f"price within {PRICE_MIN}-{PRICE_MAX} c/kWh", bad == 0, f"{bad} out of range"))
    latest = q("SELECT MAX(month) FROM retail_sales_monthly")[0][0]
    y, m = int(latest[:4]), int(latest[5:7])
    t = date.today()
    lag = (t.year - y) * 12 + (t.month - m)
    results.append((f"latest month within {max_lag_months} months", lag <= max_lag_months,
                    f"latest {latest[:7]} ({lag} months ago)"))
    full = q("SELECT COUNT(DISTINCT state) FROM retail_sales_monthly WHERE month = "
             "(SELECT MAX(month) FROM retail_sales_monthly) AND sector='RES' "
             "AND price_cents_per_kwh IS NOT NULL")[0][0]
    results.append(("latest month has RES price for all 51", full == 51, f"{full} states"))
    con.close()
    return results
