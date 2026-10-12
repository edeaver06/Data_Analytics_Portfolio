"""Headless smoke test: every Streamlit page renders on the bundled data without an exception."""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app/streamlit_app.py"
st_testing = pytest.importorskip("streamlit.testing.v1")
PAGES = ['Overview',
         'Strategies vs the breakeven',
         'Follow a strategy',
         'Home underdogs',
         'Are the odds honest?']


@pytest.mark.skipif(not (APP.parent / "data/strategy_by_season.csv").exists(), reason="app data not present")
@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = st_testing.AppTest.from_file(str(APP), default_timeout=120).run()
    assert list(at.sidebar.radio[0].options) == PAGES
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception
    assert at.title or at.header
