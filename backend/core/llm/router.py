"""
LLM Router — provider-agnostic multi-provider routing with:
  - Priority list (configurable via settings.LLM_PROVIDER_PRIORITY)
  - Per-provider circuit breaker (skip after N consecutive failures)
  - Retry with backoff (max LLM_MAX_RETRIES per provider)
  - Fallback to the next provider on failure
  - Records provider_used on every call

Rule: feature code NEVER calls a provider SDK directly.
      Every LLM call goes through router.complete().
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from django.conf import settings

from core.llm.providers.base import (
    BaseProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Per-provider circuit breaker.
    Opens after `threshold` consecutive failures; stays open for `cooldown_s` seconds.
    """

    def __init__(self, threshold: int = 3, cooldown_s: float = 300.0) -> None:
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self._failures: dict[str, int] = defaultdict(int)
        self._opened_at: dict[str, float] = {}

    def is_open(self, provider_name: str) -> bool:
        opened = self._opened_at.get(provider_name)
        if opened is None:
            return False
        if time.monotonic() - opened > self.cooldown_s:
            # Cooldown elapsed — allow a retry (half-open)
            del self._opened_at[provider_name]
            self._failures[provider_name] = 0
            return False
        return True

    def record_success(self, provider_name: str) -> None:
        self._failures[provider_name] = 0
        self._opened_at.pop(provider_name, None)

    def record_failure(self, provider_name: str) -> None:
        self._failures[provider_name] += 1
        if self._failures[provider_name] >= self.threshold:
            if provider_name not in self._opened_at:
                logger.warning(
                    "Circuit breaker OPENED for provider=%s after %d consecutive failures",
                    provider_name,
                    self._failures[provider_name],
                )
                self._opened_at[provider_name] = time.monotonic()

    def failure_count(self, provider_name: str) -> int:
        return self._failures[provider_name]


class LLMRouter:
    """
    Provider-agnostic router.

    Usage:
        router = get_router()
        response = router.complete(request)  # returns LLMResponse
        # response.provider tells you which provider was used
    """

    def __init__(
        self,
        providers: list[BaseProvider],
        max_retries: int = 2,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._providers: dict[str, BaseProvider] = {p.name: p for p in providers}
        self._priority: list[str] = [p.name for p in providers]
        self.max_retries = max_retries
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            threshold=settings.LLM_CIRCUIT_BREAKER_THRESHOLD
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Try each provider in priority order.
        Per provider: retry up to max_retries on transient errors.
        Returns the first successful LLMResponse.
        Raises AllProvidersFailedError if every provider failed.
        """
        last_exc: Exception | None = None

        for name in self._priority:
            provider = self._providers.get(name)
            if provider is None:
                continue

            # Skip unavailable providers (no key) and open circuits
            if not provider.is_available():
                logger.debug("Provider %s skipped: not available (no key)", name)
                continue

            if self.circuit_breaker.is_open(name):
                logger.debug("Provider %s skipped: circuit open", name)
                continue

            for attempt in range(1, self.max_retries + 2):  # +1 for first try
                try:
                    response = provider.complete(request)
                    self.circuit_breaker.record_success(name)
                    if name != self._priority[0]:
                        response.raw  # noqa — response already has provider set
                        logger.info(
                            "Fallback used: provider=%s recipe=%s",
                            name,
                            request.recipe_name,
                        )
                    return response

                except RateLimitError as exc:
                    logger.warning("Provider %s rate limited: %s", name, exc)
                    self.circuit_breaker.record_failure(name)
                    last_exc = exc
                    break  # Don't retry on rate limit; try next provider

                except LLMProviderError as exc:
                    logger.warning(
                        "Provider %s attempt %d/%d failed: %s",
                        name,
                        attempt,
                        self.max_retries + 1,
                        exc,
                    )
                    last_exc = exc
                    if not exc.retriable or attempt > self.max_retries:
                        self.circuit_breaker.record_failure(name)
                        break
                    # Exponential backoff before retry
                    time.sleep(0.5 * (2 ** (attempt - 1)))

        raise AllProvidersFailedError(
            f"All LLM providers failed for recipe={request.recipe_name!r}"
        ) from last_exc

    def set_priority(self, priority: list[str]) -> None:
        """Override provider order (useful in tests)."""
        self._priority = [n for n in priority if n in self._providers]

    def add_provider(self, provider: BaseProvider) -> None:
        """Register an additional provider (e.g. FakeProvider in tests)."""
        self._providers[provider.name] = provider
        if provider.name not in self._priority:
            self._priority.append(provider.name)

    def status(self) -> dict[str, Any]:
        """Return current status of all providers (for health checks)."""
        return {
            name: {
                "available": self._providers[name].is_available(),
                "circuit_open": self.circuit_breaker.is_open(name),
                "failures": self.circuit_breaker.failure_count(name),
            }
            for name in self._priority
        }


class AllProvidersFailedError(Exception):
    """Raised when every provider in the priority list has failed."""


# ---------------------------------------------------------------------------
# Module-level singleton — built once from settings
# ---------------------------------------------------------------------------
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Return the singleton router, building it from settings on first call."""
    global _router
    if _router is None:
        _router = _build_router()
    return _router


def _build_router() -> LLMRouter:
    from core.llm.providers.anthropic import AnthropicProvider
    from core.llm.providers.fake import FakeProvider
    from core.llm.providers.gemini import GeminiProvider
    from core.llm.providers.groq import GroqProvider

    provider_configs = getattr(settings, "LLM_PROVIDER_CONFIG", {})
    priority = getattr(settings, "LLM_PROVIDER_PRIORITY", ["gemini_1", "gemini_2", "groq"])
    max_retries = getattr(settings, "LLM_MAX_RETRIES", 2)

    provider_map: dict[str, BaseProvider] = {}

    for name in priority:
        cfg = provider_configs.get(name, {})
        model = cfg.get("model", "")

        if name.startswith("gemini"):
            api_key_env = cfg.get("api_key_env", f"GEMINI_API_KEY_{name[-1].upper()}")
            provider_map[name] = GeminiProvider(name=name, api_key_env=api_key_env, model=model)

        elif name == "groq":
            provider_map[name] = GroqProvider(model=model)

        elif name == "anthropic":
            provider_map[name] = AnthropicProvider(model=model)

        elif name == "fake":
            provider_map[name] = FakeProvider()

        else:
            logger.warning("Unknown provider name in priority list: %s", name)

    # Build in priority order
    ordered = [provider_map[n] for n in priority if n in provider_map]
    return LLMRouter(
        providers=ordered,
        max_retries=max_retries,
    )


def reset_router() -> None:
    """Force re-build of the singleton (use in tests that swap providers)."""
    global _router
    _router = None
