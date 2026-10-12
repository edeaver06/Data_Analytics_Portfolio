"""Steam Pulse interactive dashboard. Run: streamlit run app/streamlit_app.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd, plotly.express as px, streamlit as st
import marts

BLUE, ORANGE, GREEN, GREY, VERM, SKY = "#0072B2", "#E69F00", "#009E73", "#8C8C8C", "#D55E00", "#56B4E9"
PRICE_COLORS = {"Free-to-play": ORANGE, "Paid": BLUE, "Unknown": GREY}
STORE = "https://store.steampowered.com/app/{}"

@st.cache_data(show_spinner=False)
def data():
    dim, fct, snaps, src = marts.load()
    return marts.add_score(marts.enrich(dim, fct)), fct, snaps, src

@st.cache_data(show_spinner=False)
def bridge():
    return marts.load_bridge()

def source_note(extra=""):
    _, _, snaps, src = data()
    ts = pd.to_datetime(snaps.snapshot_ts).max().strftime("%Y-%m-%d %H:%M UTC")
    st.caption(f"{extra} Source: Steam Web API concurrent players ({len(snaps)} snapshot(s), latest {ts}); "
               f"SteamSpy owner estimates and prices (estimates, bucketed); Steam store details. Loaded from {src}.")

def style(fig, h=420):
    fig.update_layout(template="simple_white", height=h, margin=dict(l=10, r=10, t=60, b=10),
                      legend_title_text="", font=dict(size=13))
    return fig

def fmt(n):
    return "n/a" if pd.isna(n) else f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.0f}K" if n >= 1e3 else f"{n:,.0f}"

# ------------------------------------------------------------------ pages
def overview():
    g, fct, snaps, _ = data()
    total = g.last_players.sum(); top3 = g.nlargest(3, "last_players")
    st.title("Steam Pulse")
    st.markdown("Daily concurrent-player tracking for Steam's top 1,000 games.")
    c = st.columns(4)
    c[0].metric("Games tracked", f"{g.last_players.notna().sum():,}")
    c[1].metric("Concurrent players", fmt(total))
    c[2].metric("Top-3 share", f"{top3.last_players.sum()/total:.0%}")
    c[3].metric("Free-to-play share of players", f"{g.loc[g.pricing=='Free-to-play','last_players'].sum()/total:.0%}")
    top = g.nlargest(15, "last_players").sort_values("last_players")
    fig = px.bar(top, x="last_players", y="game_name", color="pricing", orientation="h", color_discrete_map=PRICE_COLORS,
                 title=f"3 free-to-play games hold {top3.last_players.sum()/total:.0%} of all players in the top 1,000",
                 labels={"last_players": "Concurrent players", "game_name": ""}, hover_data=["appid"])
    st.plotly_chart(style(fig, 520), width="stretch")
    if len(snaps) < 2:
        st.info("Only one snapshot has been collected so far. Time-series views fill in as the daily cron runs.")
    source_note()

def decay():
    g, fct, snaps, _ = data()
    st.header("Launch decay")
    days = fct.snapshot_date_utc.nunique()
    if days >= 7:
        st.subheader("Per-game decay curves")
        pick = st.multiselect("Games", g.game_name.dropna().sort_values(), default=list(g.nlargest(5, "last_players").game_name))
        ts = fct.merge(g[["appid", "game_name"]], on="appid"); ts = ts[ts.game_name.isin(pick)]
        st.plotly_chart(style(px.line(ts, x="snapshot_date_utc", y="peak_players_sampled", color="game_name")), width="stretch")
    else:
        st.warning(f"True decay curves need daily history; the mart has {days} day(s). Showing a cross-sectional proxy instead.")
    d = g.dropna(subset=["years_since_release", "players_per_1k_owners"]); d = d[d.players_per_1k_owners > 0]
    fig = px.scatter(d, x="years_since_release", y="players_per_1k_owners", color="pricing", log_y=True,
                     color_discrete_map=PRICE_COLORS, hover_name="game_name",
                     title="Older games keep a smaller share of their owners playing",
                     labels={"years_since_release": "Years since release", "players_per_1k_owners": "Players per 1,000 owners (log)"})
    d = d.assign(bucket=pd.cut(d.years_since_release, [0, 1, 2, 5, 10, 30], labels=["<1", "1-2", "2-5", "5-10", "10+"]))
    st.plotly_chart(style(fig, 480), width="stretch")
    st.dataframe(d.groupby("bucket", observed=False).agg(games=("appid", "size"), median_players_per_1k=("players_per_1k_owners", "median")).round(3))
    source_note(f"{len(d)} games with store release dates (skewed to popular titles).")

def f2p():
    g, *_ = data()
    st.header("Free-to-play vs paid")
    k = g[g.pricing != "Unknown"]
    s = k.groupby("pricing").agg(games=("appid", "size"), players=("last_players", "sum"), median_players=("last_players", "median"),
                                 median_positive_reviews=("positive_review_share", "median"))
    s["share_of_games"] = s.games / s.games.sum(); s["share_of_players"] = s.players / s.players.sum()
    st.subheader(f"Free-to-play is {s.loc['Free-to-play','share_of_games']:.0%} of games but {s.loc['Free-to-play','share_of_players']:.0%} of players")
    c = st.columns(2)
    long = s[["share_of_games", "share_of_players"]].reset_index().melt("pricing")
    c[0].plotly_chart(style(px.bar(long, x="variable", y="value", color="pricing", barmode="group", color_discrete_map=PRICE_COLORS,
                                   text_auto=".0%", title="Share of games vs share of players", labels={"variable": "", "value": ""})), width="stretch")
    c[1].plotly_chart(style(px.box(k, x="pricing", y="last_players", color="pricing", log_y=True, color_discrete_map=PRICE_COLORS, points=False,
                                   title="The typical paid game has more players", labels={"last_players": "Concurrent players (log)", "pricing": ""})), width="stretch")
    st.dataframe(s.style.format({"players": "{:,.0f}", "median_players": "{:,.0f}", "median_positive_reviews": "{:.1%}",
                                 "share_of_games": "{:.1%}", "share_of_players": "{:.1%}"}))
    source_note("Free-to-play = SteamSpy current price $0.")

def sales():
    g, *_ = data()
    st.header("Sales impact")
    paid = g[(g.pricing == "Paid") & g.players_per_1k_owners.notna()].copy()
    paid["band"] = pd.cut(paid.discount_pct.fillna(0), [-1, 0, 25, 50, 75, 100], labels=["Full price", "1-25%", "26-50%", "51-75%", "76-100%"])
    si = paid.groupby("band", observed=False).agg(games=("appid", "size"), median_players_per_1k=("players_per_1k_owners", "median")).reset_index()
    fig = px.bar(si, x="band", y="median_players_per_1k", text="games", color_discrete_sequence=[GREEN],
                 title="Deeper discounts sit on less-played games",
                 labels={"band": "Current discount", "median_players_per_1k": "Median players per 1,000 owners"})
    fig.update_traces(texttemplate="n=%{text}")
    st.plotly_chart(style(fig), width="stretch")
    st.warning("This is a cross-sectional association from the current snapshot, not a before/after sale effect. "
               "A causal view needs daily snapshots spanning each sale's start and end.")
    st.dataframe(paid[paid.on_sale].sort_values("discount_pct", ascending=False)[["game_name", "discount_pct", "price_usd", "initial_price_usd", "last_players"]], hide_index=True)
    source_note()

def lookup():
    g, fct, *_ = data()
    st.header("Game lookup")
    name = st.selectbox("Search a game", g.game_name.dropna().sort_values().unique(), index=None, placeholder="Type a name…")
    if name is None:
        name = g.nlargest(1, "last_players").game_name.iloc[0]
    r = g[g.game_name == name].iloc[0]
    st.subheader(f"[{name}]({STORE.format(int(r.appid))})")
    c = st.columns(4)
    c[0].metric("Concurrent players", fmt(r.last_players)); c[1].metric("Owners (est.)", r.owners_estimate_range or "n/a")
    c[2].metric("Positive reviews", "n/a" if pd.isna(r.positive_review_share) else f"{r.positive_review_share:.0%}")
    c[3].metric("Price", "Free" if r.pricing == "Free-to-play" else ("n/a" if pd.isna(r.price_usd) else f"${r.price_usd:.2f}"))
    st.write({k: (None if pd.isna(v) else v) for k, v in r[["developer", "publisher", "primary_genre", "release_date", "discount_pct", "metacritic_score", "players_per_1k_owners"]].items()})
    ts = fct[fct.appid == r.appid]
    st.plotly_chart(style(px.line(ts, x="snapshot_date_utc", y=["peak_players_sampled", "avg_players_sampled"], markers=True,
                                  title="Daily players", labels={"value": "Players", "snapshot_date_utc": "Date (UTC)"})), width="stretch")
    source_note()

# --------------------------------------------------------------# Ranking options: Data Analyst's composite score (default) or one single metric.
RANKS = {"score": "Composite score", "positive_review_share": "Positive reviews", "last_players": "Concurrent players"}
PARTS = {"review_bayes_part": "Reviews (Bayes-adjusted) x0.45", "player_strength_part": "Players (log CCU) x0.35",
         "value_per_dollar_part": "Value per dollar x0.20"}
SOFTWARE_NOTE = ("Note: software such as Wallpaper Engine and Blender is still ranked, because it can't be excluded "
                 "until Code Builder adds `app_type` for every game. The filter turns on automatically when it does.")

def app_type_ready(df):
    """True once dim_game carries app_type for (nearly) every scored game."""
    return "app_type" in df and df.loc[df.score.notna(), "app_type"].notna().mean() >= 0.95

def finder_frame():
    g, *_ = data(); b = bridge()
    det = g[g.score.notna()].copy()  # all scored games (999); store-detail filters narrow to the 150 with details
    for kind, col in [("genre", "genres"), ("category", "categories")]:
        det[col] = det.appid.map(b[b.kind == kind].groupby("appid").label.apply(list)).apply(lambda v: v if isinstance(v, list) else [])
    return det, b

def apply_app_type(det, key):
    if app_type_ready(det):
        types = sorted(det.app_type.dropna().unique())
        keep = st.sidebar.multiselect("App type", types, default=[t for t in types if t == "game"] or types, key=key)
        return det[det.app_type.isin(keep)]
    st.info(SOFTWARE_NOTE)
    return det

def fmt_rank(m, v):
    if pd.isna(v): return "n/a"
    return f"{v:.3f}" if m == "score" else f"{v:.0%}" if m == "positive_review_share" else fmt(v)

def finder():
    st.header("Game Finder")
    st.caption("Ranked by Data Analyst's validated composite score (analysis/src/best_score.py): percentile ranks of "
               "Bayesian review share (0.45), log concurrent players (0.35) and value per dollar (0.20). Retention and momentum are weighted 0 "
               "until there is daily history.")
    det, b = finder_frame()
    with st.sidebar:
        st.subheader("Finder filters")
        genres = st.multiselect("Genres (match any)", sorted(b[b.kind == "genre"].label.unique()))
        cats = st.multiselect("Store categories (match all)", sorted(b[b.kind == "category"].label.unique()))
        coop = st.checkbox("Local co-op (Shared/Split Screen Co-op)")
        split = st.checkbox("Split-screen (any Shared/Split Screen)")
        ctrl = st.multiselect("Controller support", ["Full controller support", "Partial Controller Support"])
        st.multiselect("Tags", [], disabled=True, help="stg_steamspy_tags exists in dbt but raw.steamspy_tags is not in the DB yet.")
        st.checkbox("Steam Deck verified", disabled=True, help="No Steam Deck compatibility data in the marts.")
        price = det.steamspy_price_usd.fillna(0)
        pr = st.slider("Price (USD)", 0.0, float(price.max()), (0.0, float(price.max())))
        yrs = pd.to_datetime(det.release_date).dt.year.dropna()
        yr = st.slider("Release year (games without a date are kept unless narrowed)", int(yrs.min()), int(yrs.max()), (int(yrs.min()), int(yrs.max())))
        rank_by = st.selectbox("Rank by", list(RANKS), format_func=RANKS.get, index=0)
    f = apply_app_type(det, "finder_app_type")
    if genres: f = f[f.genres.apply(lambda v: bool(set(v) & set(genres)))]
    req = set(cats) | ({"Shared/Split Screen Co-op"} if coop else set())
    if req: f = f[f.categories.apply(lambda v: req <= set(v))]
    if split: f = f[f.categories.apply(lambda v: any(x.startswith("Shared/Split Screen") for x in v))]
    if ctrl: f = f[f.categories.apply(lambda v: bool(set(v) & set(ctrl)))]
    f = f[f.steamspy_price_usd.fillna(0).between(*pr)]
    y = pd.to_datetime(f.release_date).dt.year
    narrowed = (yr[0], yr[1]) != (int(yrs.min()), int(yrs.max()))
    f = f[y.between(*yr) | (y.isna() & (not narrowed))]
    f = f.dropna(subset=[rank_by]).sort_values(rank_by, ascending=False)
    st.write(f"**{len(f)}** of {len(det)} scored games match.")
    if f.empty:
        st.info("No games match. Loosen the filters."); return
    top = f.iloc[0]
    with st.container(border=True):
        st.markdown(f"### ⭐ [{top.game_name}]({STORE.format(int(top.appid))})")
        st.write(", ".join(top.genres) if top.genres else "")
        c = st.columns(4)
        c[0].metric("Composite score", f"{top.score:.3f}", f"#{int(top.score_rank)} of {int(det.score.notna().sum())}", delta_color="off")
        for col, (k, lab) in zip(c[1:], PARTS.items()):
            col.metric(lab, f"{top[k]:.3f}")
        if rank_by != "score":
            st.caption(f"Ranked by {RANKS[rank_by]}: {fmt_rank(rank_by, top[rank_by])}")
    tbl = f.assign(rank=range(1, len(f) + 1), store=f.appid.map(lambda a: STORE.format(int(a))))
    show = ["rank", "game_name", "store", "score", *PARTS, "positive_review_share", "last_players", "steamspy_price_usd"]
    st.dataframe(tbl[show], hide_index=True, column_config={
        "store": st.column_config.LinkColumn("Steam store", display_text="Open"),
        "score": st.column_config.NumberColumn("Score", format="%.3f"),
        "positive_review_share": st.column_config.NumberColumn("Positive reviews", format="percent"),
        "last_players": st.column_config.NumberColumn("Concurrent players", format="%d"),
        "steamspy_price_usd": st.column_config.NumberColumn("Price", format="$%.2f"),
        **{k: st.column_config.ProgressColumn(v, min_value=0, max_value=0.45, format="%.3f") for k, v in PARTS.items()}})
    comp = st.multiselect("Compare games side by side", list(f.game_name), default=list(f.game_name[:min(3, len(f))]), max_selections=5)
    if comp:
        cmp = f[f.game_name.isin(comp)].set_index("game_name")
        st.dataframe(cmp[["score", *PARTS, "review_bayes", "positive_review_share", "last_players", "steamspy_price_usd", "owners_estimate_range", "primary_genre", "release_date"]].T.astype(str))
        long = cmp[list(PARTS)].rename(columns=PARTS).reset_index().melt("game_name")
        st.plotly_chart(style(px.bar(long, x="game_name", y="value", color="variable", color_discrete_sequence=[BLUE, ORANGE, GREEN],
                                     title="Score breakdown: the three weighted parts add up to the composite score",
                                     labels={"game_name": "", "value": "Contribution to score", "variable": ""})), width="stretch")
    source_note("Composite score from analysis/src/best_score.py (999 games with players and reviews); values match analysis/best_score_results.json.")

def leaderboards():
    st.header("Category leaderboards")
    det, b = finder_frame()
    det = apply_app_type(det, "lb_app_type")
    kind = st.radio("Group by", ["genre", "category"], horizontal=True)
    n = st.slider("Top N per group", 3, 10, 5)
    lab = b[b.kind == kind].merge(det[["appid", "game_name", "score", *PARTS, "last_players"]], on="appid")
    counts = lab.groupby("label").appid.nunique(); keep = counts[counts >= 5].sort_values(ascending=False).index
    lb = (lab[lab.label.isin(keep)].sort_values("score", ascending=False).groupby("label").head(n)
          .assign(store=lambda d: d.appid.map(lambda a: STORE.format(int(a)))))
    for label in keep:
        with st.expander(f"{label} ({counts[label]} games)"):
            st.dataframe(lb[lb.label == label][["game_name", "score", *PARTS, "store"]], hide_index=True,
                         column_config={"store": st.column_config.LinkColumn("Steam store", display_text="Open"),
                                        **{k: st.column_config.NumberColumn(v, format="%.3f") for k, v in PARTS.items()}})
    st.subheader("Category gaps: low supply, high score or demand")
    agg = lab[lab.label.isin(keep)].groupby("label").agg(games=("appid", "nunique"), median_score=("score", "median"),
                                                          median_players=("last_players", "median"))
    pct = agg.rank(pct=True); pct["games"] = 1 - pct["games"]  # high = scarce
    pct = pct.rename(columns={"games": "scarcity (fewer games)"}).sort_values("scarcity (fewer games)", ascending=False)
    fig = px.imshow(pct, color_continuous_scale="cividis", aspect="auto", text_auto=".0%",
                    title=f"{kind.title()} x metric percentile (bright in every column = scarce but strong)")
    st.plotly_chart(style(fig, 40 + 26 * len(pct)), width="stretch")
    st.dataframe(agg.sort_values("games"))
    source_note(f"{kind.title()}s with at least 5 games among the 150 with store details. Score = Data Analyst composite.")


PAGES = {"Overview": overview, "Launch decay curves": decay, "Free-to-play vs paid": f2p, "Sales impact": sales,
         "Game lookup": lookup, "Game Finder": finder, "Category leaderboards": leaderboards}

def main():
    st.set_page_config(page_title="Steam Pulse", page_icon="🎮", layout="wide")
    page = st.sidebar.radio("Page", list(PAGES))
    PAGES[page]()

if __name__ == "__main__" or st.runtime.exists():
    main()
