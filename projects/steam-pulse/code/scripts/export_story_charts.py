"""Save the story notebook's charts as PNGs for STORY.md.
Run from code/: python scripts/export_story_charts.py  (execute the notebook first).
The 3 charts the README also uses go to ../images/; the rest to figures/."""
import base64, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "steam_pulse_story.ipynb"
# in notebook order (one chart per section)
NAMES = ["top15_games", "player_concentration", "free_vs_paid", "players_by_genre", "playing_with_friends",
         "steam_deck_rating", "players_after_launch", "sales_discount_depth", "top10_overall_score"]
MAIN = {"playing_with_friends", "players_after_launch", "sales_discount_depth"}

def main():
    imgs = [o["data"]["image/png"] for c in json.loads(NB.read_text())["cells"] if c["cell_type"] == "code"
            for o in c.get("outputs", []) if "image/png" in o.get("data", {})]
    assert len(imgs) == len(NAMES), f"expected {len(NAMES)} charts, found {len(imgs)}"
    for name, b64 in zip(NAMES, imgs):
        d = ROOT.parent / "images" if name in MAIN else ROOT / "figures"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.png").write_bytes(base64.b64decode(b64))
        print("wrote", d / f"{name}.png")

if __name__ == "__main__":
    main()
