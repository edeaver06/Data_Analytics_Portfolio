"""Charts for the README, read from the built warehouse."""
from pathlib import Path
import duckdb, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT.parent / "images"; IMG.mkdir(exist_ok=True)
con = duckdb.connect(str(ROOT / "data/aircraft_readiness.duckdb"), read_only=True)
win = con.sql("SELECT min(difficulty_date), max(difficulty_date) FROM mart.fct_discrepancy").fetchone()
SRC = f"Source: FAA Service Difficulty Reporting System, {win[0]} to {win[1]}"

# 1. Which systems interrupt operations
d = con.sql("""SELECT d.ata_chapter || ' ' || lower(d.ata_chapter_name) AS ch, count(*) n,
               sum(f.is_operational_interruption::INT) AS ints
               FROM mart.fct_discrepancy f JOIN mart.dim_ata d USING (ata_key) GROUP BY 1 ORDER BY ints DESC LIMIT 10""").df()[::-1]
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(d.ch, d.ints, color="#b5432b")
for y, (i, n) in enumerate(zip(d.ints, d.n)): ax.text(i, y, f"  {int(i):,} of {int(n):,} reports", va="center", fontsize=8)
top3 = ", ".join(c.split(" ",1)[1] for c in d.ch[::-1][:3])
ax.set_title(f"Most operational interruptions trace to {top3}\n(unscheduled landings, aborted takeoffs, returns to gate, engine shutdowns)", loc="left", fontsize=10)
ax.set_xlabel("Reports with an operational interruption"); ax.margins(x=0.3)
fig.text(0.01, 0.01, SRC, fontsize=7, color="grey"); fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(IMG / "interruptions_by_ata.png", dpi=150)

# 2. GAO MC benchmark
b = con.sql("SELECT * FROM mart.fct_mc_rate_benchmark ORDER BY aircraft, fiscal_year").df()
fig, ax = plt.subplots(figsize=(9, 5))
for a, g in b.groupby("aircraft"):
    hl = a == "B-1B"
    ax.plot(g.fiscal_year, g.gap_to_goal_pts, marker="o" if hl else None, lw=3 if hl else 1,
            color="#b5432b" if hl else "#999", label=a if hl else None, zorder=3 if hl else 1)
    if not hl: ax.text(2021.1, g.gap_to_goal_pts.iloc[-1], a, fontsize=7, color="#666", va="center")
ax.axhline(0, color="black", lw=0.8); ax.text(2015, 1, "goal", fontsize=8)
ax.set_title("None of 8 GAO-reviewed fleets met its mission-capable goal in FY2021\nB-1B (Ellsworth AFB) highlighted: 40.7% vs a 52% goal", loc="left", fontsize=10)
ax.set_ylabel("Mission-capable rate minus goal (pct points)"); ax.legend(loc="lower left"); ax.set_xlim(2014.7, 2022)
fig.text(0.01, 0.01, "Source: GAO-22-104533, Table 1 (Air Force and Navy data)", fontsize=7, color="grey")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(IMG / "mc_rate_vs_goal.png", dpi=150)

# 3. Reporting lag
r = con.sql("SELECT * FROM mart.kpi_report_lag ORDER BY reports DESC LIMIT 12").df()[::-1]
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh(r.operator_code, r.median_lag_days, color="#2b6cb5")
ax.set_title("Days from difficulty to FAA submission vary 0 to 60+ by operator (median)", loc="left", fontsize=10)
ax.set_xlabel("Median report lag (days)"); fig.text(0.01, 0.01, SRC, fontsize=7, color="grey")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(IMG / "report_lag_by_operator.png", dpi=150)

# 4. C-MAPSS
e = con.sql("SELECT dataset, cycles_to_failure FROM mart.fct_engine_run").df()
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.boxplot([g.cycles_to_failure for _, g in e.groupby("dataset")], tick_labels=sorted(e.dataset.unique()), orientation="horizontal")
ax.set_title("Simulated turbofans fail anywhere from 128 to 543 cycles: a fixed overhaul interval wastes life or risks failure", loc="left", fontsize=10)
ax.set_xlabel("Cycles to failure (709 engines)")
fig.text(0.01, 0.01, "Source: NASA C-MAPSS turbofan degradation simulation (train sets)", fontsize=7, color="grey")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(IMG / "engine_cycles_to_failure.png", dpi=150)
print("figures written to", IMG)
