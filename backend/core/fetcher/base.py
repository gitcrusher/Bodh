"""
Fetcher base interfaces.

Rules (rules.md rules 24-27, design doc 9, 14.6):
  - API fetchers: prefer over scrapers; no key needed for arXiv.
  - Scraper fetchers: schema-validated output; quarantine after repeated failures.
  - One central rate limiter.
  - Hard stops: login-walled, paywalled, CAPTCHA, robots.txt disallowed.
"""

from __future__ import annotations

import abc
import dataclasses
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical fetch result
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class FetchedItem:
    """
    The standard shape that every fetcher produces.
    This maps 1:1 to raw_items columns (minus the DB id/status).
    """

    external_id: str          # Source-assigned unique identifier (e.g. arXiv ID)
    title: str
    url: str                  # Canonical source URL
    published_at: datetime
    abstract: str             # Abstract / summary text (required; may be empty string)
    full_text: str = ""       # Full text — populated only by the full-text fetch step
    authors: list[str] = dataclasses.field(default_factory=list)
    raw_metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


class FetchError(Exception):
    """Raised when a fetcher cannot retrieve an item."""

    def __init__(self, message: str, quarantine: bool = False) -> None:
        super().__init__(message)
        self.quarantine = quarantine  # True = repeated failure; disable source


# ---------------------------------------------------------------------------
# Base fetcher
# ---------------------------------------------------------------------------
class BaseFetcher(abc.ABC):
    """
    Abstract base for all fetchers (API and scraper).

    Every subclass must implement fetch_new_items().
    The framework calls it and handles:
      - Rate limiting (via the central limiter)
      - robots.txt checking (scrapers only — API fetchers skip this)
      - Schema validation on the output
      - Quarantine tracking
    """

    #: Human-readable name, used for logging and the sources table
    source_name: str = ""
    #: True = API fetcher (preferred); False = HTML scraper
    is_api: bool = True
    #: Hostname for the rate limiter
    host: str = ""
    #: Seconds between requests to this host
    rate_limit_s: float = 3.0

    @abc.abstractmethod
    def fetch_new_items(self, since: datetime) -> list[FetchedItem]:
        """
        Fetch items published/updated after `since`.
        Must return a list of FetchedItem; never raise unless truly unrecoverable.
        On partial failure, return what was retrieved and log the rest.
        """
        ...

    def fetch_full_text(self, item: FetchedItem) -> str:
        """
        Fetch full text for a single item.
        Default implementation returns the abstract (sufficient for some sources).
        Override for sources where full text is separately retrievable.
        Returns empty string if unavailable — never raises.
        """
        return item.abstract

    def validate_item(self, item: FetchedItem) -> bool:
        """
        Schema validation for a fetched item.
        Returns True if the item is valid; False = quarantine candidate.
        Scrapers override this with HTML-structure-aware checks.
        """
        return bool(item.external_id and item.title and item.url and item.published_at)
