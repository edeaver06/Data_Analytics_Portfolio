"""Headless smoke test of every Streamlit page on the bundled extract."""
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "app/streamlit_app.py"
st_testing = pytest.importorskip("streamlit.testing.v1")
PAGES = ["Overview", "Disruptions & repeats by system", "Hours between reports by model", "Reporting lag",
         "Top parts", "Engine life (NASA C-MAPSS)", "Simulated fleet (demo data)"]


@pytest.mark.skipif(not (APP.parent / "data/discrepancy.parquet").exists(), reason="app extract not built")
@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = st_testing.AppTest.from_file(str(APP), default_timeout=60).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception
    assert at.title[0].value


def test_app_excludes_gao():
    text = APP.read_text().lower()
    assert "gao" not in text and "mc_rate_benchmark" not in text
