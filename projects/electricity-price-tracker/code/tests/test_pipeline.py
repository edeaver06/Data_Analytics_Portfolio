"""Tests run offline: the API is replaced by a fake, so no key or network is needed."""
import pandas as pd
import pytest

import clean
import fetch_eia
import load_sqlite
import quality_checks
from states import STATES


def raw_row(period="2026-07", state="SD", sector="RES", price="15.37", customers="400000"):
    return {"period": period, "stateid": state, "stateDescription": STATES[state],
            "sectorid": sector, "sectorName": sector.lower(), "price": price,
            "sales": "100.5", "revenue": "15.4", "customers": customers,
            "price-units": "cents per kilowatt-hour", "sales-units": "million kilowatt hours",
            "revenue-units": "million dollars", "customers-units": "number of customers"}


class FakeResp:
    def __init__(self, body): self.body = body
    def raise_for_status(self): pass
    def json(self): return {"response": self.body}


def fake_api(total_rows, reported_total=None):
    """A fake requests.get that serves `total_rows` rows in pages."""
    data = [{"i": i} for i in range(total_rows)]
    calls = []
    def get(url, params, timeout):
        p = dict(params)
        calls.append(p)
        off, ln = int(p["offset"]), int(p["length"])
        return FakeResp({"total": str(reported_total or total_rows), "data": data[off:off + ln]})
    return get, calls


def test_paging_collects_every_row():
    get, calls = fake_api(12)
    rows, total, pages = fetch_eia.fetch_all("k", get=get, page_size=5)
    assert len(rows) == total == 12 and len(pages) == 3
    assert [c["offset"] for c in calls] == [0, 5, 10]
    assert [r["i"] for r in rows] == list(range(12))   # no gaps, no repeats


def test_paging_exact_multiple_stops():
    get, calls = fake_api(10)
    rows, total, _ = fetch_eia.fetch_all("k", get=get, page_size=5)
    assert len(rows) == 10 and len(calls) == 2


def test_paging_detects_count_mismatch():
    get, _ = fake_api(7, reported_total=9)   # API claims more rows than it serves
    with pytest.raises(RuntimeError, match="mismatch"):
        fetch_eia.fetch_all("k", get=get, page_size=5)


def test_params_cover_all_states_and_sectors():
    p = fetch_eia.build_params("k", 0)
    assert sum(1 for k, _ in p if k == "facets[stateid][]") == 51
    assert {v for k, v in p if k == "facets[sectorid][]"} == {"RES", "COM", "ALL"}


def test_redact_hides_key():
    assert "SECRET" not in fetch_eia.redact("https://x/?api_key=SECRET&frequency=monthly")


def test_clean_types_missing_and_pre2008_customers():
    raw = pd.DataFrame([raw_row(), raw_row(period="2005-03", customers="0"),
                        raw_row(period="2016-08", state="AK", price=None, customers=None),
                        raw_row()])  # last one is a duplicate
    df = clean.clean(raw)
    assert len(df) == 3
    assert df["month"].dtype.kind == "M"
    assert df["price_cents_per_kwh"].dtype == float
    old = df[df.month == "2005-03-01"].iloc[0]
    assert pd.isna(old.customers) and old.customers_not_collected == 1
    ak = df[df.state == "AK"].iloc[0]
    assert pd.isna(ak.price_cents_per_kwh) and ak.any_value_missing == 1   # withheld stays blank


def test_clean_rejects_unit_change():
    r = raw_row(); r["price-units"] = "dollars per kilowatt-hour"
    with pytest.raises(ValueError):
        clean.clean(pd.DataFrame([r]))


def test_region_seed_covers_all_51():
    regions = clean.load_regions()
    assert set(regions.state) == set(STATES) and len(regions) == 51
    assert regions.primary_region.ne("").all()
    multi = regions[regions.multi_region == "1"]
    assert multi.other_regions.ne("").all()     # split states name their other regions


def test_sqlite_load_and_checks(tmp_path):
    rows = [raw_row(state=s, sector=sec) for s in STATES for sec in ("RES", "COM", "ALL")]
    df = clean.clean(pd.DataFrame(rows))
    db = tmp_path / "t.db"
    counts = load_sqlite.load(df, clean.load_regions(), db_path=db)
    assert counts == {"retail_sales_monthly": 153, "state_region": 51, "v_residential_price": 51}
    results = {n: ok for n, ok, _ in quality_checks.run_checks(db, max_lag_months=1000)}
    assert all(results.values()), results
    # rerun = same counts (idempotent)
    assert load_sqlite.load(df, clean.load_regions(), db_path=db) == counts
