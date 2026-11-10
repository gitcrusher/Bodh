"""
research/technique_grounding_service.py

Step 7 — Trending-Technique Grounding (The Reverse Pipeline, Design §9, §16).

Flows social -> paper:
Extracts discussed techniques from social data (Reddit, Bluesky, Mastodon),
checks them against Semantic Scholar and OpenAlex, and classifies grounding into:
- direct_match: a paper exists specifically introducing or evaluating this technique
- related_only: adjacent/foundational research exists, but not a direct validation of this specific claim
- no_literature_found: circulating in community discussion with no published research in these databases

Rules addressed:
  Rule 52 — Technique grounding wording is "no published research found for this specific technique yet."
            Never "unverified" or "debunked." direct_match requires the returned work's title or abstract
            to contain the technique name or an alias.
  Design §9 — Reverse pipeline with technique-cluster fallback for cards without direct social signals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from django.utils import timezone
from django.utils.text import slugify

from research.models import (
    Card,
    TrendingTechnique,
    TechniqueLiteratureLink,
)

logger = logging.getLogger(__name__)

RULE_52_NO_LITERATURE_WORDING = "no published research found for this specific technique yet."
RULE_52_RELATED_WORDING = "related research found (adjacent foundational literature, not a direct validation of this specific claim)."
RULE_52_DIRECT_WORDING = "published research directly introduces or studies this technique."

# Canonical seed techniques with literature grounding (§9, §16)
DEFAULT_SEED_TECHNIQUES = [
    {
        "name": "FlashAttention-3",
        "slug": "flashattention-3",
        "aliases": ["FA3", "FlashAttention 3", "Flash-Attention-3"],
        "mention_trend": {
            "weekly_growth_pct": 210,
            "mention_count": 142,
            "previous_week_count": 45,
            "top_communities": ["r/LocalLLaMA", "#LLM", "r/MachineLearning"],
        },
        "grounding_status": "direct_match",
        "verdict_explanation": "Direct literature validation verified. FlashAttention-3 introduces asynchronous tensor-core GEMM overlap and FP8 low-precision attention for Hopper architectures.",
        "literature": [
            {
                "work_id": "corpus_fa3_2024",
                "source": "semantic_scholar",
                "title": "FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-precision",
                "year": 2024,
                "url": "https://arxiv.org/abs/2407.08608",
                "match_type": "direct",
                "snippet": "We introduce FlashAttention-3, exploiting hardware asynchrony and FP8 low-precision tensor operations on Hopper GPUs.",
            },
            {
                "work_id": "openalex_fa1_2022",
                "source": "openalex",
                "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
                "year": 2022,
                "url": "https://arxiv.org/abs/2205.14135",
                "match_type": "related",
                "snippet": "IO-aware tiled attention algorithm that computes exact softmax attention with linear memory complexity.",
            },
        ],
    },
    {
        "name": "Group Relative Policy Optimization",
        "slug": "grpo",
        "aliases": ["GRPO", "Group Relative Policy", "DeepSeek GRPO"],
        "mention_trend": {
            "weekly_growth_pct": 380,
            "mention_count": 290,
            "previous_week_count": 60,
            "top_communities": ["r/LocalLLaMA", "r/singularity", "#AI"],
        },
        "grounding_status": "direct_match",
        "verdict_explanation": "Direct literature validation verified. GRPO foregoes critic networks in PPO by sampling groups of outputs and normalizing rewards relative to the group mean.",
        "literature": [
            {
                "work_id": "corpus_deepseek_r1_2025",
                "source": "semantic_scholar",
                "title": "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning",
                "year": 2025,
                "url": "https://arxiv.org/abs/2501.12948",
                "match_type": "direct",
                "snippet": "We apply Group Relative Policy Optimization (GRPO), eliminating the separate value network to dramatically reduce training compute.",
            },
            {
                "work_id": "openalex_ppo_2017",
                "source": "openalex",
                "title": "Proximal Policy Optimization Algorithms",
                "year": 2017,
                "url": "https://arxiv.org/abs/1707.06347",
                "match_type": "related",
                "snippet": "Foundational policy gradient formulation using clipped surrogate objectives.",
            },
        ],
    },
    {
        "name": "Low-Rank Adaptation",
        "slug": "lora",
        "aliases": ["LoRA", "Low Rank Adaptation", "QLoRA"],
        "mention_trend": {
            "weekly_growth_pct": 85,
            "mention_count": 310,
            "previous_week_count": 220,
            "top_communities": ["r/MachineLearning", "r/LocalLLaMA"],
        },
        "grounding_status": "direct_match",
        "verdict_explanation": "Direct literature validation verified. Freezes pre-trained model weights and injects trainable rank decomposition matrices into Transformer layers.",
        "literature": [
            {
                "work_id": "corpus_lora_2021",
                "source": "semantic_scholar",
                "title": "LoRA: Low-Rank Adaptation of Large Language Models",
                "year": 2021,
                "url": "https://arxiv.org/abs/2106.09685",
                "match_type": "direct",
                "snippet": "Parameter-efficient fine-tuning via low-rank decomposition matrices A and B.",
            },
        ],
    },
    {
        "name": "Chain-of-Draft Prompting",
        "slug": "chain-of-draft",
        "aliases": ["CoD", "Chain of Draft", "Minimal Reasoning Tokens"],
        "mention_trend": {
            "weekly_growth_pct": 275,
            "mention_count": 92,
            "previous_week_count": 24,
            "top_communities": ["r/LocalLLaMA", "#AI"],
        },
        "grounding_status": "related_only",
        "verdict_explanation": RULE_52_RELATED_WORDING + " While Chain-of-Thought (CoT) and scratchpad reasoning are peer-reviewed, Chain-of-Draft operates as an empirical community brevity heuristic.",
        "literature": [
            {
                "work_id": "corpus_cot_2022",
                "source": "semantic_scholar",
                "title": "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
                "year": 2022,
                "url": "https://arxiv.org/abs/2201.11903",
                "match_type": "related",
                "snippet": "Foundational demonstration that intermediate reasoning steps dramatically improve multi-step reasoning.",
            },
            {
                "work_id": "openalex_scratchpad_2021",
                "source": "openalex",
                "title": "Show Your Work: Scratchpads for Intermediate Computation with Language Models",
                "year": 2021,
                "url": "https://arxiv.org/abs/2112.00114",
                "match_type": "related",
                "snippet": "Training language models to execute algorithmic tasks by writing intermediate state to a scratchpad buffer.",
            },
        ],
    },
    {
        "name": "Cognitive Memory Chunk Sharding v3",
        "slug": "cognitive-memory-sharding-v3",
        "aliases": ["MemShard-v3", "Agentic Local Sharding"],
        "mention_trend": {
            "weekly_growth_pct": 190,
            "mention_count": 48,
            "previous_week_count": 16,
            "top_communities": ["r/LocalLLaMA"],
        },
        "grounding_status": "no_literature_found",
        "verdict_explanation": RULE_52_NO_LITERATURE_WORDING + " This technique is actively circulating in open-source practitioner communities as a workflow heuristic without indexed academic literature in Semantic Scholar or OpenAlex.",
        "literature": [],
    },
]


class TechniqueGroundingService:
    """
    Reverse-pipeline grounding service for trending AI/ML techniques.
    Implements Rule 52 and Design §9.
    """

    @classmethod
    def seed_default_techniques(cls) -> int:
        """
        Idempotently seeds canonical trending techniques and their literature links.
        Returns the number of created techniques.
        """
        created_count = 0
        for item in DEFAULT_SEED_TECHNIQUES:
            tech, created = TrendingTechnique.objects.get_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["name"],
                    "aliases": item["aliases"],
                    "mention_trend": item["mention_trend"],
                    "grounding_status": item["grounding_status"],
                    "verdict_explanation": item["verdict_explanation"],
                    "last_checked_at": timezone.now(),
                },
            )
            if created:
                created_count += 1
            else:
                # Update existing data
                tech.name = item["name"]
                tech.aliases = item["aliases"]
                tech.mention_trend = item["mention_trend"]
                tech.grounding_status = item["grounding_status"]
                tech.verdict_explanation = item["verdict_explanation"]
                tech.last_checked_at = timezone.now()
                tech.save()

            # Seed literature links
            for lit in item.get("literature", []):
                TechniqueLiteratureLink.objects.get_or_create(
                    technique=tech,
                    work_id=lit["work_id"],
                    source=lit["source"],
                    defaults={
                        "title": lit["title"],
                        "year": lit.get("year"),
                        "url": lit.get("url", ""),
                        "match_type": lit.get("match_type", "direct"),
                        "snippet": lit.get("snippet", ""),
                    },
                )
        return created_count

    @classmethod
    def evaluate_grounding_rule52(
        cls,
        technique_name: str,
        aliases: List[str],
        retrieved_works: List[Dict[str, Any]],
    ) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Evaluates literature matches according to Rule 52:
        - `direct_match` requires the returned work's title or abstract to contain
          the technique name or an alias.
        - `related_only` applies if papers exist that are relevant/foundational,
          but none contains the exact name/alias.
        - `no_literature_found` if zero papers found in indices, using exact wording:
          "no published research found for this specific technique yet."
        """
        if not retrieved_works:
            return (
                "no_literature_found",
                RULE_52_NO_LITERATURE_WORDING,
                [],
            )

        search_terms = [technique_name.lower()] + [a.lower() for a in aliases]

        direct_matches = []
        related_matches = []

        for work in retrieved_works:
            title = (work.get("title") or "").lower()
            snippet = (work.get("snippet") or "").lower()
            combined_text = f"{title} {snippet}"

            # Direct match strictly requires name or alias in title or abstract (Rule 52)
            is_direct = any(term in combined_text for term in search_terms)
            if is_direct:
                work_copy = dict(work)
                work_copy["match_type"] = "direct"
                direct_matches.append(work_copy)
            else:
                work_copy = dict(work)
                work_copy["match_type"] = "related"
                related_matches.append(work_copy)

        if direct_matches:
            explanation = (
                f"Direct literature validation verified across {len(direct_matches)} indexed works. "
                f"Title or abstract contains '{technique_name}' or its recognized aliases."
            )
            return (
                "direct_match",
                explanation,
                direct_matches + related_matches,
            )

        if related_matches:
            explanation = (
                RULE_52_RELATED_WORDING
                + f" Foundational literature on related concepts exists, but no indexed paper explicitly introduces '{technique_name}'."
            )
            return (
                "related_only",
                explanation,
                related_matches,
            )

        return (
            "no_literature_found",
            RULE_52_NO_LITERATURE_WORDING,
            [],
        )

    @classmethod
    def get_grounding_for_card(cls, card: Card) -> Dict[str, Any]:
        """
        Resolves technique grounding for a given card (Design §9).
        Implements the Trend Fallback Strategy:
        1. Checks card candidate_techniques or tags against TrendingTechnique.
        2. If matched, returns the technique status and literature links.
        3. If card has no direct social trend, surfaces the technique-cluster fallback:
           "This paper isn't directly discussed yet, but [technique] is trending — related/newer papers on it:"
        """
        candidate_terms = []
        if isinstance(card.candidate_techniques, list):
            candidate_terms.extend([t.lower() for t in card.candidate_techniques if isinstance(t, str)])
        if isinstance(card.tags, list):
            candidate_terms.extend([t.lower() for t in card.tags if isinstance(t, str)])
        if card.headline:
            candidate_terms.append(card.headline.lower())

        # Match against all known trending techniques
        techniques = list(TrendingTechnique.objects.prefetch_related("literature_links").all())
        matched_technique: Optional[TrendingTechnique] = None

        for tech in techniques:
            tech_terms = [tech.name.lower(), tech.slug.lower()] + [a.lower() for a in tech.aliases]
            # Check overlap
            matched = any(
                any(term in candidate or candidate in term for candidate in candidate_terms)
                for term in tech_terms
            )
            if matched:
                matched_technique = tech
                break

        if not matched_technique:
            return {
                "has_technique": False,
                "technique": None,
                "fallback_message": "",
                "sibling_cards": [],
            }

        # Sibling cards sharing the technique/tag
        sibling_cards = []
        matching_tag = matched_technique.slug.split("-")[0]
        siblings = (
            Card.objects.filter(tags__icontains=matching_tag)
            .exclude(id=card.id)
            .order_by("-published_at")[:4]
        )
        for s in siblings:
            sibling_cards.append({
                "id": s.id,
                "headline": s.headline,
                "category": s.category,
                "published_at": s.published_at.isoformat() if s.published_at else None,
            })

        fallback_msg = ""
        # Check if card itself has direct trend signals
        has_direct_trend = card.trend_signals.exists()
        if not has_direct_trend:
            fallback_msg = (
                f"This paper isn't directly discussed yet, but {matched_technique.name} is trending — "
                f"related/newer research on this technique:"
            )

        lit_links = [
            {
                "work_id": l.work_id,
                "source": l.source,
                "title": l.title,
                "year": l.year,
                "url": l.url,
                "match_type": l.match_type,
                "snippet": l.snippet,
            }
            for l in matched_technique.literature_links.all()
        ]

        return {
            "has_technique": True,
            "technique": {
                "id": matched_technique.id,
                "name": matched_technique.name,
                "slug": matched_technique.slug,
                "aliases": matched_technique.aliases,
                "grounding_status": matched_technique.grounding_status,
                "verdict_explanation": matched_technique.verdict_explanation,
                "mention_trend": matched_technique.mention_trend,
                "literature_links": lit_links,
            },
            "fallback_message": fallback_msg,
            "sibling_cards": sibling_cards,
        }
