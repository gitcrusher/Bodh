"""
research/retention.py

Registers retention handlers for all research tables that grow unboundedly.
Called from ResearchConfig.ready().

Rules addressed:
  Rule 37 — clear transient content after grace period
  Rule 38 — every growing table must have a registered retention rule

Handlers registered:
  clear_raw_content       — null raw_content after grace_period_expires_at
  clear_raw_embeddings    — null raw_item embeddings after 90 days
  evict_unused_chat_chunks — evict paper_chat_chunks unused for 30 days
                             (table created in Step 3; handler is a no-op until then)
"""

import logging
from datetime import timedelta

from django.utils import timezone

from core.retention.runner import register_handler

logger = logging.getLogger(__name__)


def _clear_raw_content(rule):
    """
    Null out raw_content on RawItem rows whose grace period has expired.
    The identity fields (external_id, url, published_at) are kept forever.
    """
    from research.models import RawItem  # local import — avoids circular at module level

    now = timezone.now()
    qs = RawItem.objects.filter(
        grace_period_expires_at__lte=now,
        raw_content__isnull=False,
    )
    count = qs.update(raw_content=None)
    if count:
        logger.info("research.retention: cleared raw_content on %d RawItem rows", count)


def _clear_raw_embeddings(rule):
    """
    Null out embeddings on RawItem rows older than raw_embedding_retention_days.
    Near-duplicate coverage of the same paper appears within days to weeks,
    so embeddings don't need to live forever (system design §6 note).
    """
    from django.conf import settings

    from research.models import RawItem

    retention_days = getattr(settings, "RAW_EMBEDDING_RETENTION_DAYS", 90)
    cutoff = timezone.now() - timedelta(days=retention_days)
    qs = RawItem.objects.filter(
        fetched_at__lt=cutoff,
        embedding__isnull=False,
    )
    count = qs.update(embedding=None)
    if count:
        logger.info(
            "research.retention: cleared embeddings on %d old RawItem rows", count
        )


def _evict_unused_chat_chunks(rule):
    """
    Evict paper_chat_chunks unused for > 30 days.
    Table created in Step 3; this handler is a no-op until then.
    """
    try:
        from research.models import PaperChatChunk  # noqa: F401 — Step 3 model
    except ImportError:
        return  # table doesn't exist yet

    from django.conf import settings

    evict_days = getattr(settings, "CHAT_CHUNK_EVICT_DAYS", 30)
    cutoff = timezone.now() - timedelta(days=evict_days)
    count = PaperChatChunk.objects.filter(last_accessed_at__lt=cutoff).delete()[0]
    if count:
        logger.info(
            "research.retention: evicted %d unused PaperChatChunk rows", count
        )


def register_research_retention():
    """Register all research retention handlers with the core runner."""
    from core.models import RetentionRule

    _rules = [
        {
            "key": "research.clear_raw_content",
            "description": "Null raw_content after grace_period_expires_at",
            "handler": _clear_raw_content,
        },
        {
            "key": "research.clear_raw_embeddings",
            "description": "Null raw_item embeddings after RAW_EMBEDDING_RETENTION_DAYS days",
            "handler": _clear_raw_embeddings,
        },
        {
            "key": "research.evict_chat_chunks",
            "description": "Evict paper_chat_chunks unused for CHAT_CHUNK_EVICT_DAYS days",
            "handler": _evict_unused_chat_chunks,
        },
    ]

    for r in _rules:
        register_handler(r["key"], r["handler"])
        # Ensure the DB row exists (idempotent).
        RetentionRule.objects.get_or_create(
            rule_key=r["key"],
            defaults={"description": r["description"], "active": True},
        )
