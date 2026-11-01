"""Tests for build_context(), recipe registry, and token overflow handling."""

import pytest
from core.pipeline.context import (
    DATA_BLOCK_CLOSE,
    DATA_BLOCK_INSTRUCTION,
    DATA_BLOCK_OPEN,
    ContextPiece,
    Recipe,
    build_context,
    get_recipe,
    list_recipes,
    register_recipe,
    wrap_data_block,
)


def test_wrap_data_block():
    wrapped = wrap_data_block("paper_abstract", "This is an AI paper.")
    assert DATA_BLOCK_OPEN in wrapped
    assert "[paper_abstract]" in wrapped
    assert "This is an AI paper." in wrapped
    assert DATA_BLOCK_CLOSE in wrapped


def test_recipe_registry():
    r = Recipe(
        name="test_reg_recipe",
        logic_version="1.0",
        system_template="System prompt",
    )
    register_recipe(r)
    assert "test_reg_recipe" in list_recipes()
    fetched = get_recipe("test_reg_recipe")
    assert fetched.name == "test_reg_recipe"
    assert fetched.logic_version == "1.0"


def test_build_context_system_and_evidence():
    r = Recipe(
        name="test_context_recipe",
        logic_version="1.0",
        system_template="Base system prompt.",
        input_budget_tokens=1000,
    )
    evidence = [
        ContextPiece(content="Evidence piece 1", rank=0, label="primary_evidence"),
        ContextPiece(content="Evidence piece 2", rank=1, label="secondary_evidence"),
    ]
    messages = build_context(r, evidence=evidence)

    # First message is system with DATA_BLOCK_INSTRUCTION prepended
    assert messages[0]["role"] == "system"
    assert DATA_BLOCK_INSTRUCTION in messages[0]["content"]
    assert "Base system prompt." in messages[0]["content"]

    # User message contains wrapped evidence
    user_msg = [m for m in messages if m["role"] == "user"][0]
    assert "Evidence piece 1" in user_msg["content"]
    assert "Evidence piece 2" in user_msg["content"]


def test_build_context_overflow_drops_lower_rank_evidence():
    r = Recipe(
        name="test_overflow_recipe",
        logic_version="1.0",
        system_template="Sys",
        # Budget is tight: 50 tokens ≈ 200 chars
        input_budget_tokens=50,
    )
    evidence = [
        ContextPiece(content="A" * 80, rank=0, label="must_keep"),
        ContextPiece(content="B" * 200, rank=5, label="drop_me"),
    ]
    messages = build_context(r, evidence=evidence)
    user_msg = [m for m in messages if m["role"] == "user"][0]

    # Rank 0 must be kept
    assert "must_keep" in user_msg["content"]
    # Rank 5 should be dropped due to budget
    assert "drop_me" not in user_msg["content"]


def test_build_context_history_overflow_drops_oldest():
    r = Recipe(
        name="test_history_overflow",
        logic_version="1.0",
        system_template="Sys",
        input_budget_tokens=50,  # ~200 chars budget
    )
    history = [
        {"role": "user", "content": "OLD_MESSAGE_" + ("1" * 250)},
        {"role": "user", "content": "NEW_MESSAGE"},
    ]
    messages = build_context(r, history=history)

    contents = [m["content"] for m in messages]
    assert any("NEW_MESSAGE" in c for c in contents)
    assert not any("OLD_MESSAGE" in c for c in contents)
