"""Tests for LLM router, circuit breaker, and provider fallback."""

import pytest
from core.llm.providers.base import (
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)
from core.llm.providers.fake import FakeProvider
from core.llm.router import AllProvidersFailedError, CircuitBreaker, LLMRouter


def test_circuit_breaker_trip_and_cooldown():
    cb = CircuitBreaker(threshold=3, cooldown_s=1.0)
    assert not cb.is_open("gemini_1")

    cb.record_failure("gemini_1")
    cb.record_failure("gemini_1")
    assert not cb.is_open("gemini_1")

    cb.record_failure("gemini_1")
    assert cb.is_open("gemini_1")

    # Success resets failure count
    cb.record_success("gemini_1")
    assert not cb.is_open("gemini_1")


def test_router_success_primary():
    p1 = FakeProvider(name="fake_primary", canned_responses=["hello from primary"])
    p2 = FakeProvider(name="fake_secondary", canned_responses=["hello from secondary"])
    router = LLMRouter(providers=[p1, p2], max_retries=1)

    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    resp = router.complete(req)

    assert resp.content == "hello from primary"
    assert resp.provider == "fake_primary"
    assert len(p1.recorded_requests) == 1
    assert len(p2.recorded_requests) == 0


def test_router_fallback_on_failure():
    p1 = FakeProvider(name="fake_primary", always_fail=True)
    p2 = FakeProvider(name="fake_secondary", canned_responses=["fallback succeeded"])
    router = LLMRouter(providers=[p1, p2], max_retries=1)

    req = LLMRequest(messages=[{"role": "user", "content": "test fallback"}])
    resp = router.complete(req)

    assert resp.content == "fallback succeeded"
    assert resp.provider == "fake_secondary"
    assert len(p1.recorded_requests) >= 1
    assert len(p2.recorded_requests) == 1


def test_router_all_providers_failed():
    p1 = FakeProvider(name="fake_1", always_fail=True)
    p2 = FakeProvider(name="fake_2", always_fail=True)
    router = LLMRouter(providers=[p1, p2], max_retries=0)

    req = LLMRequest(messages=[{"role": "user", "content": "hello"}])
    with pytest.raises(AllProvidersFailedError):
        router.complete(req)


def test_task_aware_routing_segregation():
    """
    Fast & low-token tasks (triage, relation critic) prioritize Groq (Llama 3.1 8B).
    Heavy reasoning tasks (summarize, deep dive) prioritize Gemini Flash/Pro.
    """
    gemini = FakeProvider(name="gemini_1", canned_responses=["gemini answer"])
    groq = FakeProvider(name="groq", canned_responses=["groq answer"])
    router = LLMRouter(providers=[gemini, groq], max_retries=1)

    # 1. Fast & Low-Token Task -> routes to Groq first
    fast_req = LLMRequest(
        messages=[{"role": "user", "content": "check relation"}],
        recipe_name="scientific_paper_relation_critic",
    )
    fast_resp = router.complete(fast_req)
    assert fast_resp.provider == "groq"
    assert fast_resp.content == "groq answer"

    # 2. Heavy Reasoning Task -> routes to Gemini first
    heavy_req = LLMRequest(
        messages=[{"role": "user", "content": "summarize paper"}],
        recipe_name="research_summarize",
    )
    heavy_resp = router.complete(heavy_req)
    assert heavy_resp.provider == "gemini_1"
    assert heavy_resp.content == "gemini answer"


def test_multi_account_pool_rotation():
    """
    Consecutive calls rotate between accounts in the same provider pool
    (e.g. gemini_1 <-> gemini_2) to balance quota and prevent RPM limits.
    """
    g1 = FakeProvider(name="gemini_1", canned_responses=["g1_resp"])
    g2 = FakeProvider(name="gemini_2", canned_responses=["g2_resp"])
    router = LLMRouter(providers=[g1, g2], max_retries=1)

    req = LLMRequest(
        messages=[{"role": "user", "content": "query"}],
        recipe_name="research_summarize",
    )

    # Call 1 -> g2 (or rotated index)
    r1 = router.complete(req)
    # Call 2 -> g1
    r2 = router.complete(req)

    # Both providers received requests due to rotation pool
    assert len(g1.recorded_requests) == 1
    assert len(g2.recorded_requests) == 1
    providers_used = {r1.provider, r2.provider}
    assert providers_used == {"gemini_1", "gemini_2"}
