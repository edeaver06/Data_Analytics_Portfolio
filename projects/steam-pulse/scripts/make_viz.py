"""Regenerate Steam Pulse static figures (figures/polished/) and Tableau CSVs (tableau/).
Usage: .venv/bin/python scripts/make_viz.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from marts import load, enrich, add_score

BLUE, ORANGE, GREEN, GREY, VERM = "#0072B2", "#E69F00", "#009E73", "#8C8C8C", "#D55E00"
OUT = ROOT / "figures" / "polished"; OUT.mkdir(parents=True, exist_ok=True)
TAB = ROOT / "tableau"; TAB.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
                     "figure.dpi": 150, "axes.grid": True, "grid.alpha": .25})

dim, fct, snaps, src_label = load(); g = add_score(enrich(dim, fct))
snap = pd.to_datetime(snaps.snapshot_ts.iloc[-1]).strftime("%Y-%m-%d %H:%M UTC")
SRC = f"Source: Steam Web API concurrent players (snapshot {snap}), SteamSpy owner estimates & prices, Steam store details. Steam Pulse / Evan Deaver."
def note(fig, extra=""):
    fig.text(0.01, 0.01, (extra + "\n" if extra else "") + SRC, fontsize=7, color=GREY, ha="left", va="bottom")
def fmt(n): return f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.0f}K" if n >= 1e3 else f"{n:.0f}"

# ---------- hero: top 15 games by concurrent players, coloured by pricing ----------
top = g.nlargest(15, "last_players").iloc[::-1]
total = g.last_players.sum(); top3 = g.nlargest(3, "last_players").last_players.sum()
fig, ax = plt.subplots(figsize=(10, 6.2))
cols = [ORANGE if p == "Free-to-play" else BLUE for p in top.pricing]
ax.barh(top.game_name, top.last_players, color=cols)
for y, v in enumerate(top.last_players): ax.text(v, y, " " + fmt(v), va="center", fontsize=8)
ax.set_title(f"3 free-to-play games hold {top3/total:.0%} of all players in the top 1,000", pad=22)
ax.text(0, 1.02, f"Concurrent players, {fmt(total)} total across {int(g.last_players.notna().sum())} games",
        transform=ax.transAxes, fontsize=9, color="#444")
ax.xaxis.set_major_formatter(lambda v, _: fmt(v)); ax.grid(axis="y", visible=False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=ORANGE, label="Free-to-play"), Patch(color=BLUE, label="Paid")], loc="lower right", frameon=False)
fig.tight_layout(rect=(0, .05, 1, 1)); note(fig); fig.savefig(OUT / "hero.png"); plt.close(fig)

# ---------- launch decay (cross-sectional proxy: players per 1k owners vs years since release) ----------
d = g.dropna(subset=["years_since_release", "players_per_1k_owners"])
d = d[d.players_per_1k_owners > 0]
bins = [0, 1, 2, 5, 10, 30]; labels = ["<1 yr", "1-2", "2-5", "5-10", "10+"]
d = d.assign(age_bucket=pd.cut(d.years_since_release, bins, labels=labels))
med = d.groupby("age_bucket", observed=False).agg(n=("appid", "size"), med=("players_per_1k_owners", "median")).reset_index()
fig, ax = plt.subplots(figsize=(10, 5.8))
ax.scatter(d.years_since_release, d.players_per_1k_owners, s=18, color=BLUE, alpha=.45, label="Game")
mids = [0.5, 1.5, 3.5, 7.5, 15]
ax.plot(mids, med.med, color=VERM, marker="o", lw=2.2, label="Median by age bucket")
for x, (_, r) in zip(mids, med.iterrows()): ax.annotate(f"{r.med:.2f}\n(n={r.n})", (x, r.med), textcoords="offset points", xytext=(6, 6), fontsize=8, color=VERM)
ax.set_yscale("log"); ax.set_xlabel("Years since release"); ax.set_ylabel("Concurrent players per 1,000 estimated owners (log)")
ax.set_title("Older games keep a smaller share of their owners playing", pad=22)
ax.text(0, 1.02, "Cross-sectional proxy for launch decay: one snapshot, games with store details only", transform=ax.transAxes, fontsize=9, color="#444")
ax.legend(frameon=False)
fig.tight_layout(rect=(0, .07, 1, 1))
note(fig, f"Only {len(d)} games (the store-details sample, skewed to popular titles); <1 yr bucket has n={med.n.iloc[0]}. True per-game decay curves need daily snapshots.")
fig.savefig(OUT / "launch_decay.png"); plt.close(fig)

# ---------- f2p vs paid ----------
k = g[g.pricing.isin(["Free-to-play", "Paid"])]
s = k.groupby("pricing").agg(games=("appid", "size"), players=("last_players", "sum"),
      median_players=("last_players", "median"), median_review=("positive_review_share", "median"),
      median_p1k=("players_per_1k_owners", "median")).reindex(["Free-to-play", "Paid"])
s["player_share"] = s.players / s.players.sum(); s["game_share"] = s.games / s.games.sum()
fig, axs = plt.subplots(1, 4, figsize=(12, 4.6))
panels = [("game_share", "Share of games", lambda v: f"{v:.0%}"), ("player_share", "Share of players", lambda v: f"{v:.0%}"),
          ("median_players", "Median concurrent players", lambda v: f"{v:,.0f}"), ("median_review", "Median positive reviews", lambda v: f"{v:.0%}")]
for ax, (c, t, f) in zip(axs, panels):
    ax.bar(s.index, s[c], color=[ORANGE, BLUE]); ax.set_title(t, fontsize=10, loc="center")
    for i, v in enumerate(s[c]): ax.text(i, v, f(v), ha="center", va="bottom", fontsize=9)
    ax.set_yticks([]); ax.grid(False); ax.spines["left"].set_visible(False)
fig.suptitle(f"Free-to-play is {s.game_share.iloc[0]:.0%} of games but {s.player_share.iloc[0]:.0%} of players; the typical paid game is busier and better reviewed",
             x=.01, ha="left", fontweight="bold", fontsize=12)
fig.tight_layout(rect=(0, .06, 1, .93)); note(fig, "Free-to-play = SteamSpy current price $0. Medians are per game.")
fig.savefig(OUT / "f2p_vs_paid.png"); plt.close(fig)

# ---------- sales impact (cross-sectional) ----------
paid = g[(g.pricing == "Paid") & g.players_per_1k_owners.notna()].copy()
paid["discount_band"] = pd.cut(paid.discount_pct.fillna(0), [-1, 0, 25, 50, 75, 100], labels=["Full price", "1-25%", "26-50%", "51-75%", "76-100%"])
si = paid.groupby("discount_band", observed=False).agg(games=("appid", "size"), median_p1k=("players_per_1k_owners", "median"),
      median_players=("last_players", "median"), median_owners=("owners_mid", "median")).reset_index()
fig, ax = plt.subplots(figsize=(10, 5.6))
ax.bar(si.discount_band.astype(str), si.median_p1k, color=[GREY] + [GREEN] * 4)
for i, r in si.iterrows(): ax.text(i, r.median_p1k, f"{r.median_p1k:.2f}\n(n={r.games})", ha="center", va="bottom", fontsize=9)
ax.set_ylabel("Median concurrent players per 1,000 owners"); ax.grid(axis="x", visible=False)
ax.set_title("Deeper discounts sit on less-played games: sales don't look like a player-count boost", pad=22)
ax.text(0, 1.02, "Paid games in Steam's top 1,000, by current discount", transform=ax.transAxes, fontsize=9, color="#444")
fig.tight_layout(rect=(0, .07, 1, 1))
note(fig, "Cross-sectional association from one snapshot, not a before/after effect; 1-25% band has few games. A true sales-impact chart needs snapshots spanning sale start/end.")
fig.savefig(OUT / "sales_impact.png"); plt.close(fig)

# ---------- Tableau CSVs (one per view) ----------
keep = ["appid", "game_name", "developer", "publisher", "primary_genre", "release_date", "years_since_release", "pricing",
        "price_usd", "initial_price_usd", "discount_pct", "on_sale", "owners_estimate_range", "owners_estimate_low",
        "owners_estimate_high", "owners_mid", "positive", "negative", "positive_review_share", "metacritic_score",
        "last_players", "ccu_yesterday_peak", "players_per_1k_owners", "has_store_details"]
g[keep].rename(columns={"last_players": "concurrent_players"}).to_csv(TAB / "games.csv", index=False)
top.iloc[::-1][["appid", "game_name", "pricing", "last_players"]].rename(columns={"last_players": "concurrent_players"}).to_csv(TAB / "hero_top15.csv", index=False)
d[["appid", "game_name", "pricing", "release_date", "years_since_release", "age_bucket", "last_players", "owners_mid", "players_per_1k_owners"]].to_csv(TAB / "launch_decay.csv", index=False)
s.reset_index().to_csv(TAB / "f2p_vs_paid.csv", index=False)
paid[["appid", "game_name", "discount_pct", "discount_band", "price_usd", "initial_price_usd", "last_players", "owners_mid", "players_per_1k_owners"]].to_csv(TAB / "sales_impact.csv", index=False)
fct.merge(dim[["appid", "game_name"]], on="appid").to_csv(TAB / "daily_players.csv", index=False)

print("data:", src_label); print("total players", total, "top3 share", round(top3 / total, 4))
print(s.round(4).to_string()); print(med.to_string()); print(si.round(3).to_string())

# ---------- Game Finder / leaderboard CSVs ----------
from marts import load_bridge
b = load_bridge()
b.merge(g[["appid", "game_name"]], on="appid").to_csv(TAB / "game_labels.csv", index=False)  # bridge: appid x genre/category

# composite score per game (Data Analyst best_score.py, reused via marts.add_score)
g[["appid", "game_name", "app_type", "steamspy_price_usd", "positive", "negative", "last_players", "score", "score_rank",
   "review_bayes", "player_strength", "value_per_dollar", "review_bayes_part", "player_strength_part", "value_per_dollar_part"]
  ].dropna(subset=["score"]).sort_values("score", ascending=False).to_csv(TAB / "game_scores.csv", index=False)
