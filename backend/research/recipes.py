"""
research/recipes.py

Versioned prompt recipes for all LLM steps in the research pipeline.

Every recipe is registered here so the pipeline nodes just import by name.
Bumping logic_version on any recipe triggers eval + shadow comparison before
the new version can replace existing cards (Rule 36).

Recipes registered:
  research_triage       — cheap classifier (ai/ml research or not?)
  research_summarize    — 60-second card generator
  research_number_check — number/entity faithfulness verifier
"""

from core.pipeline.context import Recipe, register_recipe

# ---------------------------------------------------------------------------
# Triage — cheap, no structured output needed
# ---------------------------------------------------------------------------

TRIAGE_RECIPE = Recipe(
    name="research_triage",
    logic_version="1",
    # Cheapest / fastest provider; the router falls back on failure.
    # We indicate preference via the recipe name so callers can pass provider_hint.
    system_template=(
        "You are a strict research classifier for an AI/ML news app. "
        "Your only job is to decide whether a paper is a genuine AI/ML research contribution. "
        "Reply with a single JSON object: {\"accept\": true} or {\"accept\": false}. "
        "No other text."
    ),
    input_budget_tokens=512,
    output_reserve_tokens=20,
    temperature=0.0,
    schema={
        "type": "object",
        "properties": {"accept": {"type": "boolean"}},
        "required": ["accept"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# Summarize — the main card generator
# ---------------------------------------------------------------------------

SUMMARIZE_RECIPE = Recipe(
    name="research_summarize",
    logic_version="1",
    system_template=(
        "You are an expert AI/ML science communicator writing for the AI News app. "
        "Your task is to summarize a research paper into a 60-second card for a "
        "technically literate but time-pressed reader.\n\n"
        "Rules:\n"
        "- headline: one sentence, active voice, no jargon, max 15 words.\n"
        "- summary_60s: exactly 3-4 bullet points prefixed with '•', each at most 40 words. "
        "  Cover what the paper does, why it matters, and one concrete result. "
        "  No speculation beyond the paper.\n"
        "- tags: 2-5 lowercase tags from: transformers, rl, diffusion, safety, agents, "
        "  nlp, cv, multimodal, mlops, theory, benchmark, dataset.\n"
        "- candidate_techniques: up to 5 named technical concepts mentioned "
        "  (e.g. LoRA, RLHF, flash-attention). Empty list if none.\n"
        "- is_priority: true only if the paper is exceptionally novel or high-impact "
        "  (NeurIPS/ICML/ICLR accepted, or from a top lab with a striking result). "
        "  Default false.\n\n"
        "Return only valid JSON matching the schema. No markdown fences."
    ),
    input_budget_tokens=3000,
    output_reserve_tokens=512,
    temperature=0.3,
    schema={
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "summary_60s": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "candidate_techniques": {"type": "array", "items": {"type": "string"}},
            "is_priority": {"type": "boolean"},
        },
        "required": ["headline", "summary_60s", "tags", "candidate_techniques", "is_priority"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# Number / entity faithfulness check
# ---------------------------------------------------------------------------

NUMBER_CHECK_RECIPE = Recipe(
    name="research_number_check",
    logic_version="1",
    system_template=(
        "You are a strict faithfulness checker. You will receive a paper abstract and "
        "a generated summary. Your task is to verify that every number, percentage, model "
        "name, dataset name, and benchmark name that appears in the summary also appears "
        "in the abstract. Reply with a single JSON object:\n"
        "  {\"faithful\": true}  — all numbers/names check out\n"
        "  {\"faithful\": false, \"mismatches\": [\"...\", ...]}  — list what is wrong\n"
        "No other text."
    ),
    input_budget_tokens=2000,
    output_reserve_tokens=256,
    temperature=0.0,
    schema={
        "type": "object",
        "properties": {
            "faithful": {"type": "boolean"},
            "mismatches": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["faithful"],
        "additionalProperties": False,
    },
)


# ---------------------------------------------------------------------------
# Paper Chat — Step 3: Grounded per-paper RAG
# ---------------------------------------------------------------------------

PAPER_CHAT_RECIPE = Recipe(
    name="research_paper_chat",
    logic_version="1",
    system_template=(
        "You are an expert research paper QA assistant grounded strictly in the provided paper context.\n\n"
        "Rules:\n"
        "- Answer the user's question using ONLY the provided excerpts in <paper_context>.\n"
        "- For every factual claim you make, you MUST cite the chunk ID and provide an exact quote "
        "from that chunk in the citations list.\n"
        "- The quote must appear verbatim in the cited chunk text. Never paraphrase or alter the quote.\n"
        "- If the paper excerpts do not contain sufficient evidence to answer the question, set "
        "\"abstain\": true, \"citations\": [], and set \"answer\" to \"The paper does not appear to cover that.\"\n"
        "- Never fabricate citations, chunk IDs, URLs, or external claims (Rule 8 & 12).\n"
        "- Return valid JSON matching the schema only. No markdown fences."
    ),
    input_budget_tokens=4000,
    output_reserve_tokens=1024,
    temperature=0.1,
    schema={
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {"type": "integer"},
                        "quote": {"type": "string"},
                        "claim": {"type": "string"},
                    },
                    "required": ["chunk_id", "quote", "claim"],
                    "additionalProperties": False,
                },
            },
            "abstain": {"type": "boolean"},
        },
        "required": ["answer", "citations", "abstain"],
        "additionalProperties": False,
    },
)


def register_research_recipes() -> None:
    """Register all research recipes with the core registry. Called from graph.py."""
    for recipe in [TRIAGE_RECIPE, SUMMARIZE_RECIPE, NUMBER_CHECK_RECIPE, PAPER_CHAT_RECIPE]:
        register_recipe(recipe)
