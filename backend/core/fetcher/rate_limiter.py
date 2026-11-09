"""
Central rate limiter for all fetchers.

Rules (rules.md rule 24-25, design doc 14.6):
  - One central rate limiter driven by sources.rate_limit_policy.
  - arXiv: one request per 3 seconds, one connection.
  - Scrapers: 3-5 seconds per host.

This is a synchronous token-bucket limiter keyed by host.
For the single-job scheduler (no Celery), a module-level instance is fine.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Per-host token-bucket rate limiter.

    Usage:
        limiter = RateLimiter()
        limiter.wait("export.arxiv.org", min_interval_s=3.0)
        # ... make the request
    """

    def __init__(self) -> None:
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def wait(self, host: str, min_interval_s: float) -> None:
        """
        Block until at least min_interval_s has elapsed since the last
        request to this host. Updates the timestamp after waiting.
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request[host]
            if elapsed < min_interval_s:
                sleep_s = min_interval_s - elapsed
                logger.debug(
                    "Rate limiter: sleeping %.2fs for host=%s", sleep_s, host
                )
                time.sleep(sleep_s)
            self._last_request[host] = time.monotonic()

    def reset(self, host: str | None = None) -> None:
        """Reset timestamps (for tests)."""
        with self._lock:
            if host:
                self._last_request.pop(host, None)
            else:
                self._last_request.clear()


# Module-level singleton — shared by all fetchers
rate_limiter = RateLimiter()
