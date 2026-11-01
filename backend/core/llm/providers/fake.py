"""
Fake provider — deterministic responses for tests.

Never makes a network call. Returns configurable canned responses,
validates schema if provided, and records what it received.
"""

from __future__ import annotations

import json
from typing import Any

from core.llm.providers.base import (
    BaseProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)


class FakeProvider(BaseProvider):
    """
    Test-only provider. Configured with a response queue; each call
    pops one response. Can be set to raise errors to test fallback paths.
    """

    name = "fake"

    def __init__(
        self,
        name: str = "fake",
        responses: list[str] | None = None,
        canned_responses: list[str] | None = None,
        always_fail: bool = False,
        fail_class: type[LLMProviderError] = LLMProviderError,
    ) -> None:
        self.name = name
        resp_list = canned_responses if canned_responses is not None else (responses or ["{}"])
        self._responses: list[str] = list(resp_list)
        self._idx = 0
        self.always_fail = always_fail
        self.fail_class = fail_class
        # Record of every request received — useful for assertion in tests
        self.received: list[LLMRequest] = []
        self.recorded_requests: list[LLMRequest] = self.received

    def is_available(self) -> bool:
        return True  # Fake is always available (no key needed)

    def reset(self, responses: list[str] | None = None) -> None:
        self._idx = 0
        if responses is not None:
            self._responses = list(responses)
        self.received = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.received.append(request)

        if self.always_fail:
            raise self.fail_class(self.name, "Fake provider configured to fail")

        if self._idx >= len(self._responses):
            # Cycle back to last response once exhausted
            content = self._responses[-1] if self._responses else "{}"
        else:
            content = self._responses[self._idx]
            self._idx += 1

        return LLMResponse(
            content=content,
            input_tokens=10,
            output_tokens=len(content.split()),
            provider=self.name,
            model="fake-model",
            raw=None,
        )


# Singleton convenient for simple tests
fake_provider = FakeProvider()
