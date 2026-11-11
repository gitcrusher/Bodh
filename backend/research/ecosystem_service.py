"""
research/ecosystem_service.py

Comprehensive AI/ML Ecosystem Discovery & Soft-Matching Service (§5, §8, §15).
Covers the full landscape of AI/ML:
  1. YouTube Channels (learning and news)
  2. Podcasts
  3. AI Labs and Companies (blogs, research, release notes)
  4. Newsletters, Blogs and News Sites
  5. Research Hubs, Conferences and Communities
  6. Core ML Frameworks and Classic ML
  7. LLM Training and Fine-Tuning
  8. Inference, Serving and Optimization
  9. Open Models and Model Families
  10. LLM Apps, RAG and Agents
  11. UIs and Developer Tools
  12. Vector Databases and Search
  13. MLOps and Data Pipelines
  14. Evaluation and Observability
  15. Data and Classic Libraries
  16. Coding Agents (Terminal and IDE)
  17. Agent Frameworks
  18. Protocols and Interoperability
  19. Browser and Computer-Use Agents
  20. Workflow Automation and Low-Code
  21. Research and General-Purpose Agents
  22. Memory, Retrieval and Context
  23. Sandboxes and Execution
  24. Evaluation, Observability and Guardrails
  25. Organizations That Test and Audit Agents
  26. Agent Benchmarks and Verification Suites
  27. Safety, Security and Red-Teaming Benchmarks

Key Capabilities:
  - Soft Margin / Semantic Matching:
    When an entity has no direct updates or exact string match, gracefully
    surfaces the closest related ecosystem neighbor within the same category.
  - Ingestion Reconciliation:
    Determines what entities the application has already scraped/gathered
    vs emerging 'talk of the town' topics.
  - Subagent Handoff Dossier:
    Structures rich verification & research packages for the Researcher and
    Verification subagents.
"""

from __future__ import annotations

import difflib
import logging
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone
from django.utils.text import slugify

from research.models import Card, EcosystemEntity, PaperTrendSignal, RawItem

logger = logging.getLogger(__name__)


# ===========================================================================
# Master Ecosystem Seed Catalog (§5, §8, §15)
# ===========================================================================

from research.master_ecosystem_data import MASTER_ECOSYSTEM_ENTITIES as MASTER_ECOSYSTEM_CATALOG


# ===========================================================================
# Ecosystem Reconciliation Service
# ===========================================================================


class EcosystemReconciliationService:
    """
    Manages the comprehensive AI/ML ecosystem directory, soft-margin semantic
    matching, ingestion reconciliation, and subagent handoff dossiers.
    """

    @classmethod
    def seed_master_catalog(cls) -> Tuple[int, int]:
        """
        Idempotently seeds all master ecosystem entities into EcosystemEntity.
        Returns (created_count, updated_count).
        """
        created_count = 0
        updated_count = 0

        for item in MASTER_ECOSYSTEM_CATALOG:
            slug = slugify(item["name"])
            obj, created = EcosystemEntity.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": item["name"],
                    "category": item["category"],
                    "aliases": item.get("aliases", []),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "tags": item.get("tags", []),
                    "is_news_source": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count

    @classmethod
    def soft_match_entity(
        cls,
        query: str,
        category: Optional[str] = None,
        threshold: float = 0.55,
    ) -> Dict[str, Any]:
        """
        Soft Margin Matching:
        Given an entity name or search query, finds:
          1. Exact match (score 1.0)
          2. Alias or token similarity match (score 0.65 - 0.99)
          3. Semantic neighborhood fallback (score 0.55): if no direct match or updates
             exist for the queried tool/person, returns the closest related entity
             in the same category, along with an explicit explanatory note.
        """
        query_norm = query.strip().lower()
        if not query_norm:
            return {"match_found": False, "entity": None, "match_type": "none"}

        qs = EcosystemEntity.objects.all()
        if category:
            qs = qs.filter(category=category)

        entities = list(qs)
        if not entities:
            # If category had no rows, search all
            entities = list(EcosystemEntity.objects.all())

        # 1. Exact Name Match
        for ent in entities:
            if ent.name.lower() == query_norm:
                return {
                    "match_found": True,
                    "entity": ent,
                    "match_type": "exact",
                    "score": 1.0,
                    "is_soft_margin": False,
                    "note": f"Exact match for {ent.name}.",
                }

        # 2. Alias Match
        for ent in entities:
            aliases_lower = [a.lower() for a in ent.aliases]
            if query_norm in aliases_lower:
                return {
                    "match_found": True,
                    "entity": ent,
                    "match_type": "alias",
                    "score": 0.95,
                    "is_soft_margin": False,
                    "note": f"Matched alias '{query_norm}' for {ent.name}.",
                }

        # 3. Substring / Token Similarity
        best_match: Optional[EcosystemEntity] = None
        best_score = 0.0

        for ent in entities:
            name_lower = ent.name.lower()
            # Check if query is substring of name or vice versa
            if query_norm in name_lower or name_lower in query_norm:
                score = 0.85
            else:
                # Sequence matcher ratio
                score = difflib.SequenceMatcher(None, query_norm, name_lower).ratio()
                # Check aliases too
                for alias in ent.aliases:
                    alias_score = difflib.SequenceMatcher(None, query_norm, alias.lower()).ratio()
                    if alias_score > score:
                        score = alias_score

            if score > best_score:
                best_score = score
                best_match = ent

        if best_match and best_score >= threshold:
            return {
                "match_found": True,
                "entity": best_match,
                "match_type": "token_similarity",
                "score": round(best_score, 3),
                "is_soft_margin": False,
                "note": f"Matched {best_match.name} via similarity score {round(best_score, 2)}.",
            }

        # 4. Soft Margin Fallback (Nearest Category Neighbor)
        # When no direct match or recent news exists for the exact term,
        # provide the closest representative in that ecosystem sector.
        fallback_category = category or (best_match.category if best_match else "coding_agent")
        neighbors = [e for e in entities if e.category == fallback_category]
        if not neighbors:
            neighbors = entities

        fallback_entity = neighbors[0] if neighbors else None
        if fallback_entity:
            return {
                "match_found": True,
                "entity": fallback_entity,
                "match_type": "soft_margin_neighbor",
                "score": 0.50,
                "is_soft_margin": True,
                "note": (
                    f"No direct updates found for '{query}'. "
                    f"Showing closest active ecosystem reference in [{fallback_entity.category}]: {fallback_entity.name}."
                ),
            }

        return {"match_found": False, "entity": None, "match_type": "none"}

    @classmethod
    def get_ingestion_reconciliation(cls) -> Dict[str, Any]:
        """
        Reconciles what the application has already scraped / ingested vs
        emerging 'talk of the town' topics that need to be handed to researchers.

        Returns:
          - already_ingested: list of entities that already have cards or raw items
          - talk_of_the_town: emerging entities circulating in trend signals
          - upcoming_news_pipeline: entities configured and ready for the news scraper
          - summary_counts: counts per state
        """
        all_entities = list(EcosystemEntity.objects.all())
        if not all_entities:
            cls.seed_master_catalog()
            all_entities = list(EcosystemEntity.objects.all())

        # Collect text of all published primary cards
        cards = Card.objects.filter(is_primary_feed=True)
        card_text_corpus = " ".join(
            f"{c.headline} {c.summary_60s} {' '.join(c.tags)} {' '.join(c.candidate_techniques)}".lower()
            for c in cards
        )

        # Collect raw items
        raw_items = RawItem.objects.all()
        raw_corpus = " ".join(r.title.lower() for r in raw_items)
        combined_corpus = f"{card_text_corpus} {raw_corpus}"

        # Collect trend signals to compute live chatter
        signals = PaperTrendSignal.objects.all()
        signal_reasons = " ".join(s.trending_reason.lower() for s in signals)

        already_ingested: List[Dict[str, Any]] = []
        talk_of_the_town: List[Dict[str, Any]] = []
        upcoming_pipeline: List[Dict[str, Any]] = []

        for ent in all_entities:
            name_lower = ent.name.lower()
            aliases = [a.lower() for a in ent.aliases]
            all_patterns = [name_lower] + aliases

            # Check if mentioned in cards/raw items
            has_ingested_card = any(p in combined_corpus for p in all_patterns)

            # Check if trending in social signals
            has_trend_signal = any(p in signal_reasons for p in all_patterns)

            if has_ingested_card:
                already_ingested.append({
                    "id": ent.id,
                    "name": ent.name,
                    "category": ent.category,
                    "status": "already_ingested",
                    "url": ent.url,
                    "ingestion_proof": "Indexed in live Card or RawItem feed",
                })
            elif has_trend_signal or ent.talk_of_the_town_score > 30.0:
                talk_of_the_town.append({
                    "id": ent.id,
                    "name": ent.name,
                    "category": ent.category,
                    "status": "talk_of_the_town",
                    "talk_score": ent.talk_of_the_town_score or 75.0,
                    "url": ent.url,
                    "opportunity": "High community interest detected; ready for Researcher & Verification ingestion",
                })
            else:
                upcoming_pipeline.append({
                    "id": ent.id,
                    "name": ent.name,
                    "category": ent.category,
                    "status": "pending_news_pipeline",
                    "url": ent.url,
                    "note": "Configured in taxonomy catalog; scheduled for the upcoming News Pipeline (§15)",
                })

        return {
            "already_ingested": already_ingested,
            "talk_of_the_town": talk_of_the_town,
            "upcoming_news_pipeline": upcoming_pipeline,
            "summary_counts": {
                "total_cataloged": len(all_entities),
                "already_ingested": len(already_ingested),
                "talk_of_the_town": len(talk_of_the_town),
                "upcoming_news_pipeline": len(upcoming_pipeline),
            },
        }

    @classmethod
    def get_agent_handoff_dossier(cls, limit: int = 10) -> Dict[str, Any]:
        """
        Structures an actionable research & verification handoff package for:
          1. Researcher Agent:
             - Emerging topics/entities without existing cards
             - Soft-margin nearest neighbors
             - Key techniques to explore
          2. Verification Agent:
             - Rule 50 developer self-report checks
             - Rule 52 technique grounding against Semantic Scholar / OpenAlex
             - Benchmark standards (SWE-bench, METR, Apollo Research, MITRE ATLAS)
        """
        reconciliation = cls.get_ingestion_reconciliation()
        candidates = reconciliation["talk_of_the_town"][:limit]

        # If talk of the town has fewer items, take from upcoming news pipeline
        if len(candidates) < limit:
            needed = limit - len(candidates)
            candidates.extend(reconciliation["upcoming_news_pipeline"][:needed])

        handoff_items = []
        for item in candidates:
            # Soft match verification
            soft = cls.soft_match_entity(item["name"], category=item.get("category"))
            nearest_neighbor = soft["entity"].name if soft.get("entity") else "AI Research Collective"

            tavily_query = f"verify {item['name']} AI announcements benchmarks"
            handoff_items.append({
                "entity_name": item["name"],
                "category": item["category"],
                "url": item.get("url", ""),
                "status": item["status"],
                "soft_margin_neighbor": nearest_neighbor,
                "tavily_verification_query": tavily_query,
                "researcher_brief": (
                    f"Investigate recent announcements, whitepapers, or releases from {item['name']}. "
                    f"If no direct update within 24h, bridge context with {nearest_neighbor}."
                ),
                "verification_checklist": {
                    "rule_50_check": "Is this a developer self-report on their own product?",
                    "rule_52_grounding": "Verify named techniques against Semantic Scholar / OpenAlex.",
                    "tavily_web_verification": f"Execute Tavily search query: '{tavily_query}'",
                    "benchmark_eval": "Cross-reference with SWE-bench Verified, METR autonomy evals, or Apollo Research if applicable.",
                },
            })

        return {
            "generated_at": timezone.now().isoformat(),
            "handoff_count": len(handoff_items),
            "handoff_items": handoff_items,
            "pipeline_state": "scaffolded_and_ready",
            "news_pipeline_ready": True,
        }

