"""
Base interface for all LLM providers.

Rule: feature code never calls a provider SDK directly.
Everything goes through the router -> provider adapter -> SDK.
"""

from __future__ import annotations

import abc
import dataclasses
import enum
from typing import Any


class ProviderStatus(enum.Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    NO_KEY = "no_key"
    ERROR = "error"


@dataclasses.dataclass
class LLMRequest:
    """Canonical request shape passed to every provider."""

    messages: list[dict[str, str]]          # [{"role": "user"|"system"|"assistant", "content": "..."}]
    schema: dict[str, Any] | None = None    # JSON Schema for structured output; None = free text
    max_tokens: int = 2048
    temperature: float = 0.2               # Low default for factual tasks (rules.md rule 11)
    recipe_name: str = ""                  # For logging
    logic_version: str = "1.0"


@dataclasses.dataclass
class LLMResponse:
    """Canonical response returned by every provider adapter."""

    content: str                            # Raw text content
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""
    raw: Any = None                         # Provider-specific response object (for debugging)


class LLMProviderError(Exception):
    """Raised when a provider call fails after its own retries."""

    def __init__(self, provider: str, message: str, retriable: bool = True) -> None:
        super().__init__(message)
        self.provider = provider
        self.retriable = retriable


class RateLimitError(LLMProviderError):
    """Provider returned a rate-limit / quota error."""


class SchemaError(LLMProviderError):
    """Provider returned content that does not match the requested schema."""


class BaseProvider(abc.ABC):
    """Abstract base that all provider adapters implement."""

    name: str = ""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider has a key and has not tripped its circuit breaker."""
        ...

    @abc.abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Perform one completion call.
        Raises LLMProviderError (or a subclass) on failure.
        Does NOT retry — the router handles retries.
        """
        ...
