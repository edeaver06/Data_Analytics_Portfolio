"""Polite HTTP: per-host minimum spacing, retries with exponential backoff + jitter, honors Retry-After."""
from __future__ import annotations

import random
import threading
import time

import requests

# Longest we will ever sleep between retries, even if the server asks for more via Retry-After.
MAX_BACKOFF = 30.0


class Redirected(Exception):
    """Raised when a call that should return JSON was redirected (e.g. Steam bouncing us to its homepage)."""

USER_AGENT = "steam-pulse/0.1 (portfolio data pipeline; low-rate, cached)"
# minimum seconds between requests per host (Steam store appdetails ~200 req / 5 min; SteamSpy 1 req/s, 'all' 1/min)
MIN_INTERVAL = {
    "api.steampowered.com": 0.12,
    "store.steampowered.com": 1.6,
    "steamspy.com": 1.1,
}


class PoliteSession:
    def __init__(self, max_retries: int = 5, timeout: float = 20.0):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self.max_retries, self.timeout = max_retries, timeout
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _wait(self, host: str) -> None:
        gap = MIN_INTERVAL.get(host, 1.0)
        with self._lock:
            now = time.monotonic()
            nxt = max(now, self._last.get(host, 0) + gap)
            self._last[host] = nxt
        if nxt > now:
            time.sleep(nxt - now)

    def get_json(self, url: str, params: dict | None = None, follow_redirects: bool = True,
                 raise_on_redirect: bool = False):
        """Fetch JSON with polite retries.

        follow_redirects=False: a 3xx answer is not followed. A redirect (or a 200 that is HTML instead of
        JSON) means the endpoint is refusing us, so we give up at once instead of retrying.
        With raise_on_redirect=True a redirect raises Redirected so the caller can count them.
        """
        host = url.split("/")[2]
        for attempt in range(self.max_retries + 1):
            self._wait(host)
            try:
                r = self.s.get(url, params=params, timeout=self.timeout, allow_redirects=follow_redirects)
            except requests.RequestException:
                r = None
            if r is not None and not follow_redirects and (300 <= r.status_code < 400 or r.history):
                if raise_on_redirect:
                    raise Redirected(r.headers.get("Location", ""))
                return None  # redirected: not retryable
            if r is not None and r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    if not follow_redirects:
                        return None  # HTML page where JSON was expected: retrying will not help
                    # otherwise: HTML error page etc. -> retry
            if r is not None and r.status_code in (400, 403, 404):
                return None  # not retryable (403/404 are normal for delisted apps)
            if attempt == self.max_retries:
                return None
            retry_after = r.headers.get("Retry-After") if r is not None else None
            delay = float(retry_after) if retry_after and retry_after.isdigit() else min(60, 2 ** attempt)
            if r is not None and r.status_code == 429:
                delay = max(delay, 30)
            # never sleep longer than MAX_BACKOFF, whatever the server says
            time.sleep(min(delay, MAX_BACKOFF) + random.uniform(0, 1))
        return None
