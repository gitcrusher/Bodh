"""
research/pipeline/nodes.py

LangGraph node functions for the daily research ingestion pipeline.

Each node is a plain Python function: (PipelineState) -> dict  (partial state update).
LangGraph merges the returned dict into the shared state.

Pipeline order (from system design §5.6 workflow A):
  fetch → persist → dedup → triage → budget_check → summarize → number_check → validity

Rules enforced:
  Rule 18 — cheap triage before expensive summarization
  Rule 19 — iteration caps and daily token budgets
  Rule 26 — all fetched items already schema-validated before we touch them here
  Rule 31 — external ID check is the first dedup gate (database unique_together)
  Rule 37 — raw_content cleared after grace_period_expires_at (set in persist)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import IntegrityError, transaction

from core.embedding.service import embedding_service
from core.pipeline.context import ContextPiece, build_context
from core.pipeline.ledger import StageLedger
from core.pipeline.run_step import (
    BudgetExceededError,
    FailedGenerationError,
    run_step,
)
from research.models import Card, CardSource, PaperValiditySignal, RawItem, Source
from research.pipeline.state import PipelineState
from research.recipes import NUMBER_CHECK_RECIPE, SUMMARIZE_RECIPE, TRIAGE_RECIPE

logger = logging.getLogger(__name__)

_DEDUP_COSINE_THRESHOLD = 0.92   # system design §9
_LOGIC_VERSION = "1"

# Module-level ledger singleton
_ledger = StageLedger()


# ---------------------------------------------------------------------------
# Node 1 — Fetch
# ---------------------------------------------------------------------------


def fetch_node(state: PipelineState) -> dict:
    """
    Fetch new papers from the source using its registered fetcher.

    Returns: raw_items_fetched (list of raw dicts).
    """
    from research.fetchers.arxiv import fetch_arxiv_papers  # lazy import

    source_id = state.get("source_id")
    errors: list[str] = list(state.get("errors", []))
    dry_run: bool = state.get("dry_run", False)

    if dry_run:
        logger.info("fetch_node: dry_run=True, skipping HTTP fetch")
        return {"raw_items_fetched": [], "errors": errors}

    try:
        source = Source.objects.get(pk=source_id, active=True)
    except Source.DoesNotExist:
        errors.append(f"Source {source_id} not found or inactive")
        return {"raw_items_fetched": [], "errors": errors}

    try:
        raw_items = fetch_arxiv_papers(source, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        logger.error("fetch_node: source=%s error=%s", source.name, exc, exc_info=True)
        errors.append(f"fetch error: {exc}")
        raw_items = []

    logger.info("fetch_node: source=%s fetched=%d", source.name, len(raw_items))
    return {"raw_items_fetched": raw_items, "errors": errors}


# ---------------------------------------------------------------------------
# Node 2 — Persist raw items
# ---------------------------------------------------------------------------


def persist_node(state: PipelineState) -> dict:
    """
    Write fetched papers to raw_items table; skip duplicates via external_id unique index.
    Sets grace_period_expires_at so the retention job knows when to clear raw_content.

    Returns: raw_item_ids (list of RawItem PKs that are new).
    """
    source_id = state.get("source_id")
    raw_items = state.get("raw_items_fetched", [])
    errors: list[str] = list(state.get("errors", []))

    grace_days = getattr(settings, "RAW_CONTENT_GRACE_DAYS", 7)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=grace_days)

    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        errors.append(f"persist_node: Source {source_id} not found")
        return {"raw_item_ids": [], "errors": errors}

    new_ids: list[int] = []

    for item in raw_items:
        try:
            with transaction.atomic():
                obj, created = RawItem.objects.get_or_create(
                    source=source,
                    external_id=item["external_id"],
                    defaults={
                        "title": item["title"],
                        "url": item["url"],
                        "published_at": item["published_at"],
                        "raw_content": item.get("raw_content", ""),
                        "content_hash": item.get("content_hash", ""),
                        "grace_period_expires_at": expires_at,
                        "status": "new",
                    },
                )
                if created:
                    new_ids.append(obj.pk)
        except IntegrityError:
            pass  # Race condition: another process beat us; safe to skip
        except Exception as exc:  # noqa: BLE001
            logger.warning("persist_node: failed to persist %s: %s", item.get("external_id"), exc)
            errors.append(f"persist error {item.get('external_id')}: {exc}")

    logger.info("persist_node: wrote %d new raw_items (of %d fetched)", len(new_ids), len(raw_items))
    return {"raw_item_ids": new_ids, "errors": errors}


# ---------------------------------------------------------------------------
# Node 3 — Dedup (near-duplicate detection via embedding cosine similarity)
# ---------------------------------------------------------------------------


def dedup_node(state: PipelineState) -> dict:
    """
    For each new RawItem:
      1. Embed title + abstract.
      2. Cosine similarity against existing card embeddings — threshold 0.92.
         - Above threshold → attach as CardSource on the most similar card; mark duplicate.
         - Below threshold → pass through to triage.

    Returns: dedup_ids (RawItem PKs to send to triage).
    """
    raw_item_ids: list[int] = state.get("raw_item_ids", [])
    errors: list[str] = list(state.get("errors", []))
    dedup_ids: list[int] = []

    for raw_id in raw_item_ids:
        try:
            item = RawItem.objects.get(pk=raw_id)
        except RawItem.DoesNotExist:
            continue

        # Ledger check — skip if already deduped with this logic_version
        if _ledger.check("raw_item", raw_id, "dedup", item.external_id, _LOGIC_VERSION):
            dedup_ids.append(raw_id)
            continue

        # Embed title + abstract
        text = f"{item.title}\n{item.raw_content or ''}"
        try:
            vec = embedding_service.embed(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("dedup_node: embed failed for %s: %s", item.external_id, exc)
            errors.append(f"embed error {item.external_id}: {exc}")
            dedup_ids.append(raw_id)  # pass through on embed failure
            continue

        # Store embedding for future dedup comparisons
        item.embedding = vec
        item.save(update_fields=["embedding"])

        # Near-dup check against existing cards
        near_dup_card = _find_near_duplicate(vec)

        if near_dup_card is not None:
            CardSource.objects.get_or_create(
                card=near_dup_card,
                source_url=item.url,
                defaults={"source": item.source},
            )
            item.status = "duplicate"
            item.save(update_fields=["status"])
            _ledger.mark_done("raw_item", raw_id, "dedup", item.external_id, _LOGIC_VERSION)
            logger.debug("dedup_node: %s is near-dup of card %d", item.external_id, near_dup_card.pk)
        else:
            dedup_ids.append(raw_id)

    logger.info("dedup_node: %d / %d items passed dedup", len(dedup_ids), len(raw_item_ids))
    return {"dedup_ids": dedup_ids, "errors": errors}


def _find_near_duplicate(vec: list[float]) -> Card | None:
    """
    Return the most similar Card if cosine similarity exceeds threshold, else None.
    Uses pgvector ANN on Postgres; Python fallback on SQLite.
    """
    from django.db import connection

    if "postgresql" in connection.vendor:
        vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, 1 - (embedding <=> %s::vector) AS similarity
                FROM cards
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT 1
                """,
                [vec_str, vec_str],
            )
            row = cursor.fetchone()
        if row and row[1] >= _DEDUP_COSINE_THRESHOLD:
            try:
                return Card.objects.get(pk=row[0])
            except Card.DoesNotExist:
                return None
    else:
        # SQLite fallback — Python loop (small corpus in tests)
        import json

        best_sim = 0.0
        best_card: Card | None = None
        for card in Card.objects.exclude(embedding=None):
            raw = card.embedding
            if isinstance(raw, str):
                try:
                    existing_vec = json.loads(raw)
                except (ValueError, TypeError):
                    continue
            elif isinstance(raw, list):
                existing_vec = raw
            else:
                continue
            sim = embedding_service.cosine_similarity(vec, existing_vec)
            if sim > best_sim:
                best_sim = sim
                best_card = card
        if best_sim >= _DEDUP_COSINE_THRESHOLD:
            return best_card

    return None


# ---------------------------------------------------------------------------
# Node 4 — Triage (cheap LLM classifier)
# ---------------------------------------------------------------------------


def triage_node(state: PipelineState) -> dict:
    """
    Run the research_triage recipe on each deduped item.
    Rejected items are marked status='discarded'.

    Returns: triage_ids (RawItem PKs that pass).
    """
    dedup_ids: list[int] = state.get("dedup_ids", [])
    token_budget: int = state.get("token_budget", getattr(settings, "DAILY_TOKEN_BUDGET", 500_000))
    tokens_used: int = state.get("tokens_used", 0)
    errors: list[str] = list(state.get("errors", []))
    triage_ids: list[int] = []

    for raw_id in dedup_ids:
        try:
            item = RawItem.objects.get(pk=raw_id)
        except RawItem.DoesNotExist:
            continue

        if _ledger.check("raw_item", raw_id, "triage", item.external_id, _LOGIC_VERSION):
            triage_ids.append(raw_id)
            continue

        messages = build_context(
            TRIAGE_RECIPE,
            evidence=[
                ContextPiece(
                    content=f"Title: {item.title}\n\nAbstract: {item.raw_content or ''}",
                    rank=0,
                    label="paper",
                )
            ],
        )
        messages.append({"role": "user", "content": "Is this a genuine AI/ML research paper? Reply with JSON."})

        try:
            _, parsed = run_step(
                TRIAGE_RECIPE,
                messages,
                input_ref=item.external_id,
                agent_name="research_triage",
                token_budget_remaining=token_budget - tokens_used,
            )
            if parsed.get("accept", False):
                triage_ids.append(raw_id)
            else:
                item.status = "discarded"
                item.save(update_fields=["status"])
                logger.debug("triage_node: discarded %s", item.external_id)
            _ledger.mark_done("raw_item", raw_id, "triage", item.external_id, _LOGIC_VERSION)

        except (BudgetExceededError, FailedGenerationError) as exc:
            logger.warning("triage_node: %s for %s — passing through", type(exc).__name__, item.external_id)
            triage_ids.append(raw_id)  # fail-open on LLM failure
        except Exception as exc:  # noqa: BLE001
            errors.append(f"triage error {item.external_id}: {exc}")
            triage_ids.append(raw_id)

    logger.info("triage_node: %d / %d items passed triage", len(triage_ids), len(dedup_ids))
    return {"triage_ids": triage_ids, "tokens_used": tokens_used, "errors": errors}


# ---------------------------------------------------------------------------
# Node 5 — Budget gate
# ---------------------------------------------------------------------------


def budget_node(state: PipelineState) -> dict:
    """
    Enforce the daily card budget (DAILY_CARD_BUDGET).
    Items beyond the budget stay status='new' for the next run.

    Returns: budgeted_ids (subset of triage_ids within budget).
    """
    triage_ids: list[int] = state.get("triage_ids", [])
    daily_budget = getattr(settings, "DAILY_CARD_BUDGET", 50)

    from django.utils import timezone as dj_tz
    today_start = dj_tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cards_today = Card.objects.filter(created_at__gte=today_start).count()
    remaining = max(0, daily_budget - cards_today)

    budgeted_ids = triage_ids[:remaining]
    deferred_count = len(triage_ids) - len(budgeted_ids)

    if deferred_count:
        logger.info("budget_node: deferring %d items (daily budget exhausted)", deferred_count)

    logger.info("budget_node: %d items within budget (%d slot(s) remaining)", len(budgeted_ids), remaining)
    return {"budgeted_ids": budgeted_ids}


# ---------------------------------------------------------------------------
# Node 6 — Summarize
# ---------------------------------------------------------------------------


def summarize_node(state: PipelineState) -> dict:
    """
    Generate the 60-second card for each budgeted item via research_summarize recipe.

    On all-providers-fail: item stays status='new', retried next run.
    On schema failure after retry: extractive fallback, card written with needs_review=True.

    Returns: card_ids (Card PKs written this run).
    """
    budgeted_ids: list[int] = state.get("budgeted_ids", [])
    token_budget: int = state.get("token_budget", getattr(settings, "DAILY_TOKEN_BUDGET", 500_000))
    tokens_used: int = state.get("tokens_used", 0)
    errors: list[str] = list(state.get("errors", []))
    card_ids: list[int] = []

    for raw_id in budgeted_ids:
        try:
            item = RawItem.objects.get(pk=raw_id)
        except RawItem.DoesNotExist:
            continue

        if _ledger.check("raw_item", raw_id, "summarize", item.external_id, _LOGIC_VERSION):
            try:
                card_ids.append(item.card.pk)
            except Exception:  # noqa: BLE001
                pass
            continue

        abstract = item.raw_content or ""
        messages = build_context(
            SUMMARIZE_RECIPE,
            evidence=[
                ContextPiece(
                    content=f"Title: {item.title}\n\nAbstract:\n{abstract}",
                    rank=0,
                    label="paper_abstract",
                )
            ],
        )
        messages.append({
            "role": "user",
            "content": "Summarize this paper into a 60-second card. Return only valid JSON.",
        })

        needs_review = False
        headline = ""
        summary_60s = ""
        tags: list[str] = []
        candidate_techniques: list[str] = []

        try:
            _, parsed = run_step(
                SUMMARIZE_RECIPE,
                messages,
                input_ref=item.external_id,
                agent_name="research_summarize",
                token_budget_remaining=token_budget - tokens_used,
            )
            headline = parsed.get("headline", item.title[:120])
            summary_60s = parsed.get("summary_60s", "")
            tags = parsed.get("tags", [])
            candidate_techniques = parsed.get("candidate_techniques", [])

        except FailedGenerationError:
            needs_review = True
            headline = item.title[:120]
            sentences = abstract.split(". ")
            summary_60s = "• " + "\n• ".join(s.strip() for s in sentences[:3] if s.strip())
            logger.warning("summarize_node: extractive fallback for %s", item.external_id)

        except BudgetExceededError:
            logger.warning("summarize_node: budget exceeded, skipping %s", item.external_id)
            continue

        except Exception as exc:  # noqa: BLE001
            errors.append(f"summarize error {item.external_id}: {exc}")
            needs_review = True
            headline = item.title[:120]
            summary_60s = abstract[:500]

        # Embed headline + summary for Research Assistant coarse retrieval
        card_text = f"{headline}\n{summary_60s}"
        try:
            card_embedding = embedding_service.embed(card_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("summarize_node: card embed failed for %s: %s", item.external_id, exc)
            card_embedding = None

        with transaction.atomic():
            card = Card.objects.create(
                raw_item=item,
                category="research",
                headline=headline,
                summary_60s=summary_60s,
                tags=tags,
                candidate_techniques=candidate_techniques,
                deep_dive_base=None,
                embedding=card_embedding,
                source_url=item.url,
                published_at=item.published_at,
                needs_review=needs_review,
            )
            item.status = "processed"
            item.save(update_fields=["status"])

        # Rule 57: Automated ingest-time cross-paper dynamic linking
        try:
            from research.paper_linker import link_newly_ingested_card

            link_newly_ingested_card(card)
        except Exception as exc:  # noqa: BLE001
            logger.warning("summarize_node: link_newly_ingested_card failed for card %d: %s", card.pk, exc)

        card_ids.append(card.pk)
        _ledger.mark_done("raw_item", raw_id, "summarize", item.external_id, _LOGIC_VERSION)
        logger.debug("summarize_node: wrote card %d for %s", card.pk, item.external_id)

    logger.info("summarize_node: wrote %d cards", len(card_ids))
    return {"card_ids": card_ids, "tokens_used": tokens_used, "errors": errors}


# ---------------------------------------------------------------------------
# Node 7 — Number / entity check
# ---------------------------------------------------------------------------


def number_check_node(state: PipelineState) -> dict:
    """
    Verify numbers and named entities in the summary match the abstract.
    On mismatch: mark card needs_review (extractive fallback will be used by UI).
    """
    card_ids: list[int] = state.get("card_ids", [])
    tokens_used: int = state.get("tokens_used", 0)
    token_budget: int = state.get("token_budget", getattr(settings, "DAILY_TOKEN_BUDGET", 500_000))
    errors: list[str] = list(state.get("errors", []))

    for card_id in card_ids:
        try:
            card = Card.objects.select_related("raw_item").get(pk=card_id)
        except Card.DoesNotExist:
            continue

        ref_key = f"card:{card_id}"
        if _ledger.check("card", card_id, "number_check", ref_key, _LOGIC_VERSION):
            continue

        abstract = card.raw_item.raw_content or ""
        messages = build_context(
            NUMBER_CHECK_RECIPE,
            evidence=[
                ContextPiece(
                    content=f"ABSTRACT:\n{abstract}\n\nSUMMARY:\n{card.summary_60s}",
                    rank=0,
                    label="check_input",
                )
            ],
        )
        messages.append({"role": "user", "content": "Check the summary for faithfulness to the abstract."})

        try:
            _, parsed = run_step(
                NUMBER_CHECK_RECIPE,
                messages,
                input_ref=ref_key,
                agent_name="research_number_check",
                token_budget_remaining=token_budget - tokens_used,
            )
            if not parsed.get("faithful", True):
                mismatches = parsed.get("mismatches", [])
                logger.warning("number_check_node: card %d has mismatches: %s", card_id, mismatches)
                card.needs_review = True
                card.save(update_fields=["needs_review"])

        except (BudgetExceededError, FailedGenerationError):
            pass  # Non-fatal; card stays as-is
        except Exception as exc:  # noqa: BLE001
            errors.append(f"number_check error card:{card_id}: {exc}")

        _ledger.mark_done("card", card_id, "number_check", ref_key, _LOGIC_VERSION)

    return {"tokens_used": tokens_used, "errors": errors}


# ---------------------------------------------------------------------------
# Node 8 — Validity signals
# ---------------------------------------------------------------------------


def validity_node(state: PipelineState) -> dict:
    """
    Populate paper_validity_signals from arXiv metadata.
    Semantic Scholar enrichment is added in Step 4.
    """
    card_ids: list[int] = state.get("card_ids", [])
    errors: list[str] = list(state.get("errors", []))

    for card_id in card_ids:
        try:
            card = Card.objects.select_related("raw_item__source").get(pk=card_id)
        except Card.DoesNotExist:
            continue

        if PaperValiditySignal.objects.filter(card=card).exists():
            continue

        try:
            PaperValiditySignal.objects.create(
                card=card,
                venue="arXiv preprint",
                venue_tier=3,
                authors=[],
                affiliation_tier=3,
                data_source="arxiv_metadata",
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"validity error card:{card_id}: {exc}")

    return {"errors": errors}


# ---------------------------------------------------------------------------
# Node 9 — Run report
# ---------------------------------------------------------------------------


def report_node(state: PipelineState) -> dict:
    """Collate a summary of the run and update source.last_successful_run_at."""
    source_id = state.get("source_id")
    card_ids: list[int] = state.get("card_ids", [])
    errors: list[str] = state.get("errors", [])
    tokens_used: int = state.get("tokens_used", 0)

    summary = {
        "source_id": source_id,
        "cards_written": len(card_ids),
        "tokens_used": tokens_used,
        "errors": errors,
        "finished_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    if not errors:
        try:
            Source.objects.filter(pk=source_id).update(
                last_successful_run_at=datetime.now(tz=timezone.utc)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("report_node: failed to update last_successful_run_at: %s", exc)

    logger.info(
        "report_node: source=%s cards=%d tokens=%d errors=%d",
        source_id,
        len(card_ids),
        tokens_used,
        len(errors),
    )
    return {"run_summary": summary}
