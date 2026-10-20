"""Charts for the README, read from the built warehouse."""
from pathlib import Path
import duckdb, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT.parent / "images"; IMG.mkdir(exist_ok=True)
con = duckdb.connect(str(ROOT / "data/aircraft_readiness.duckdb"), read_only=True)
win = con.sql("SELECT min(difficulty_date), max(difficulty_date) FROM mart.fct_discrepancy").fetchone()
SRC = f"Source: FAA Service Difficulty Reporting System, {win[0]} to {win[1]}; analysis by Evan Deaver"

# 1. Which systems interrupt operations
d = con.sql("""SELECT d.ata_chapter || ' ' || lower(d.ata_chapter_name) AS ch, count(*) n,
               sum(f.is_operational_interruption::INT) AS ints
               FROM mart.fct_discrepancy f JOIN mart.dim_ata d USING (ata_key) GROUP BY 1 ORDER BY ints DESC LIMIT 10""").df()[::-1]
fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(d.ch, d.ints, color="#b5432b")
for y, (i, n) in enumerate(zip(d.ints, d.n)): ax.text(i, y, f"  {int(i):,} of {int(n):,} reports", va="center", fontsize=8)
# plain labels: drop the ATA chapter code; chapter 75 ("air") is engine air
d["lbl"] = [("engine air" if c.startswith("75 ") else c.split(" ", 1)[1]) for c in d.ch]
ax.set_yticks(range(len(d)), d.lbl)
t1, t2 = d.iloc[::-1].iloc[0], d.iloc[::-1].iloc[1]
ax.set_title(f"{t1.lbl.capitalize()} ({int(t1.ints):,}) and {t2.lbl} ({int(t2.ints):,}) cause the most flight disruptions\n(unscheduled landings, aborted takeoffs, returns to gate, engine shutdowns)", loc="left", fontsize=10)
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
ax.set_title("In FY2021, all 8 military fleets GAO reviewed fell short of their readiness goal\nB-1B (Ellsworth AFB): 40.7% ready (mission-capable) vs a 52% goal", loc="left", fontsize=10)
ax.set_ylabel("Points above/below readiness goal"); ax.legend(loc="lower left"); ax.set_xlim(2014.7, 2022)
fig.text(0.01, 0.01, "Source: GAO-22-104533, Table 1 (Air Force and Navy data); analysis by Evan Deaver", fontsize=7, color="grey")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(IMG / "mc_rate_vs_goal.png", dpi=150)

# 3. Reporting lag
r = con.sql("SELECT * FROM mart.kpi_report_lag ORDER BY reports DESC LIMIT 12").df()[::-1]
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh(r.operator_code, r.median_lag_days, color="#2b6cb5")
ax.set_title("One of the 12 busiest operators takes 60+ days to report a problem to the FAA (median)", loc="left", fontsize=10)
ax.set_xlabel("Median report lag (days)"); fig.text(0.01, 0.01, SRC, fontsize=7, color="grey")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(IMG / "report_lag_by_operator.png", dpi=150)

# 4. C-MAPSS
e = con.sql("SELECT dataset, cycles_to_failure FROM mart.fct_engine_run").df()
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.boxplot([g.cycles_to_failure for _, g in e.groupby("dataset")], tick_labels=sorted(e.dataset.unique()), orientation="horizontal")
ax.set_title("SIMULATED: engines fail between 128 and 543 cycles, so fixed overhaul schedules waste parts or risk failure", loc="left", fontsize=10)
ax.set_xlabel("Cycles to failure (709 engines)")
fig.text(0.01, 0.01, "Source: NASA C-MAPSS turbofan degradation simulation (train sets); analysis by Evan Deaver", fontsize=7, color="grey")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(IMG / "engine_cycles_to_failure.png", dpi=150)
print("figures written to", IMG)
