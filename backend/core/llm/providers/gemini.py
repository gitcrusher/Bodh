"""Google Gemini provider adapter (free tier: gemini-1.5-flash-latest)."""

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

# Lazy import — only load the SDK when actually used
_genai: Any = None


def _get_genai() -> Any:
    global _genai
    if _genai is None:
        import google.generativeai as genai  # type: ignore

        _genai = genai
    return _genai


class GeminiProvider(BaseProvider):
    """
    Google Gemini adapter.
    Supports two keys (gemini_1, gemini_2) for quota pooling.
    Free tier: 1M tokens/min, 15 RPM on Flash-latest (as of Oct 2026).
    """

    def __init__(self, name: str, api_key_env: str = "", model: str = "", api_key: str | None = None) -> None:
        self.name = name
        self._api_key_env = api_key_env
        self._model_name = model or "gemini-3.5-flash"
        self._api_key_override = api_key
        self._client: Any = None

    def _api_key(self) -> str | None:
        return self._api_key_override or os.getenv(self._api_key_env) or None

    def is_available(self) -> bool:
        return bool(self._api_key())

    def _get_client(self) -> Any:
        if self._client is None:
            key = self._api_key()
            if not key:
                raise LLMProviderError(self.name, "No API key configured", retriable=False)
            genai = _get_genai()
            genai.configure(api_key=key, transport="rest")
            self._client = genai.GenerativeModel(self._model_name)
        return self._client

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            client = self._get_client()

            # Build the prompt from the canonical message list
            # Gemini uses a single string or a multi-turn format
            system_parts: list[str] = []
            user_parts: list[str] = []
            for msg in request.messages:
                if msg["role"] == "system":
                    system_parts.append(msg["content"])
                else:
                    user_parts.append(msg["content"])

            prompt = "\n\n".join(system_parts + user_parts)

            # If a JSON schema is requested, instruct the model explicitly
            if request.schema:
                schema_str = json.dumps(request.schema, indent=2)
                prompt = (
                    f"{prompt}\n\n"
                    f"Respond ONLY with valid JSON matching this schema:\n{schema_str}\n"
                    "Do not include markdown fences or any text outside the JSON object."
                )

            generation_config = _get_genai().types.GenerationConfig(
                max_output_tokens=request.max_tokens,
                temperature=request.temperature,
            )

            response = client.generate_content(prompt, generation_config=generation_config)

            content = response.text or ""

            # Token counts (Gemini returns usage_metadata)
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            return LLMResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider=self.name,
                model=self._model_name,
                raw=response,
            )

        except Exception as exc:
            err_str = str(exc).lower()
            if "quota" in err_str or "rate" in err_str or "429" in err_str:
                raise RateLimitError(self.name, f"Rate limited: {exc}") from exc
            raise LLMProviderError(self.name, f"Gemini error: {exc}") from exc
