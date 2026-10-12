"""Helpers for notebooks/steam_pulse_story.ipynb.

Keeps the notebook readable: every function loads or summarises data and returns a small table,
or draws one chart. All numbers come from the bundled extract in app/data/ and the saved
results in analysis/*.json. Nothing here calls the internet.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"
BLUE, GREY, ORANGE = "#1f77b4", "#b0b0b0", "#ff7f0e"
plt.rcParams.update({"figure.figsize": (9, 4.5), "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "font.size": 11})


def load_games():
    """One row per game: name, latest player count, flags, and score."""
    dim = pd.read_parquet(DATA / "dim_game.parquet")
    fct = pd.read_parquet(DATA / "fct_daily_players.parquet")
    scores = pd.read_parquet(DATA / "mart_game_scores.parquet")
    latest = fct.sort_values("snapshot_date_utc").groupby("appid").tail(1)[["appid", "last_players"]]
    g = dim.merge(latest, on="appid").merge(scores, on="appid", how="left")
    return g.rename(columns={"last_players": "players"})


def history():
    return json.loads((ROOT / "analysis" / "history_results.json").read_text())


def _label_bars(ax, bars, fmt="{:,.0f}"):
    for b in bars:
        ax.annotate(fmt.format(b.get_width()), (b.get_width(), b.get_y() + b.get_height() / 2),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=9)


def hbar(series, title, xlabel, highlight=None, fmt="{:,.0f}"):
    s = series[::-1]
    colors = [ORANGE if highlight and k in highlight else BLUE for k in s.index]
    fig, ax = plt.subplots(figsize=(9, max(3, 0.38 * len(s) + 1)))
    _label_bars(ax, ax.barh(s.index, s.values, color=colors), fmt)
    ax.set_title(title); ax.set_xlabel(xlabel)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 10 else f"{v:g}"))
    plt.tight_layout(); plt.show()


def concentration(g):
    p = g["players"].sort_values(ascending=False).reset_index(drop=True)
    cum = p.cumsum() / p.sum()
    return pd.DataFrame({"rank": range(1, len(p) + 1), "share": cum})


def plot_concentration(c):
    fig, ax = plt.subplots()
    ax.plot(c["rank"], c["share"] * 100, color=BLUE, lw=2.5)
    for n in (10, 100):
        v = c.loc[n - 1, "share"] * 100
        ax.scatter([n], [v], color=ORANGE, zorder=3)
        ax.annotate(f"Top {n} games: {v:.1f}% of all players", (n, v), xytext=(15, -15), textcoords="offset points")
    ax.set_xscale("log"); ax.set_ylim(0, 100)
    ax.set_xlabel("Games, ranked from most to least played (log scale)")
    ax.set_ylabel("% of all players (running total)")
    ax.set_title("A handful of games hold most of the players")
    plt.tight_layout(); plt.show()


def median_by_flag(g, flags):
    """Typical (median) player count for games with vs without each feature."""
    rows = []
    for label, col in flags.items():
        for has in (True, False):
            sub = g[g[col] == has]
            rows.append({"feature": label, "has_it": "Yes" if has else "No",
                         "games": len(sub), "median_players": sub["players"].median()})
    return pd.DataFrame(rows)


def plot_paired(t, title):
    w = t.pivot(index="feature", columns="has_it", values="median_players")[["Yes", "No"]]
    ax = w.plot.barh(color=[BLUE, GREY], figsize=(9, 0.9 * len(w) + 1.5))
    for cont in ax.containers:
        ax.bar_label(cont, fmt="{:,.0f}", padding=3, fontsize=9)
    ax.set_title(title); ax.set_xlabel("Typical (median) players right now"); ax.set_ylabel("")
    ax.legend(title="Game has it?", frameon=False)
    plt.tight_layout(); plt.show()


def genre_medians(g, min_games=20):
    software = {"Utilities", "Software", "Design & Illustration", "Animation & Modeling", "Audio Production",
                "Video Production", "Photo Editing", "Web Publishing", "Game Development", "Education"}
    e = g[~g["is_software"].fillna(False)].explode("genres_any").dropna(subset=["genres_any"])
    e = e[~e["genres_any"].isin(software)]
    t = e.groupby("genres_any")["players"].agg(games="count", median_players="median")
    return t[t["games"] >= min_games].sort_values("median_players", ascending=False)


def retention_table(h):
    out = {}
    for k in ("all", "free", "paid"):
        out[k] = {r["m"]: r["median"] for r in h["retention"][k]}
    return pd.DataFrame(out)


def plot_retention(r):
    fig, ax = plt.subplots()
    for col, color, name in (("free", ORANGE, "Free-to-play"), ("paid", BLUE, "Paid"), ("all", GREY, "All games")):
        ax.plot(r.index, r[col] * 100, marker="o", color=color, lw=2.5 if col != "all" else 1.5, label=name)
    ax.set_xticks(r.index); ax.set_ylim(0, 105)
    ax.set_xlabel("Months after launch"); ax.set_ylabel("% of launch-month players still playing")
    ax.set_title("Most games lose about half their players after month one")
    ax.legend(frameon=False); plt.tight_layout(); plt.show()


def plot_discount(h):
    d = h["discount_did"]["by_depth"]
    s = pd.Series({k: v["pct"] for k, v in d.items()})
    fig, ax = plt.subplots()
    bars = ax.bar(s.index, s.values, color=BLUE)
    ax.bar_label(bars, labels=[f"+{v:.0f}%" for v in s.values], padding=3)
    ax.set_xlabel("Size of the discount"); ax.set_ylabel("Extra daily players in sale week (%)")
    ax.set_title("Bigger discounts, bigger bump in players")
    plt.tight_layout(); plt.show()
