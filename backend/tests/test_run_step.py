"""Tests for run_step() execution, logging to AgentRun, schema validation, and budgets."""

import json
import pytest
from core.llm.providers.fake import FakeProvider
from core.llm.router import LLMRouter
import core.llm.router as router_module
from core.models import AgentRun
from core.pipeline.context import Recipe
from core.pipeline.run_step import (
    BudgetExceededError,
    FailedGenerationError,
    run_step,
)


@pytest.fixture(autouse=True)
def cleanup_router():
    yield
    router_module.reset_router()


@pytest.mark.django_db
def test_run_step_happy_path():
    fake = FakeProvider(name="fake", canned_responses=['{"summary": "Test paper summary"}'])
    router_module._router = LLMRouter(providers=[fake], max_retries=0)

    recipe = Recipe(
        name="test_summarizer",
        logic_version="1.0",
        system_template="Summarize the paper.",
        schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )

    messages = [
        {"role": "system", "content": "You are an assistant."},
        {"role": "user", "content": "Summarize this."},
    ]

    content, meta = run_step(recipe, messages, input_ref="raw_item:1", agent_name="summarizer")

    data = json.loads(content)
    assert data["summary"] == "Test paper summary"
    assert meta["provider"] == "fake"
    assert meta["status"] == "done"

    # Verify AgentRun was logged
    run = AgentRun.objects.filter(agent_name="summarizer").latest("created_at")
    assert run.status == "done"
    assert run.input_ref == "raw_item:1"
    assert run.provider_used == "fake"


@pytest.mark.django_db
def test_run_step_budget_exceeded():
    recipe = Recipe(
        name="test_budget",
        logic_version="1.0",
        system_template="System prompt",
    )
    # Long message: 400 chars ≈ 100 tokens
    messages = [{"role": "user", "content": "x" * 400}]

    with pytest.raises(BudgetExceededError):
        run_step(recipe, messages, token_budget_remaining=10)


@pytest.mark.django_db
def test_run_step_schema_retry_success():
    # First response is invalid JSON / missing field; second response is valid
    fake = FakeProvider(
        name="fake",
        canned_responses=[
            '{"wrong_key": 123}',
            '{"summary": "Fixed summary"}',
        ],
    )
    router_module._router = LLMRouter(providers=[fake], max_retries=0)

    recipe = Recipe(
        name="test_schema_retry",
        logic_version="1.0",
        system_template="System prompt",
        schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )

    messages = [{"role": "user", "content": "Generate summary"}]
    content, meta = run_step(recipe, messages)
    data = json.loads(content)
    assert data["summary"] == "Fixed summary"


@pytest.mark.django_db
def test_run_step_schema_retry_failure():
    # Both responses invalid
    fake = FakeProvider(
        name="fake",
        canned_responses=[
            '{"wrong": 1}',
            '{"still_wrong": 2}',
        ],
    )
    router_module._router = LLMRouter(providers=[fake], max_retries=0)

    recipe = Recipe(
        name="test_schema_fail",
        logic_version="1.0",
        system_template="System prompt",
        schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )

    messages = [{"role": "user", "content": "Generate summary"}]
    with pytest.raises(FailedGenerationError):
        run_step(recipe, messages, input_ref="raw_item:99")

    # Verify AgentRun recorded failed_generation per rule 11
    run = AgentRun.objects.filter(input_ref="raw_item:99").latest("created_at")
    assert run.status == "failed_generation"
