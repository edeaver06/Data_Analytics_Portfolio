"""CLEARLY SYNTHETIC layer. Public data has no tail-level status, work-order or requisition records.

Simulates a notional 20-aircraft fleet for 2025 so the dashboard can show MC/NMCM/NMCS, MTTR and parts
backlog visuals. Real inputs: the FAA SDR rate of operational interruptions per flight hour and the real
ATA-chapter mix behind those interruptions. Every other parameter is an assumption (syn_assumptions),
chosen so the simulated mission-capable rate lands in the range GAO reports for real military fleets
(roughly 32-75%, FY2015-21). Every table carries is_synthetic = TRUE. Do not quote these numbers as findings.
"""
import numpy as np
import pandas as pd

SEED = 42
ASSUMPTIONS = {
    "fleet_size": (20, "notional fleet size"),
    "sim_days": (365, "simulated days (calendar 2025)"),
    "flight_hours_per_sortie": (6.0, "assumed sortie length when an MC aircraft flies"),
    "sortie_probability": (0.30, "assumed chance an MC aircraft flies on a given day"),
    "rate_multiplier": (60.0, "assumed ratio of all grounding defects to SDR-reportable interruptions (SDRs capture only serious events; military fleets also log far more write-ups per hour)"),
    "repair_days_median": (2.5, "assumed median hands-on repair (NMCM), lognormal sigma 0.8"),
    "awaiting_maint_days_median": (1.0, "assumed median wait for technicians before repair starts (NMCM), lognormal sigma 0.7"),
    "p_needs_part": (0.55, "assumed share of unscheduled failures that need a part not on base"),
    "lead_time_days_median": (9.0, "assumed median requisition lead time, lognormal sigma 0.9"),
    "requisition_due_days": (7, "assumed priority (due) date after requisition"),
    "phase_interval_fh": (300, "assumed flight hours between phase inspections"),
    "phase_days_median": (14.0, "assumed median phase inspection duration (NMCM), lognormal sigma 0.3"),
    "phase_requisitions_mean": (8.0, "assumed mean bench-stock requisitions raised per phase inspection (Poisson; do not ground)"),
}


def build(con):
    rng = np.random.default_rng(SEED)
    A = {k: v[0] for k, v in ASSUMPTIONS.items()}
    hrs, ints = con.execute("SELECT sum(hours_between), sum(ends_in_interruption::INT) FROM mart.fct_tail_interval WHERE is_valid").fetchone()
    rate = (float(ints) / float(hrs)) if hrs and ints else 1 / 3000
    ata = con.execute("""SELECT d.ata_chapter, count(*) n FROM mart.fct_discrepancy f JOIN mart.dim_ata d USING (ata_key)
                         WHERE f.is_operational_interruption AND d.ata_chapter <> '--' GROUP BY 1""").df()
    if ata.empty:
        ata = pd.DataFrame({"ata_chapter": ["32"], "n": [1]})
    p_ata = (ata.n / ata.n.sum()).to_numpy()
    p_fail_per_fh = rate * A["rate_multiplier"]
    days = pd.date_range("2025-01-01", periods=A["sim_days"], freq="D")
    status, wos, reqs = [], [], []
    wo = rq = 0

    def add_req(tail, ch, day, wo_id, grounding):
        nonlocal rq
        rq += 1
        lead = max(0.5, rng.lognormal(np.log(A["lead_time_days_median"]), 0.9))
        reqs.append(dict(requisition_id=rq, work_order_id=wo_id, tail_id=tail, ata_chapter=ch,
                         priority="MICAP (grounding)" if grounding else "Routine (bench stock)",
                         requisition_date=day.date(), due_date=(day + pd.Timedelta(days=A["requisition_due_days"])).date(),
                         receipt_date=(day + pd.Timedelta(days=lead)).date(), lead_time_days=round(lead, 2),
                         backorder_days=round(max(0.0, lead - A["requisition_due_days"]), 2), is_synthetic=True))
        return lead

    for t in range(1, A["fleet_size"] + 1):
        tail = f"SIM-{t:02d}"
        st = ["MC"] * len(days); reason = [None] * len(days); fh = [0.0] * len(days)
        since_phase = rng.uniform(0, A["phase_interval_fh"])  # stagger phase inspections
        i = 0
        while i < len(days):
            if since_phase >= A["phase_interval_fh"]:  # scheduled phase inspection
                wo += 1
                dur = max(3.0, rng.lognormal(np.log(A["phase_days_median"]), 0.3))
                opened = days[i] + pd.Timedelta(hours=8)
                for _ in range(rng.poisson(A["phase_requisitions_mean"])):
                    add_req(tail, rng.choice(ata.ata_chapter, p=p_ata), days[i], wo, False)
                wos.append(dict(work_order_id=wo, tail_id=tail, ata_chapter="05", work_type="Scheduled phase inspection",
                                opened_at=opened, closed_at=opened + pd.Timedelta(days=dur), awaiting_parts_days=0.0,
                                hands_on_days=round(dur, 2), repair_hours=round(dur * 24, 1), is_synthetic=True))
                n = int(np.ceil(dur))
                for j in range(i, min(len(days), i + n)):
                    st[j] = "NMCM"; reason[j] = "05"
                i += n; since_phase = 0.0; continue
            flew = rng.random() < A["sortie_probability"]
            hours = A["flight_hours_per_sortie"] if flew else 0.0
            fh[i] = hours; since_phase += hours
            if flew and rng.random() < 1 - np.exp(-p_fail_per_fh * hours):  # unscheduled failure on this sortie
                wo += 1
                ch = rng.choice(ata.ata_chapter, p=p_ata)
                wait_m = max(0.0, rng.lognormal(np.log(A["awaiting_maint_days_median"]), 0.7))
                repair = max(0.25, rng.lognormal(np.log(A["repair_days_median"]), 0.8))
                wait_p = add_req(tail, ch, days[i], wo, True) if rng.random() < A["p_needs_part"] else 0.0
                opened = days[i] + pd.Timedelta(hours=float(rng.uniform(10, 20)))
                total = wait_m + wait_p + repair
                wos.append(dict(work_order_id=wo, tail_id=tail, ata_chapter=ch, work_type="Unscheduled repair",
                                opened_at=opened, closed_at=opened + pd.Timedelta(days=total), awaiting_parts_days=round(wait_p, 2),
                                hands_on_days=round(wait_m + repair, 2), repair_hours=round(total * 24, 1), is_synthetic=True))
                # status from the day after the sortie: NMCM while awaiting/under maintenance, NMCS while awaiting parts
                k = i + 1
                for label, d in (("NMCM", wait_m), ("NMCS", wait_p), ("NMCM", repair)):
                    for _ in range(int(round(d))):
                        if k < len(days):
                            st[k] = label; reason[k] = ch; k += 1
                i = k; continue
            i += 1
        for d, s, r, h in zip(days, st, reason, fh):
            status.append(dict(tail_id=tail, date_key=int(d.strftime("%Y%m%d")), date=d.date(), status=s,
                               is_mission_capable=s == "MC", reason_ata_chapter=r,
                               reason_type=None if r is None else ("Scheduled phase inspection" if r == "05" else "Unscheduled failure"), flight_hours=h, is_synthetic=True))
    frames = {
        "syn_dim_tail": pd.DataFrame({"tail_id": [f"SIM-{t:02d}" for t in range(1, A["fleet_size"] + 1)], "is_synthetic": True}),
        "syn_fct_status_daily": pd.DataFrame(status), "syn_fct_work_order": pd.DataFrame(wos),
        "syn_fct_requisition": pd.DataFrame(reqs),
        "syn_assumptions": pd.DataFrame([dict(parameter=k, value=str(v[0]), note=v[1]) for k, v in ASSUMPTIONS.items()]
                                        + [dict(parameter="sdr_interruptions_per_flight_hour", value=f"{rate:.6g}",
                                                note="REAL input: operational interruptions / valid flight hours from FAA SDRS")]),
    }
    for name, df in frames.items():
        con.register("tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE mart.{name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    # requisition backlog per day (open = requisitioned and not yet received)
    con.execute("""CREATE OR REPLACE TABLE mart.syn_fct_backlog_daily AS
      SELECT d.date_key, d.date, count(r.requisition_id) AS open_requisitions,
             count(r.requisition_id) FILTER (WHERE d.date > r.due_date) AS overdue_requisitions,
             coalesce(avg(date_diff('day', r.requisition_date, d.date)),0) AS avg_age_days, TRUE AS is_synthetic
      FROM (SELECT DISTINCT date_key, date FROM mart.syn_fct_status_daily) d
      LEFT JOIN mart.syn_fct_requisition r ON r.requisition_date <= d.date AND d.date < r.receipt_date
      GROUP BY 1,2 ORDER BY 1""")
    con.execute("""CREATE OR REPLACE TABLE mart.syn_kpi_fleet AS
      SELECT 'SYNTHETIC' AS data_flag,
        (SELECT round(100*avg(is_mission_capable::INT),1) FROM mart.syn_fct_status_daily) AS mc_rate_pct,
        (SELECT round(100*avg((status='NMCM')::INT),1) FROM mart.syn_fct_status_daily) AS nmcm_pct,
        (SELECT round(100*avg((status='NMCS')::INT),1) FROM mart.syn_fct_status_daily) AS nmcs_pct,
        (SELECT round(sum(flight_hours),0) FROM mart.syn_fct_status_daily) AS total_flight_hours,
        (SELECT round((SELECT sum(flight_hours) FROM mart.syn_fct_status_daily)/count(*),1) FROM mart.syn_fct_work_order WHERE work_type='Unscheduled repair') AS mtbf_flight_hours,
        (SELECT round(avg(repair_hours),1) FROM mart.syn_fct_work_order WHERE work_type='Unscheduled repair') AS mttr_hours,
        (SELECT count(*) FROM mart.syn_fct_work_order) AS work_orders,
        (SELECT count(*) FROM mart.syn_fct_requisition) AS requisitions,
        (SELECT round(avg(lead_time_days),1) FROM mart.syn_fct_requisition) AS mean_parts_lead_days,
        (SELECT round(100*avg((backorder_days>0)::INT),1) FROM mart.syn_fct_requisition) AS pct_requisitions_late,
        (SELECT round(avg(open_requisitions),1) FROM mart.syn_fct_backlog_daily) AS avg_open_requisitions,
        TRUE AS is_synthetic""")
