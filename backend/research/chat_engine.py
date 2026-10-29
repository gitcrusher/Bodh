"""
research/chat_engine.py — Step 3: Per-paper grounded chat engine (RAG)

Rules enforced:
  Rule 12: Every cited chunk ID must have been retrieved and the quoted text
           must appear in it. A failed check or score below the similarity floor
           returns "The paper does not appear to cover that." Target 100% citation validity.
  Rule 17: User message length is capped (2,000 characters).
  Rule 46: Never store raw PDF; fetch, extract text, chunk, discard binary.
  Rule 47: Check whether paper_chat_chunks already exists for card_id; if so reuse
           and update last_accessed_at.
  Rule 48: Chat retrieval passes only top 4-6 chunks.
  Rule 49: Show what was found and where (titles, excerpts), never pipeline internals.
  design.md §5: Abstention is a designed honest state, not an error.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.contrib.auth.models import User
from django.utils import timezone

from core.embedding.service import EmbeddingService
from core.llm.router import LLMRouter
from core.pipeline.context import build_context, wrap_data_block
from research.models import Card, ChatMessage, ChatSession, PaperChatChunk
from research.recipes import PAPER_CHAT_RECIPE

logger = logging.getLogger(__name__)

# Constants
MAX_USER_MESSAGE_CHARS = 2000
CHUNK_WORD_TARGET = 150
CHUNK_OVERLAP_WORDS = 25
SIMILARITY_FLOOR = 0.20
TOP_K_CHUNKS = 5
ABSTAIN_TEXT = "The paper does not appear to cover that."


# ---------------------------------------------------------------------------
# Text Chunking Helpers
# ---------------------------------------------------------------------------


def _split_into_chunks(text: str, target_words: int = CHUNK_WORD_TARGET, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """Split text into ~target_words chunks with sliding word overlap."""
    words = text.split()
    if not words:
        return []

    if len(words) <= target_words:
        return [" ".join(words)]

    chunks = []
    step = target_words - overlap
    for i in range(0, len(words), step):
        chunk = words[i : i + target_words]
        if len(chunk) < 40 and chunks:
            # Append trailing short fragment to last chunk
            chunks[-1] = chunks[-1] + " " + " ".join(chunk)
            break
        chunks.append(" ".join(chunk))
    return chunks


# ---------------------------------------------------------------------------
# Chunk Management (Lazy & Reused)
# ---------------------------------------------------------------------------


def get_or_create_paper_chunks(card: Card, embedding_service: EmbeddingService | None = None) -> list[PaperChatChunk]:
    """Retrieve existing chunks for a card or chunk and embed on first demand.

    Rule 46: Never store raw PDF.
    Rule 47: Reuse existing chunks if present; update last_accessed_at.
    """
    existing = list(PaperChatChunk.objects.filter(card=card).order_by("chunk_index"))
    if existing:
        # Touch last_accessed_at for 30-day retention tracking
        now = timezone.now()
        PaperChatChunk.objects.filter(card=card).update(last_accessed_at=now)
        return existing

    # Extract text from raw_content if available, otherwise compile from card metadata
    raw_content = ""
    if card.raw_item and card.raw_item.raw_content:
        raw_content = card.raw_item.raw_content.strip()

    if not raw_content:
        # Clean compilation of available paper sections
        parts = [
            f"Title: {card.headline}",
            f"Abstract and Summary:\n{card.summary_60s}",
        ]
        if card.deep_dive_base:
            parts.append(f"Technical Details:\n{card.deep_dive_base}")
        if card.candidate_techniques:
            parts.append(f"Techniques: {', '.join(card.candidate_techniques)}")
        raw_content = "\n\n".join(parts)

    chunks_text = _split_into_chunks(raw_content)
    if not chunks_text:
        chunks_text = [card.summary_60s or card.headline]

    # Compute embeddings using pinned model
    emb_service = embedding_service or EmbeddingService()
    embeddings = emb_service.embed_batch(chunks_text)

    created_chunks = []
    for idx, (chunk_str, emb) in enumerate(zip(chunks_text, embeddings)):
        chunk_obj = PaperChatChunk.objects.create(
            card=card,
            chunk_index=idx,
            chunk_text=chunk_str,
            embedding=emb,
            embedding_model_version=emb_service.model_version,
            last_accessed_at=timezone.now(),
        )
        created_chunks.append(chunk_obj)

    logger.info("Created %d chat chunks for card #%d", len(created_chunks), card.id)
    return created_chunks


# ---------------------------------------------------------------------------
# Vector Retrieval & Similarity Floor
# ---------------------------------------------------------------------------


def retrieve_top_chunks(
    card: Card,
    query: str,
    top_k: int = TOP_K_CHUNKS,
    similarity_floor: float = SIMILARITY_FLOOR,
    embedding_service: EmbeddingService | None = None,
) -> list[tuple[PaperChatChunk, float]]:
    """Retrieve the top-K chunks exceeding the similarity floor.

    Rule 48: Passes top 4-6 chunks.
    Rule 12: Below similarity floor returns empty (triggers abstention).
    """
    emb_service = embedding_service or EmbeddingService()
    chunks = get_or_create_paper_chunks(card, embedding_service=emb_service)
    if not chunks:
        return []

    query_vec = emb_service.embed(query)
    scored: list[tuple[PaperChatChunk, float]] = []

    for c in chunks:
        if c.embedding:
            sim = emb_service.cosine_similarity(query_vec, c.embedding)
            if sim >= similarity_floor:
                scored.append((c, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Deterministic Citation Verification (Rule 12)
# ---------------------------------------------------------------------------


def verify_citations(
    retrieved_chunks: list[PaperChatChunk],
    citations: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    """Verify that every citation references a retrieved chunk and its quote appears verbatim.

    Rule 12 target: 100% citation validity.
    """
    if not citations:
        return True, []

    chunk_map = {c.id: c.chunk_text for c in retrieved_chunks}
    verified = []

    for cit in citations:
        chunk_id = cit.get("chunk_id")
        quote = cit.get("quote", "").strip()

        if chunk_id not in chunk_map:
            logger.warning("Citation references unretrieved chunk_id=%s", chunk_id)
            return False, []

        chunk_text = chunk_map[chunk_id]

        # Normalize whitespace for exact substring match
        normalized_chunk = re.sub(r"\s+", " ", chunk_text).lower()
        normalized_quote = re.sub(r"\s+", " ", quote).lower()

        if normalized_quote not in normalized_chunk:
            logger.warning(
                "Citation quote not found in chunk #%s: '%s'",
                chunk_id,
                quote[:60],
            )
            return False, []

        verified.append({
            "chunk_id": chunk_id,
            "quote": quote,
            "claim": cit.get("claim", ""),
        })

    return True, verified


# ---------------------------------------------------------------------------
# Public Chat Runner
# ---------------------------------------------------------------------------


def run_paper_chat(
    card: Card,
    user_message: str,
    session: ChatSession | None = None,
    user: User | None = None,
    user_level: str = "familiar",
    router: LLMRouter | None = None,
    embedding_service: EmbeddingService | None = None,
) -> dict[str, Any]:
    """Process one turn of per-paper grounded chat.

    Returns:
        {
            "session_id": int,
            "answer": str,
            "citations": list[dict],
            "abstain": bool,
        }
    """
    # 1. Enforce user message length cap (Rule 17)
    clean_message = user_message.strip()
    if len(clean_message) > MAX_USER_MESSAGE_CHARS:
        clean_message = clean_message[:MAX_USER_MESSAGE_CHARS]

    # 2. Get or create session
    if session is None:
        session = ChatSession.objects.create(card=card, user=user)

    # Record user message
    ChatMessage.objects.create(session=session, role="user", content=clean_message)

    # 3. Retrieve relevant chunks
    scored_chunks = retrieve_top_chunks(
        card=card,
        query=clean_message,
        top_k=TOP_K_CHUNKS,
        similarity_floor=SIMILARITY_FLOOR,
        embedding_service=embedding_service,
    )

    # 4. If no chunks exceed similarity floor -> Honest Abstention (Rule 12 & design.md §5)
    if not scored_chunks:
        ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=ABSTAIN_TEXT,
            citations=[],
        )
        return {
            "session_id": session.id,
            "answer": ABSTAIN_TEXT,
            "citations": [],
            "abstain": True,
        }

    retrieved_chunks = [c for c, _ in scored_chunks]

    # 5. Build context: paper excerpts + recent history (last 6 turns, Rule 15)
    evidence_blocks = []
    for c in retrieved_chunks:
        evidence_blocks.append(f"[Chunk {c.id}]:\n{c.chunk_text}")

    evidence_text = "\n\n".join(evidence_blocks)
    context_data = wrap_data_block("paper_context", evidence_text)

    # Recent history
    recent_msgs = ChatMessage.objects.filter(session=session).order_by("-created_at")[:6]
    history_lines = []
    for m in reversed(list(recent_msgs)):
        history_lines.append(f"{m.role.capitalize()}: {m.content}")
    history_text = "\n".join(history_lines)

    prompt = (
        f"{context_data}\n\n"
        f"Conversation History:\n{history_text}\n\n"
        f"Reader knowledge level: {user_level}.\n"
        f"User question: {clean_message}\n\n"
        "Provide your grounded answer as valid JSON adhering to the schema."
    )

    # 6. Call LLM Router with low temperature
    llm = router or LLMRouter()
    try:
        response_text = llm.complete(
            prompt=prompt,
            recipe_name=PAPER_CHAT_RECIPE.name,
            temperature=PAPER_CHAT_RECIPE.temperature,
            max_tokens=PAPER_CHAT_RECIPE.output_reserve_tokens,
            system_instruction=PAPER_CHAT_RECIPE.system_template,
        )

        # Parse JSON
        parsed = json.loads(response_text)
        answer = parsed.get("answer", "")
        citations = parsed.get("citations", [])
        abstain = parsed.get("abstain", False)

        # If LLM self-reported abstention
        if abstain or answer.strip() == ABSTAIN_TEXT:
            answer = ABSTAIN_TEXT
            citations = []
            abstain = True
        else:
            # 7. Deterministic non-LLM citation verification (Rule 12)
            is_valid, verified_citations = verify_citations(retrieved_chunks, citations)
            if not is_valid:
                logger.warning("Deterministic citation verification failed; falling back to abstention")
                answer = ABSTAIN_TEXT
                citations = []
                abstain = True
            else:
                citations = verified_citations

    except Exception as exc:
        logger.error("Chat generation failed: %s; returning honest failure notice", exc)
        # Rule 2: All providers down / error -> say temporarily unavailable
        answer = "Paper chat is temporarily unavailable."
        citations = []
        abstain = False

    # 8. Record assistant message
    ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=answer,
        citations=citations,
    )

    return {
        "session_id": session.id,
        "answer": answer,
        "citations": citations,
        "abstain": abstain,
    }
