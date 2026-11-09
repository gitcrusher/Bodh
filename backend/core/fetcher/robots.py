"""
robots.txt handler — fetchers check this before every scrape.

Rules (rules.md rule 25): Scrapers obey robots.txt and crawl-delay.
Hard stop: never scrape if disallowed.
"""

from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
_USER_AGENT = "AINewsBot/1.0 (research aggregator; contact: admin@localhost)"


def is_allowed(url: str, user_agent: str = _USER_AGENT) -> bool:
    """
    Return True if robots.txt permits fetching this URL.
    Caches the parsed robots.txt per host.
    Returns True if robots.txt cannot be fetched (fail-open for API sources;
    scrapers should treat fetch failure as uncertain and log a warning).
    """
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"

    if host not in _robots_cache:
        robots_url = f"{host}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            _robots_cache[host] = rp
        except Exception as exc:
            logger.warning("Could not fetch robots.txt for %s: %s", host, exc)
            return True  # Fail-open; caller should log a warning

    rp = _robots_cache[host]
    allowed = rp.can_fetch(user_agent, url)
    if not allowed:
        logger.warning("robots.txt disallows fetching %s for agent %r", url, user_agent)
    return allowed


def crawl_delay(url: str, user_agent: str = _USER_AGENT) -> float | None:
    """Return the crawl-delay for this host/agent, or None if not specified."""
    parsed = urlparse(url)
    host = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(host)
    if rp is None:
        return None
    return rp.crawl_delay(user_agent)


def clear_cache() -> None:
    """Clear cached robots.txt data (for tests)."""
    _robots_cache.clear()
