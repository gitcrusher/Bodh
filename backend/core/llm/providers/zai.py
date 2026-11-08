"""
Z.AI / Zhipu AI GLM provider adapter (100% Free text models: GLM-4.7-Flash, GLM-4.5-Flash).
Uses OpenAI-compatible endpoint: https://api.z.ai/api/paas/v4/
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

_openai_module: Any = None


def _get_openai() -> Any:
    global _openai_module
    if _openai_module is None:
        import openai as _o  # type: ignore

        _openai_module = _o
    return _openai_module


class ZAIProvider(BaseProvider):
    """
    Z.AI adapter using OpenAI-compatible SDK endpoint.
    Free tier models:
    - glm-4.7-flash: High-performance free text model with extended reasoning.
    - glm-4.5-flash: Ultra-fast free text model.
    """

    def __init__(
        self,
        name: str = "zai",
        api_key_env: str = "ZAI_API_KEY",
        model: str = "",
        api_key: str | None = None,
        base_url: str = "https://api.z.ai/api/paas/v4/",
    ) -> None:
        self.name = name
        self._api_key_env = api_key_env
        self._model_name = model or "glm-4.7-flash"
        self._api_key_override = api_key
        self._base_url = os.getenv("ZAI_BASE_URL", base_url)
        self._client: Any = None

    def _api_key(self) -> str | None:
        return (
            self._api_key_override
            or os.getenv(self._api_key_env)
            or os.getenv("ZAI_API_KEY")
            or os.getenv("Z.AI_API_KEY")
            or os.getenv("ZHIPU_API_KEY")
            or None
        )

    def is_available(self) -> bool:
        return bool(self._api_key())

    def _get_client(self) -> Any:
        if self._client is None:
            key = self._api_key()
            if not key:
                raise LLMProviderError(
                    self.name,
                    f"No API key configured for {self.name} ({self._api_key_env})",
                    retriable=False,
                )
            openai = _get_openai()
            self._client = openai.OpenAI(api_key=key, base_url=self._base_url)
        return self._client

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            client = self._get_client()

            messages = list(request.messages)

            # Append schema instructions if structured JSON requested
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

            # GLM models need sufficient max_tokens because reasoning_content consumes tokens
            max_tokens = max(request.max_tokens or 1024, 1024)

            response = client.chat.completions.create(
                model=self._model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=request.temperature,
            )

            msg = response.choices[0].message
            content = msg.content or getattr(msg, "reasoning_content", "") or ""
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
            raise LLMProviderError(self.name, f"Z.AI error: {exc}") from exc

