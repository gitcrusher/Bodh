"""
core/llm/byok.py

Bring-Your-Own-Key (BYOK) Resolution & Cost-Split Routing (Step 4 & Design Doc §12).

Cost Responsibility Split:
1. Shared Pipeline Work (Ingestion, Summarization, Triage):
   - Runs once per paper using owner's pooled keys via LLMRouter.
   - Cost is independent of user count.

2. Personalized Work (Level-Adaptive Deep-Dives, Paper Chat, Study Sessions):
   - Uses user's own BYOK key when configured (unlimited, zero owner cost).
   - When no BYOK key is configured: falls back to shared quota with visible daily cap (5 free calls/day).
   - Fallback Matrix (§14.1): If user's BYOK key is invalid/revoked/rate-limited,
     falls back to shared quota ONLY while under daily cap; otherwise reports key error without looping.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.models import User
from django.utils import timezone

from core.llm.providers.base import BaseProvider, LLMProviderError, LLMRequest, LLMResponse, RateLimitError
from core.llm.providers.gemini import GeminiProvider
from core.llm.providers.groq import GroqProvider
from core.llm.providers.openai import OpenAIProvider
from core.llm.router import LLMRouter, get_router
from core.models import DailyPersonalizedQuota, LLMCredential

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when user exceeds daily shared quota and has not configured a BYOK key."""

    def __init__(self, message: str, used: int = 5, limit: int = 5) -> None:
        super().__init__(message)
        self.used = used
        self.limit = limit


def get_user_byok_credential(user: User | None, provider_name: str | None = None) -> LLMCredential | None:
    """Returns active BYOK credential for user, prioritizing default or requested provider."""
    if not user or not user.is_authenticated:
        return None

    qs = LLMCredential.objects.filter(user=user)
    if provider_name:
        match = qs.filter(provider=provider_name).first()
        if match:
            return match

    # Prefer is_default=True, then newest
    return qs.order_by("-is_default", "-updated_at").first()


def create_byok_provider(credential: LLMCredential) -> BaseProvider:
    """Instantiates a provider adapter using the user's decrypted BYOK key."""
    api_key = credential.get_api_key()
    p = credential.provider.lower()

    if p == "gemini":
        return GeminiProvider(name="byok_gemini", model="gemini-3.5-flash", api_key=api_key)
    elif p == "groq":
        return GroqProvider(model="openai/gpt-oss-20b", api_key=api_key)
    elif p == "zai":
        from core.llm.providers.zai import ZAIProvider
        return ZAIProvider(name="byok_zai", model="glm-4.7-flash", api_key=api_key)
    else:
        # Default to Groq
        return GroqProvider(model="openai/gpt-oss-20b", api_key=api_key)


def get_daily_quota_status(user: User | None, session_id: str = "") -> dict[str, Any]:
    """Returns current daily quota usage and limits for personalized work."""
    today = timezone.now().date()
    has_byok = bool(get_user_byok_credential(user))

    if user and user.is_authenticated:
        quota_row = DailyPersonalizedQuota.objects.filter(user=user, date=today).first()
    elif session_id:
        quota_row = DailyPersonalizedQuota.objects.filter(session_id=session_id, date=today).first()
    else:
        quota_row = None

    used = quota_row.call_count if quota_row else 0
    limit = DailyPersonalizedQuota.DEFAULT_DAILY_CAP
    remaining = max(0, limit - used)

    return {
        "has_byok": has_byok,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "is_capped": used >= limit if not has_byok else False,
    }


def execute_personalized_task(
    request: LLMRequest,
    user: User | None = None,
    session_id: str = "",
    preferred_provider: str | None = None,
) -> LLMResponse:
    """
    Executes an LLM request for personalized work (deep-dive or chat).
    Adheres strictly to Fallback Matrix §14.1 and Step 4 rules.
    """
    credential = get_user_byok_credential(user, provider_name=preferred_provider)

    if credential:
        try:
            provider = create_byok_provider(credential)
            logger.info("Executing personalized work using BYOK provider=%s for user_id=%s", credential.provider, user.id if user else None)
            res = provider.complete(request)
            res.provider = f"byok_{credential.provider}"
            return res
        except (LLMProviderError, RateLimitError) as exc:
            logger.warning("User BYOK key failed (provider=%s): %s. Checking shared fallback quota.", credential.provider, exc)
            # Fallback Matrix §14.1: Fall back to shared quota ONLY while under daily cap
            status = get_daily_quota_status(user, session_id=session_id)
            if status["is_capped"]:
                raise LLMProviderError(
                    provider=credential.provider,
                    message=f"Your BYOK key for {credential.provider} failed ({exc}) and your daily shared fallback quota ({status['limit']}/{status['limit']}) is exhausted.",
                    retriable=False,
                ) from exc
            logger.info("Falling back to shared quota for user_id=%s under daily cap", user.id if user else None)

    # Use Shared Quota (Caps at 5/day)
    today = timezone.now().date()
    if user and user.is_authenticated:
        quota_row, _ = DailyPersonalizedQuota.objects.get_or_create(user=user, date=today)
    elif session_id:
        quota_row, _ = DailyPersonalizedQuota.objects.get_or_create(session_id=session_id, date=today)
    else:
        quota_row, _ = DailyPersonalizedQuota.objects.get_or_create(session_id="anon_default", date=today)

    if quota_row.is_capped():
        raise QuotaExceededError(
            f"Daily free personalized quota reached ({quota_row.call_count}/{quota_row.DEFAULT_DAILY_CAP}). Add your own API key (BYOK) in settings for unlimited personalized deep-dives and paper chat.",
            used=quota_row.call_count,
            limit=quota_row.DEFAULT_DAILY_CAP,
        )

    # Route through system LLM Router
    router = get_router()
    response = router.complete(request)
    quota_row.increment()
    return response

