"""
research/pipeline/state.py

TypedDict that flows through every node in the daily research graph.

Keeping state in one place means nodes can be tested in isolation by
constructing a PipelineState directly without running the full graph.
"""

from __future__ import annotations

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    """
    Mutable state passed between LangGraph nodes.

    Fields are added incrementally as nodes run:
      - fetch_node         → raw_items_fetched
      - persist_node       → raw_item_ids
      - dedup_node         → dedup_ids (subset of raw_item_ids that are not duplicates)
      - triage_node        → triage_ids (subset of dedup_ids that pass the classifier)
      - budget_node        → budgeted_ids (subset after daily budget check)
      - summarize_node     → card_ids (persisted card IDs)
      - number_check_node  → (sets needs_review on cards in-place)
      - validity_node      → (sets validity_signal rows)
      - report             → run_summary dict
    """

    # Set by the caller before the graph starts
    source_id: int               # research.models.Source PK
    token_budget: int            # tokens remaining for this run
    dry_run: bool                # if True, bypasses network fetch

    # Accumulated across nodes
    raw_items_fetched: list[dict]   # raw dicts from the fetcher
    raw_item_ids: list[int]         # RawItem PKs after persist
    dedup_ids: list[int]            # RawItem PKs that passed dedup
    triage_ids: list[int]           # RawItem PKs that passed triage
    budgeted_ids: list[int]         # RawItem PKs after daily budget gate
    card_ids: list[int]             # Card PKs written this run

    # Bookkeeping
    tokens_used: int
    errors: list[str]
    run_summary: dict
