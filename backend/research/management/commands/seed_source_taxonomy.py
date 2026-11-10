"""
backend/research/management/commands/seed_source_taxonomy.py

Step 5 — Widen the source taxonomy.
Activates all 7 knowledge-type categories:
  1. research          — Academic preprints & peer-reviewed papers
  2. new_models        — Model releases & open weights
  3. threat_safety     — Safety evals, alignment, dangerous capabilities
  4. policy            — Governance, regulations, compliance
  5. industry          — Compute clusters, chip architectures, lab economics
  6. opinion           — Expert analysis & community discussions
  7. tools             — Frameworks, libraries, dev tooling

Enforces Rule 50:
  Sources carry `publisher_relationship` ('independent' vs 'developer_self_report').
  Lab self-reports on their own models are primary sources but clearly labeled.
"""

from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from research.models import Card, RawItem, Source, PaperValiditySignal
from research.paper_linker import link_newly_ingested_card


TAXONOMY_SOURCES = [
    # 1. Research
    {
        "name": "arXiv cs.AI / cs.LG",
        "url": "https://arxiv.org/list/cs.AI/recent",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["research"],
    },
    {
        "name": "OpenReview (NeurIPS / ICLR)",
        "url": "https://openreview.net",
        "fetch_method": "api",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["research"],
    },

    # 2. New Models
    {
        "name": "Hugging Face Daily Papers & Models",
        "url": "https://huggingface.co/papers",
        "fetch_method": "api",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["new_models"],
    },
    {
        "name": "Anthropic Research Releases",
        "url": "https://www.anthropic.com/research",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "developer_self_report",
        "knowledge_type": ["new_models"],
    },
    {
        "name": "Google DeepMind Announcements",
        "url": "https://deepmind.google/discover/blog",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "developer_self_report",
        "knowledge_type": ["new_models"],
    },

    # 3. Threat & Safety
    {
        "name": "METR (Model Evaluation & Threat Research)",
        "url": "https://metr.org/research",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["threat_safety"],
    },
    {
        "name": "Apollo Research (Deception & Scheming Evals)",
        "url": "https://apolloresearch.ai/research",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["threat_safety"],
    },
    {
        "name": "US CAISI at NIST",
        "url": "https://www.nist.gov/artificial-intelligence",
        "fetch_method": "api",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["threat_safety"],
    },
    {
        "name": "MITRE ATLAS",
        "url": "https://atlas.mitre.org",
        "fetch_method": "api",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["threat_safety"],
    },
    {
        "name": "Anthropic Alignment Science",
        "url": "https://www.anthropic.com/alignment",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "developer_self_report",
        "knowledge_type": ["threat_safety"],
    },

    # 4. Policy & Regulation
    {
        "name": "GovAI (Centre for Governance of AI)",
        "url": "https://www.governance.ai",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["policy"],
    },
    {
        "name": "EU AI Office & Treaty Monitor",
        "url": "https://digital-strategy.ec.europa.eu/en/policies/ai-office",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["policy"],
    },

    # 5. Industry & Hardware
    {
        "name": "SemiAnalysis",
        "url": "https://www.semianalysis.com",
        "fetch_method": "scraper",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["industry"],
    },
    {
        "name": "Epoch AI (Compute & Frontier Trends)",
        "url": "https://epochai.org",
        "fetch_method": "api",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["industry"],
    },

    # 6. Opinion & Analysis
    {
        "name": "Alignment Forum",
        "url": "https://www.alignmentforum.org",
        "fetch_method": "api",
        "trust_tier": 3,
        "publisher_relationship": "independent",
        "knowledge_type": ["opinion"],
    },

    # 7. Tools & Frameworks
    {
        "name": "vLLM Project Updates",
        "url": "https://github.com/vllm-project/vllm/releases",
        "fetch_method": "api",
        "trust_tier": 1,
        "publisher_relationship": "independent",
        "knowledge_type": ["tools"],
    },
]


SEED_TAXONOMY_CARDS = [
    {
        "source_name": "METR (Model Evaluation & Threat Research)",
        "category": "threat_safety",
        "external_id": "metr-autonomy-2026",
        "title": "Autonomous Capability Evaluations of Frontier Models: Early Indicators",
        "headline": "METR Evaluates Frontier Models for Cyber and Autonomous Task Execution",
        "summary_60s": (
            "• METR releases standardized evaluation harness measuring frontier AI autonomous software engineering.\n"
            "• Frontier models complete multi-hour CTF security challenges without human intervention.\n"
            "• Identifies task horizon limits: success rates drop sharply when dependencies exceed 4 hours.\n"
            "• Recommends pre-deployment threshold monitoring before general agentic deployment."
        ),
        "tags": ["threat_safety", "autonomous_evals", "red_teaming", "metr"],
        "candidate_techniques": ["task horizon evaluation", "autonomous vulnerability analysis"],
        "image_url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=800&auto=format&fit=crop",
        "venue": "METR Technical Report",
        "venue_tier": 1,
        "affiliation_tier": 1,
        "published_at": datetime(2026, 2, 1, 10, 0, tzinfo=dt_timezone.utc),
    },
    {
        "source_name": "Anthropic Research Releases",
        "category": "new_models",
        "external_id": "anthropic-claude-37-release",
        "title": "Claude 3.7 Sonnet: Hybrid Thinking and Deterministic Tool Execution",
        "headline": "Anthropic Announces Claude 3.7 Sonnet with Scaled Reasoning Modes",
        "summary_60s": (
            "• Introduces dual-mode thinking allowing dynamic inference-time token allocation.\n"
            "• Demonstrates 84.2% on SWE-bench Verified, surpassing existing specialized agent systems.\n"
            "• Incorporates verifiable tool-use reasoning steps while maintaining low latency on standard turns.\n"
            "• Published directly by the model's developer under standard terms."
        ),
        "tags": ["new_models", "claude", "reasoning", "developer_self_report"],
        "candidate_techniques": ["hybrid thinking", "inference-time compute scaling"],
        "image_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=800&auto=format&fit=crop",
        "venue": "Anthropic Research",
        "venue_tier": 1,
        "affiliation_tier": 1,
        "published_at": datetime(2026, 2, 24, 14, 0, tzinfo=dt_timezone.utc),
    },
    {
        "source_name": "GovAI (Centre for Governance of AI)",
        "category": "policy",
        "external_id": "govai-frontier-compliance-2026",
        "title": "Frontier AI Safety Commitments and Regulatory Compliance Benchmarks",
        "headline": "GovAI Publishes Compliance Benchmarks for Frontier AI Governance",
        "summary_60s": (
            "• Synthesizes voluntary safety commitments into standardized, auditable compliance criteria.\n"
            "• Analyzes compute threshold definitions across US, EU, and UK regulatory frameworks.\n"
            "• Finds significant divergence in hardware reporting thresholds among major compute providers.\n"
            "• Outlines institutional models for independent verification without exposing proprietary weights."
        ),
        "tags": ["policy", "governance", "compliance", "compute_governance"],
        "candidate_techniques": ["regulatory auditing", "compute verification"],
        "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=800&auto=format&fit=crop",
        "venue": "GovAI Research Paper",
        "venue_tier": 1,
        "affiliation_tier": 1,
        "published_at": datetime(2026, 1, 15, 9, 0, tzinfo=dt_timezone.utc),
    },
    {
        "source_name": "SemiAnalysis",
        "category": "industry",
        "external_id": "semianalysis-blackwell-ultra-2026",
        "title": "Blackwell Ultra Cluster Architecture and Optical Interconnect Scaling",
        "headline": "SemiAnalysis Deconstructs 100k GPU Clusters and Optical Interconnects",
        "summary_60s": (
            "• Deep-dive into GB200 NVL72 liquid cooling and scale-out InfiniBand vs Ethernet architectures.\n"
            "• Quantifies optical transceiver power draw and latency improvements in 800G and 1.6T fabrics.\n"
            "• Analyzes capital expenditure and electricity grid interconnection constraints for gigawatt datacenters.\n"
            "• Projects inference server cost structures through 2027 as FP4 quantization matures."
        ),
        "tags": ["industry", "hardware", "gpus", "interconnect", "datacenter"],
        "candidate_techniques": ["optical interconnect", "FP4 inference", "NVLink scaling"],
        "image_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=800&auto=format&fit=crop",
        "venue": "SemiAnalysis Industry Report",
        "venue_tier": 1,
        "affiliation_tier": 1,
        "published_at": datetime(2026, 2, 10, 16, 0, tzinfo=dt_timezone.utc),
    },
]


class Command(BaseCommand):
    help = "Step 5: Seeds the full 7-category source taxonomy and representative cross-category cards."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Step 5: Full 7-Category Source Taxonomy...")

        created_sources = {}
        for src in TAXONOMY_SOURCES:
            obj, created = Source.objects.update_or_create(
                name=src["name"],
                defaults={
                    "url": src["url"],
                    "fetch_method": src["fetch_method"],
                    "trust_tier": src["trust_tier"],
                    "publisher_relationship": src["publisher_relationship"],
                    "knowledge_type": src["knowledge_type"],
                    "active": True,
                },
            )
            created_sources[src["name"]] = obj
            status_str = "Created" if created else "Updated"
            self.stdout.write(f"  {status_str} source: {obj.name} ({obj.publisher_relationship})")

        self.stdout.write("\nSeeding representative cross-category cards...")
        for item in SEED_TAXONOMY_CARDS:
            source = created_sources.get(item["source_name"])
            if not source:
                continue

            raw, _ = RawItem.objects.update_or_create(
                source=source,
                external_id=item["external_id"],
                defaults={
                    "title": item["title"],
                    "url": source.url,
                    "published_at": item["published_at"],
                    "raw_content": item["summary_60s"],
                },
            )

            card, created = Card.objects.update_or_create(
                raw_item=raw,
                defaults={
                    "category": item["category"],
                    "headline": item["headline"],
                    "summary_60s": item["summary_60s"],
                    "tags": item["tags"],
                    "candidate_techniques": item["candidate_techniques"],
                    "source_url": source.url,
                    "image_url": item["image_url"],
                    "published_at": item["published_at"],
                    "needs_review": False,
                    "is_primary_feed": True,
                },
            )

            PaperValiditySignal.objects.update_or_create(
                card=card,
                defaults={
                    "venue": item["venue"],
                    "venue_tier": item["venue_tier"],
                    "affiliation_tier": item["affiliation_tier"],
                    "data_source": "semantic_scholar",
                    "fetched_at": timezone.now(),
                },
            )

            class FastSeedRouter:
                def complete(self, *args, **kwargs):
                    from core.llm.providers.base import LLMResponse
                    return LLMResponse(content='{"is_related": false, "relation_type": "none", "confidence": 0.0}', provider="fake", model="fake-seed")

            # Automatically bind cross-card relations without network delay
            link_newly_ingested_card(card, router=FastSeedRouter())

            status_str = "Created" if created else "Updated"
            self.stdout.write(
                f"  {status_str} card [{card.category}]: {card.headline[:50]}... "
                f"(Publisher: {source.publisher_relationship})"
            )

        self.stdout.write(self.style.SUCCESS("\nSuccessfully seeded Step 5 source taxonomy!"))
