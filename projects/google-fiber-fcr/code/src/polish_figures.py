"""Regenerate portfolio-ready figures + dashboard for the Google Fiber FCR project.
Run: .venv/bin/python src/polish_figures.py   (README/STORY charts -> ../images/, others -> figures/)"""
import sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fcr import load_data, preprocess, summary_by_category, summary_by_market, weekly_trend  # noqa

# Charts shown in README/STORY live in the project-root images/; the rest go to code/figures/.
MAIN = {"wifi_tech_share_by_market.png", "repeat_rate_by_market.png", "billing_with_without_market3.png", "dashboard.png"}
def fig_path(name):
    d = (ROOT.parent / "images") if name in MAIN else (ROOT / "figures")
    d.mkdir(parents=True, exist_ok=True)
    return d / name
SOURCE = "Source: Google Fiber FCR sample data, Jan-Mar 2022"
# Okabe-Ito colorblind-safe palette
BLUE, ORANGE, GREEN, VERM, SKY, GREY, YELLOW = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#9E9E9E", "#F0E442"
CAT_COLORS = {"Wi-Fi & Internet": BLUE, "Technical Troubleshooting": SKY,
              "Account Management & Billing": VERM, "Scheduling": ORANGE, "Construction": GREEN}
MKT = {"market_1": "Market 1", "market_2": "Market 2", "market_3": "Market 3"}
WT = ["Wi-Fi & Internet", "Technical Troubleshooting"]
BILL = "Account Management & Billing"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": "#888", "axes.titleweight": "bold",
    "axes.titlesize": 14, "axes.titlelocation": "left", "figure.dpi": 100, "savefig.dpi": 200})

# ---------- metrics ----------
df = preprocess(load_data())
cat = summary_by_category(df)
mkt = summary_by_market(df)
mc = summary_by_market(df, by_category=True)
wk = weekly_trend(df)

tot_rep = cat.repeat_calls.sum()
wt_share = cat[cat.problem_category.isin(WT)].repeat_calls.sum() / tot_rep * 100
share = {}
share_ex = {}
for m, g in mc.groupby("market"):
    wt = g[g.problem_category.isin(WT)].repeat_calls.sum()
    share[m] = wt / g.repeat_calls.sum() * 100
    share_ex[m] = wt / g[g.problem_category != BILL].repeat_calls.sum() * 100
b = mc[mc.problem_category == BILL].set_index("market")
bill_all = b.repeat_calls.sum() / b.first_calls.sum() * 100
b12 = b.drop("market_3")
bill_ex3 = b12.repeat_calls.sum() / b12.first_calls.sum() * 100
m3b = b.loc["market_3"]
METRICS = dict(wt_share=wt_share, share=share, share_ex=share_ex, bill_all=bill_all, bill_ex3=bill_ex3,
               m3_bill_rep=int(m3b.repeat_calls), m3_bill_first=int(m3b.first_calls))

def note(fig, extra=""):
    fig.text(0.01, 0.01, SOURCE + (f"  ·  {extra}" if extra else ""), fontsize=8.5, color="#666")

def title(ax, t, s):
    ax.set_title(t, pad=28)
    ax.text(0, 1.02, s, transform=ax.transAxes, fontsize=10.5, color="#444")

def save(fig, name):
    fig.savefig(fig_path(name), bbox_inches="tight", facecolor="white"); plt.close(fig)

# ---------- matplotlib draw fns (reused for dashboard) ----------
def draw_wt_share(ax, neutral=True):
    ms = list(MKT); y = range(len(ms))
    v = [share[m] for m in ms]; ve = [share_ex[m] for m in ms]
    ax.barh(y, v, color=BLUE, height=0.55, label="All categories")
    ax.scatter([ve[2]], [2], marker="D", color=ORANGE, zorder=3, s=60, label="Market 3 excl. Billing")
    for i, x in enumerate(v): ax.text(x + 1, i, f"{x:.1f}%", va="center", fontweight="bold")
    ax.text(ve[2] + 1.5, 2 - 0.32, f"{ve[2]:.1f}% excl. Billing", color=ORANGE, fontsize=9)
    ax.axvline(50, color=GREY, ls="--", lw=1); ax.text(50.5, 2.45, "50%", color=GREY, fontsize=9)
    ax.axvline(wt_share, color="#333", ls=":", lw=1); ax.text(wt_share + .5, 2.45, f"overall {wt_share:.1f}%", fontsize=9)
    ax.set_yticks(list(y), [MKT[m] for m in ms]); ax.invert_yaxis()
    ax.set_xlim(0, 100); ax.xaxis.set_major_formatter(PercentFormatter())
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False, fontsize=9)
    t = ("Wi-Fi + Tech Troubleshooting share of repeat calls by market" if neutral else
         "Wi-Fi + Tech Troubleshooting are the majority of repeats in every market")
    title(ax, t, f"{wt_share:.1f}% of all repeat calls; Market 3's share is diluted by suspect Billing rows")

def draw_rate_by_cat(ax):
    c = cat.sort_values("repeat_rate_pct")
    bars = ax.barh(c.problem_category, c.repeat_rate_pct, color=[CAT_COLORS[x] for x in c.problem_category])
    for bb, r, n in zip(bars, c.repeat_rate_pct, c.repeat_calls):
        ax.text(bb.get_width() + 1, bb.get_y() + bb.get_height()/2, f"{r:.1f}%  ({n:,} repeats)", va="center", fontsize=9.5)
    ax.set_xlim(0, 90); ax.xaxis.set_major_formatter(PercentFormatter())
    ax.set_xlabel("Repeat calls per 100 first calls")
    title(ax, "Repeat rate by problem category", f"Billing {bill_all:.1f}% (inflated by Market 3) and Scheduling "
          f"{cat.set_index('problem_category').loc['Scheduling','repeat_rate_pct']:.1f}% have the highest rates")

def draw_vol_by_cat(ax):
    c = cat.sort_values("repeat_calls")
    bars = ax.barh(c.problem_category, c.repeat_calls, color=[CAT_COLORS[x] for x in c.problem_category])
    for bb, n, p in zip(bars, c.repeat_calls, c.pct_of_total_repeats):
        ax.text(bb.get_width() + 150, bb.get_y() + bb.get_height()/2, f"{n:,}  ({p:.1f}%)", va="center", fontsize=9.5)
    ax.set_xlim(0, c.repeat_calls.max() * 1.3); ax.set_xlabel("Repeat calls")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    title(ax, "Repeat-call volume by problem category", f"Wi-Fi + Tech Troubleshooting account for {wt_share:.1f}% of {tot_rep:,} repeat calls")

def draw_rate_by_mkt(ax):
    m = mkt.copy(); cols = [VERM if x == "market_3" else GREY for x in m.market]
    bars = ax.bar([MKT[x] for x in m.market], m.repeat_rate_pct, color=cols, width=0.6)
    for bb, r, f in zip(bars, m.repeat_rate_pct, m.first_calls):
        ax.text(bb.get_x() + bb.get_width()/2, r + 1, f"{r:.1f}%", ha="center", fontweight="bold")
        ax.text(bb.get_x() + bb.get_width()/2, 1.5, f"{f:,}\nfirst calls", ha="center", fontsize=8, color="white")
    ax.set_ylim(0, 55); ax.yaxis.set_major_formatter(PercentFormatter()); ax.set_ylabel("Repeat rate")
    title(ax, "Repeat rate by market", "Market 3 is highest at "
          f"{mkt.set_index('market').loc['market_3','repeat_rate_pct']:.1f}% and deserves a closer look")

def draw_billing(ax):
    labels = ["All markets", "Markets 1-2 only\n(excl. Market 3)"]; vals = [bill_all, bill_ex3]
    bars = ax.bar(labels, vals, color=[VERM, BLUE], width=0.55)
    for bb, v in zip(bars, vals): ax.text(bb.get_x() + bb.get_width()/2, v + 1.5, f"{v:.1f}%", ha="center", fontweight="bold", fontsize=13)
    ax.set_ylim(0, 85); ax.yaxis.set_major_formatter(PercentFormatter()); ax.set_ylabel("Billing repeat rate")
    ax.annotate(f"Market 3 Billing: {METRICS['m3_bill_rep']:,} repeats on\n{METRICS['m3_bill_first']:,} first calls "
                f"({METRICS['m3_bill_rep']/METRICS['m3_bill_first']*100:.0f}%) - likely\ndata-quality / mapping issue",
                xy=(0, bill_all), xytext=(0.55, 72), fontsize=9, color="#333",
                arrowprops=dict(arrowstyle="->", color="#555"),
                bbox=dict(boxstyle="round", fc="#FFF8E1", ec=ORANGE))
    title(ax, "Billing repeat rate, with and without Market 3", f"{bill_all:.1f}% overall drops to {bill_ex3:.1f}% once Market 3 is excluded")

def draw_weekly(ax):
    ax.plot(wk.week, wk.repeat_rate_pct, color=BLUE, lw=2.2, marker="o", ms=4)
    avg = tot_rep / cat.first_calls.sum() * 100
    ax.axhline(avg, color=GREY, ls="--", lw=1); ax.text(wk.week.iloc[0], avg + .6, f"Q1 avg {avg:.1f}%", color="#555", fontsize=9)
    for i in [wk.repeat_rate_pct.idxmax(), wk.repeat_rate_pct.idxmin()]:
        ax.annotate(f"{wk.repeat_rate_pct[i]:.1f}%", (wk.week[i], wk.repeat_rate_pct[i]), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    ax.yaxis.set_major_formatter(PercentFormatter()); ax.set_ylabel("Repeat rate")
    ax.tick_params(axis="x", labelsize=9); plt.setp(ax.get_xticklabels(), rotation=0)
    import matplotlib.dates as md; ax.xaxis.set_major_formatter(md.DateFormatter("%b %d"))
    title(ax, "Weekly repeat rate, Q1 2022", f"Weekly range {wk.repeat_rate_pct.min():.1f}%-{wk.repeat_rate_pct.max():.1f}% (weeks start Monday)")

CHARTS = [("wifi_tech_share_by_market.png", draw_wt_share), ("billing_with_without_market3.png", draw_billing),
          ("repeat_rate_by_market.png", draw_rate_by_mkt), ("repeat_rate_by_category.png", draw_rate_by_cat),
          ("repeat_volume_by_category.png", draw_vol_by_cat), ("weekly_trend.png", draw_weekly)]

for name, fn in CHARTS:
    fig, ax = plt.subplots(figsize=(10, 5.6)); fn(ax); note(fig); save(fig, name)
# alternate headline title (only if Evan confirms "majority in every market")
fig, ax = plt.subplots(figsize=(10, 5.6)); draw_wt_share(ax, neutral=False); note(fig)
save(fig, "wifi_tech_share_by_market_headline_alt.png")

# ---------- static dashboard ----------
fig = plt.figure(figsize=(20, 17))
fig.suptitle("Google Fiber First-Call Resolution - Q1 2022", x=0.01, ha="left", fontsize=22, fontweight="bold", y=0.995)
fig.text(0.01, 0.965, f"Wi-Fi + Tech Troubleshooting drive {wt_share:.1f}% of repeat calls  ·  Billing {bill_all:.1f}% "
         f"overall vs {bill_ex3:.1f}% excl. Market 3  ·  Market 3 repeat rate "
         f"{mkt.set_index('market').loc['market_3','repeat_rate_pct']:.1f}%", fontsize=13, color="#333")
gs = fig.add_gridspec(3, 2, hspace=0.55, wspace=0.35, top=0.91, bottom=0.05)
for i, (_, fn) in enumerate(CHARTS):
    fn(fig.add_subplot(gs[i // 2, i % 2]))
note(fig, f"{len(df):,} rows; repeat rate = repeat calls (days 1-7) / first calls")
save(fig, "dashboard.png")

# ---------- interactive HTML dashboard ----------
p = make_subplots(rows=3, cols=2, vertical_spacing=0.11, horizontal_spacing=0.14, subplot_titles=[
    "Wi-Fi + Tech share of repeat calls by market", "Billing repeat rate, with vs without Market 3",
    "Repeat rate by market", "Repeat rate by problem category",
    "Repeat-call volume by category", "Weekly repeat rate"])
ms = list(MKT)
p.add_bar(y=[MKT[m] for m in ms], x=[share[m] for m in ms], orientation="h", marker_color=BLUE, name="All categories",
          text=[f"{share[m]:.1f}%" for m in ms], textposition="outside", row=1, col=1)
p.add_bar(y=[MKT[m] for m in ms], x=[share_ex[m] for m in ms], orientation="h", marker_color=ORANGE, name="Excl. Billing",
          text=[f"{share_ex[m]:.1f}%" for m in ms], textposition="outside", row=1, col=1)
p.add_bar(x=["All markets", "Markets 1-2"], y=[bill_all, bill_ex3], marker_color=[VERM, BLUE], showlegend=False,
          text=[f"{bill_all:.1f}%", f"{bill_ex3:.1f}%"], textposition="outside", row=1, col=2)
p.add_bar(x=[MKT[m] for m in mkt.market], y=mkt.repeat_rate_pct, showlegend=False,
          marker_color=[VERM if m == "market_3" else GREY for m in mkt.market],
          text=[f"{v:.1f}%" for v in mkt.repeat_rate_pct], textposition="outside",
          customdata=mkt[["first_calls", "repeat_calls"]], hovertemplate="%{x}: %{y:.1f}%<br>first %{customdata[0]:,}<br>repeat %{customdata[1]:,}<extra></extra>", row=2, col=1)
c = cat.sort_values("repeat_rate_pct")
p.add_bar(y=c.problem_category, x=c.repeat_rate_pct, orientation="h", showlegend=False,
          marker_color=[CAT_COLORS[x] for x in c.problem_category], text=[f"{v:.1f}%" for v in c.repeat_rate_pct], textposition="outside", row=2, col=2)
c = cat.sort_values("repeat_calls")
p.add_bar(y=c.problem_category, x=c.repeat_calls, orientation="h", showlegend=False,
          marker_color=[CAT_COLORS[x] for x in c.problem_category], text=[f"{n:,} ({s:.1f}%)" for n, s in zip(c.repeat_calls, c.pct_of_total_repeats)], textposition="outside", row=3, col=1)
p.add_scatter(x=wk.week, y=wk.repeat_rate_pct, mode="lines+markers", line_color=BLUE, showlegend=False, row=3, col=2)
p.update_layout(template="simple_white", height=1300, width=1300, barmode="group", font_family="Arial",
    title=dict(text=f"<b>Google Fiber First-Call Resolution - Q1 2022</b><br><sup>Wi-Fi + Tech drive {wt_share:.1f}% of repeat calls · "
               f"Billing {bill_all:.1f}% overall vs {bill_ex3:.1f}% excl. Market 3 (Market 3 Billing: {METRICS['m3_bill_rep']:,} repeats on "
               f"{METRICS['m3_bill_first']:,} first calls, likely data issue) · Market 3 repeat rate {mkt.set_index('market').loc['market_3','repeat_rate_pct']:.1f}%</sup>", x=0.01),
    legend=dict(orientation="h", x=0, y=1.04), margin=dict(t=130, b=70),
    annotations=list(p.layout.annotations) + [dict(text=SOURCE, xref="paper", yref="paper", x=0, y=-0.05, showarrow=False, font=dict(size=10, color="#666"))])
for r, cc in [(1, 1), (2, 2)]: p.update_xaxes(range=[0, 100 if r == 1 else 90], ticksuffix="%", row=r, col=cc)
p.update_yaxes(ticksuffix="%", range=[0, 85], row=1, col=2); p.update_yaxes(ticksuffix="%", range=[0, 55], row=2, col=1)
p.update_xaxes(range=[0, cat.repeat_calls.max() * 1.35], row=3, col=1); p.update_yaxes(ticksuffix="%", row=3, col=2)
p.write_html(fig_path("dashboard.html"), include_plotlyjs=True, full_html=True)

if __name__ == "__main__":
    print(f"WT overall {wt_share:.1f}% | per market " + ", ".join(f"{m} {share[m]:.1f}% (exBill {share_ex[m]:.1f}%)" for m in ms))
    print(f"Billing all {bill_all:.1f}% | ex-m3 {bill_ex3:.1f}% | m3 billing {METRICS['m3_bill_rep']}/{METRICS['m3_bill_first']}")
    print(mkt.to_string(index=False)); print("weeks", len(wk), wk.repeat_rate_pct.min(), wk.repeat_rate_pct.max())
