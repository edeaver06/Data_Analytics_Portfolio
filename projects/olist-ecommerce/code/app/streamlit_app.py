"""Olist e-commerce dashboard (aggregates only). Run from code/: streamlit run app/streamlit_app.py"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

D = Path(__file__).resolve().parent / "data"
BLUE, ORANGE, GREY = "#0072B2", "#D55E00", "#999999"
FOOTER = ("Source: Olist Brazilian E-Commerce Public Dataset (Kaggle, CC BY-NC-SA 4.0), about 99k orders, Sep 2016 - Oct 2018. "
          "Only aggregated summaries are shown. Late = delivered after the estimated date. Analysis by Evan Deaver.")


@st.cache_data(show_spinner=False)
def load():
    t = {f.stem.replace("mart_", ""): pd.read_csv(f) for f in D.glob("mart_*.csv")}
    t["H"] = json.loads((D / "headline_metrics.json").read_text())
    return t


def style(fig, h=420):
    fig.update_layout(template="simple_white", height=h, margin=dict(l=10, r=10, t=60, b=10), legend_title_text="")
    return fig


def overview(t):
    H = t["H"]
    st.title("Olist: what drives bad reviews?")
    st.markdown("Olist connects small Brazilian sellers to big online marketplaces. Its reputation lives on 1-5 star reviews. "
                "This dashboard asks how strongly **late deliveries** are linked to bad reviews, and where lateness comes from.")
    k = st.columns(4)
    k[0].metric("Orders", f"{H['orders']:,}")
    k[1].metric("Delivered late", f"{H['late_rate_pct']:.2f}%")
    k[2].metric("Avg stars, reviewed after delivery: late vs on time",
                f"{H['late_after_delivery_score']:.2f} vs {H['ontime_after_delivery_score']:.2f}")
    k[3].metric("Sellers making 80% of sales", f"{H['sellers_for_80pct_gmv']:,} of {H['sellers_total']:,}")
    st.markdown(f"""
**Main findings**
- Counting reviews written after delivery, late orders average **{H['late_after_delivery_score']:.2f}★** vs **{H['ontime_after_delivery_score']:.2f}★** on time, a gap of **{H['gap_after_delivery']:+.2f}★**.
- Across all reviews the gap looks far bigger ({H['late_avg_score']:.2f}★ vs {H['ontime_avg_score']:.2f}★), because {H['pct_late_reviews_before_delivery']:.0f}% of late orders were reviewed *before* the parcel arrived. Much of the damage is the review prompt arriving too early.
- "Bad sellers" are only part of it: last year's least reliable sellers are late {H['seller_q4_late_pct']}% vs {H['seller_q1_late_pct']}% for the best (about {H['seller_q4_late_pct'] / H['seller_q1_late_pct']:.1f}x), while {H['worst_lane'].replace('->', ' → ')} is late {H['worst_lane_late_pct']}% of the time.

These are associations in observed data, not proof of cause.""")
    st.caption(FOOTER)


def lateness(t):
    st.header("How much does a late delivery hurt the review?")
    d = t["delivery_vs_reviews"].copy()
    d["bucket"] = d.late_bucket.str.replace(r"^\d\. ", "", regex=True)
    m = st.radio("Show", ["Average stars", "Share of 1-2 star reviews"], horizontal=True)
    y = "avg_score" if m == "Average stars" else "pct_1_2_star"
    fig = px.bar(d, x="bucket", y=y, text=d[y].round(2), hover_data=["orders"], color_discrete_sequence=[BLUE],
                 labels={"bucket": "When the order arrived", "avg_score": "Average stars", "pct_1_2_star": "1-2 star reviews (%)"})
    st.plotly_chart(style(fig), width="stretch")
    st.markdown("**What this means:** reviews drop sharply after a few days late; 8+ days late, most reviews are 1-2 stars.")
    st.caption(FOOTER)


def timing(t):
    H = t["H"]
    st.header("Were late orders reviewed before they even arrived?")
    d = t["late_vs_ontime_by_timing"]
    fig = px.bar(d, x="delivery", y="avg_score", color="review_timing", barmode="group", text="avg_score",
                 hover_data=["orders", "pct_of_group"], color_discrete_map={"before delivery": ORANGE, "after delivery": BLUE},
                 labels={"delivery": "", "avg_score": "Average stars", "review_timing": "Review written"})
    st.plotly_chart(style(fig), width="stretch")
    st.dataframe(d, hide_index=True, column_config={"delivery": "Delivery", "review_timing": "Review written", "orders": "Orders",
                 "pct_of_group": st.column_config.NumberColumn("% of group", format="%.1f"),
                 "avg_score": st.column_config.NumberColumn("Avg stars", format="%.2f"),
                 "pct_1_2_star": st.column_config.NumberColumn("1-2 star %", format="%.1f")})
    lo, hi = H["gap_after_boot_ci"]
    st.markdown(f"**What this means:** {H['pct_late_reviews_before_delivery']:.0f}% of late orders were reviewed before arrival, "
                f"averaging {H['late_before_delivery_score']:.2f}★. Among reviews written after delivery the late-vs-on-time gap is "
                f"{H['gap_after_delivery']:+.2f}★ (95% range {lo:+.2f} to {hi:+.2f}): real, but far smaller. "
                "Sending the review request after delivery is a cheap fix to test.")
    st.caption(FOOTER)


def sellers(t):
    H = t["H"]
    st.header("Is it a few bad sellers, or the whole network?")
    d = t["seller_tiers"].copy()
    d["tier"] = d.late_quartile.map({1: "Most reliable in 2017", 2: "2nd", 3: "3rd", 4: "Least reliable in 2017"})
    fig = px.bar(d, x="tier", y="late_rate_pct", text="late_rate_pct", hover_data=["sellers", "orders_2018", "pct_sp_sellers"],
                 color_discrete_sequence=[BLUE], labels={"tier": "Seller group (ranked on 2017)", "late_rate_pct": "Late in 2018 (%)"})
    st.plotly_chart(style(fig), width="stretch")
    st.markdown(f"**What this means:** sellers were ranked on 2017 lateness, then checked on 2018. The least reliable group was late "
                f"{H['seller_q4_late_pct']}% vs {H['seller_q1_late_pct']}% for the most reliable, about {H['seller_q4_late_pct'] / H['seller_q1_late_pct']:.1f}x: a real but modest gap. "
                f"{H['seller_q4_pct_sp']}% of the least reliable group ship from São Paulo, so location is mixed in. "
                f"Each group has {H['seller_tier_sellers_each']} sellers with enough orders in both years.")
    st.caption(FOOTER)


def routes(t):
    st.header("Which routes are late most often?")
    view = st.radio("View", ["Seller → customer routes", "Customer states"], horizontal=True)
    if view.startswith("Seller"):
        d = t["lanes"].copy()
        mn = st.slider("Only routes with at least this many orders", int(d.orders.min()), 2000, 200, step=50)
        d = d[d.orders >= mn].copy(); d["route"] = d.seller_state + " → " + d.customer_state
        d = d.sort_values("late_rate_pct").tail(15)
        y = "route"
    else:
        d = t["customer_states"].sort_values("late_rate_pct"); y = "customer_state"
    if d.empty:
        st.info("No routes have that many orders."); return
    fig = px.bar(d, x="late_rate_pct", y=y, orientation="h", text="late_rate_pct",
                 hover_data=["orders", "median_delivery_days", "avg_score"], color_discrete_sequence=[BLUE],
                 labels={"late_rate_pct": "Late (%)", "route": "", "customer_state": ""})
    st.plotly_chart(style(fig, 560), width="stretch")
    H = t["H"]; lo, hi = H["worst_lane_wilson_ci_pct"]
    st.markdown(f"**What this means:** long routes out of São Paulo to the north-east are late far more often. "
                f"{H['worst_lane'].replace('->', ' → ')} is late {H['worst_lane_late_pct']}% of the time across {H['worst_lane_orders']} orders (95% range {lo}-{hi}%).")
    st.caption(FOOTER)


def growth(t):
    H = t["H"]
    st.header("Growth and repeat customers")
    m = t["monthly"].copy(); m["purchase_month"] = pd.to_datetime(m.purchase_month)
    y = st.radio("Show", ["Orders", "Sales (R$)"], horizontal=True)
    fig = px.line(m, x="purchase_month", y="orders" if y == "Orders" else "gmv", markers=True, color_discrete_sequence=[BLUE],
                  labels={"purchase_month": "Month", "orders": "Orders", "gmv": "Sales (R$)"})
    st.plotly_chart(style(fig, 360), width="stretch")
    c = t["cohorts"]
    size = c[c.month_offset == 0].set_index("cohort").customers
    big = size[size >= 100].index
    piv = c[c.cohort.isin(big) & (c.month_offset.between(1, 12))].pivot(index="cohort", columns="month_offset", values="retention_pct")
    fig2 = px.imshow(piv, color_continuous_scale="Blues", aspect="auto", text_auto=".1f",
                     labels={"x": "Months after first order", "y": "First-order month", "color": "% ordering again"})
    st.plotly_chart(style(fig2, 520), width="stretch")
    st.markdown(f"**What this means:** sales grew {H['gmv_yoy_jan_aug_2018_pct']}% year over year (Jan-Aug 2018 vs 2017), but only "
                f"{H['repeat_rate_pct']}% of customers ever ordered twice. Growth came from new buyers, not repeat ones. "
                "(Cohorts under 100 customers are hidden.)")
    st.caption(FOOTER)


PAGES = {"Overview": overview, "Late deliveries vs stars": lateness, "Review timing": timing,
         "Seller reliability": sellers, "Routes and states": routes, "Growth and retention": growth}


def main():
    st.set_page_config(page_title="Olist: what drives bad reviews?", page_icon="📦", layout="wide")
    page = st.sidebar.radio("Page", list(PAGES))
    PAGES[page](load())


main()
