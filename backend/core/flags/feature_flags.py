"""
Feature flag mechanism.

Modules ship dormant (enabled=False in the DB) and are enabled after
their evals pass (phases.md gate, rule 31).

Lookup order:
  1. DB row (FeatureFlag model) — authoritative at runtime
  2. settings.FEATURE_FLAGS_DEFAULT — bootstrap when no DB row exists
  3. Default: False (dormant)

Uses a short in-process cache to avoid a DB hit on every request.
"""

from __future__ import annotations

import logging
import time
from threading import Lock

from django.conf import settings

logger = logging.getLogger(__name__)

# In-process TTL cache: avoid a DB round-trip on every flag check
_CACHE_TTL_S = 60.0
_cache: dict[str, tuple[bool, float]] = {}
_lock = Lock()


def is_enabled(name: str) -> bool:
    """
    Return True if the named feature flag is enabled.
    Thread-safe; cached for 60 seconds.
    """
    now = time.monotonic()

    with _lock:
        if name in _cache:
            value, expires = _cache[name]
            if now < expires:
                return value

    # Cache miss or expired — query DB
    value = _lookup(name)

    with _lock:
        _cache[name] = (value, now + _CACHE_TTL_S)

    return value


def _lookup(name: str) -> bool:
    try:
        from core.models import FeatureFlag  # lazy

        flag = FeatureFlag.objects.filter(name=name).first()
        if flag is not None:
            return flag.enabled
    except Exception as exc:
        # DB not ready (e.g. during migrations) — fall through to defaults
        logger.debug("Feature flag DB lookup failed for %r: %s", name, exc)

    # Fall back to settings defaults
    defaults = getattr(settings, "FEATURE_FLAGS_DEFAULT", {})
    return defaults.get(name, False)


def enable(name: str) -> None:
    """Enable a flag in the DB (creates if not exists). Clears cache."""
    from core.models import FeatureFlag  # lazy

    FeatureFlag.objects.update_or_create(name=name, defaults={"enabled": True})
    with _lock:
        _cache.pop(name, None)


def disable(name: str) -> None:
    """Disable a flag in the DB. Clears cache."""
    from core.models import FeatureFlag  # lazy

    FeatureFlag.objects.update_or_create(name=name, defaults={"enabled": False})
    with _lock:
        _cache.pop(name, None)


def clear_cache() -> None:
    """Invalidate the entire in-process cache (useful in tests)."""
    with _lock:
        _cache.clear()
