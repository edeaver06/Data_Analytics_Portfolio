"""README hero chart from the committed parquet extract (app/data) -> ../images/hero_concentration.png (project root)"""
from pathlib import Path
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "app" / "data"
dim = pd.read_parquet(P / "dim_game.parquet")
fct = pd.read_parquet(P / "fct_daily_players.parquet")
snaps = pd.read_parquet(P / "snapshots.parquet")
ts = pd.to_datetime(snaps.snapshot_ts).max().tz_convert("America/Guatemala")
latest = fct.sort_values("snapshot_date_utc").groupby("appid").tail(1)
df = latest.merge(dim[["appid", "game_name"]], on="appid")[["game_name", "last_players"]].dropna()
df = df.sort_values("last_players", ascending=False).rename(columns={"last_players": "player_count"})
tot = int(df.player_count.sum()); top = df.head(15).iloc[::-1]; share = df.head(10).player_count.sum() / tot
fig, ax = plt.subplots(figsize=(9, 6.3)); fig.patch.set_facecolor("white")
ax.barh(top.game_name, top.player_count / 1e3, color=["#d95f02" if i >= 5 else "#1b9e77" for i in range(15)])
for y, v in enumerate(top.player_count):
    ax.text(v / 1e3 + 8, y, f"{v/1e3:,.0f}k", va="center", fontsize=8)
fig.suptitle(f"10 games hold {share:.0%} of all concurrent players\nacross {len(df):,} tracked Steam games",
             x=0.02, ha="left", fontsize=13, weight="bold")
ax.set_xlabel("Concurrent players (thousands) · orange = top 10"); ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, f"Latest snapshot {ts:%Y-%m-%d %H:%M} CST (UTC-6); {len(df):,} games, {tot:,} players. Universe: SteamSpy top-1,000 by owners plus newly tracked releases.\n"
         "Source: Steam Web API, SteamSpy; analysis by Evan Deaver", fontsize=7, color="gray")
plt.tight_layout(rect=(0, 0.045, 1, 1)); plt.savefig(ROOT.parent / "images" / "hero_concentration.png", dpi=150)
print(f"hero title: 10 games hold {share:.0%} | top-10 share {share:.4f}, total {tot}, games {len(df)}")
