"""Markets vs polls dashboard. Run from code/: streamlit run app/streamlit_app.py"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

D = Path(__file__).resolve().parent / "data"
NAMES = {"polymarket": "Polymarket", "kalshi": "Kalshi", "polls": "Poll average"}
COLORS = {"Polymarket": "#0072B2", "Kalshi": "#009E73", "Poll average": "#D55E00"}
FOOTER = ("Sources: Polymarket and Kalshi public price data, 538 archived state polls, MIT Election Lab certified results. "
          "2024 US presidential race, states with both markets and polls on the same date.")


@st.cache_data(show_spinner=False)
def load():
    s = pd.read_csv(D / "scores.csv"); s["name"] = s.source.map(NAMES)
    p = pd.read_csv(D / "matched_panel.csv")
    p["poll_miss"] = p.actual_margin_2p - p.poll_margin_2p  # positive = result more Republican than polls
    return s, p, json.loads((D / "findings.json").read_text())


def style(fig, h=420):
    fig.update_layout(template="simple_white", height=h, margin=dict(l=10, r=10, t=60, b=10), legend_title_text="")
    return fig


def overview(s, p, F):
    d1 = s[s.days_before == 1].set_index("source")
    st.title("Markets vs polls: who called 2024 better?")
    st.markdown("Betting markets (Polymarket, Kalshi) and polls both tried to predict who would win each state in the 2024 "
                "presidential election. This dashboard scores them on the **same states on the same dates**.")
    st.markdown("We use the **Brier score**: the average squared gap between the forecast chance and what happened. "
                "**Lower is better**; 0 is perfect, and always saying 50/50 scores 0.25.")
    k = st.columns(4)
    for i, src in enumerate(["polymarket", "kalshi", "polls"]):
        k[i].metric(f"{NAMES[src]} (1 day out)", f"{d1.loc[src, 'brier']:.3f}", f"{int(d1.loc[src, 'correct'])}/{int(d1.loc[src, 'states'])} states right", delta_color="off")
    k[3].metric("Average poll miss", f"{F['coverage']['mean_poll_error_T1']:.1f} pts", "toward Republicans", delta_color="off")
    d = p[p.days_before == 1]
    st.markdown(f"""
**Main findings**
- The markets scored better than the poll average at every matched date, from 4 weeks to 1 day out.
- The polls missed in one direction: results were more Republican than the polls in **{(d.poll_miss > 0).sum()} of {len(d)}** states.
- The two markets were close to each other.

**Caveat:** this is one election. A shared poll miss in one year doesn't prove markets always win.""")
    st.caption(FOOTER)


def horizon(s, p, F):
    st.header("How accurate was each forecast as election day got closer?")
    metric = st.radio("Score", ["Brier score", "States called right"], horizontal=True)
    y = "brier" if metric == "Brier score" else "pct"
    s = s.assign(pct=s.correct / s.states * 100)
    fig = px.line(s, x="days_before", y=y, color="name", markers=True, color_discrete_map=COLORS, hover_data=["states"],
                  labels={"days_before": "Days before the election", "brier": "Brier score (lower is better)",
                          "pct": "States with the right winner (%)", "name": ""})
    fig.update_xaxes(autorange="reversed", tickvals=[28, 21, 14, 7, 1])
    st.plotly_chart(style(fig), width="stretch")
    st.markdown("**What this means:** markets had the lower (better) score at each date. Fewer states had both a market and polls "
                f"far out (only {int(s.loc[s.days_before == s.days_before.max(), 'states'].iloc[0])} at {s.days_before.max()} days), so the early points are less certain.")
    st.dataframe(s.pivot(index="days_before", columns="name", values="brier").sort_index(ascending=False).round(3),
                 column_config={"days_before": "Days before"})
    st.caption(FOOTER)


def explorer(s, p, F):
    st.header("State explorer")
    states = sorted(p.state_po.unique())
    st_ = st.selectbox("State", states, index=states.index("PA") if "PA" in states else 0)
    v = p[p.state_po == st_].sort_values("days_before", ascending=False)
    won = "Trump (R)" if v.rep_won.iloc[0] == 1 else "Harris (D)"
    st.markdown(f"**Winner:** {won}, by {abs(v.actual_margin_2p.iloc[0]):.1f} points (two-party margin).")
    m = v.melt(id_vars="days_before", value_vars=["polymarket", "kalshi", "polls"], var_name="src", value_name="prob")
    m["name"] = m.src.map(NAMES)
    fig = px.line(m, x="days_before", y=m.prob * 100, color="name", markers=True, color_discrete_map=COLORS,
                  labels={"days_before": "Days before the election", "y": "Chance Trump wins the state (%)", "name": ""})
    fig.add_hline(y=50, line_dash="dash", line_color="#888")
    fig.update_xaxes(autorange="reversed", tickvals=[28, 21, 14, 7, 1])
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(style(fig), width="stretch")
    st.dataframe(v[["days_before", "polymarket", "kalshi", "polls", "poll_margin_2p", "n_pollsters"]], hide_index=True,
                 column_config={"days_before": "Days before", "polymarket": st.column_config.NumberColumn("Polymarket", format="percent"),
                                "kalshi": st.column_config.NumberColumn("Kalshi", format="percent"),
                                "polls": st.column_config.NumberColumn("Polls", format="percent"),
                                "poll_margin_2p": st.column_config.NumberColumn("Poll margin (+ = R)", format="%.1f"),
                                "n_pollsters": "Pollsters"})
    st.caption("Not every state has every date: a state appears only when both markets and polls existed that day. " + FOOTER)


def miss(s, p, F):
    st.header("Which way did the polls miss?")
    d = p[p.days_before == 1].sort_values("poll_miss")
    fig = px.bar(d, x="poll_miss", y="state_po", orientation="h", color=d.poll_miss > 0,
                 color_discrete_map={True: "#D55E00", False: "#0072B2"}, hover_data=["poll_margin_2p", "actual_margin_2p"],
                 labels={"poll_miss": "Result minus poll margin (points, + = more Republican)", "state_po": ""})
    fig.update_layout(showlegend=False)
    st.plotly_chart(style(fig, 720), width="stretch")
    st.markdown(f"**What this means:** the result was more Republican than the final poll average in {(d.poll_miss > 0).sum()} of "
                f"{len(d)} states, by {d.poll_miss.mean():.1f} points on average. When every poll misses the same way, "
                "averaging more polls doesn't fix it.")
    st.caption(FOOTER)


def close(s, p, F):
    st.header("Where did forecasts pick the wrong winner?")
    day = st.select_slider("Days before the election", options=[28, 21, 14, 7, 1], value=1)
    d = p[p.days_before == day]
    rows = []
    for src in ["polymarket", "kalshi", "polls"]:
        wrong = d[(d[src] > 0.5) != (d.rep_won == 1)]
        rows.append({"Forecast": NAMES[src], "Wrong calls": len(wrong), "States": ", ".join(sorted(wrong.state_po)) or "none"})
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption(f"{len(d)} states matched at {day} day(s) out. A 'call' is whichever candidate had over 50%. " + FOOTER)


PAGES = {"Overview": overview, "Accuracy by date": horizon, "State explorer": explorer,
         "Poll miss": miss, "Wrong calls": close}


def main():
    st.set_page_config(page_title="Markets vs polls, 2024", page_icon="🗳️", layout="wide")
    page = st.sidebar.radio("Page", list(PAGES))
    PAGES[page](*load())


main()
