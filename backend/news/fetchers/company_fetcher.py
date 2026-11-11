"""
news/fetchers/company_fetcher.py

Dedicated company & AI research lab fetcher.
Maintains curated feeds for top frontier labs:
  - OpenAI Research & News
  - Anthropic Research & Announcements
  - Google DeepMind Blog
  - Meta AI Research
  - Mistral AI News
  - Hugging Face Blog

Enforces Rule 50: Company release posts carry `publisher_relationship="vendor_marketing"`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from core.fetcher.base import FetchedItem
from .rss_fetcher import RSSNewsFetcher

logger = logging.getLogger(__name__)


COMPANY_FEEDS: Dict[str, Dict[str, str]] = {
    "openai": {
        "name": "OpenAI Blog",
        "url": "https://openai.com/news/rss.xml",
        "website": "https://openai.com/news/",
    },
    "anthropic": {
        "name": "Anthropic Research",
        "url": "https://www.anthropic.com/news/rss.xml",
        "website": "https://www.anthropic.com/news",
    },
    "deepmind": {
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
        "website": "https://deepmind.google/discover/blog/",
    },
    "meta_ai": {
        "name": "Meta AI Research",
        "url": "https://ai.meta.com/blog/rss/",
        "website": "https://ai.meta.com/blog/",
    },
    "mistral": {
        "name": "Mistral AI News",
        "url": "https://mistral.ai/news/index.xml",
        "website": "https://mistral.ai/news/",
    },
    "huggingface": {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "website": "https://huggingface.co/blog",
    },
}


class CompanyNewsFetcher:
    """
    Fetches official blog and engineering release posts from frontier AI labs.
    """

    @classmethod
    def fetch_lab_news(
        cls, lab_key: str, since: Optional[datetime] = None
    ) -> List[FetchedItem]:
        """Fetches news from a specific AI lab."""
        info = COMPANY_FEEDS.get(lab_key)
        if not info:
            logger.warning(f"Unknown lab key: {lab_key}")
            return []

        fetcher = RSSNewsFetcher(feed_url=info["url"], source_name=info["name"])
        items = fetcher.fetch_new_items(since=since)

        # Tag vendor marketing per Rule 50
        for item in items:
            item.raw_metadata["source_tier"] = "vendor_marketing"
            item.raw_metadata["company_key"] = lab_key
            item.raw_metadata["is_developer_self_report"] = True

        return items

    @classmethod
    def fetch_all_labs(
        cls, since: Optional[datetime] = None
    ) -> Dict[str, List[FetchedItem]]:
        """Fetches from all frontier AI labs in one call."""
        results: Dict[str, List[FetchedItem]] = {}
        for key in COMPANY_FEEDS:
            try:
                results[key] = cls.fetch_lab_news(key, since=since)
            except Exception as e:
                logger.warning(f"Error fetching company lab '{key}': {e}")
                results[key] = []
        return results

