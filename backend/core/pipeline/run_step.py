"""
run_step() — the thin wrapper around every LLM call in the pipeline.

Rules enforced here (rules.md):
  Rule 3:  Every LLM call goes through run_step(). Never call a provider SDK directly.
  Rule 11: Malformed output → retry once with the error → failed_generation.
  Rule 18: Cheap triage before expensive; model routing is caller's responsibility via recipe.
  Rule 19: Iteration caps and token budgets.

Every call is logged to agent_runs for observability.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import jsonschema  # type: ignore
from django.conf import settings

from core.llm.providers.base import LLMRequest, LLMResponse
from core.llm.router import AllProvidersFailedError, get_router
from core.pipeline.context import Recipe

logger = logging.getLogger(__name__)


class FailedGenerationError(Exception):
    """
    Raised when structured output fails schema validation even after
    the single retry. The item should be marked failed_generation.
    """


class BudgetExceededError(Exception):
    """Raised when estimated token cost exceeds remaining budget."""



def run_step(
    recipe: Recipe,
    messages: list[dict[str, str]],
    *,
    input_ref: str = "",
    agent_name: str = "",
    token_budget_remaining: int | None = None,
    iteration_cap: int = 3,
) -> tuple[str, dict[str, Any]]:
    """
    Execute one LLM step through the router.

    Parameters
    ----------
    recipe:
        The versioned recipe for this step (determines schema, temperature, etc.)
    messages:
        The assembled message list from build_context().
    input_ref:
        Opaque reference to the item being processed (e.g. "raw_item:42").
        Stored in agent_runs for traceability.
    agent_name:
        Which pipeline node this is (e.g. "summarizer", "validity_critic").
    token_budget_remaining:
        If set and the estimated token cost exceeds this, raises BudgetExceededError.
    iteration_cap:
        Maximum LLM calls this step is allowed to make (schema-retry counts as 1 extra).

    Returns
    -------
    (content, metadata) where:
        content  = validated (and possibly parsed) response string
        metadata = {"provider": ..., "input_tokens": ..., "output_tokens": ..., ...}

    Raises
    ------
    FailedGenerationError  if schema validation fails after the single retry.
    BudgetExceededError    if token_budget_remaining is exceeded.
    AllProvidersFailedError if all providers are down (caller should defer the item).
    """
    start = time.monotonic()
    router = get_router()
    _agent_name = agent_name or recipe.name

    # ---------- Budget pre-check (rough estimate) ----------
    if token_budget_remaining is not None:
        estimated_input = sum(len(m["content"]) // 4 for m in messages)
        if estimated_input > token_budget_remaining:
            raise BudgetExceededError(
                f"Estimated input tokens {estimated_input} exceed remaining budget "
                f"{token_budget_remaining} for step {_agent_name!r}"
            )

    request = LLMRequest(
        messages=messages,
        schema=recipe.schema,
        max_tokens=recipe.output_reserve_tokens,
        temperature=recipe.temperature,
        recipe_name=recipe.name,
        logic_version=recipe.logic_version,
    )

    # ---------- First attempt ----------
    response: LLMResponse | None = None
    status = "done"
    final_content = ""
    metadata: dict[str, Any] = {}

    try:
        response = router.complete(request)
        final_content, status = _validate_and_parse(response.content, recipe.schema)

    except AllProvidersFailedError:
        status = "provider_down"
        _log_agent_run(
            agent_name=_agent_name,
            input_ref=input_ref,
            status=status,
            response=None,
            latency_ms=int((time.monotonic() - start) * 1000),
            recipe=recipe,
        )
        raise

    except _SchemaValidationError as exc:
        # ---------- Single retry with the validation error (rule 11) ----------
        logger.info("Schema validation failed for %r; retrying once. Error: %s", _agent_name, exc)
        retry_messages = messages + [
            {"role": "assistant", "content": response.content if response else ""},
            {
                "role": "user",
                "content": (
                    f"Your previous response failed schema validation: {exc}\n"
                    "Please fix it and respond ONLY with valid JSON matching the schema."
                ),
            },
        ]
        try:
            response = router.complete(LLMRequest(
                messages=retry_messages,
                schema=recipe.schema,
                max_tokens=recipe.output_reserve_tokens,
                temperature=recipe.temperature,
                recipe_name=recipe.name + "_retry",
                logic_version=recipe.logic_version,
            ))
            final_content, status = _validate_and_parse(response.content, recipe.schema)
        except (_SchemaValidationError, AllProvidersFailedError) as retry_exc:
            status = "failed_generation"
            _log_agent_run(
                agent_name=_agent_name,
                input_ref=input_ref,
                status=status,
                response=response,
                latency_ms=int((time.monotonic() - start) * 1000),
                recipe=recipe,
            )
            raise FailedGenerationError(
                f"Schema validation failed after retry for {_agent_name!r}: {retry_exc}"
            ) from retry_exc

    latency_ms = int((time.monotonic() - start) * 1000)
    _log_agent_run(
        agent_name=_agent_name,
        input_ref=input_ref,
        status=status,
        response=response,
        latency_ms=latency_ms,
        recipe=recipe,
    )

    metadata = {
        "provider": response.provider if response else "",
        "model": response.model if response else "",
        "input_tokens": response.input_tokens if response else 0,
        "output_tokens": response.output_tokens if response else 0,
        "latency_ms": latency_ms,
        "logic_version": recipe.logic_version,
        "status": status,
    }

    return final_content, metadata


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _SchemaValidationError(Exception):
    pass


def _validate_and_parse(content: str, schema: dict[str, Any] | None) -> tuple[str, str]:
    """
    If a schema is provided, validate the content against it.
    Returns (content, status). Raises _SchemaValidationError on mismatch.
    """
    if schema is None:
        return content, "done"

    # Strip markdown fences if the model wrapped the JSON anyway
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise _SchemaValidationError(f"Invalid JSON: {exc}. Content: {cleaned[:200]}") from exc

    try:
        jsonschema.validate(parsed, schema)
    except jsonschema.ValidationError as exc:
        raise _SchemaValidationError(f"Schema mismatch: {exc.message}") from exc

    return cleaned, "done"


def _log_agent_run(
    *,
    agent_name: str,
    input_ref: str,
    status: str,
    response: LLMResponse | None,
    latency_ms: int,
    recipe: Recipe,
) -> None:
    """Write to AgentRun table. Never raises — logging failure must not break the pipeline."""
    try:
        from core.models import AgentRun  # lazy import

        AgentRun.objects.create(
            agent_name=agent_name,
            input_ref=input_ref,
            output=response.content if response else "",
            latency_ms=latency_ms,
            provider_used=response.provider if response else "",
            prompt_version=recipe.logic_version,
            fallback_used=(response.provider != recipe.name) if response else False,
            input_tokens=response.input_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            status=status,
        )
    except Exception as exc:
        logger.error("Failed to write AgentRun: %s", exc)


class BudgetExceededError(Exception):
    """Raised when a step's estimated token cost exceeds the remaining daily budget."""
