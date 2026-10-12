from steam_pulse.http import MIN_INTERVAL


def test_rate_limits_are_conservative():
    assert MIN_INTERVAL["store.steampowered.com"] >= 1.5   # <= 200 req / 5 min
    assert MIN_INTERVAL["steamspy.com"] >= 1.0


def test_oldest_first_prefers_never_fetched():
    from datetime import datetime, timedelta, timezone
    from steam_pulse.ingest import _oldest_first
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    seen = {1: now - timedelta(days=9), 2: now - timedelta(days=1), 3: now - timedelta(days=30)}
    assert _oldest_first([1, 2, 3, 4], seen, now, timedelta(days=7), 2) == [4, 3]
