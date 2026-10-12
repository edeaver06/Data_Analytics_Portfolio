"""Render the polished charts from the DuckDB marts (run src/run_pipeline.py first)."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import plotly.express as px  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.olist import connect  # noqa: E402

# Charts shown in README/STORY live in the project-root images/; the rest go to code/figures/.
MAIN = {"08_review_timing.png", "01_late_vs_reviews.png", "02_seller_tiers.png", "06_lane_heatmap.png"}
def fig_path(name):
    d = (ROOT.parent / "images") if name in MAIN else (ROOT / "figures")
    d.mkdir(parents=True, exist_ok=True)
    return d / name
# Okabe-Ito colorblind-safe palette: blue = baseline, vermillion = problem/highlight
NAVY, RED, GREY, INK = "#0072B2", "#D55E00", "#6b7280", "#1f2937"
SOURCE = ("Source: Brazilian E-Commerce Public Dataset by Olist (Kaggle, CC BY-NC-SA 4.0), "
          "orders Sep 2016 - Oct 2018.")
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#9ca3af", "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
    "axes.grid": False, "legend.frameon": False})


def finish(fig, path, title, subtitle, note=""):
    """Takeaway title + subtitle top-left, source note bottom-left, consistent margins."""
    fig.suptitle(title, x=0.01, y=0.985, ha="left", va="top", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.01, 0.925, subtitle, ha="left", va="top", fontsize=10.5, color=GREY)
    fig.text(0.01, 0.012, (note + "\n" if note else "") + SOURCE, ha="left", va="bottom", fontsize=7.5, color=GREY)
    fig.tight_layout(rect=(0, 0.07 if note else 0.04, 1, 0.9))
    fig.savefig(path, dpi=160); plt.close(fig)


def ygrid(ax, axis="y"):
    ax.grid(axis=axis, color="#e5e7eb", lw=0.8); ax.set_axisbelow(True)


def late_vs_score(con):
    df = con.execute("SELECT * FROM mart_delivery_vs_reviews").fetchdf()
    import textwrap
    labels = [textwrap.fill(b.split(". ")[1], 14) for b in df.late_bucket]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = [NAVY, NAVY] + [RED] * 4
    bars = ax.bar(labels, df.pct_1_2_star, color=colors)
    ax.bar_label(bars, labels=[f"{v:.0f}%" for v in df.pct_1_2_star], padding=3)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylabel("Share of 1-2 star reviews (bars)"); ax.set_xlabel("Delivery vs. promised date")
    ax.set_ylim(0, max(df.pct_1_2_star) * 1.18); ygrid(ax)
    ax2 = ax.twinx()
    ax2.plot(labels, df.avg_score, color=INK, marker="o", lw=2)
    for x, v in zip(labels, df.avg_score):
        ax2.annotate(f"{v:.1f}", (x, v), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=INK)
    ax2.set_ylim(1, 5); ax2.set_ylabel("Avg review score, 1-5 (line)")
    ax2.spines["top"].set_visible(False)
    finish(fig, fig_path("01_late_vs_reviews.png"),
           "Lateness is associated with a steep rise in 1-2 star reviews",
           "Share of 1-2 star reviews and average score by delivery timing (vermillion = late)",
           "Delivered orders with a review, n = %s. 'On estimate day' counts as on time. Most late-order "
           "reviews were written before the parcel arrived (chart 08)." % f"{df.orders.sum():,}")


def seller_tiers(con):
    df = con.execute("SELECT * FROM mart_seller_tiers").fetchdf()
    labels = [f"Q{int(r.late_quartile)}\n{r.pct_sp_sellers:.0f}% SP" for r in df.itertuples()]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    b = axes[0].bar(labels, df.late_rate_pct, color=[NAVY, NAVY, NAVY, RED])
    axes[0].bar_label(b, labels=[f"{v:.1f}%" for v in df.late_rate_pct], padding=3)
    axes[0].set_title("2018 late-delivery rate", fontsize=12); axes[0].yaxis.set_major_formatter(mtick.PercentFormatter())
    axes[0].set_ylim(0, max(df.late_rate_pct) * 1.18)
    b = axes[1].bar(labels, df.avg_score, color=[NAVY, NAVY, NAVY, RED])
    axes[1].bar_label(b, labels=[f"{v:.2f}" for v in df.avg_score], padding=3)
    axes[1].set_ylim(3.5, 4.5); axes[1].set_title("2018 avg review score (axis starts at 3.5)", fontsize=12)
    for a in axes:
        ygrid(a)
    axes[0].set_xlabel("Quartile by 2017 late rate (share of SP sellers)"); axes[1].set_xlabel("Quartile by 2017 late rate (share of SP sellers)")
    finish(fig, fig_path("02_seller_tiers.png"),
           "Last year's least reliable sellers are only modestly later this year",
           "Ranked on 2017 late rate (shrunk toward the mean), measured on 2018 orders; %d sellers with 30+ orders in both years"
           % int(df.sellers.sum()),
           "Q4 is 89% São Paulo sellers, so seller quality and shipping lanes are entangled.")


def review_timing(con):
    df = con.execute("SELECT * FROM mart_late_vs_ontime_by_timing").fetchdf()
    order = [("on time", "after delivery"), ("late", "after delivery"), ("late", "before delivery")]
    rows = [df[(df.delivery == d) & (df.review_timing == t)].iloc[0] for d, t in order]
    labels = [f"{d}\nreviewed {t}\n(n = {r.orders:,})" for (d, t), r in zip(order, rows)]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bars = ax.bar(labels, [r.avg_score for r in rows], color=[NAVY, "#E69F00", RED])
    ax.bar_label(bars, labels=[f"{r.avg_score:.2f}" for r in rows], padding=3)
    ax.set_ylim(1, 5); ax.set_ylabel("Avg review score (1-5)"); ygrid(ax)
    finish(fig, fig_path("08_review_timing.png"),
           "Reviewed after it arrived, a late order scores about half a star lower",
           "Average review score by delivery outcome and review timing; 84% of late-order reviews came before arrival",
           "Delivered orders with a review. On-time orders reviewed before delivery (3%) score 4.28.")


def monthly_gmv(con):
    df = con.execute("SELECT * FROM mart_monthly").fetchdf()
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(df.purchase_month, df.gmv.astype(float) / 1e3, color=NAVY, lw=2.5, marker="o", ms=4)
    ax.set_ylabel("GMV (R$ thousands)"); ax.set_xlabel("Purchase month"); ygrid(ax)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    peak = df.loc[df.purchase_month.dt.month.eq(11) & df.purchase_month.dt.year.eq(2017)].iloc[0]
    ax.annotate("Black Friday\nNov 2017", (peak.purchase_month, float(peak.gmv) / 1e3),
                xytext=(-90, 5), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": RED},
                color=RED, fontsize=10)
    ax.plot([peak.purchase_month], [float(peak.gmv) / 1e3], "o", color=RED, ms=7)
    finish(fig, fig_path("03_monthly_gmv.png"),
           "GMV grew through 2017 and peaked around Black Friday",
           "Monthly gross merchandise value, Jan 2017 - Aug 2018 (R$ thousands)")


def state_late(con):
    df = con.execute("SELECT * FROM mart_customer_states ORDER BY late_rate_pct").fetchdf()
    fig, ax = plt.subplots(figsize=(8, 7))
    avg = con.execute("SELECT late_rate_pct FROM mart_estimate_accuracy").fetchone()[0]
    bars = ax.barh(df.customer_state, df.late_rate_pct, color=[RED if v > 2 * avg else NAVY for v in df.late_rate_pct])
    ax.bar_label(bars, labels=[f"{v:.1f}%" for v in df.late_rate_pct], padding=2, fontsize=7.5, color=INK)
    ax.axvline(avg, color=INK, ls="--", lw=1); ax.text(avg + 0.3, 0.2, f"national {avg:.1f}%", fontsize=9)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter()); ax.tick_params(axis="y", labelsize=9)
    ax.set_xlabel("Late-delivery rate"); ax.set_xlim(0, max(df.late_rate_pct) * 1.15); ygrid(ax, "x")
    finish(fig, fig_path("04_state_late_rate.png"),
           "Late deliveries cluster in the North and Northeast",
           "Late-delivery rate by customer state (vermillion = more than 2x the national rate)")


def category_matrix(con):
    df = con.execute("SELECT * FROM mart_categories WHERE orders >= 500").fetchdf()
    df["gmv_k"] = df.gmv.astype(float) / 1e3
    fig = px.scatter(df, x="late_rate_pct", y="avg_score", size="gmv_k", text="category",
                     hover_data=["orders", "aov"], size_max=45,
                     labels={"late_rate_pct": "Late-delivery rate (%)", "avg_score": "Avg review score",
                             "gmv_k": "GMV (R$k)"},
                     title="Categories with more late deliveries tend to score lower"
                           "<br><sup>Late-delivery rate vs. average review score; bubble = GMV (categories with 500+ orders)</sup>")
    fig.update_traces(textposition="top center", textfont_size=9, marker_color=NAVY, marker_opacity=0.6)
    fig.update_layout(template="simple_white", width=1000, height=640, font_family="Arial",
                      margin={"b": 90}, xaxis_showgrid=True, yaxis_showgrid=True)
    fig.add_annotation(text=SOURCE, xref="paper", yref="paper", x=0, y=-0.14, showarrow=False,
                       xanchor="left", font={"size": 10, "color": GREY})
    fig.write_html(fig_path("05_category_matrix.html"), include_plotlyjs="cdn")
    # static fallback for the README (matplotlib, so no browser/kaleido dependency)
    fig2, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(df.late_rate_pct, df.avg_score, s=df.gmv_k / 3, color=NAVY, alpha=0.5)
    for _, r in df.nlargest(10, "gmv").iterrows():
        ax.annotate(r.category, (r.late_rate_pct, r.avg_score), fontsize=8, ha="center", va="bottom")
    ax.set_xlabel("Late-delivery rate"); ax.set_ylabel("Avg review score (1-5)"); ygrid(ax, "both")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    finish(fig2, fig_path("05_category_matrix.png"),
           "Categories with more late deliveries tend to score lower",
           "Product categories with 500+ orders; bubble size = GMV, top 10 by GMV labelled")


def lane_heatmap(con, min_orders: int = 100):
    import numpy as np
    df = con.execute("SELECT seller_state, customer_state, orders, late_rate_pct FROM mart_lanes "
                     "WHERE orders >= ?", [min_orders]).fetchdf()
    piv = df.pivot(index="seller_state", columns="customer_state", values="late_rate_pct")
    piv = piv.loc[piv.notna().sum(axis=1).sort_values(ascending=False).index]
    piv = piv[piv.notna().sum().sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(12, 4.8))
    im = ax.imshow(piv.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(piv.shape[1]), piv.columns); ax.set_yticks(range(piv.shape[0]), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if v > 15 else "black")
    ax.set_xlabel("Customer state"); ax.set_ylabel("Seller state")
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    fig.colorbar(im, ax=ax, label="Late rate (%)", fraction=0.03, pad=0.01).outline.set_visible(False)
    finish(fig, fig_path("06_lane_heatmap.png"),
           "The slowest lanes run from Sao Paulo sellers to Northeastern customers",
           f"Late-delivery rate (%) by seller -> customer state lane; lanes with {min_orders}+ single-seller "
           "delivered orders (blank = fewer)")


def cohort_retention(con, max_offset: int = 12, min_cohort: int = 500):
    df = con.execute("""
        SELECT c.cohort, c.month_offset, c.retention_pct
        FROM mart_cohorts c
        JOIN (SELECT cohort FROM mart_cohorts WHERE month_offset = 0 AND customers >= ?) big USING (cohort)
        WHERE c.month_offset BETWEEN 1 AND ?""", [min_cohort, max_offset]).fetchdf()
    piv = df.pivot(index="cohort", columns="month_offset", values="retention_pct").sort_index()
    fig, ax = plt.subplots(figsize=(11, 6))
    im = ax.imshow(piv.values, cmap="Blues", aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), [d.strftime("%Y-%m") for d in piv.index])
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            if v == v:
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7)
    ax.set_xlabel("Months since first purchase"); ax.set_ylabel("First-purchase cohort")
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    fig.colorbar(im, ax=ax, label="% of cohort ordering again", fraction=0.03, pad=0.01).outline.set_visible(False)
    finish(fig, fig_path("07_cohort_retention.png"),
           "Under 1% of customers return in any later month",
           f"Cohort retention (%) by first-purchase month; cohorts with {min_cohort}+ customers, colour capped at 1%")


def main() -> None:
    con = connect()
    for f in (late_vs_score, review_timing, seller_tiers, monthly_gmv, state_late, category_matrix, lane_heatmap, cohort_retention):
        f(con)
    print("figures ->", ROOT.parent / "images", "and", ROOT / "figures")


if __name__ == "__main__":
    main()
