"""
research/graph.py

LangGraph daily research ingestion graph.

Build the graph once with build_research_graph(), then invoke it with:

    graph = build_research_graph()
    result = graph.invoke({"source_id": source.pk, "token_budget": 500_000})

The graph is NOT a service — it is a library-style in-process workflow.
One graph instance is reusable across runs.

Node order (system design §5.6 workflow A):
  fetch → persist → dedup → triage → budget → summarize → number_check → validity → report

All nodes follow the (state: dict) -> dict contract so they are independently testable
without LangGraph.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_research_graph():
    """
    Build and compile the research ingestion LangGraph.

    Returns a CompiledGraph whose .invoke(state) runs the full pipeline.
    """
    from langgraph.graph import StateGraph

    from research.pipeline.nodes import (
        budget_node,
        dedup_node,
        fetch_node,
        number_check_node,
        persist_node,
        report_node,
        summarize_node,
        triage_node,
        validity_node,
    )
    from research.pipeline.state import PipelineState
    from research.recipes import register_research_recipes

    # Ensure all recipes are in the registry before any node runs
    register_research_recipes()

    graph = StateGraph(PipelineState)

    graph.add_node("fetch", fetch_node)
    graph.add_node("persist", persist_node)
    graph.add_node("dedup", dedup_node)
    graph.add_node("triage", triage_node)
    graph.add_node("budget", budget_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("number_check", number_check_node)
    graph.add_node("validity", validity_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "persist")
    graph.add_edge("persist", "dedup")
    graph.add_edge("dedup", "triage")
    graph.add_edge("triage", "budget")
    graph.add_edge("budget", "summarize")
    graph.add_edge("summarize", "number_check")
    graph.add_edge("number_check", "validity")
    graph.add_edge("validity", "report")
    graph.set_finish_point("report")

    return graph.compile()


def run_daily_research(source_id: int, *, dry_run: bool = False) -> dict:
    """
    Entry point for the management command and scheduler.

    Args:
        source_id: research.models.Source PK to run.
        dry_run:   If True, builds the graph but invokes with an empty fetch result
                   (useful for smoke-testing the graph without hitting arXiv).

    Returns:
        The run_summary dict from report_node.
    """
    from django.conf import settings

    from core.flags.feature_flags import is_enabled

    if not is_enabled("research_module"):
        logger.info("run_daily_research: research_module flag is off — skipping")
        return {"skipped": True, "reason": "feature flag off"}

    token_budget = getattr(settings, "DAILY_TOKEN_BUDGET", 500_000)

    initial_state = {
        "source_id": source_id,
        "token_budget": token_budget,
        "tokens_used": 0,
        "dry_run": dry_run,
        "errors": [],
        "raw_items_fetched": [],
        "raw_item_ids": [],
        "dedup_ids": [],
        "triage_ids": [],
        "budgeted_ids": [],
        "card_ids": [],
    }

    graph = build_research_graph()

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:
        logger.error("run_daily_research: graph crashed for source=%s: %s", source_id, exc, exc_info=True)
        return {"error": str(exc), "source_id": source_id}

    return final_state.get("run_summary", {})
