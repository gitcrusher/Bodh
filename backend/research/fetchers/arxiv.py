"""
research/fetchers/arxiv.py

arXiv API fetcher — incremental, date-range queried, rate-limited.

Design (system design §9):
  - Uses arXiv Atom API (no key required).
  - Queries only categories cs.AI, cs.LG, cs.CL.
  - Fetches only papers published/updated since `source.last_successful_run_at`.
    On first run (last_successful_run_at is None): fetches the last 7 days.
  - Rate limit: 1 request / ARXIV_RATE_LIMIT_SECONDS (default 3 s).
  - Respects robots.txt (checked once per host, cached 24 h).
  - Paginates until all matching papers for the date range are fetched,
    bounded by source.daily_request_cap.
  - Returns a list of raw item dicts, not ORM objects.
    The pipeline node persists them.

arXiv Atom API reference:
  https://info.arxiv.org/help/api/index.html
"""

import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from django.conf import settings

from core.fetcher import robots as _robots_mod
from core.fetcher.rate_limiter import rate_limiter as _global_rate_limiter

logger = logging.getLogger(__name__)

# arXiv Atom XML namespaces
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

_BATCH_SIZE = 100          # max_results per API call
_USER_AGENT = "AINewsApp/1.0 (research aggregator; contact: admin@example.com)"

_ARXIV_HOST = "export.arxiv.org"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def fetch_arxiv_papers(
    source,  # research.models.Source ORM instance
    *,
    since: Optional[datetime] = None,
    dry_run: bool = False,
) -> list[dict]:
    """
    Fetch arXiv papers for `source` published after `since`.

    Args:
        source:   Source ORM row (fetch_method='api', name contains 'arXiv').
        since:    Lower bound datetime (UTC). Defaults to source.last_successful_run_at
                  or 7 days ago if None.
        dry_run:  If True, returns an empty list without making any HTTP calls
                  (useful in tests without needing to mock HTTP).

    Returns:
        List of raw-item dicts ready to be persisted as RawItem rows::

            {
                "external_id": "2310.12345",
                "title": "Attention Is All You Need",
                "url": "https://arxiv.org/abs/2310.12345",
                "published_at": <datetime>,
                "raw_content": "<abstract text>",
                "content_hash": "<sha256>",
                "authors": ["Author One", "Author Two"],
            }
    """
    if dry_run:
        return []

    base_url = getattr(settings, "ARXIV_BASE_URL", "https://export.arxiv.org")
    categories = getattr(settings, "ARXIV_CATEGORIES", ["cs.AI", "cs.LG", "cs.CL"])
    daily_cap = source.daily_request_cap

    # --- Date range ---
    if since is None:
        since = source.last_successful_run_at
    if since is None:
        since = datetime.now(tz=timezone.utc) - timedelta(days=7)

    # arXiv date format: YYYYMMDDHHMMSS
    since_str = since.strftime("%Y%m%d%H%M%S")
    until_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")

    # Build the search query: category filter + date range
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    date_query = f"submittedDate:[{since_str} TO {until_str}]"
    search_query = f"({cat_query}) AND {date_query}"

    # --- robots.txt check ---
    api_url = f"{base_url}/api/query"
    if not _robots_mod.is_allowed(api_url, user_agent=_USER_AGENT):
        logger.warning("arXiv fetcher: robots.txt disallows %s — skipping", api_url)
        return []

    rate_interval = getattr(settings, "ARXIV_RATE_LIMIT_SECONDS", 3.0)
    results: list[dict] = []
    start = 0
    requests_made = 0

    with httpx.Client(
        headers={"User-Agent": _USER_AGENT},
        timeout=30.0,
    ) as client:
        while requests_made < daily_cap:
            _global_rate_limiter.wait(_ARXIV_HOST, min_interval_s=rate_interval)

            params = {
                "search_query": search_query,
                "start": start,
                "max_results": _BATCH_SIZE,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }

            try:
                resp = client.get(api_url, params=params)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    retry_after = int(exc.response.headers.get("Retry-After", 60))
                    logger.warning(
                        "arXiv fetcher: 429 rate limited — sleeping %ds", retry_after
                    )
                    time.sleep(retry_after)
                    continue
                logger.error("arXiv fetcher: HTTP %d — %s", exc.response.status_code, exc)
                break
            except httpx.RequestError as exc:
                logger.error("arXiv fetcher: request error — %s", exc)
                break

            requests_made += 1
            batch = _parse_atom(resp.text, since=since)

            if not batch:
                # No more results in this date range
                break

            results.extend(batch)

            # Pagination: if we got fewer than _BATCH_SIZE, we've reached the end
            if len(batch) < _BATCH_SIZE:
                break

            start += _BATCH_SIZE

    logger.info(
        "arXiv fetcher: fetched %d papers in %d requests (source=%s)",
        len(results),
        requests_made,
        source.name,
    )
    return results


# ---------------------------------------------------------------------------
# Atom XML parsing
# ---------------------------------------------------------------------------


def _parse_atom(xml_text: str, *, since: datetime) -> list[dict]:
    """
    Parse arXiv Atom XML response into a list of raw-item dicts.
    Filters out entries published before `since`.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("arXiv fetcher: XML parse error — %s", exc)
        return []

    entries = root.findall("atom:entry", _NS)
    results = []

    for entry in entries:
        try:
            item = _parse_entry(entry, since=since)
            if item is not None:
                results.append(item)
        except Exception as exc:  # noqa: BLE001
            logger.warning("arXiv fetcher: failed to parse entry — %s", exc)

    return results


def _parse_entry(entry: ET.Element, *, since: datetime) -> Optional[dict]:
    """Parse a single Atom <entry> element. Returns None if the entry should be skipped."""

    # --- arXiv ID ---
    id_el = entry.find("atom:id", _NS)
    if id_el is None or not id_el.text:
        return None
    raw_id = id_el.text.strip()
    # Normalise: "http://arxiv.org/abs/2310.12345v1" → "2310.12345"
    arxiv_id = raw_id.split("/abs/")[-1].split("v")[0].strip()

    # --- Published date ---
    pub_el = entry.find("atom:published", _NS)
    if pub_el is None or not pub_el.text:
        return None
    try:
        published_at = datetime.fromisoformat(pub_el.text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None

    # Filter by date range
    if published_at <= since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since:
        return None

    # --- Title ---
    title_el = entry.find("atom:title", _NS)
    title = (title_el.text or "").strip() if title_el is not None else ""
    if not title:
        return None

    # --- Abstract (summary) ---
    summary_el = entry.find("atom:summary", _NS)
    abstract = (summary_el.text or "").strip() if summary_el is not None else ""

    # --- Source URL ---
    url = f"https://arxiv.org/abs/{arxiv_id}"

    # --- Authors ---
    authors = []
    for author_el in entry.findall("atom:author", _NS):
        name_el = author_el.find("atom:name", _NS)
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    # --- Content hash (title + abstract, stable across re-fetches) ---
    content = f"{title}\n{abstract}"
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    return {
        "external_id": arxiv_id,
        "title": title,
        "url": url,
        "published_at": published_at,
        "raw_content": abstract,  # abstract only; full text fetched on demand
        "content_hash": content_hash,
        "authors": authors,
    }
