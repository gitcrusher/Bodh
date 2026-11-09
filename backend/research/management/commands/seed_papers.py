"""
backend/research/management/commands/seed_papers.py

Seeds the local database with representative AI research papers,
validity signals, paper chat chunks, and automatically binds dynamic links
via the ingest-time linking engine (Rule 57).
"""

from datetime import datetime, timezone, timedelta
from django.core.management.base import BaseCommand
from research.models import Card, RawItem, Source, PaperValiditySignal
from research.paper_linker import link_newly_ingested_card


class Command(BaseCommand):
    help = "Seeds database with representative research papers and dynamic links."

    def handle(self, *args, **options):
        self.stdout.write("Seeding research sources and papers...")

        source, _ = Source.objects.get_or_create(
            name="arXiv CS.AI",
            defaults={
                "url": "https://arxiv.org/list/cs.AI/recent",
                "fetch_method": "scraper",
                "trust_tier": 1,
                "publisher_relationship": "independent",
                "active": True,
            },
        )

        papers_data = [
            {
                "external_id": "1706.03762",
                "title": "Attention Is All You Need",
                "url": "https://arxiv.org/abs/1706.03762",
                "headline": "Attention Is All You Need: The Transformer Architecture",
                "summary_60s": (
                    "• Proposes the Transformer, eliminating recurrence and convolution in sequence models.\n"
                    "• Employs multi-head self-attention to draw global dependencies across all tokens.\n"
                    "• Reaches SOTA on WMT English-to-German after only 12 hours on 8 GPUs.\n"
                    "• Foundation for modern LLMs including GPT, Claude, BERT, and Gemini."
                ),
                "tags": ["transformers", "attention", "nlp", "architecture"],
                "candidate_techniques": ["multi-head attention", "scaled-dot-product attention", "transformer architecture"],
                "image_url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=800&auto=format&fit=crop",
                "venue": "NeurIPS 2017",
                "venue_tier": 1,
                "affiliation_tier": 1,
                "published_at": datetime(2017, 6, 12, 17, 0, tzinfo=timezone.utc),
                "is_primary_feed": False,
            },
            {
                "external_id": "2106.09685",
                "title": "LoRA: Low-Rank Adaptation of Large Language Models",
                "url": "https://arxiv.org/abs/2106.09685",
                "headline": "LoRA: Low-Rank Adaptation of Large Language Models",
                "summary_60s": (
                    "• Freezes pre-trained weights and injects trainable rank decomposition matrices.\n"
                    "• Reduces the number of trainable parameters by 10,000x and GPU memory by 3x.\n"
                    "• Matches or exceeds full fine-tuning performance on RoBERTa, DeBERTa, and GPT-3.\n"
                    "• Zero added inference latency by folding weights Delta W = B * A at deployment."
                ),
                "tags": ["fine_tuning", "peft", "efficiency"],
                "candidate_techniques": ["low-rank adaptation", "rank-decomposition matrices", "peft fine-tuning"],
                "image_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=800&auto=format&fit=crop",
                "venue": "ICLR 2022",
                "venue_tier": 1,
                "affiliation_tier": 1,
                "published_at": datetime(2021, 6, 17, 18, 0, tzinfo=timezone.utc),
                "is_primary_feed": False,
            },
            {
                "external_id": "2407.08608",
                "title": "FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-Precision",
                "url": "https://arxiv.org/abs/2407.08608",
                "headline": "FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-Precision",
                "summary_60s": (
                    "• Exploits Hopper architecture tensor cores (FP16/FP8) with asynchronous execution.\n"
                    "• Overlaps GEMM and softmax computations across warp-group specialization.\n"
                    "• Achieves up to 740 TFLOPs/s (75% of H100 theoretical peak).\n"
                    "• Delivers 1.5x–2.0x speedup over FlashAttention-2 with identical numerical precision."
                ),
                "tags": ["hardware_acceleration", "gpu", "efficiency", "h100"],
                "candidate_techniques": ["sram-tiling", "warp-specialization", "fp8-attention"],
                "image_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=800&auto=format&fit=crop",
                "venue": "arXiv preprint · Stanford University",
                "venue_tier": 1,
                "affiliation_tier": 1,
                "published_at": datetime(2024, 7, 12, 14, 0, tzinfo=timezone.utc),
                "is_primary_feed": True,
            },
            {
                "external_id": "2501.12948",
                "title": "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning",
                "url": "https://arxiv.org/abs/2501.12948",
                "headline": "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Pure RL",
                "summary_60s": (
                    "• Demonstrates reasoning emergence purely from large-scale RL without supervised cold-start.\n"
                    "• Employs Group Relative Policy Optimization (GRPO) with verified reward models.\n"
                    "• Scores 97.3% on MATH-500 and 79.8% on AIME 2024, matching frontier proprietary models.\n"
                    "• Open-weights distilled models from 1.5B to 70B parameters for open research."
                ),
                "tags": ["reasoning", "reinforcement_learning", "grpo", "reasoning_models"],
                "candidate_techniques": ["grpo reinforcement learning", "reasoning distillation", "rule-based reward verification"],
                "image_url": "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?q=80&w=800&auto=format&fit=crop",
                "venue": "DeepSeek AI Research",
                "venue_tier": 1,
                "affiliation_tier": 2,
                "published_at": datetime(2025, 1, 22, 10, 0, tzinfo=timezone.utc),
                "is_primary_feed": True,
            },
            {
                "external_id": "2412.19437",
                "title": "The Llama 3 Herd of Models: Advancing Open Foundation and Fine-Tuned Models",
                "url": "https://arxiv.org/abs/2412.19437",
                "headline": "Llama 3.3: 70B Frontier Capabilities with Industry Efficiency",
                "summary_60s": (
                    "• Introduces 70B dense architecture delivering performance on par with previous 405B flagship.\n"
                    "• Employs Grouped-Query Attention (GQA) with 128k context length support natively.\n"
                    "• Demonstrates leading mathematical reasoning, coding, and multilingual understanding.\n"
                    "• Released under permissive community license powering global edge deployments."
                ),
                "tags": ["open_weights", "foundation_models", "llama"],
                "candidate_techniques": ["grouped-query attention", "direct preference optimization", "open-weights foundation model"],
                "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=800&auto=format&fit=crop",
                "venue": "Meta AI Research",
                "venue_tier": 1,
                "affiliation_tier": 1,
                "published_at": datetime(2024, 12, 6, 16, 0, tzinfo=timezone.utc),
                "is_primary_feed": True,
            },
        ]

        created_cards = []
        now = datetime.now(timezone.utc)

        for p in papers_data:
            # Rule 59: Authoritative research paper publishing date
            pub_date = p.get("published_at") or (now - timedelta(hours=p.get("hours_ago", 0)))
            raw_item, _ = RawItem.objects.update_or_create(
                source=source,
                external_id=p["external_id"],
                defaults={
                    "title": p["title"],
                    "url": p["url"],
                    "published_at": pub_date,
                    "status": "processed",
                    "raw_content": f"Abstract for {p['title']}. Details technical implementation and evaluations.",
                    "figure_url": p["image_url"],
                },
            )

            card, created = Card.objects.update_or_create(
                raw_item=raw_item,
                defaults={
                    "category": "research",
                    "headline": p["headline"],
                    "summary_60s": p["summary_60s"],
                    "tags": p["tags"],
                    "candidate_techniques": p["candidate_techniques"],
                    "source_url": p["url"],
                    "image_url": p["image_url"],
                    "published_at": pub_date,
                    "needs_review": False,
                    "is_primary_feed": p.get("is_primary_feed", True),
                },
            )

            PaperValiditySignal.objects.update_or_create(
                card=card,
                defaults={
                    "venue": p["venue"],
                    "venue_tier": p["venue_tier"],
                    "affiliation_tier": p["affiliation_tier"],
                    "data_source": "semantic_scholar",
                },
            )

            created_cards.append(card)

        # Ingest-time dynamic linking across all seeded cards (Rule 57)
        self.stdout.write("Running automated ingest-time dynamic linker...")
        from research.models import CardRelation
        CardRelation.objects.all().delete()
        total_links = 0
        for card in created_cards:
            links = link_newly_ingested_card(card)
            total_links += len(links)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {len(created_cards)} cards and created {total_links} dynamic research links!"
            )
        )

