"""NFL closing-line dashboard. Run from code/: streamlit run app/streamlit_app.py"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

D = Path(__file__).resolve().parent / "data"
BREAKEVEN = 110 / 210  # win share needed at -110 odds
FOOTER = ("Source: nflverse games data (closing lines), 1999 to early 2026 seasons. "
          "Hit rates count decided games (pushes excluded); analysis by Evan Deaver.")


@st.cache_data(show_spinner=False)
def load():
    return {"tests": pd.read_csv(D / "strategy_tests.csv"), "season": pd.read_csv(D / "strategy_by_season.csv"),
            "buckets": pd.read_csv(D / "spread_buckets.csv"), "cal": pd.read_csv(D / "ml_calibration.csv"),
            "wf": pd.read_csv(D / "walk_forward.csv"), "F": json.loads((D / "findings.json").read_text())}


def style(fig, h=420):
    fig.update_layout(template="simple_white", height=h, margin=dict(l=10, r=10, t=60, b=10), legend_title_text="")
    return fig


def nice(s):
    return s.str.replace("^Bet ", "", regex=True)


def overview(x):
    F, t = x["F"], x["tests"]
    st.title("Is the market's closing price an accurate forecast?")
    st.markdown("Before every NFL game, the market publishes a forecast of the result (the closing *line*). A pattern has to be right "
                "**52.38%** of the time just to cover the market's built-in margin. This dashboard tests how accurate the closing "
                "line is and whether any popular pattern clears that bar.")
    k = st.columns(4)
    k[0].metric("Games", f"{F['games']:,}", f"{F['seasons'][0]}-{F['seasons'][1]}", delta_color="off")
    k[1].metric("Strategies tested", len(t))
    k[2].metric("Accuracy needed to cover the margin", f"{BREAKEVEN:.2%}")
    k[3].metric("Typical miss of the spread", f"{F['efficiency']['result']['mae']:.1f} pts")
    st.markdown(f"""
**Main findings**
- The closing spread is right **on average** (average miss {F['efficiency']['result']['mean_err']:+.2f} points), even though single games miss by about {F['efficiency']['result']['mae']:.0f} points.
- None of the {len(t)} popular patterns clears 52.38% in a statistically defensible way.
- Closing prices give honest win chances once the bookmaker's margin is removed.""")
    st.caption(FOOTER)


def strategies(x):
    st.header("Which patterns beat a coin flip?")
    t = x["tests"].assign(name=lambda d: nice(d.strategy)).sort_values("win_rate")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t.win_rate * 100, y=t.name, mode="markers", marker=dict(size=11, color="#0072B2"),
                             error_x=dict(type="data", symmetric=False, array=(t.ci_high - t.win_rate) * 100,
                                          arrayminus=(t.win_rate - t.ci_low) * 100), name="Hit rate (95% range)"))
    fig.add_vline(x=BREAKEVEN * 100, line_dash="dash", line_color="#D55E00", annotation_text="52.38% needed to cover the margin")
    fig.update_xaxes(title="Forecast hit rate (%)")
    st.plotly_chart(style(fig, 460), width="stretch")
    show = t[["name", "bets", "win_rate", "ci_low", "ci_high", "p_beats_vig_holm"]].sort_values("win_rate", ascending=False)
    st.dataframe(show, hide_index=True, column_config={
        "name": "Pattern", "bets": "Decided games", "win_rate": st.column_config.NumberColumn("Hit rate", format="percent"),
        "ci_low": st.column_config.NumberColumn("Low end (95%)", format="percent"),
        "ci_high": st.column_config.NumberColumn("High end (95%)", format="percent"),
        "p_beats_vig_holm": st.column_config.NumberColumn("Chance it's luck (corrected p)", format="%.2f")})
    w = x["tests"].set_index("strategy").loc["Bet unders, wind 15+ mph"]
    st.markdown("**What this means:** the lines show how uncertain each win rate is. Only windy-game unders sit fully right of the "
                f"dashed line ({w.win_rate:.1%} over {w.bets:,} decided games), but after correcting for testing {len(x['tests'])} ideas at once the chance it's "
                f"luck is {w.p_beats_vig_holm:.2f}, above the usual 0.05 bar. So no pattern is proven to beat the market.")
    st.subheader("Does the pattern hold in later seasons?")
    wf = x["wf"].assign(name=lambda d: nice(d.strategy))
    st.dataframe(wf[["name", "in_sample_rate", "oos_rate", "oos_bets", "picked"]], hide_index=True, column_config={
        "name": "Pattern", "in_sample_rate": st.column_config.NumberColumn("Hit rate, 1999-2014", format="percent"),
        "oos_rate": st.column_config.NumberColumn("Hit rate, 2015 on", format="percent"),
        "oos_bets": "Decided games, 2015 on", "picked": "Looked good early?"})
    st.markdown("Each strategy is judged on 1999-2014, then checked on 2015 onward, seasons it never saw.")
    st.caption(FOOTER)


def bankroll(x):
    st.header("What if you had followed a strategy?")
    s, t = x["season"], x["tests"]
    names = sorted(s.strategy.unique())
    pick = st.multiselect("Strategies", names, default=["Bet favorites ATS", "Bet home underdogs ATS", "Bet unders, wind 15+ mph"])
    lo, hi = int(s.season.min()), int(s.season.max())
    yr = st.slider("Seasons", lo, hi, (lo, hi))
    v = s[s.strategy.isin(pick) & s.season.between(*yr)].sort_values("season").copy()
    if v.empty:
        st.info("Pick at least one strategy."); return
    v["profit"] = v.groupby("strategy").units.cumsum()
    v["name"] = nice(v.strategy)
    fig = px.line(v, x="season", y="profit", color="name", markers=True,
                  labels={"season": "Season", "profit": "Running profit (units, 1 unit per bet)", "name": ""})
    fig.add_hline(y=0, line_color="#888")
    st.plotly_chart(style(fig, 460), width="stretch")
    tot = v.groupby("name").agg(bets=("bets", "sum"), wins=("wins", "sum"), units=("units", "sum")).reset_index()
    tot["win_rate"] = tot.wins / tot.bets
    st.dataframe(tot, hide_index=True, column_config={"name": "Strategy", "bets": "Bets", "wins": "Wins",
                 "units": st.column_config.NumberColumn("Profit (units)", format="%.1f"),
                 "win_rate": st.column_config.NumberColumn("Win rate", format="percent")})
    st.markdown("**What this means:** most simple rules drift below zero over time, because the -110 fee eats any small edge. "
                "A good-looking stretch of seasons can happen by luck.")
    st.caption(FOOTER)


def spreads(x):
    st.header("Are home underdogs underrated?")
    b = x["buckets"].copy()
    b["group"] = b.bucket.str.replace(r"^[a-z]\) ", "", regex=True)
    fig = px.bar(b, x="group", y=b.home_cover_rate * 100, text=b.home_cover_rate.map("{:.1%}".format), hover_data=["games"],
                 color_discrete_sequence=["#0072B2"], labels={"group": "Home team's spread", "y": "Home team cover rate (%)"})
    fig.add_hline(y=BREAKEVEN * 100, line_dash="dash", line_color="#D55E00", annotation_text="52.38% needed to cover the margin")
    fig.update_yaxes(range=[40, 62])
    st.plotly_chart(style(fig), width="stretch")
    st.markdown("**What this means:** most groups sit below 52.38%. The 7+ point home underdogs look good, but that's one slice "
                "out of many, not a tested strategy.")
    st.caption(FOOTER)


def calibration(x):
    F, c = x["F"], x["cal"]
    st.header("Do closing prices give honest win chances?")
    st.markdown(f"After removing the bookmaker's margin (about {F['mean_overround']:.1%}), each game's odds give a win chance. "
                "If the odds are honest, the dots sit on the diagonal line.")
    fig = px.scatter(c, x=c.pred * 100, y=c.actual * 100, size="n", hover_data=["bin", "n"],
                     labels={"x": "Win chance from the odds (%)", "y": "How often the home team actually won (%)"})
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(dash="dash", color="#888"), name="Perfect"))
    st.plotly_chart(style(fig, 460), width="stretch")
    k = st.columns(3)
    k[0].metric("Accuracy score (Brier, lower is better)", f"{F['brier']:.3f}")
    k[1].metric("Coin flip would score", f"{F['brier_coinflip']:.3f}")
    k[2].metric("Games with moneylines", f"{F['ml_games']:,}")
    st.markdown("**What this means:** the odds' win chances closely match how often teams actually won, in every probability band we checked.")
    st.caption(FOOTER)


PAGES = {"Overview": overview, "Which patterns beat a coin flip?": strategies,
         "Home underdogs": spreads, "Are closing prices honest?": calibration}


def main():
    st.set_page_config(page_title="Is the market's closing price an accurate forecast?", page_icon="🏈", layout="wide")
    page = st.sidebar.radio("Page", list(PAGES))
    PAGES[page](load())


main()
