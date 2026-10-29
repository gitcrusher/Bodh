"""
research/paper_linker.py

Dynamic Research Linking Engine (Rule 56 & 57).

Responsibilities:
1. Automated Ingest-Time Dynamic Linking:
   As soon as new papers are scraped and read, this engine binds cross-paper links
   (CardRelation) between the newly created card and existing corpus papers based on
   shared techniques, topic clusters, benchmark comparisons, or semantic overlap.
2. Dynamic Paper Links Flow:
   Exposes get_dynamic_paper_links() to query connected papers formatted for the
   reusable DynamicPaperLinkTile components, enabling dynamic and horizontal scalability.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction

if TYPE_CHECKING:
    from research.models import Card, CardRelation

logger = logging.getLogger(__name__)

# Known evaluation benchmarks for benchmark_comparison detection
KNOWN_BENCHMARKS = [
    "mmlu",
    "gsm8k",
    "humaneval",
    "imagenet",
    "swe-bench",
    "arc",
    "gpqa",
    "hellaswag",
    "math",
    "truthfulqa",
]


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def link_newly_ingested_card(card: Card, max_links: int = 5) -> list[CardRelation]:
    """
    Rule 57: Ingest-time cross-paper linker.
    Runs when a card is newly created or ingested into the research database.
    Computes relationships against existing corpus cards and persists CardRelation rows.
    """
    from research.models import Card, CardRelation

    candidates = Card.objects.exclude(pk=card.pk).order_by("-published_at")[:50]
    if not candidates.exists():
        logger.debug("paper_linker: No existing candidates to link for Card #%d", card.pk)
        return []

    scored_matches: list[tuple[Card, str, str, float]] = []

    card_techs = {t.strip().lower() for t in (card.candidate_techniques or []) if t.strip()}
    card_tags = {t.strip().lower() for t in (card.tags or []) if t.strip()}
    card_headline_lower = card.headline.lower()

    for other in candidates:
        other_techs = {t.strip().lower() for t in (other.candidate_techniques or []) if t.strip()}
        other_tags = {t.strip().lower() for t in (other.tags or []) if t.strip()}
        other_headline_lower = other.headline.lower()

        # 1. Check Shared Techniques
        shared_techs = card_techs & other_techs
        if shared_techs:
            tech_name = sorted(shared_techs)[0]
            label = f"Shared Technique: {tech_name.title()}"
            score = min(0.95, 0.88 + 0.03 * len(shared_techs))
            scored_matches.append((other, "shared_technique", label, score))
            continue

        # 2. Check Benchmark / Dataset Overlap
        shared_benches = [
            b for b in KNOWN_BENCHMARKS
            if (b in card_headline_lower or b in " ".join(card_tags) or b in " ".join(card_techs))
            and (b in other_headline_lower or b in " ".join(other_tags) or b in " ".join(other_techs))
        ]
        if shared_benches:
            bench_name = shared_benches[0].upper()
            label = f"Benchmark Comparison: {bench_name}"
            scored_matches.append((other, "benchmark_comparison", label, 0.85))
            continue

        # 3. Check Shared Topic Tags
        shared_tags = card_tags & other_tags
        if shared_tags:
            tag_name = sorted(shared_tags)[0].replace("_", " ").title()
            label = f"Topic Cluster: {tag_name}"
            score = min(0.82, 0.75 + 0.03 * len(shared_tags))
            scored_matches.append((other, "topic_cluster", label, score))
            continue

        # 4. Check Embedding Semantic Overlap
        if card.embedding and other.embedding:
            sim = _cosine_similarity(card.embedding, other.embedding)
            if sim >= 0.70:
                label = f"Semantic Alignment: {int(sim * 100)}%"
                scored_matches.append((other, "topic_cluster", label, sim))
                continue

    # Sort candidates by score descending
    scored_matches.sort(key=lambda x: x[3], reverse=True)
    top_matches = scored_matches[:max_links]

    created_relations: list[CardRelation] = []
    with transaction.atomic():
        for target_card, rel_type, rel_label, score in top_matches:
            rel, _ = CardRelation.objects.update_or_create(
                source_card=card,
                target_card=target_card,
                defaults={
                    "relation_type": rel_type,
                    "relation_label": rel_label,
                    "similarity_score": score,
                },
            )
            created_relations.append(rel)

            # Bidirectional connection so reciprocal card also references this new research
            CardRelation.objects.update_or_create(
                source_card=target_card,
                target_card=card,
                defaults={
                    "relation_type": rel_type,
                    "relation_label": rel_label,
                    "similarity_score": score,
                },
            )

    logger.info("paper_linker: Created %d dynamic links for Card #%d", len(created_relations), card.pk)
    return created_relations


def get_dynamic_paper_links(card: Card, limit: int = 8) -> list[dict[str, Any]]:
    """
    Rule 56: Retrieve dynamic research links for a card.
    If no links exist yet, triggers ingest-time linking on-the-fly.
    Returns clean dictionary format consumed by API serializers and frontend tiles.
    """
    from research.models import Card, CardRelation

    relations = list(
        CardRelation.objects.filter(source_card=card)
        .select_related("target_card")
        .order_by("-similarity_score")[:limit]
    )

    if not relations:
        # Trigger linking on-demand
        created = link_newly_ingested_card(card, max_links=limit)
        if created:
            relations = list(
                CardRelation.objects.filter(source_card=card)
                .select_related("target_card")
                .order_by("-similarity_score")[:limit]
            )

    # If still empty (e.g. test environments or solitary papers), provide dynamic topic cluster fallback
    if not relations:
        fallback_query = Card.objects.exclude(pk=card.pk)
        if card.tags:
            fallback_query = fallback_query.filter(tags__icontains=card.tags[0])
        elif card.candidate_techniques:
            fallback_query = fallback_query.filter(candidate_techniques__icontains=card.candidate_techniques[0])

        fallbacks = list(fallback_query.order_by("-published_at")[:limit])
        if not fallbacks:
            fallbacks = list(Card.objects.exclude(pk=card.pk).order_by("-published_at")[:limit])

        formatted_links = []
        for idx, target in enumerate(fallbacks):
            formatted_links.append({
                "id": -(idx + 1),  # Dynamic virtual ID
                "relation_type": "topic_cluster",
                "relation_label": f"Topic: {card.tags[0].replace('_', ' ').title()}" if card.tags else "Related Corpus",
                "similarity_score": 0.70,
                "created_at": target.published_at.isoformat() if target.published_at else None,
                "target_card_id": target.id,
                "target_headline": target.headline,
                "target_summary_60s": target.summary_60s,
                "target_category": target.category,
                "target_source_url": target.source_url,
                "target_image_url": target.image_url,
                "target_published_at": target.published_at.isoformat() if target.published_at else None,
                "target_tags": target.tags,
                "target_techniques": target.candidate_techniques,
            })
        return formatted_links

    formatted_links = []
    for rel in relations:
        target = rel.target_card
        formatted_links.append({
            "id": rel.id,
            "relation_type": rel.relation_type,
            "relation_label": rel.relation_label,
            "similarity_score": rel.similarity_score,
            "created_at": rel.created_at.isoformat() if rel.created_at else None,
            "target_card_id": target.id,
            "target_headline": target.headline,
            "target_summary_60s": target.summary_60s,
            "target_category": target.category,
            "target_source_url": target.source_url,
            "target_image_url": target.image_url,
            "target_published_at": target.published_at.isoformat() if target.published_at else None,
            "target_tags": target.tags,
            "target_techniques": target.candidate_techniques,
        })
    return formatted_links

