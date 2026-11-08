"""OpenAI ChatGPT provider adapter (gpt-4o, gpt-4o-mini)."""

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

_openai_module: Any = None


def _get_openai() -> Any:
    global _openai_module
    if _openai_module is None:
        import openai as _o  # type: ignore

        _openai_module = _o
    return _openai_module


class OpenAIProvider(BaseProvider):
    """
    OpenAI ChatGPT adapter.
    Use for complex tasks requiring high reasoning, structured synthesis,
    or multi-turn research assistant conversations.
    Supports multiple accounts via api_key_env (e.g. OPENAI_API_KEY_1, OPENAI_API_KEY_2).
    """

    def __init__(
        self,
        name: str = "openai",
        api_key_env: str = "OPENAI_API_KEY",
        model: str = "",
        api_key: str | None = None,
    ) -> None:
        self.name = name
        self._api_key_env = api_key_env
        self._model_name = model or "gpt-4o-mini"
        self._api_key_override = api_key
        self._client: Any = None

    def _api_key(self) -> str | None:
        return self._api_key_override or os.getenv(self._api_key_env) or os.getenv("OPENAI_API_KEY") or None

    def is_available(self) -> bool:
        return bool(self._api_key())

    def _get_client(self) -> Any:
        if self._client is None:
            key = self._api_key()
            if not key:
                raise LLMProviderError(self.name, f"No API key configured for {self.name} ({self._api_key_env})", retriable=False)
            openai = _get_openai()
            self._client = openai.OpenAI(api_key=key)
        return self._client

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            client = self._get_client()

            messages = list(request.messages)

            # If JSON schema is requested, append explicit instructions to the prompt
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

            response = client.chat.completions.create(
                model=self._model_name,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )

            content = response.choices[0].message.content or ""
            usage = response.usage

            return LLMResponse(
                content=content,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                provider=self.name,
                model=self._model_name,
                raw=response,
            )

        except Exception as exc:
            openai = _get_openai()
            if isinstance(exc, openai.RateLimitError):
                raise RateLimitError(self.name, f"OpenAI rate limit: {exc}") from exc
            if isinstance(exc, openai.APIConnectionError):
                raise LLMProviderError(self.name, f"OpenAI connection error: {exc}", retriable=True) from exc
            if isinstance(exc, openai.APIStatusError) and exc.status_code in (429, 500, 502, 503, 504):
                raise LLMProviderError(self.name, f"OpenAI server error ({exc.status_code}): {exc}", retriable=True) from exc
            raise LLMProviderError(self.name, f"OpenAI error: {exc}", retriable=False) from exc

