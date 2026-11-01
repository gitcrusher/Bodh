"""
learning/deep_dive.py — Level-adaptive deep-dive generator (Step 2)

Reads real quiz scores from LearnerProfile (not defaults) and generates
pitched-at-level explanations via the LLM router.

Rules enforced:
  Rule 20: generated lazily on first open, then cached (DeepDiveCache).
  Rule 20: never pre-generate all three levels.
  Rule 8: model never produces URLs or citations from memory; source text
          passed in from the card's content field.
  Rule 11: factual tasks use low temperature and schema-validated output.
  design.md §4: paper-derived content and general background are visually
                labelled apart (returned as separate fields in the payload).
  design.md §4: a level change never adds new factual claims about the paper.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.models import User

from core.llm.router import LLMRouter
from .models import DeepDiveCache, KnowledgeLevel
from .quiz_engine import get_user_level

logger = logging.getLogger(__name__)

LOGIC_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Level-specific prompt pitches
# ---------------------------------------------------------------------------

_LEVEL_INSTRUCTIONS = {
    KnowledgeLevel.NEW: (
        "Explain this as if the reader has never studied machine learning. "
        "Use simple analogies. Avoid jargon. Define every technical term on first use. "
        "Focus on what the result means in plain language, not how it was achieved."
    ),
    KnowledgeLevel.FAMILIAR: (
        "The reader knows basic ML concepts (gradient descent, neural networks, "
        "attention) but is not a researcher. Explain the core contribution clearly. "
        "You may use standard terminology but briefly gloss unfamiliar terms."
    ),
    KnowledgeLevel.FLUENT: (
        "The reader is an ML practitioner or researcher. Be precise and technical. "
        "Focus on the method, architecture choices, and empirical claims. "
        "No need to explain standard concepts."
    ),
}

_PROMPT_TEMPLATE = """\
You are generating a level-adaptive deep-dive explanation of an AI research paper.

READER LEVEL: {level_label}
INSTRUCTION: {level_instruction}

PAPER CONTENT (source text — do not invent facts beyond this):
<paper_source>
{source_text}
</paper_source>

Produce a JSON object with exactly these keys:
{{
  "paper_explanation": "<3-5 paragraphs pitched at the reader level, derived ONLY from the paper source above>",
  "background_context": "<1-2 paragraphs of general background knowledge that helps the reader understand the paper, clearly separate from paper claims>",
  "key_takeaway": "<one sentence the reader should remember>"
}}

Rules:
- paper_explanation must not contain claims not supported by the source text.
- background_context is general knowledge; label it mentally as background, not a paper claim.
- A level change never adds new factual claims about the paper.
- Output valid JSON only. No markdown fences.
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_deep_dive(
    user: User,
    card_id: int,
    topic_slug: str,
    source_text: str,
    card_headline: str,
    force_level: str | None = None,
) -> dict[str, Any]:
    """Return a level-adaptive deep-dive for the given card and user.

    Args:
        user:          The requesting user (used to look up their quiz level).
        card_id:       research.Card PK (integer reference, no cross-module FK).
        topic_slug:    Topic slug to look up calibrated level.
        source_text:   Abstract + intro + conclusion text to ground the explanation.
        card_headline: Used for cache lookup and LLM context.
        force_level:   Override level (for testing or admin preview).

    Returns:
        {
            "level": "new" | "familiar" | "fluent",
            "paper_explanation": str,
            "background_context": str,
            "key_takeaway": str,
            "from_cache": bool,
        }
    """
    level = force_level or get_user_level(user, topic_slug)

    # Check cache first (Rule 20)
    cached = DeepDiveCache.objects.filter(
        card_id=card_id, level=level, logic_version=LOGIC_VERSION
    ).first()

    if cached:
        import json as _json
        try:
            data = _json.loads(cached.content)
        except Exception:
            data = {"paper_explanation": cached.content, "background_context": "", "key_takeaway": ""}
        cached.save(update_fields=["last_accessed_at"])  # auto_now handles the timestamp
        return {
            "level": level,
            "from_cache": True,
            **data,
        }

    # Generate via LLM (Rule 11: low temperature, schema-validated)
    result = _generate(level=level, source_text=source_text, card_headline=card_headline)

    # Store in cache
    import json as _json
    DeepDiveCache.objects.update_or_create(
        card_id=card_id,
        level=level,
        defaults={
            "content": _json.dumps(result),
            "logic_version": LOGIC_VERSION,
        },
    )

    return {
        "level": level,
        "from_cache": False,
        **result,
    }


def _generate(level: str, source_text: str, card_headline: str) -> dict[str, str]:
    """Call the LLM router and return the parsed deep-dive dict."""
    import json as _json

    prompt = _PROMPT_TEMPLATE.format(
        level_label=level.upper(),
        level_instruction=_LEVEL_INSTRUCTIONS.get(level, _LEVEL_INSTRUCTIONS[KnowledgeLevel.FAMILIAR]),
        source_text=source_text[:6000],  # stay well within smallest context window (Rule 14)
    )

    router = LLMRouter()
    response = router.complete(
        prompt=prompt,
        temperature=0.2,        # Rule 11: low temperature for factual tasks
        max_tokens=1200,
        task_name="deep_dive",
    )

    # Schema validation (Rule 11: malformed → retry once → fallback)
    raw = response.text.strip()
    for attempt in range(2):
        try:
            parsed = _json.loads(raw)
            assert "paper_explanation" in parsed
            assert "background_context" in parsed
            assert "key_takeaway" in parsed
            return {
                "paper_explanation": str(parsed["paper_explanation"]),
                "background_context": str(parsed["background_context"]),
                "key_takeaway": str(parsed["key_takeaway"]),
            }
        except (ValueError, AssertionError, KeyError) as exc:
            if attempt == 0:
                logger.warning("Deep-dive JSON parse failed (attempt 1), retrying: %s", exc)
                # Retry with validation hint
                retry_prompt = prompt + f"\n\nPrevious output failed JSON validation: {exc}\nOutput ONLY valid JSON."
                response = router.complete(
                    prompt=retry_prompt, temperature=0.1, max_tokens=1200, task_name="deep_dive_retry"
                )
                raw = response.text.strip()
            else:
                # Extractive fallback (Rule 11: never save partial output — return safe fallback)
                logger.error("Deep-dive generation failed twice; using extractive fallback.")
                return {
                    "paper_explanation": source_text[:1200],
                    "background_context": "",
                    "key_takeaway": card_headline,
                }

    # Should never reach here
    return {
        "paper_explanation": source_text[:1200],
        "background_context": "",
        "key_takeaway": card_headline,
    }
