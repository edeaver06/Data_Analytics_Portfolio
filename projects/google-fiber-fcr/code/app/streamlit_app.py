"""Google Fiber repeat-calls dashboard. Run from code/: streamlit run app/streamlit_app.py"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).resolve().parent / "data" / "daily_calls.csv"
FOOTER = ("Source: Google Data Analytics certificate case study (fictional Google Fiber data, 3 markets, "
          "Jan 1 - Mar 31, 2022). Repeat call = another call within 7 days of the first.")
COLORS = {"Wi-Fi & Internet": "#0072B2", "Technical Troubleshooting": "#56B4E9",
          "Account Management & Billing": "#D55E00", "Scheduling": "#E69F00", "Construction": "#009E73"}


@st.cache_data(show_spinner=False)
def load():
    return pd.read_csv(DATA, parse_dates=["date"])


def rates(df, by):
    g = df.groupby(by, as_index=False)[["first_calls", "repeat_calls"]].sum()
    g["repeat_rate_pct"] = (100 * g.repeat_calls / g.first_calls).round(1)
    g["share_of_repeats_pct"] = (100 * g.repeat_calls / g.repeat_calls.sum()).round(1)
    return g


def style(fig, h=420):
    fig.update_layout(template="simple_white", height=h, margin=dict(l=10, r=10, t=60, b=10), legend_title_text="")
    return fig


def footer():
    st.caption(FOOTER)


def overview(d):
    st.title("Google Fiber: Why do customers call back?")
    st.markdown("When a support call doesn't fix the problem, the customer calls again. This dashboard shows "
                "**which problems and which markets cause the most repeat calls**, so the support team knows where a fix pays off most.")
    tot = d[["first_calls", "repeat_calls"]].sum()
    c = rates(d, "problem_category")
    wt = c[c.problem_category.isin(["Wi-Fi & Internet", "Technical Troubleshooting"])].repeat_calls.sum() / tot.repeat_calls
    k = st.columns(4)
    k[0].metric("First calls", f"{tot.first_calls:,}")
    k[1].metric("Repeat calls (within 7 days)", f"{tot.repeat_calls:,}")
    k[2].metric("Overall repeat rate", f"{tot.repeat_calls / tot.first_calls:.1%}")
    k[3].metric("Repeats from Wi-Fi + Technical", f"{wt:.1%}")
    st.markdown("""
**How to read this:** a *repeat rate* of 30% means that for every 100 first calls, 30 more calls came back within a week.

**Main findings**
- Two problem types, Wi-Fi & Internet and Technical Troubleshooting, cause most repeat calls.
- Market_3 has the highest repeat rate (44.7%; 36.7% without its impossible Billing rows).
- Market_3's Billing numbers are impossible (more repeats than first calls), so they're most likely a data error. See *Billing: a data check*.

Use the pages on the left to explore.""")
    footer()


def problems(d):
    st.header("Which problems cause the most callbacks?")
    mk = st.multiselect("Markets", sorted(d.market.unique()), default=sorted(d.market.unique()))
    metric = st.radio("Show", ["Number of repeat calls", "Repeat rate"], horizontal=True)
    c = rates(d[d.market.isin(mk)], "problem_category")
    if c.empty:
        st.info("Pick at least one market."); return
    col = "repeat_calls" if metric == "Number of repeat calls" else "repeat_rate_pct"
    c = c.sort_values(col)
    fig = px.bar(c, x=col, y="problem_category", orientation="h", color="problem_category", color_discrete_map=COLORS,
                 text=col, labels={col: metric, "problem_category": ""})
    fig.update_layout(showlegend=False)
    st.plotly_chart(style(fig), width="stretch")
    st.dataframe(c.rename(columns={"problem_category": "Problem type", "first_calls": "First calls", "repeat_calls": "Repeat calls",
                                   "repeat_rate_pct": "Repeat rate (%)", "share_of_repeats_pct": "Share of all repeats (%)"}),
                 hide_index=True)
    st.markdown("**What this means:** Wi-Fi and technical problems create the most callbacks by volume; Scheduling and Billing have high *rates* but fewer calls.")
    footer()


def markets(d):
    st.header("Which market has the most callbacks?")
    m = rates(d, "market")
    fig = px.bar(m, x="market", y="repeat_rate_pct", text="repeat_rate_pct", color_discrete_sequence=["#0072B2"],
                 labels={"market": "", "repeat_rate_pct": "Repeat rate (%)"})
    st.plotly_chart(style(fig), width="stretch")
    st.subheader("Repeat rate by market and problem type")
    mc = rates(d, ["market", "problem_category"]).pivot(index="problem_category", columns="market", values="repeat_rate_pct")
    st.plotly_chart(style(px.imshow(mc, text_auto=".1f", color_continuous_scale="Blues", aspect="auto",
                                    labels={"color": "Repeat rate (%)", "x": "", "y": ""})), width="stretch")
    st.markdown("**What this means:** market_3 stands out. Before blaming its support team, check its data (next page).")
    footer()


def billing(d):
    st.header("Billing: a data check")
    st.markdown("Billing looks like the worst problem type. But in market_3, Billing logs **more repeat calls than first calls**, "
                "which is impossible if repeats are follow-ups to first calls.")
    b = d[d.problem_category == "Account Management & Billing"]
    by_m = rates(b, "market")
    st.dataframe(by_m[["market", "first_calls", "repeat_calls", "repeat_rate_pct"]].rename(columns={
        "market": "Market", "first_calls": "Billing first calls", "repeat_calls": "Billing repeat calls", "repeat_rate_pct": "Repeat rate (%)"}),
        hide_index=True)
    excl = st.toggle("Leave out market_3", value=True)
    s = b[b.market != "market_3"] if excl else b
    r = s.repeat_calls.sum() / s.first_calls.sum()
    st.metric("Billing repeat rate" + (" without market_3" if excl else " (all markets)"), f"{r:.1%}")
    st.markdown("**What this means:** without market_3, Billing is in line with other problem types. Fix market_3's data before acting on Billing.")
    footer()


def weekly(d):
    st.header("Do callbacks change week to week?")
    cats = st.multiselect("Problem types", list(COLORS), default=list(COLORS))
    s = d[d.problem_category.isin(cats)].copy()
    if s.empty:
        st.info("Pick at least one problem type."); return
    s["week"] = s.date.dt.to_period("W-SUN").dt.start_time
    w = s.groupby("week", as_index=False)[["first_calls", "repeat_calls"]].sum()
    long = w.melt("week", var_name="kind", value_name="calls").replace({"first_calls": "First calls", "repeat_calls": "Repeat calls"})
    fig = px.line(long, x="week", y="calls", color="kind", markers=True, labels={"week": "Week starting", "calls": "Calls", "kind": ""})
    fig.update_xaxes(tickformat="%b %d")
    st.plotly_chart(style(fig), width="stretch")
    st.caption("The first week is partial because the data starts on Jan 1, 2022.")
    st.markdown("**What this means:** repeat calls move with total call volume. That's a pattern, not proof of what causes them.")
    footer()


PAGES = {"Overview": overview, "Problem types": problems, "Markets": markets, "Billing: a data check": billing, "Week by week": weekly}


def main():
    st.set_page_config(page_title="Google Fiber repeat calls", page_icon="📞", layout="wide")
    page = st.sidebar.radio("Page", list(PAGES))
    PAGES[page](load())


main()
