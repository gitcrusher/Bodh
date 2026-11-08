"""
Groq provider adapter — high-speed inference on LPUs.
Hosted models:
- openai/gpt-oss-120b: Flagship 120B open-weight MoE reasoning model (~500 tps).
- openai/gpt-oss-20b: Ultra-fast 20B open-weight MoE model (~1,000 tps).
- llama-3.1-8b-instant: Lightweight fallback model.
"""

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

_groq_module: Any = None


def _get_groq() -> Any:
    global _groq_module
    if _groq_module is None:
        import groq as _g  # type: ignore

        _groq_module = _g
    return _groq_module


class GroqProvider(BaseProvider):
    """
    Groq adapter with OpenAI GPT-OSS support on LPUs.
    Supports:
    - openai/gpt-oss-120b: Complex reasoning, agentic tasks, deep synthesis (~500 tps).
    - openai/gpt-oss-20b: Medium & fast tasks, function calling, low token overhead (~1,000 tps).
    - Multi-account rotation via api_key_env (e.g. GROQ_API_KEY_1, GROQ_API_KEY_2).
    """

    def __init__(
        self,
        name: str = "groq",
        api_key_env: str = "GROQ_API_KEY",
        model: str = "",
        api_key: str | None = None,
    ) -> None:
        self.name = name
        self._api_key_env = api_key_env
        self._model_name = model or "openai/gpt-oss-20b"
        self._api_key_override = api_key
        self._client: Any = None

    def _api_key(self) -> str | None:
        return self._api_key_override or os.getenv(self._api_key_env) or os.getenv("GROQ_API_KEY") or None

    def is_available(self) -> bool:
        return bool(self._api_key())

    def _get_client(self) -> Any:
        if self._client is None:
            key = self._api_key()
            if not key:
                raise LLMProviderError(self.name, f"No API key configured for {self.name} ({self._api_key_env})", retriable=False)
            groq = _get_groq()
            self._client = groq.Groq(api_key=key)
        return self._client

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            client = self._get_client()

            messages = list(request.messages)  # already in OpenAI-compatible format

            # Groq uses the OpenAI-compatible chat completions endpoint.
            # If a JSON schema is requested, append instructions to the last user message.
            if request.schema:
                schema_str = json.dumps(request.schema, indent=2)
                schema_instruction = (
                    f"\n\nRespond ONLY with valid JSON matching this schema:\n{schema_str}\n"
                    "Do not include markdown fences or any text outside the JSON object."
                )
                # Append to last user message
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
            err_str = str(exc).lower()
            if "rate" in err_str or "429" in err_str or "quota" in err_str:
                raise RateLimitError(self.name, f"Rate limited: {exc}") from exc
            raise LLMProviderError(self.name, f"Groq error: {exc}") from exc
