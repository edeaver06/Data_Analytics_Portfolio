"""Hero chart from the latest snapshot in data/steam_pulse.duckdb -> images/hero_concentration.png"""
from pathlib import Path
import duckdb, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
c = duckdb.connect(str(ROOT / "data" / "steam_pulse.duckdb"), read_only=True)
c.execute("SET TimeZone='America/Guatemala'")
ts = c.execute("select max(snapshot_ts) from raw.player_counts").fetchone()[0]
df = c.execute("""select g.game_name, p.player_count from raw.player_counts p join marts.dim_game g using(appid)
 where p.snapshot_ts=(select max(snapshot_ts) from raw.player_counts) and p.ok order by 2 desc""").df()
tot = df.player_count.sum(); top = df.head(15).iloc[::-1]; share = df.head(10).player_count.sum() / tot
fig, ax = plt.subplots(figsize=(9, 6.3)); fig.patch.set_facecolor("white")
ax.barh(top.game_name, top.player_count / 1e3, color=["#d95f02" if i >= 5 else "#1b9e77" for i in range(15)])
for y, v in enumerate(top.player_count):
    ax.text(v / 1e3 + 8, y, f"{v/1e3:,.0f}k", va="center", fontsize=8)
fig.suptitle(f"10 games hold {share:.0%} of all concurrent players\nacross Steam's 1,000 most-owned games",
             x=0.02, ha="left", fontsize=13, weight="bold")
ax.set_xlabel("Concurrent players (thousands) · orange = top 10"); ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, f"Source: Steam Web API GetNumberOfCurrentPlayers, snapshot {ts:%Y-%m-%d %H:%M} CST (UTC-6); "
         f"{len(df)} games, {tot:,} players. Universe: SteamSpy top-1,000 by owners.", fontsize=7, color="gray")
plt.tight_layout(rect=(0, 0.03, 1, 1)); plt.savefig(ROOT / "images" / "hero_concentration.png", dpi=150)
print(f"top-10 share {share:.3f}, total {tot}, games {len(df)}")
