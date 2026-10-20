"""Aircraft Readiness dashboard. Runs on the bundled parquet extract in app/data (no build step).

Real data: FAA Service Difficulty Reports, 1 Jan - 29 Jun 2025, and NASA C-MAPSS engine simulations.
The 'Simulated fleet (demo data)' page is synthetic and labelled as such.
"""
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data"
st.set_page_config(page_title="Aircraft Readiness", page_icon="✈️", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


SRC = "Source: FAA Service Difficulty Reporting System, reports dated 1 Jan - 29 Jun 2025."
PAGES = ["Overview", "Disruptions & repeats by system", "Hours between reports by model", "Reporting lag",
         "Top parts", "Engine life (NASA C-MAPSS)", "Simulated fleet (demo data)"]
page = st.sidebar.radio("Page", PAGES)
st.sidebar.caption("Every page except 'Simulated fleet' uses real public data.")

d = load("discrepancy")
d["system"] = d.ata_chapter + " " + d.ata_chapter_name.str.title()

if page == "Overview":
    st.title("Aircraft Readiness: what grounds airplanes, and how fast is it reported?")
    iv = load("tail_interval")
    c = st.columns(5)
    c[0].metric("Difficulty reports", f"{len(d):,}")
    c[1].metric("Aircraft models", f"{d[d.model != '<UNKNOWN>'].groupby(['make', 'model']).ngroups:,}")
    c[2].metric("Operational disruptions", f"{int(d.is_operational_interruption.sum()):,}", f"{100*d.is_operational_interruption.mean():.1f}% of reports", delta_color="off")
    inop = d.is_in_operation.sum()
    c[3].metric("Operational repeat rate", f"{100*d.is_repeat_30d.sum()/inop:.1f}%", "same tail + system within 30 days", delta_color="off")
    c[4].metric("Flight hours per disruption", f"{iv.hours_between.sum()/iv.ends_in_interruption.sum():,.0f}")
    m = d.groupby("year_month").agg(reports=("system", "size"), disruptions=("is_operational_interruption", "sum")).reset_index()
    st.plotly_chart(px.bar(m, x="year_month", y=["reports", "disruptions"], barmode="group",
                           title="Monthly reports and operational disruptions", labels={"value": "count", "year_month": "month"}),
                    width="stretch")
    st.caption(SRC + " A disruption = unscheduled landing, aborted takeoff, return to gate, engine shutdown, emergency declared, etc. (codes inferred from report text).")

elif page == "Disruptions & repeats by system":
    st.title("Disruptions and repeat defects by ATA system")
    g = d.groupby("system").agg(reports=("system", "size"), disruptions=("is_operational_interruption", "sum"),
                                in_operation=("is_in_operation", "sum"), repeats=("is_repeat_30d", "sum")).reset_index()
    g["disruption_rate_pct"] = (100 * g.disruptions / g.reports).round(1)
    g["repeat_rate_pct"] = (100 * g.repeats / g.in_operation.where(g.in_operation > 0)).round(1)
    top = g.sort_values("disruptions", ascending=False).head(15)
    st.plotly_chart(px.bar(top[::-1], x="disruptions", y="system", orientation="h", hover_data=["reports", "disruption_rate_pct"],
                           title="Top 15 systems by operational disruptions"), width="stretch")
    rep = g[g.in_operation >= 50].sort_values("repeat_rate_pct", ascending=False).head(15)
    st.plotly_chart(px.bar(rep[::-1], x="repeat_rate_pct", y="system", orientation="h", hover_data=["in_operation", "repeats"],
                           title="Repeat rate: in-operation reports repeating on the same tail and system within 30 days (systems with 50+ in-operation reports)"),
                    width="stretch")
    st.dataframe(g.sort_values("reports", ascending=False), width="stretch", hide_index=True)
    st.caption(SRC)

elif page == "Hours between reports by model":
    st.title("Flight hours between reported difficulties, by model")
    st.info("Approximation of MTBF: hours flown between consecutive reporting days on the same aircraft. "
            "Reports are only reportable difficulties, so this is an upper bound and reflects operator reporting habits.")
    iv = load("tail_interval")
    min_n = st.slider("Minimum intervals per model", 10, 200, 20)
    g = iv.groupby(["make", "model"]).agg(intervals=("hours_between", "size"), mean_hours=("hours_between", "mean"),
                                          median_hours=("hours_between", "median")).reset_index()
    g = g[g.intervals >= min_n].sort_values("mean_hours")
    g["label"] = g.make + " " + g.model
    st.plotly_chart(px.bar(g, x="label", y="mean_hours", hover_data=["intervals", "median_hours"],
                           title=f"Mean hours between reports ({len(g)} models)", labels={"label": "model"}), width="stretch")
    st.metric("All models: mean / median hours between reports", f"{iv.hours_between.mean():.0f} / {iv.hours_between.median():.0f}")
    st.caption(SRC)

elif page == "Reporting lag":
    st.title("Days from difficulty to FAA submission")
    lag = d.dropna(subset=["report_lag_days"])
    g = lag.groupby("operator_code").agg(reports=("report_lag_days", "size"), median_lag=("report_lag_days", "median"),
                                         p90_lag=("report_lag_days", lambda s: s.quantile(0.9))).reset_index()
    g = g[(g.reports >= 50) & (g.operator_code != "<UNKNOWN>")].sort_values("reports", ascending=False).head(20)
    c = st.columns(2)
    c[0].metric("Median lag (all reports)", f"{lag.report_lag_days.median():.0f} days")
    c[1].metric("Share over 3 days", f"{100*(lag.report_lag_days > 3).mean():.1f}%")
    st.plotly_chart(px.bar(g, x="operator_code", y=["median_lag", "p90_lag"], barmode="group",
                           title="Top 20 operators by volume: median and 90th-percentile lag (days)"), width="stretch")
    st.caption(SRC + " SDRS publishes operator designators only, not names.")

elif page == "Top parts":
    st.title("Parts reported most often (demand signal, not a backlog)")
    p = d[~d.part_name.isin(["<UNKNOWN>", "UNKNOWN", "NONE", "N/A"])]
    g = p.groupby("part_name").agg(reports=("part_name", "size"), disruptions=("is_operational_interruption", "sum"),
                                   condition=("part_condition", lambda s: s.mode().iat[0] if s.notna().any() else None)).reset_index()
    g = g.sort_values("reports", ascending=False).head(25)
    st.plotly_chart(px.bar(g[::-1], x="reports", y="part_name", orientation="h", color="condition",
                           title="Top 25 parts by reports (colour = most common condition)"), width="stretch")
    st.caption(SRC + " Part demand signal, not a backlog: public data has no requisitions.")

elif page == "Engine life (NASA C-MAPSS)":
    st.title("SIMULATED: engine cycles to failure (NASA C-MAPSS simulation)")
    e = load("engine_run")
    st.plotly_chart(px.box(e, x="cycles_to_failure", y="dataset", points="all", title=f"{len(e)} simulated turbofans run to failure"),
                    width="stretch")
    st.dataframe(e.groupby("dataset").cycles_to_failure.describe().round(1), width="stretch")
    st.caption("Source: NASA C-MAPSS Turbofan Engine Degradation Simulation (train FD001-FD004). Simulated, not field data.")

else:
    st.title("SIMULATED fleet (demo data, not real aircraft)")
    st.error("SYNTHETIC DATA. A notional 20-aircraft fleet simulated for 2025 to demonstrate readiness visuals "
             "(MC/NMCM/NMCS, MTTR, parts backlog). Only the failure rate and system mix come from real FAA reports; "
             "every other parameter is an assumption listed below. These are not findings.")
    k = load("syn_kpi_fleet").iloc[0]
    c = st.columns(6)
    c[0].metric("MC rate", f"{k.mc_rate_pct}%"); c[1].metric("NMCM", f"{k.nmcm_pct}%"); c[2].metric("NMCS", f"{k.nmcs_pct}%")
    c[3].metric("MTBF (flight hrs)", f"{k.mtbf_flight_hours}"); c[4].metric("MTTR (hrs)", f"{k.mttr_hours}")
    c[5].metric("Requisitions", f"{int(k.requisitions)}", f"{k.pct_requisitions_late}% late", delta_color="off")
    s = load("syn_fct_status_daily")
    s["month"] = pd.to_datetime(s.date).dt.to_period("M").astype(str)
    m = s.groupby(["month", "status"]).size().reset_index(name="aircraft_days")
    st.plotly_chart(px.bar(m, x="month", y="aircraft_days", color="status", title="Aircraft-days by status (SYNTHETIC)",
                           color_discrete_map={"MC": "#2b8a3e", "NMCM": "#e67700", "NMCS": "#c92a2a"}), width="stretch")
    b = load("syn_fct_backlog_daily")
    st.plotly_chart(px.line(b, x="date", y=["open_requisitions", "overdue_requisitions"], title="Open and overdue parts requisitions (SYNTHETIC)"),
                    width="stretch")
    r = load("syn_fct_requisition")
    st.plotly_chart(px.histogram(r, x="lead_time_days", color="priority", nbins=40, title="Requisition lead time, days (SYNTHETIC)"),
                    width="stretch")
    st.subheader("Assumptions"); st.dataframe(load("syn_assumptions"), width="stretch", hide_index=True)
