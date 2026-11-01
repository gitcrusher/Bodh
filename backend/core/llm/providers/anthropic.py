"""Anthropic Claude provider adapter (paid; premium fallback)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from core.llm.providers.base import (
    BaseProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    RateLimitError,
)

logger = logging.getLogger(__name__)

_anthropic_module: Any = None


def _get_anthropic() -> Any:
    global _anthropic_module
    if _anthropic_module is None:
        import anthropic as _a  # type: ignore

        _anthropic_module = _a
    return _anthropic_module


class AnthropicProvider(BaseProvider):
    """
    Anthropic Claude adapter (paid — included as premium fallback).
    If ANTHROPIC_API_KEY is not set the provider reports is_available=False
    and the router skips it automatically.
    """

    name = "anthropic"

    def __init__(self, model: str = "", api_key: str | None = None) -> None:
        self._model_name = model or "claude-3-5-haiku-20241022"
        self._api_key_override = api_key
        self._client: Any = None

    def _api_key(self) -> str | None:
        return self._api_key_override or os.getenv("ANTHROPIC_API_KEY") or None

    def is_available(self) -> bool:
        return bool(self._api_key())

    def _get_client(self) -> Any:
        if self._client is None:
            key = self._api_key()
            if not key:
                raise LLMProviderError(
                    self.name, "No ANTHROPIC_API_KEY configured", retriable=False
                )
            anthropic = _get_anthropic()
            self._client = anthropic.Anthropic(api_key=key)
        return self._client

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            client = self._get_client()

            # Separate system message from the conversation
            system_content = ""
            messages: list[dict[str, str]] = []
            for msg in request.messages:
                if msg["role"] == "system":
                    system_content += msg["content"] + "\n"
                else:
                    messages.append(msg)

            if not messages:
                messages = [{"role": "user", "content": ""}]

            # JSON schema: append instruction to the last user message
            if request.schema:
                schema_str = json.dumps(request.schema, indent=2)
                schema_instruction = (
                    f"\n\nRespond ONLY with valid JSON matching this schema:\n{schema_str}\n"
                    "Do not include markdown fences or any text outside the JSON object."
                )
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i]["role"] == "user":
                        messages[i] = {
                            "role": "user",
                            "content": messages[i]["content"] + schema_instruction,
                        }
                        break

            kwargs: dict[str, Any] = dict(
                model=self._model_name,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                messages=messages,
            )
            if system_content.strip():
                kwargs["system"] = system_content.strip()

            response = client.messages.create(**kwargs)

            content = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            usage = response.usage

            return LLMResponse(
                content=content,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                provider=self.name,
                model=self._model_name,
                raw=response,
            )

        except Exception as exc:
            err_str = str(exc).lower()
            if "rate" in err_str or "429" in err_str or "overloaded" in err_str:
                raise RateLimitError(self.name, f"Rate limited: {exc}") from exc
            raise LLMProviderError(self.name, f"Anthropic error: {exc}") from exc
