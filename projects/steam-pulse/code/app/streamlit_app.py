"""Steam Pulse interactive dashboard. Run: streamlit run app/streamlit_app.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd, plotly.express as px, streamlit as st
import marts

BLUE, ORANGE, GREEN, GREY, VERM, SKY = "#0072B2", "#E69F00", "#009E73", "#8C8C8C", "#D55E00", "#56B4E9"
PRICE_COLORS = {"Free-to-play": ORANGE, "Paid": BLUE, "Unknown": GREY}
STORE = "https://store.steampowered.com/app/{}"

@st.cache_data(show_spinner=False, ttl=3600)
def data():
    dim, fct, snaps, src = marts.load()
    return marts.add_score(marts.enrich(dim, fct)), fct, snaps, src

@st.cache_data(show_spinner=False, ttl=3600)
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

def short(n):
    """Compact count for narrow metric tiles: 100M, 1.5M, 20K."""
    for div, suf in ((1e6, "M"), (1e3, "K")):
        if n >= div: return f"{n/div:.1f}".rstrip("0").rstrip(".") + suf
    return f"{n:,.0f}"

# ------------------------------------------------------------------ pages
def overview():
    g, fct, snaps, _ = data()
    total = g.last_players.sum(); top3 = g.nlargest(3, "last_players")
    st.title("Steam Pulse")
    n_live = int(g.last_players.notna().sum())
    st.markdown(f"Concurrent-player tracking for {n_live:,} popular Steam games "
                f"({len(g):,} in the catalogue; {len(g) - n_live} had no player count in the latest snapshot).")
    c = st.columns(4)
    c[0].metric("Games tracked", f"{g.last_players.notna().sum():,}")
    c[1].metric("Concurrent players", fmt(total))
    c[2].metric("Top-3 share", f"{top3.last_players.sum()/total:.0%}")
    c[3].metric("Free-to-play share of players", f"{g.loc[g.pricing=='Free-to-play','last_players'].sum()/total:.0%}")
    top = g.nlargest(15, "last_players").sort_values("last_players")
    fig = px.bar(top, x="last_players", y="game_name", color="pricing", orientation="h", color_discrete_map=PRICE_COLORS,
                 title=(("Three free-to-play games" if (top3.pricing == "Free-to-play").all() else "The top 3 games")
                        + f" hold {top3.last_players.sum()/total:.0%} of players across {g.last_players.notna().sum():,} tracked games"),
                 labels={"last_players": "Concurrent players", "game_name": ""}, hover_data=["appid"])
    st.plotly_chart(style(fig, 520), width="stretch")
    if len(snaps) < 2:
        st.info("Only one snapshot has been collected so far. This public app uses a fixed snapshot, so time-series views are limited.")
    source_note()

@st.cache_data(show_spinner=False, ttl=3600)
def history():
    return marts.load_history()

@st.cache_data(show_spinner=False, ttl=3600)
def results():
    return marts.load_results()

HIST_NOTE = "Source: Analysis history (analysis/history_results.json)."

def decay():
    st.header("Launch decay curves")
    H = history()
    if H is None:
        st.warning("analysis/history_results.json is missing, so launch curves can't be shown."); return
    ret = pd.concat([pd.DataFrame(H["retention"][k]).assign(segment=lab) for k, lab in
                     [("all", "All games"), ("free", "Free-to-play"), ("paid", "Paid")]])
    a = ret[ret.segment == "All games"].set_index("m")["median"]; a1, a6, a24 = a[1], a[6], a[24]
    fig = px.line(ret, x="m", y="median", color="segment", markers=True, hover_data=["count"],
                  color_discrete_map={"All games": GREY, "Free-to-play": ORANGE, "Paid": BLUE},
                  title=f"Games keep {a1:.0%} of launch-month players after one month, {a6:.0%} by month 6 and {a24:.0%} by month 24",
                  labels={"m": "Months since launch", "median": "Median share of launch-month peak", "segment": ""})
    fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
    st.plotly_chart(style(fig, 480), width="stretch")
    f = ret[ret.segment == "Free-to-play"].set_index("m")["median"]; pd_ = ret[ret.segment == "Paid"].set_index("m")["median"]
    c = st.columns(4)
    c[0].metric("Month 1", f"{a[1]:.3f}"); c[1].metric("Month 6", f"{a[6]:.3f}"); c[2].metric("Month 24", f"{a[24]:.3f}")
    c[3].metric("F2P vs paid at month 6", f"{f[6]:.2f} vs {pd_[6]:.2f}")
    st.caption(("Free-to-play holds better than paid. " if f[6] > pd_[6] else "Free-to-play does not hold better than paid. ") + f"{H['retention_n']} of today's tracked games with an observed launch "
               f"(SteamCharts monthly players), so survivors only. " + HIST_NOTE)
    g, fct, *_ = data()
    with st.expander("Today's cross-section (players per 1,000 owners by game age)"):
        d = g.dropna(subset=["years_since_release", "players_per_1k_owners"]); d = d[d.players_per_1k_owners > 0]
        st.plotly_chart(style(px.scatter(d, x="years_since_release", y="players_per_1k_owners", color="pricing", log_y=True,
                                         color_discrete_map=PRICE_COLORS, hover_name="game_name",
                                         labels={"years_since_release": "Years since release", "players_per_1k_owners": "Players per 1,000 owners (log)"})), width="stretch")
    source_note()

def f2p():
    st.header("Free-to-play vs paid")
    s, k = f2p_table()
    Rj = results()
    _f2p_header(s, Rj)
    _f2p_body(s, k)

@st.cache_data(show_spinner="Building the free-to-play vs paid table…", ttl=3600)
def f2p_table():
    """Games with a player count only, so counts match 'Games tracked' on the Overview."""
    g, *_ = data()
    k = g[(g.pricing != "Unknown") & g.last_players.notna()]
    s = k.groupby("pricing").agg(games=("appid", "size"), players=("last_players", "sum"), median_players=("last_players", "median"),
                                 median_positive_reviews=("positive_review_share", "median"))
    s["share_of_games"] = s.games / s.games.sum(); s["share_of_players"] = s.players / s.players.sum()
    return s, k[["pricing", "last_players"]]

def _f2p_header(s, Rj):
    if Rj is not None:
        fj = {r["segment"]: r for r in Rj["f2p"]}; pv = Rj["f2p_mwu_p"]
        if pv >= 0.05:
            st.subheader(f"No clear difference in typical players between free-to-play and paid "
                         f"(median {fj['free']['med_ccu']:,.0f} vs {fj['paid']['med_ccu']:,.0f}, p = {pv:.2f})")
        else:
            hi = "free-to-play" if fj["free"]["med_ccu"] > fj["paid"]["med_ccu"] else "paid"
            st.subheader(f"The typical {hi} game has more players (median {fj['free']['med_ccu']:,.0f} free vs {fj['paid']['med_ccu']:,.0f} paid, p = {pv:.1e})")
        st.caption("Median and Mann-Whitney p from the analysis layer's analysis/results.json.")
    else:
        st.subheader(f"Free-to-play is {s.loc['Free-to-play','share_of_games']:.0%} of games and {s.loc['Free-to-play','share_of_players']:.0%} of players")

def _f2p_body(s, k):
    c = st.columns(2)
    long = s[["share_of_games", "share_of_players"]].reset_index().melt("pricing")
    c[0].plotly_chart(style(px.bar(long, x="variable", y="value", color="pricing", barmode="group", color_discrete_map=PRICE_COLORS,
                                   text_auto=".0%", title="Share of games vs share of players", labels={"variable": "", "value": ""})), width="stretch")
    c[1].plotly_chart(style(px.box(k, x="pricing", y="last_players", color="pricing", log_y=True, color_discrete_map=PRICE_COLORS, points=False,
                                   title="Concurrent players per game", labels={"last_players": "Concurrent players (log)", "pricing": ""})), width="stretch")
    st.dataframe(s.style.format({"players": "{:,.0f}", "median_players": "{:,.0f}", "median_positive_reviews": "{:.1%}",
                                 "share_of_games": "{:.1%}", "share_of_players": "{:.1%}"}))
    source_note(f"Free-to-play = Steam store is_free. {int(s.games.sum()):,} games with a player count in the latest snapshot.")

def sales():
    st.header("Sales impact")
    H = history()
    if H is None:
        st.warning("analysis/history_results.json is missing, so the discount event study can't be shown."); return
    D = H["discount_did"]
    dep = pd.DataFrame([{"depth": k, **v} for k, v in D["by_depth"].items()])
    st.subheader(f"The first week of a sale goes with +{D['did_pct']:.0f}% players, and deeper discounts with bigger lifts")
    c = st.columns(3)
    c[0].metric("First-week lift", f"+{D['did_pct']:.1f}%", f"95% CI {D['ci95_pct'][0]:.1f}-{D['ci95_pct'][1]:.1f}%", delta_color="off")
    c[1].metric("Sale starts", f"{D['n_events']:,}", f"{D['n_games']:,} games", delta_color="off")
    c[2].metric("Pre-trend (days -7 to -1)", f"{D['pretrend_days_-7_-1_pct']:+.1f}%")
    fig = px.bar(dep, x="depth", y="pct", text=dep.apply(lambda r: f"+{r.pct:.0f}% (n={r.n:,})", axis=1),
                 color_discrete_sequence=[GREEN], title="Lift by discount depth",
                 labels={"depth": "Discount depth", "pct": "Players in first week vs. controls (%)"})
    fig.add_hline(y=D["did_pct"], line_dash="dash", line_color=VERM, annotation_text=f"All sales +{D['did_pct']:.0f}%",
                  annotation_position="top left", annotation_bgcolor="rgba(255,255,255,0.85)")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(range=[0, dep.pct.max() * 1.2])
    st.plotly_chart(style(fig), width="stretch")
    st.warning("**Association, not causation, from 2019-20 data.** Difference-in-differences vs. non-discounted paid games in "
               "the same window, on a Mendeley CC BY 4.0 2019-20 price/player panel (not today's tracked games). "
               "Publishers choose sale timing, often alongside updates or events.")
    st.caption(HIST_NOTE)
    g, *_ = data()
    with st.expander("Games on sale today"):
        st.dataframe(g[g.on_sale].sort_values("discount_pct", ascending=False)[["game_name", "discount_pct", "price_usd", "initial_price_usd", "last_players"]], hide_index=True)
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
    c[0].metric("Concurrent players", fmt(r.last_players))
    lo, hi = r.owners_estimate_low, r.owners_estimate_high
    c[1].metric("Owners (est.)", "n/a" if pd.isna(lo) or pd.isna(hi) else f"{short(lo)}–{short(hi)}",
                help=f"SteamSpy estimate range: {r.owners_estimate_range}" if isinstance(r.owners_estimate_range, str) else None)
    c[2].metric("Positive reviews", "n/a" if pd.isna(r.positive_review_share) else f"{r.positive_review_share:.0%}")
    c[3].metric("Price", "Free" if r.pricing == "Free-to-play" else ("n/a" if pd.isna(r.price_usd) else f"${r.price_usd:.2f}"))
    st.table(details_table(r))
    ts = fct[fct.appid == r.appid].sort_values("snapshot_date_utc")
    if len(ts) < 3:
        st.info(f"Daily player chart appears once there are at least 3 days of data (currently {len(ts)} day"
                f"{'' if len(ts) == 1 else 's'}). The pipeline adds a day every run.")
    else:
        fig = px.line(ts.rename(columns={"peak_players_sampled": "Peak", "avg_players_sampled": "Average"}),
                      x="snapshot_date_utc", y=["Peak", "Average"], markers=True, title="Daily players",
                      labels={"value": "Players", "snapshot_date_utc": "Date (UTC)", "variable": ""})
        fig.update_xaxes(tickformat="%b %d, %Y", dtick="D1")
        st.plotly_chart(style(fig), width="stretch")
    source_note()

def details_table(r):
    """Clean, labelled details for one game: missing values shown as 'n/a', numbers rounded, dates as text."""
    def val(v, kind=None):
        if v is None or (not isinstance(v, (list, tuple)) and pd.isna(v)): return "n/a"
        if kind == "date": return pd.to_datetime(v).strftime("%b %d, %Y")
        if kind == "pct": return f"{v:.0f}%"
        if kind == "int": return f"{v:,.0f}"
        if kind == "1dp": return f"{v:,.1f}"
        return str(v)
    rows = [("Developer", val(r.developer)), ("Publisher", val(r.publisher)), ("Main genre", val(r.primary_genre)),
            ("Release date", val(r.release_date, "date")), ("Discount today", val(r.discount_pct, "pct")),
            ("Metacritic score", val(r.metacritic_score, "int")),
            ("Players per 1,000 owners", val(r.players_per_1k_owners, "1dp"))]
    return pd.DataFrame(rows, columns=["Detail", "Value"]).set_index("Detail")

# ------------------------------------------------------------------ Game Finder
# Ranking options: the analysis layer's composite score (default) or one single metric.
RANKS = {"score": "Composite score", "positive_review_share": "Positive reviews", "last_players": "Concurrent players"}
PARTS = {"review_bayes_part": "Reviews (Bayes-adjusted) x0.45", "player_strength_part": "Players (log CCU) x0.35",
         "value_per_dollar_part": "Value per dollar x0.20"}
SOFTWARE_NOTE = ("Software (e.g. Wallpaper Engine, Blender, Soundpad) is excluded from the score by the analysis layer's rule "
                 "(software-genre rule + curated list), applied in marts.mart_game_scores ({n} apps excluded).")

@st.cache_data(show_spinner=False, ttl=3600)
def scored(include_software):
    dim, fct, *_ = marts.load()
    return marts.add_score(marts.enrich(dim, fct), include_software=include_software)

def app_type_ready(df):
    """True once dim_game carries app_type for (nearly) every scored game."""
    return "app_type" in df and df.loc[df.score.notna(), "app_type"].notna().mean() >= 0.95

def finder_frame(include_software=False):
    g = scored(include_software); b = bridge()
    det = g[g.show_in_finder].copy()  # all scored games; attribute filters narrow to games that have that attribute
    for kind, col in [("genre", "genres"), ("category", "categories"), ("tag", "tags")]:  # from marts.bridge_game_category
        det[col] = det.appid.map(b[b.kind == kind].groupby("appid").label.apply(list)).apply(lambda v: v if isinstance(v, list) else [])
    return det, b

def software_controls(key):
    inc = st.sidebar.toggle("Include software", value=False, key=key + "_sw",
                            help="Lists the software apps too. The mart doesn't score software, so they appear unscored at the bottom.")
    n = int(scored(False).is_software.sum())
    st.info(SOFTWARE_NOTE.format(n=n) + (" **Software is listed, unscored, at the bottom of the ranking.**" if inc else ""))
    return inc

def apply_app_type(det, key):
    """Turns on automatically once dim_game has app_type for (nearly) every scored game."""
    if app_type_ready(det):
        types = sorted(det.app_type.dropna().unique())
        keep = st.sidebar.multiselect("App type", types, default=[t for t in types if t == "game"] or types, key=key)
        return det[det.app_type.isin(keep)]
    return det

def fmt_rank(m, v):
    if pd.isna(v): return "n/a"
    return f"{v:.3f}" if m == "score" else f"{v:.0%}" if m == "positive_review_share" else fmt(v)

def finder():
    st.header("Game Finder")
    st.caption("Ranked by the analysis layer's validated composite score (marts.mart_game_scores, ported from analysis/src/best_score.py): percentile ranks of "
               "Bayesian review share (0.45), log concurrent players (0.35) and value per dollar (0.20). Retention and momentum are weighted 0 "
               "until there is daily history.")
    inc = software_controls("finder")
    det, b = finder_frame(inc)
    with st.sidebar:
        st.subheader("Finder filters")
        genres = st.multiselect("Genres (match any)", sorted(b[b.kind == "genre"].label.unique()))
        cats = st.multiselect("Store categories (match all)", sorted(b[b.kind == "category"].label.unique()))
        tags = st.multiselect("Tags (match all)", sorted(b[b.kind == "tag"].label.unique()))
        deck = st.multiselect("Steam Deck status", sorted(det.deck_status.dropna().unique()))
        coop = st.checkbox("Local co-op (dim_game.has_local_coop)")
        split = st.checkbox("Split-screen (dim_game.has_split_screen)")
        ctrl = st.checkbox("Full controller support (dim_game.full_controller_support)")
        price = det.score_price_usd.fillna(0)
        pr = st.slider("Price (USD)", 0.0, float(price.max()), (0.0, float(price.max())))
        yrs = pd.to_datetime(det.release_date).dt.year.dropna()
        yr = st.slider("Release year (games without a date are kept unless narrowed)", int(yrs.min()), int(yrs.max()), (int(yrs.min()), int(yrs.max())))
        rank_by = st.selectbox("Rank by", list(RANKS), format_func=RANKS.get, index=0)
    f = apply_app_type(det, "finder_app_type")
    if genres: f = f[f.genres.apply(lambda v: bool(set(v) & set(genres)))]
    if cats: f = f[f.categories.apply(lambda v: set(cats) <= set(v))]
    if tags: f = f[f.tags.apply(lambda v: set(tags) <= set(v))]
    if deck: f = f[f.deck_status.isin(deck)]
    for on, flag in [(coop, "has_local_coop"), (split, "has_split_screen"), (ctrl, "full_controller_support")]:
        if on: f = f[f[flag].fillna(False).astype(bool)]
    f = f[f.score_price_usd.fillna(0).between(*pr)]
    y = pd.to_datetime(f.release_date).dt.year
    narrowed = (yr[0], yr[1]) != (int(yrs.min()), int(yrs.max()))
    f = f[y.between(*yr) | (y.isna() & (not narrowed))]
    f = f.sort_values(rank_by, ascending=False, na_position="last")
    cov = marts.coverage(data()[0])
    st.caption(f"Coverage (live): tags for {cov['tags']:,} of {cov['games']:,} games, Steam Deck status for {cov['deck']:,}, "
               f"store details (genres, categories, feature flags) for {cov['store_details']:,}. This public app uses a fixed snapshot, "
               f"so tag, Deck and feature filters only return games covered so far.")
    st.write(f"**{len(f)}** of {len(det)} {'apps' if inc else 'scored games'} match.")
    if f.empty:
        st.info("No games match. Loosen the filters."); return
    top = f.iloc[0]
    with st.container(border=True):
        st.markdown(f"### ⭐ [{top.game_name}]({STORE.format(int(top.appid))})")
        st.write(", ".join(top.genres) if top.genres else "")
        c = st.columns(4)
        if pd.isna(top.score):
            c[0].metric("Composite score", "unscored", "software", delta_color="off")
        else:
            c[0].metric("Composite score", f"{top.score:.3f}", f"#{int(top.score_rank)} of {int(det.score.notna().sum())}", delta_color="off")
        for col, (k, lab) in zip(c[1:], PARTS.items()):
            col.metric(lab, "n/a" if pd.isna(top[k]) else f"{top[k]:.3f}")
        if rank_by != "score":
            st.caption(f"Ranked by {RANKS[rank_by]}: {fmt_rank(rank_by, top[rank_by])}")
    tbl = f.assign(rank=range(1, len(f) + 1), store=f.appid.map(lambda a: STORE.format(int(a))))
    show = ["rank", "game_name", "store", "score", *PARTS, "positive_review_share", "last_players", "score_price_usd"]
    st.dataframe(tbl[show], hide_index=True, column_config={
        "store": st.column_config.LinkColumn("Steam store", display_text="Open"),
        "score": st.column_config.NumberColumn("Score", format="%.3f"),
        "positive_review_share": st.column_config.NumberColumn("Positive reviews", format="percent"),
        "last_players": st.column_config.NumberColumn("Concurrent players", format="%d"),
        "score_price_usd": st.column_config.NumberColumn("Price", format="$%.2f"),
        **{k: st.column_config.ProgressColumn(v, min_value=0, max_value=0.45, format="%.3f") for k, v in PARTS.items()}})
    comp = st.multiselect("Compare games side by side", list(f.game_name), default=list(f.game_name[:min(3, len(f))]), max_selections=5)
    if comp:
        cmp = f[f.game_name.isin(comp)].set_index("game_name")
        st.dataframe(cmp[["score", *PARTS, "review_bayes", "positive_review_share", "last_players", "score_price_usd", "owners_estimate_range", "primary_genre", "release_date"]].T.astype(str))
        long = cmp[list(PARTS)].rename(columns=PARTS).reset_index().melt("game_name")
        st.plotly_chart(style(px.bar(long, x="game_name", y="value", color="variable", color_discrete_sequence=[BLUE, ORANGE, GREEN],
                                     title="Score breakdown: the three weighted parts add up to the composite score",
                                     labels={"game_name": "", "value": "Contribution to score", "variable": ""})), width="stretch")
    source_note("Composite score from marts.mart_game_scores (software excluded); values match analysis/best_score_results.json.")

def leaderboards():
    st.header("Category leaderboards")
    inc = software_controls("lb")
    det, b = finder_frame(inc)
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
    source_note(f"{kind.title()}s with at least 5 games among the {int(det.has_store_details.fillna(False).sum()):,} scored games with store details. Score = analysis-layer composite.")


PAGES = {"Overview": overview, "Launch decay curves": decay, "Free-to-play vs paid": f2p, "Sales impact": sales,
         "Game lookup": lookup, "Game Finder": finder, "Category leaderboards": leaderboards}

def main():
    st.set_page_config(page_title="Steam Pulse", page_icon="🎮", layout="wide")
    page = st.sidebar.radio("Page", list(PAGES))
    try:
        data(); history(); results()  # warm the shared caches once so switching pages doesn't redo the loading
    except marts.DataUnavailable as e:
        st.title("Steam Pulse")
        st.error(f"Data isn't available right now. {e}")
        return
    PAGES[page]()

if __name__ == "__main__" or st.runtime.exists():
    main()
