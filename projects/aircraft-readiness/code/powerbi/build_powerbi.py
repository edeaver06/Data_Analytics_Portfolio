"""Power BI / Tableau hand-off for aircraft-readiness.

Rebuilds: powerbi/tableau/*.csv (gitignored), powerbi/kpi_values.json and powerbi/mockups/*.png.
Power BI imports the model tables directly from code/data/export/, produced by src/build.py, so they aren't copied here.
Reads code/data/aircraft_readiness.duckdb (schema mart) READ-ONLY.
Run from code/:  .venv/bin/python powerbi/build_powerbi.py
Mockups are DESIGN MOCKUPS rendered with matplotlib, not Power BI screenshots."""
from pathlib import Path
import json
import duckdb, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]          # code/
PB = ROOT / "powerbi"; MOCK = PB / "mockups"; TAB = PB / "tableau"
for p in (MOCK, TAB): p.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(ROOT / "data/aircraft_readiness.duckdb"), read_only=True)
sql = lambda s: con.sql(s).df()

# ---------- 1. Tableau tidy CSVs (Tableau Public can't read parquet). Gitignored; rebuilt here. ----------
TQ = {
 "sdr_reports.csv": """SELECT f.sdr_id, f.difficulty_date, f.submission_date, f.report_lag_days, f.is_date_anomaly,
    a.n_number, a.make, a.model, a.fleet_class, a.year_mfr, o.operator_code,
    t.ata_key AS jasc_code, t.jasc_description, t.ata_chapter, t.ata_chapter_name, p.part_name, f.part_condition,
    f.stage_code, s.stage_label, f.precaution_code, pc.precaution_label, pc.label_basis AS precaution_label_basis,
    (pc.label_basis ILIKE '%unverified%') AS precaution_label_unverified,
    f.is_in_operation, f.is_operational_interruption, f.is_repeat_30d, f.aircraft_total_hours, f.aircraft_total_cycles
  FROM mart.fct_discrepancy f
  JOIN mart.dim_aircraft a USING (aircraft_key) JOIN mart.dim_operator o USING (operator_key)
  JOIN mart.dim_ata t USING (ata_key) JOIN mart.dim_part p USING (part_key)
  JOIN mart.dim_stage s USING (stage_code) JOIN mart.dim_precaution pc USING (precaution_code)""",
 "tail_intervals.csv": """SELECT i.*, a.n_number, a.make, a.model, a.fleet_class FROM mart.fct_tail_interval i
  JOIN mart.dim_aircraft a USING (aircraft_key)""",
 "engine_runs.csv": "SELECT * FROM mart.fct_engine_run",
 "gao_mc_benchmark.csv": "SELECT * FROM mart.fct_mc_rate_benchmark",
 "SIMULATED_status_daily.csv": "SELECT * FROM mart.syn_fct_status_daily",
 "SIMULATED_work_orders.csv": "SELECT * FROM mart.syn_fct_work_order",
 "SIMULATED_requisitions.csv": "SELECT * FROM mart.syn_fct_requisition",
 "SIMULATED_backlog_daily.csv": "SELECT * FROM mart.syn_fct_backlog_daily",
}
for old in ("gao_mc_benchmark_PENDING_VERIFICATION.csv",):
    (TAB / old).unlink(missing_ok=True)
for name, q in TQ.items():
    con.sql(f"COPY ({q}) TO '{TAB / name}' (HEADER)")

# ---------- 2. KPI values (same definitions as measures.dax), computed from the warehouse ----------
one = lambda s: sql(s).iloc[0]
f = one("""SELECT count(*) reports, count(DISTINCT aircraft_key) FILTER (WHERE aircraft_key <> -1) aircraft,
           sum(is_operational_interruption::INT) ints, sum(is_repeat_30d::INT) reps, sum(is_in_operation::INT) inop,
           median(report_lag_days) lag, avg((report_lag_days>3)::INT) over3,
           count(*) FILTER (WHERE aircraft_key=-1) unk_ac, count(*) FILTER (WHERE operator_key=-1) unk_op,
           count(*) FILTER (WHERE part_key=-1) unk_part FROM mart.fct_discrepancy""")
uv = int(one("""SELECT count(*) n FROM mart.fct_discrepancy JOIN mart.dim_precaution p USING (precaution_code)
               WHERE p.is_operational_interruption AND p.label_basis ILIKE '%unverified%'""").n)
iv = one("SELECT sum(hours_between) h, count(*) n, sum(ends_in_interruption::INT) ei, median(hours_between) med FROM mart.fct_tail_interval WHERE is_valid")
eng = one("SELECT avg(cycles_to_failure) m, min(cycles_to_failure) lo, max(cycles_to_failure) hi, count(*) n FROM mart.fct_engine_run")
st = one("""SELECT count(*) n, avg(is_mission_capable::INT) mc, avg((status='NMCM')::INT) nmcm, avg((status='NMCS')::INT) nmcs,
            sum(flight_hours) fh FROM mart.syn_fct_status_daily""")
wo = one("""SELECT count(*) n, count(*) FILTER (WHERE work_type='Unscheduled repair') nu,
            avg(repair_hours) FILTER (WHERE work_type='Unscheduled repair') mttr FROM mart.syn_fct_work_order""")
rq = one("""SELECT count(*) n, count(*) FILTER (WHERE priority LIKE 'MICAP%') micap, avg(backorder_days) bo,
            avg(backorder_days) FILTER (WHERE backorder_days>0) bo_late, avg((backorder_days>0)::INT) late, avg(lead_time_days) lead
            FROM mart.syn_fct_requisition""")
bl = one("""SELECT avg(open_requisitions) avg_open, max(open_requisitions) max_open, avg(overdue_requisitions) avg_over,
            max(overdue_requisitions) max_over, sum(open_requisitions*avg_age_days)/sum(open_requisitions) age,
            arg_max(open_requisitions, date) end_open, arg_max(overdue_requisitions, date) end_over FROM mart.syn_fct_backlog_daily""")
g = sql("SELECT * FROM mart.fct_mc_rate_benchmark WHERE fiscal_year = 2021")
b1 = g[g.aircraft == "B-1B"].iloc[0]
k = {
 "reports": int(f.reports), "aircraft_reporting_excl_unknown": int(f.aircraft),
 "reports_unknown_aircraft": int(f.unk_ac), "reports_unknown_operator": int(f.unk_op), "reports_unknown_part": int(f.unk_part),
 "operational_interruptions": int(f.ints), "operational_interruption_rate_pct": round(100*f.ints/f.reports, 1),
 "interruptions_with_unverified_code": uv, "interruptions_unverified_pct": round(100*uv/f.ints, 1),
 "operational_repeat_rate_pct": round(100*f.reps/f.inop, 1), "median_report_lag_days": float(f.lag),
 "pct_reports_lag_over_3d": round(100*f.over3, 1),
 "mean_hours_between_reports": round(iv.h/iv.n, 1), "median_hours_between_reports": round(float(iv.med), 1),
 "valid_intervals": int(iv.n), "hours_per_operational_interruption": round(iv.h/iv.ei, 0),
 "engine_mean_cycles_to_failure_cmapss": round(eng.m, 1), "engine_cycles_min": int(eng.lo), "engine_cycles_max": int(eng.hi), "engines": int(eng.n),
 "GAO_fy2021_fleets": len(g), "GAO_fy2021_fleets_meeting_goal": int(g.met_goal.sum()),
 "GAO_fy2021_avg_gap_to_goal_pts": round(g.gap_to_goal_pts.mean(), 1),
 "GAO_fy2021_mc_range_pct": [float(g.mc_rate_pct.min()), float(g.mc_rate_pct.max())],
 "GAO_fy2021_B1B_mc_pct": float(b1.mc_rate_pct), "GAO_fy2021_B1B_goal_pct": int(b1.mc_goal_pct),
 "SIM_mc_rate_pct": round(100*st.mc, 1), "SIM_nmc_rate_pct": round(100*(1-st.mc), 1),
 "SIM_nmcm_pct": round(100*st.nmcm, 1), "SIM_nmcs_pct": round(100*st.nmcs, 1), "SIM_flight_hours": round(st.fh, 0),
 "SIM_work_orders": int(wo.n), "SIM_unscheduled_work_orders": int(wo.nu),
 "SIM_mtbf_flight_hours": round(st.fh/wo.nu, 1), "SIM_mttr_hours_unscheduled": round(wo.mttr, 1),
 "SIM_requisitions": int(rq.n), "SIM_micap_requisitions": int(rq.micap), "SIM_pct_requisitions_late": round(100*rq.late, 1),
 "SIM_avg_backorder_days_all": round(rq.bo, 2), "SIM_avg_backorder_days_late_only": round(rq.bo_late, 2),
 "SIM_mean_lead_time_days": round(rq.lead, 1),
 "SIM_avg_open_requisitions_per_day": round(bl.avg_open, 1), "SIM_max_open_requisitions": int(bl.max_open),
 "SIM_avg_overdue_requisitions_per_day": round(bl.avg_over, 1), "SIM_max_overdue_requisitions": int(bl.max_over),
 "SIM_backlog_avg_age_days_weighted": round(bl.age, 1),
 "SIM_open_requisitions_2025_12_31": int(bl.end_open), "SIM_overdue_requisitions_2025_12_31": int(bl.end_over),
}
# cross-check against the warehouse's own synthetic KPI row
skf = one("SELECT * FROM mart.syn_kpi_fleet")
for a, b_ in [("SIM_mc_rate_pct", "mc_rate_pct"), ("SIM_nmcm_pct", "nmcm_pct"), ("SIM_nmcs_pct", "nmcs_pct"),
              ("SIM_mtbf_flight_hours", "mtbf_flight_hours"), ("SIM_mttr_hours_unscheduled", "mttr_hours"),
              ("SIM_pct_requisitions_late", "pct_requisitions_late"), ("SIM_mean_lead_time_days", "mean_parts_lead_days"),
              ("SIM_avg_open_requisitions_per_day", "avg_open_requisitions"), ("SIM_requisitions", "requisitions")]:
    assert abs(k[a] - skf[b_]) < 0.051, (a, k[a], skf[b_])
(PB / "kpi_values.json").write_text(json.dumps(k, indent=2))

# ---------- 3. Mockups ----------
for old in ("appendix_gao_benchmark_pending_verification.png", "page4_simulated_fleet_demo_data.png"):
    (MOCK / old).unlink(missing_ok=True)
C = dict(blue="#0072B2", orange="#E69F00", green="#009E73", sky="#56B4E9", verm="#D55E00", pink="#CC79A7",
         yellow="#F0E442", grey="#6E6E6E", sim="#7F7F7F")
FOOT = "Source: FAA SDR, FAA Registry, NASA C-MAPSS; analysis by Evan Deaver"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 10,
                     "axes.titleweight": "bold", "axes.titlelocation": "left"})

def page(title, subtitle, sim=False, extra_foot=None):
    fig = plt.figure(figsize=(16, 9))
    fig.text(0.015, 0.965, title, fontsize=18, weight="bold", va="top")
    fig.text(0.015, 0.925, subtitle, fontsize=10, color=C["grey"], va="top")
    fig.text(0.985, 0.965, "DESIGN MOCKUP: not a Power BI screenshot", fontsize=9, color=C["verm"], ha="right", va="top", weight="bold")
    if sim:
        fig.patches.append(plt.Rectangle((0, 0.875), 1, 0.035, transform=fig.transFigure, color=C["yellow"], zorder=0))
        fig.text(0.5, 0.892, "SIMULATED DATA: synthetic demo fleet SIM-01..SIM-20 (is_synthetic = TRUE). Not real aircraft status, work orders or requisitions.",
                 ha="center", va="center", fontsize=10, weight="bold")
    fig.text(0.015, 0.012, FOOT + ("   |   " + extra_foot if extra_foot else ""), fontsize=8, color=C["grey"])
    return fig

def cards(fig, items, y=0.76, h=0.1, x0=0.015, width=0.97, sim=False):
    w = width / len(items)
    for i, (label, val) in enumerate(items):
        ax = fig.add_axes([x0 + i*w, y, w - 0.008, h]); ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_visible(True); s.set_color("#CCCCCC")
        ax.text(0.5, 0.58, val, ha="center", va="center", fontsize=19, weight="bold", color=C["sim"] if sim else C["blue"])
        ax.text(0.5, 0.2, label, ha="center", va="center", fontsize=8, color="#333")
        if sim: ax.text(0.97, 0.92, "SIMULATED", ha="right", va="top", fontsize=6.5, color=C["verm"], weight="bold")

def simtag(ax): ax.text(1, 1.09, "SIMULATED", transform=ax.transAxes, ha="right", fontsize=8, color=C["verm"], weight="bold")
def save(fig, name): fig.savefig(MOCK / name, dpi=110); plt.close(fig)

win = one("SELECT min(difficulty_date) a, max(difficulty_date) b FROM mart.fct_discrepancy")
WIN = f"FAA Service Difficulty Reports dated {win.a:%d %b %Y} to {win.b:%d %b %Y}"
UNVER = (f"\u2020 {uv:,} of {int(f.ints):,} interruptions ({k['interruptions_unverified_pct']}%) use precaution codes whose labels are unverified "
         "(B, F, G, H inferred from narratives; I, J, L unknown).")

# Page 1
fig = page("1  Fleet reliability overview", WIN + "  |  real data")
cards(fig, [("SDR reports", f"{k['reports']:,}"), ("Aircraft reporting (excl. <UNKNOWN>)", f"{k['aircraft_reporting_excl_unknown']:,}"),
            ("Operational interruptions\u2020", f"{k['operational_interruptions']:,}"), ("Interruption rate\u2020", f"{k['operational_interruption_rate_pct']}%"),
            ("Operational repeat rate (30 d)", f"{k['operational_repeat_rate_pct']}%"),
            ("Mean hours between reports*", f"{k['mean_hours_between_reports']:.0f} h"),
            ("Hours per op. interruption*", f"{k['hours_per_operational_interruption']:,.0f} h"),
            ("Median report lag", f"{k['median_report_lag_days']:.0f} d")])
m = sql("SELECT year_month, reports, operational_interruptions FROM mart.kpi_monthly ORDER BY 1")
ax = fig.add_axes([0.05, 0.16, 0.27, 0.49]); ax.bar(m.year_month.str[5:], m.reports, color=C["sky"], label="Reports")
ax2 = ax.twinx(); ax2.plot(m.year_month.str[5:], m.operational_interruptions, color=C["verm"], marker="o", lw=2, label="Op. interruptions")
ax2.set_ylim(0, m.operational_interruptions.max()*1.4); ax2.spines["right"].set_visible(True)
ax.set_title("Reports and interruptions by month (2025)"); ax.set_ylabel("Reports"); ax2.set_ylabel("Interruptions")
fig.legend(loc="upper left", bbox_to_anchor=(0.05, 0.655), fontsize=8, frameon=False, ncol=2)
d = sql("""SELECT t.ata_chapter||' '||t.ata_chapter_name ch, sum(f.is_operational_interruption::INT) i, count(*) n
           FROM mart.fct_discrepancy f JOIN mart.dim_ata t USING (ata_key) GROUP BY 1 ORDER BY i DESC LIMIT 10""")[::-1]
ax = fig.add_axes([0.45, 0.16, 0.2, 0.49]); ax.barh(d.ch.str.title().str.slice(0, 26), d.i, color=C["blue"])
for y, (i, n) in enumerate(zip(d.i, d.n)): ax.text(i, y, f" {int(i):,} ({100*i/n:.0f}%)", va="center", fontsize=7.5)
ax.set_title("Interruptions by ATA chapter (top 10)"); ax.margins(x=0.35)
pr = sql("""SELECT p.precaution_code c, p.precaution_label l, p.label_basis ILIKE '%unverified%' u, count(*) n
            FROM mart.fct_discrepancy f JOIN mart.dim_precaution p USING (precaution_code)
            WHERE p.is_operational_interruption GROUP BY ALL ORDER BY n""")
ax = fig.add_axes([0.835, 0.16, 0.15, 0.49])
ax.barh([f"{c} {l.split(" /")[0][:22]}" + (" \u2020" if u else "") for c, l, u in zip(pr.c, pr.l, pr.u)], pr.n,
        color=[C["sky"] if u else C["blue"] for u in pr.u], hatch=None)
for bar, u in zip(ax.patches, pr.u):
    if u: bar.set_hatch("//"); bar.set_edgecolor("white")
for y, n in enumerate(pr.n): ax.text(n, y, f" {n:,}", va="center", fontsize=7.5)
ax.set_title("Interruptions by precaution code"); ax.margins(x=0.25); ax.tick_params(axis="y", labelsize=7.5)
ax.legend(handles=[Patch(color=C["blue"], label="label inferred"), Patch(facecolor=C["sky"], hatch="//", edgecolor="white", label="label unverified \u2020")],
          fontsize=7, frameon=False, loc="lower right")
fig.text(0.015, 0.075, "* Approximation from real data: mean hours between consecutive SDR reporting days on a tail (valid intervals only). "
         "Upper bound on true MTBF; an SDR is a reportable difficulty, not every failure.", fontsize=7.5, color=C["grey"])
fig.text(0.015, 0.05, UNVER + f"  Aircraft count excludes <UNKNOWN> (aircraft_key = -1, {k['reports_unknown_aircraft']} reports).", fontsize=7.5, color=C["grey"])
save(fig, "page1_fleet_reliability_overview.png")

# Page 2
fig = page("2  Failure trends", WIN + "  |  real data  |  by ATA chapter, model, part and month")
top = sql("""SELECT t.ata_chapter||' '||t.ata_chapter_name ch FROM mart.fct_discrepancy f JOIN mart.dim_ata t USING (ata_key)
             GROUP BY 1 ORDER BY sum(is_operational_interruption::INT) DESC LIMIT 5""").ch.tolist()
mm = sql("""SELECT d.year_month, t.ata_chapter||' '||t.ata_chapter_name ch, sum(is_operational_interruption::INT) i
            FROM mart.fct_discrepancy f JOIN mart.dim_ata t USING (ata_key) JOIN mart.dim_date d ON d.date_key=f.difficulty_date_key GROUP BY ALL""")
ax = fig.add_axes([0.05, 0.53, 0.42, 0.33])
for ch, col in zip(top, [C["blue"], C["orange"], C["green"], C["pink"], C["verm"]]):
    gg = mm[mm.ch == ch].sort_values("year_month"); ax.plot(gg.year_month, gg.i, marker="o", color=col, label=ch.title())
ax.set_title("Monthly operational interruptions\u2020, top 5 ATA chapters"); ax.legend(fontsize=7, frameon=False, ncol=2)
r = sql("SELECT ata_chapter||' '||ata_chapter_name ch, operational_repeat_rate_pct p, in_operation_reports n FROM mart.kpi_repeat_by_ata WHERE in_operation_reports>=100 ORDER BY p DESC LIMIT 10")[::-1]
ax = fig.add_axes([0.62, 0.53, 0.35, 0.33]); ax.barh(r.ch.str.title(), r.p, color=C["orange"])
for y, (p, n) in enumerate(zip(r.p, r.n)): ax.text(p, y, f" {p:.1f}% (n={int(n):,})", va="center", fontsize=7.5)
ax.set_title("30-day operational repeat rate (ATA chapters, 100+ in-op reports)"); ax.margins(x=0.3)
mb = sql("SELECT make||' '||model mdl, mtbr_hours h, intervals FROM mart.kpi_mtbr_by_model ORDER BY intervals DESC LIMIT 12")[::-1]
ax = fig.add_axes([0.1, 0.1, 0.37, 0.34]); ax.barh(mb.mdl, mb.h, color=C["sky"])
for y, (h, n) in enumerate(zip(mb.h, mb.intervals)): ax.text(h, y, f" {h:.0f} h (n={n})", va="center", fontsize=7.5)
ax.set_title("Mean hours between reports (approx. MTBF), 12 models with most intervals"); ax.margins(x=0.25)
p = sql("SELECT part_name, reports FROM mart.kpi_top_parts WHERE part_name <> '<UNKNOWN>' ORDER BY reports DESC LIMIT 10")[::-1]
ax = fig.add_axes([0.62, 0.1, 0.35, 0.34]); ax.barh(p.part_name.str.title(), p.reports, color=C["blue"]); ax.set_title("Most-reported parts")
fig.text(0.015, 0.045, UNVER, fontsize=7.5, color=C["grey"])
save(fig, "page2_failure_trends.png")

# Page 3
fig = page("3  Parts and components", WIN + "  |  real data  |  parts demand signal and reporting backlog (not a supply backlog)")
p = sql("SELECT part_name, reports, interruption_rate_pct FROM mart.kpi_top_parts WHERE part_name <> '<UNKNOWN>' ORDER BY reports DESC LIMIT 15")[::-1]
ax = fig.add_axes([0.1, 0.1, 0.33, 0.74]); ax.barh(p.part_name.str.title(), p.reports, color=C["blue"])
for y, (n, r_) in enumerate(zip(p.reports, p.interruption_rate_pct)): ax.text(n, y, f" {n:,} | {r_:.1f}% interrupt", va="center", fontsize=7.5)
ax.set_title("Top 15 parts by reports, with operational interruption rate"); ax.margins(x=0.35)
pc = sql("SELECT coalesce(part_condition,'(blank)') c, count(*) n FROM mart.fct_discrepancy GROUP BY 1 ORDER BY 2 DESC LIMIT 8")[::-1]
ax = fig.add_axes([0.55, 0.53, 0.42, 0.31]); ax.barh(pc.c.str.title(), pc.n, color=C["green"]); ax.set_title("Reported part condition (top 8)")
lg = sql("SELECT operator_code, reports, median_lag_days, p90_lag_days FROM mart.kpi_report_lag WHERE operator_code <> '<UNKNOWN>' ORDER BY reports DESC LIMIT 10")[::-1]
ax = fig.add_axes([0.55, 0.1, 0.42, 0.33]); ax.barh(lg.operator_code, lg.p90_lag_days, color=C["sky"], label="90th percentile")
ax.barh(lg.operator_code, lg.median_lag_days, color=C["blue"], height=0.45, label="Median")
ax.set_title("Reporting lag (difficulty to FAA submission), 10 largest reporting operators"); ax.set_xlabel("Days"); ax.legend(frameon=False, fontsize=8)
fig.text(0.015, 0.045, f"<UNKNOWN> parts and operators excluded from rankings (operator_key = -1: {k['reports_unknown_operator']} reports; part_key = -1: {k['reports_unknown_part']}).", fontsize=7.5, color=C["grey"])
save(fig, "page3_parts_and_components.png")

# Page 4: Simulated fleet + real-world context
fig = page("4  Simulated fleet (demo data) and real-world context",
           "Left: 20 simulated tails, 365 days of 2025, showing what a maintenance system would feed.  Right: REAL GAO fleet mission-capable rates.",
           sim=True, extra_foot="Simulated fleet: src/synthetic.py, seed 42 | Real-world context: GAO-22-104533, Table 1")
cards(fig, [("MC rate", f"{k['SIM_mc_rate_pct']}%"), ("NMCM", f"{k['SIM_nmcm_pct']}%"), ("NMCS", f"{k['SIM_nmcs_pct']}%"),
            ("MTBF (flight h, unsched.)", f"{k['SIM_mtbf_flight_hours']:.1f}"), ("MTTR (h, unsched.)", f"{k['SIM_mttr_hours_unscheduled']:.0f}"),
            ("Avg open reqs / day", f"{k['SIM_avg_open_requisitions_per_day']}"), ("Requisitions late", f"{k['SIM_pct_requisitions_late']}%")],
      y=0.75, x0=0.015, width=0.68, sim=True)
sm = sql("""SELECT strftime(date,'%m') ym, 100*avg(is_mission_capable::INT) mc, 100*avg((status='NMCM')::INT) nmcm, 100*avg((status='NMCS')::INT) nmcs
            FROM mart.syn_fct_status_daily GROUP BY 1 ORDER BY 1""")
ax = fig.add_axes([0.045, 0.1, 0.2, 0.52])
ax.bar(sm.ym, sm.mc, color=C["blue"], label="MC"); ax.bar(sm.ym, sm.nmcm, bottom=sm.mc, color=C["orange"], label="NMCM")
ax.bar(sm.ym, sm.nmcs, bottom=sm.mc+sm.nmcm, color=C["pink"], label="NMCS"); ax.set_ylim(0, 100); ax.set_ylabel("% of tail-days")
ax.set_title("Status mix by month"); ax.legend(frameon=False, fontsize=7, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.06)); simtag(ax)
bd = sql("SELECT date, open_requisitions, overdue_requisitions, avg_age_days FROM mart.syn_fct_backlog_daily ORDER BY date")
ax = fig.add_axes([0.3, 0.1, 0.38, 0.52])
ax.fill_between(bd.date, bd.open_requisitions, step="post", color=C["sky"], label="Open requisitions")
ax.fill_between(bd.date, bd.overdue_requisitions, step="post", color=C["verm"], label="Overdue (past due date)")
ax.set_title(f"Parts backlog over time (syn_fct_backlog_daily; {k['SIM_requisitions']} requisitions, {k['SIM_micap_requisitions']} MICAP)")
ax.legend(frameon=False, fontsize=8, loc="upper left"); ax.set_ylabel("Requisitions"); simtag(ax)
ax.text(0.99, 0.95, f"Weighted avg backlog age {k['SIM_backlog_avg_age_days_weighted']} d\nAvg backorder (late reqs) {k['SIM_avg_backorder_days_late_only']:.1f} d",
        transform=ax.transAxes, ha="right", va="top", fontsize=8, color=C["grey"])
# Real-world context panel
fig.patches.append(plt.Rectangle((0.715, 0.04), 0.28, 0.82, transform=fig.transFigure, fill=False, ec=C["blue"], lw=1.5))
fig.text(0.725, 0.845, "REAL-WORLD CONTEXT (real data, GAO)", fontsize=10, weight="bold", color=C["blue"], va="top")
fig.text(0.725, 0.815, f"FY2021: {k['GAO_fy2021_fleets_meeting_goal']} of {k['GAO_fy2021_fleets']} fleets met their MC goal; "
         f"average {abs(k['GAO_fy2021_avg_gap_to_goal_pts'])} pts below goal.\nB-1B (Ellsworth AFB): {k['GAO_fy2021_B1B_mc_pct']}% vs {k['GAO_fy2021_B1B_goal_pct']}% goal.",
         fontsize=8.5, va="top")
gs = g.sort_values("mc_rate_pct")
ax = fig.add_axes([0.79, 0.1, 0.19, 0.6])
ax.barh(gs.aircraft, gs.mc_rate_pct, color=[C["verm"] if a_ == "B-1B" else C["blue"] for a_ in gs.aircraft])
ax.scatter(gs.mc_goal_pct, range(len(gs)), marker="|", s=250, color="black", zorder=3, label="FY2021 goal")
for y, v in enumerate(gs.mc_rate_pct): ax.text(v - 1, y, f"{v:.1f}", va="center", ha="right", fontsize=7.5, color="white")
ax.axvline(k["SIM_mc_rate_pct"], color=C["sim"], ls="--", lw=1.2)
ax.text(k["SIM_mc_rate_pct"], -0.9, f" simulated fleet {k['SIM_mc_rate_pct']}%", fontsize=7, color=C["sim"], va="center")
ax.set_xlim(0, 105); ax.set_ylim(-1.3, len(gs) - 0.5); ax.set_title("MC rate FY2021 vs goal (%)"); ax.legend(frameon=False, fontsize=7, loc="lower right")
save(fig, "page4_simulated_fleet_and_real_context.png")

# Page 5
fig = page("5  Engine health (NASA C-MAPSS)", f"Run-to-failure turbofan SIMULATION by NASA (public dataset, not field data)  |  {k['engines']} engines, datasets FD001-FD004")
cards(fig, [("Engines", f"{k['engines']}"), ("Mean cycles to failure", f"{eng.m:.0f}"), ("Shortest life", f"{int(eng.lo)}"), ("Longest life", f"{int(eng.hi)}")], y=0.74)
e = sql("SELECT dataset, cycles_to_failure c FROM mart.fct_engine_run")
ax = fig.add_axes([0.05, 0.1, 0.55, 0.53])
for ds, col in zip(sorted(e.dataset.unique()), [C["blue"], C["orange"], C["green"], C["pink"]]):
    ax.hist(e[e.dataset == ds].c, bins=range(120, 560, 15), histtype="step", lw=2, color=col, label=ds)
ax.set_title("Cycles to failure distribution by dataset"); ax.set_xlabel("Cycles"); ax.set_ylabel("Engines"); ax.legend(frameon=False)
km = sql("SELECT * FROM mart.kpi_engine_mtbf ORDER BY dataset")
ax = fig.add_axes([0.68, 0.1, 0.29, 0.53]); ax.bar(km.dataset, km.mean_cycles_to_failure, color=C["sky"])
for x, (mv, cv) in enumerate(zip(km.mean_cycles_to_failure, km.coeff_variation)): ax.text(x, mv, f"{mv:.0f}\nCV {cv:.2f}", ha="center", va="bottom", fontsize=8)
ax.set_title("Mean cycles to failure (engine MTBF, simulated cycles)"); ax.set_ylim(0, km.mean_cycles_to_failure.max()*1.25)
save(fig, "page5_engine_health.png")
print(json.dumps(k, indent=1))
