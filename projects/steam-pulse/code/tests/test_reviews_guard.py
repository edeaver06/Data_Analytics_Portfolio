"""Reviews must never stall the snapshot: redirects/HTML are skipped, time budget and circuit breaker apply."""
from datetime import datetime, timezone
from unittest import mock

import pandas as pd
import pytest

from steam_pulse import http as H
from steam_pulse import ingest


class Resp:
    def __init__(self, status=200, body=None, text="", headers=None):
        self.status_code, self._body, self.text = status, body, text
        self.headers, self.history = headers or {}, []

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


@pytest.fixture
def sess(monkeypatch):
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    s = H.PoliteSession()
    s._wait = lambda host: None
    return s


def test_redirect_is_not_retried(sess):
    sess.s.get = mock.Mock(return_value=Resp(302, headers={"Location": "https://store.steampowered.com/"}))
    assert sess.get_json("https://store.steampowered.com/appreviews/1", follow_redirects=False) is None
    assert sess.s.get.call_count == 1
    assert sess.s.get.call_args.kwargs["allow_redirects"] is False
    with pytest.raises(H.Redirected):
        sess.get_json("https://store.steampowered.com/appreviews/1", follow_redirects=False, raise_on_redirect=True)


def test_html_body_is_not_retried(sess):
    sess.s.get = mock.Mock(return_value=Resp(200, body=None, text="<html>store</html>"))
    assert sess.get_json("https://store.steampowered.com/appreviews/1", follow_redirects=False) is None
    assert sess.s.get.call_count == 1


def test_retry_after_is_capped(monkeypatch):
    slept = []
    monkeypatch.setattr(H.time, "sleep", slept.append)
    s = H.PoliteSession(max_retries=1)
    s._wait = lambda host: None
    s.s.get = mock.Mock(return_value=Resp(503, headers={"Retry-After": "3600"}))
    assert s.get_json("https://api.steampowered.com/x") is None
    assert max(slept) <= H.MAX_BACKOFF + 1


def _run(monkeypatch, tmp_path, get_json, n=20, **kw):
    monkeypatch.setattr(ingest, "RAW", tmp_path)
    monkeypatch.setattr(ingest, "_last_seen_parquet", lambda *a, **k: {})
    http = mock.Mock()
    http.get_json.side_effect = get_json
    ts = datetime(2026, 10, 23, tzinfo=timezone.utc)
    ok = ingest.refresh_reviews(http, list(range(1, n + 1)), ts, budget=n, **kw)
    files = list(tmp_path.glob("reviews/*/*.parquet"))
    return ok, http, (pd.read_parquet(files[0]) if files else None)


GOOD = {"success": 1, "query_summary": {"total_reviews": 10, "total_positive": 8, "total_negative": 2,
                                        "review_score": 7, "review_score_desc": "Positive"}}


def test_circuit_breaker_skips_whole_run(monkeypatch, tmp_path, capsys):
    def redirect(*a, **k):
        raise H.Redirected("https://store.steampowered.com/")
    ok, http, df = _run(monkeypatch, tmp_path, redirect, breaker_n=5)
    assert ok == 0 and http.get_json.call_count == 5
    assert len(df) == 5 and not df.ok.any()
    assert "skipping reviews for this run" in capsys.readouterr().err


def test_breaker_not_tripped_by_mixed_results(monkeypatch, tmp_path):
    calls = iter(range(100))
    def mixed(*a, **k):
        if next(calls) == 2:
            return GOOD
        raise H.Redirected("")
    ok, http, df = _run(monkeypatch, tmp_path, mixed, n=8, breaker_n=5)
    assert ok == 1 and http.get_json.call_count == 8 and len(df) == 8


def test_time_budget(monkeypatch, tmp_path, capsys):
    clock = iter(range(0, 10_000, 100))  # each monotonic() call advances 100 s
    monkeypatch.setattr(ingest.time, "monotonic", lambda: next(clock))
    ok, http, df = _run(monkeypatch, tmp_path, lambda *a, **k: GOOD, time_budget_s=250)
    assert http.get_json.call_count < 20 and ok == http.get_json.call_count
    assert "time budget" in capsys.readouterr().err
