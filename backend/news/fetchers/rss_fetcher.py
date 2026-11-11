"""
news/fetchers/rss_fetcher.py

Universal RSS 2.0 and Atom 1.0 feed fetcher.
Uses standard library xml.etree.ElementTree and urllib with custom User-Agent,
handling namespaces, CDATA, and varied timestamp formats.
"""

from __future__ import annotations

import email.utils
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, List, Optional

from core.fetcher.base import BaseFetcher, FetchedItem, FetchError

logger = logging.getLogger(__name__)


class RSSNewsFetcher(BaseFetcher):
    """
    Fetches articles from RSS 2.0 or Atom feeds.
    Complies with Rule 24-27 (Rate limiting, canonical FetchedItem structure).
    """

    def __init__(self, feed_url: str, source_name: str = "RSS Feed") -> None:
        self.feed_url = feed_url
        self.source_name = source_name

    def fetch_new_items(self, since: Optional[datetime] = None) -> List[FetchedItem]:
        """Fetches and parses feed items published after `since`."""
        if not self.feed_url:
            return []

        try:
            req = urllib.request.Request(
                self.feed_url,
                headers={
                    "User-Agent": "BodhResearchBot/1.0 (+https://bodh.ai; research aggregator)",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                },
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                content = response.read()
        except Exception as e:
            logger.warning(f"Failed to fetch RSS from {self.feed_url}: {e}")
            return []

        return self.parse_feed_content(content, since=since)

    def parse_feed_content(
        self, xml_bytes: bytes, since: Optional[datetime] = None
    ) -> List[FetchedItem]:
        """Parses XML bytes (RSS 2.0 or Atom 1.0) into a list of FetchedItem."""
        items: List[FetchedItem] = []
        try:
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            logger.warning(f"XML parse error for {self.feed_url}: {e}")
            return []

        # Case A: Atom Feed (<feed xmlns="http://www.w3.org/2005/Atom">)
        # Strip namespaces for robust tag matching
        tag = root.tag.lower()
        if "feed" in tag:
            for entry in root.findall("{*}entry"):
                item = self._parse_atom_entry(entry)
                if item:
                    if since is None or item.published_at > since:
                        items.append(item)
            return items

        # Case B: RSS 2.0 (<rss><channel><item>...</item></channel></rss>)
        channel = root.find("channel")
        if channel is not None:
            for node in channel.findall("item"):
                item = self._parse_rss_item(node)
                if item:
                    if since is None or item.published_at > since:
                        items.append(item)
            return items

        # Fallback search for any <item> or <entry>
        for node in root.iter():
            local_tag = node.tag.split("}")[-1].lower()
            if local_tag == "item":
                item = self._parse_rss_item(node)
                if item and (since is None or item.published_at > since):
                    items.append(item)
            elif local_tag == "entry":
                item = self._parse_atom_entry(node)
                if item and (since is None or item.published_at > since):
                    items.append(item)

        return items

    def _parse_rss_item(self, node: ET.Element) -> Optional[FetchedItem]:
        """Extracts FetchedItem from an RSS <item> tag."""
        title = self._get_text(node, ["title"])
        link = self._get_text(node, ["link", "guid"])
        guid = self._get_text(node, ["guid", "link"]) or link
        desc = self._get_text(node, ["description", "summary", "content:encoded"])
        pub_str = self._get_text(node, ["pubDate", "pubdate", "dc:date"])
        author = self._get_text(node, ["author", "dc:creator"])

        if not title or not link:
            return None

        pub_dt = self._parse_timestamp(pub_str)
        return FetchedItem(
            external_id=guid or link,
            title=title.strip(),
            url=link.strip(),
            published_at=pub_dt,
            abstract=desc.strip()[:1000] if desc else "",
            full_text=desc.strip(),
            authors=[author.strip()] if author else [],
            raw_metadata={"source_name": self.source_name, "feed_url": self.feed_url},
        )

    def _parse_atom_entry(self, node: ET.Element) -> Optional[FetchedItem]:
        """Extracts FetchedItem from an Atom <entry> tag."""
        title = self._get_text(node, ["{*}title", "title"])
        id_str = self._get_text(node, ["{*}id", "id"])
        
        # Link in Atom is typically <link href="..." />
        link = ""
        for link_node in node.findall("{*}link"):
            href = link_node.attrib.get("href")
            rel = link_node.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                link = href
                break
        if not link:
            link = self._get_text(node, ["{*}link", "link"]) or id_str

        summary = self._get_text(node, ["{*}summary", "summary", "{*}content", "content"])
        pub_str = self._get_text(node, ["{*}published", "published", "{*}updated", "updated"])
        author = self._get_text(node, ["{*}author/{*}name", "author/name"])

        if not title or not link:
            return None

        pub_dt = self._parse_timestamp(pub_str)
        return FetchedItem(
            external_id=id_str or link,
            title=title.strip(),
            url=link.strip(),
            published_at=pub_dt,
            abstract=summary.strip()[:1000] if summary else "",
            full_text=summary.strip(),
            authors=[author.strip()] if author else [],
            raw_metadata={"source_name": self.source_name, "feed_url": self.feed_url},
        )

    def _get_text(self, node: ET.Element, paths: List[str]) -> str:
        for p in paths:
            child = node.find(p)
            if child is not None and child.text:
                return child.text
        return ""

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parses RFC 822 or ISO 8601 timestamps, defaulting to now() UTC."""
        if not ts_str:
            return datetime.now(timezone.utc)

        ts_str = ts_str.strip()
        # 1. Try RFC 822 (e.g. 'Tue, 10 Nov 2026 14:00:00 GMT')
        try:
            parsed_tuple = email.utils.parsedate_to_datetime(ts_str)
            if parsed_tuple:
                return (
                    parsed_tuple
                    if parsed_tuple.tzinfo
                    else parsed_tuple.replace(tzinfo=timezone.utc)
                )
        except Exception:
            pass

        # 2. Try ISO 8601 (e.g. '2026-11-10T14:00:00Z')
        clean_iso = ts_str.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(clean_iso)
        except Exception:
            pass

        return datetime.now(timezone.utc)

