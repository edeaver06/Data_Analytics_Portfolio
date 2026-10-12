"""Parity: marts.mart_game_scores must reproduce analysis/src/best_score.py on the current DB.
Skipped when the DB or the analysis env (scipy) is absent, e.g. in a clean checkout."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "steam_pulse.duckdb"
pytestmark = pytest.mark.skipif(not DB.exists(), reason="no local DuckDB (run ./scripts/snapshot.sh)")


def test_analysis_uses_dbt_seed_exclusion_list():
    import pandas as pd
    seed = ROOT / "dbt" / "seeds" / "software_exclusions.csv"
    src = (ROOT / "analysis" / "src" / "best_score.py").read_text()
    assert '"dbt" / "seeds" / "software_exclusions.csv"' in src
    assert len(pd.read_csv(seed).appid) > 0


def test_mart_matches_best_score():
    pytest.importorskip("scipy")
    import duckdb
    import pandas as pd
    sys.path.insert(0, str(ROOT / "analysis" / "src"))
    import best_score as bs
    import steam_analysis as sa

    c = sa.connect(DB)
    g, sw = bs.filter_software(
        c.sql("select * from a_game where player_count is not null and positive+negative>0").df())
    ref = bs.score(g).set_index("appid").score
    c.close()

    m = duckdb.connect(str(DB), read_only=True).execute(
        "select appid, composite_score, is_software from marts.mart_game_scores").df().set_index("appid")
    mart = m.composite_score.dropna()
    assert set(mart.index) == set(ref.index), "scored universe differs"
    assert set(m.index[m.is_software]) >= set(sw.appid), "software flags differ"
    diff = (mart - ref.loc[mart.index]).abs().max()
    assert diff < 1e-9, f"max abs score diff {diff}"
