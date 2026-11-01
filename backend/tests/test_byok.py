"""
tests/test_byok.py — Unit & integration tests for Step 4 (Multi-provider & BYOK).

Verifies:
1. Encryption at rest via Fernet (Rule 39).
2. Key masking & security (no plaintext leaks in API responses).
3. Cost-split: shared pipeline work vs. personalized work.
4. BYOK provider routing and quota bypass.
5. Fallback Matrix (§14.1) when BYOK key fails.
6. REST API endpoints for credentials and daily quota.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from core.encryption import decrypt_secret, encrypt_secret, mask_api_key
from core.llm.byok import (
    QuotaExceededError,
    create_byok_provider,
    execute_personalized_task,
    get_daily_quota_status,
    get_user_byok_credential,
)
from core.llm.providers.base import LLMProviderError, LLMRequest, LLMResponse, RateLimitError
from core.models import DailyPersonalizedQuota, LLMCredential


@pytest.fixture
def auth_user(db):
    user, _ = User.objects.get_or_create(username="byok_tester", defaults={"email": "byok@test.local"})
    return user


@pytest.fixture
def api_client(auth_user):
    client = APIClient()
    client.force_authenticate(user=auth_user)
    return client


# ---------------------------------------------------------------------------
# 1. Encryption & Masking (Rule 39)
# ---------------------------------------------------------------------------

def test_encryption_and_decryption_at_rest():
    secret_key = "sk-ant-api03-test-secret-key-1234567890"
    cipher = encrypt_secret(secret_key)

    assert cipher != secret_key
    assert "sk-ant" not in cipher
    decrypted = decrypt_secret(cipher)
    assert decrypted == secret_key


def test_mask_api_key():
    assert mask_api_key("sk-ant-api03-abcdef123456") == "sk-...3456"
    assert mask_api_key("short") == "••••"
    assert mask_api_key("") == ""
    assert mask_api_key(None) == ""


# ---------------------------------------------------------------------------
# 2. LLMCredential Model
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_llm_credential_model(auth_user):
    cred = LLMCredential(user=auth_user, provider="gemini", is_default=True)
    cred.set_api_key("AIzaSyD-TestKey-987654321")
    cred.save()

    # Verify encrypted in raw database field
    raw_row = LLMCredential.objects.raw("SELECT id, encrypted_api_key FROM llm_credentials WHERE id = %s", [cred.id])[0]
    assert "AIzaSy" not in raw_row.encrypted_api_key

    # Verify decrypt getter and masked property
    assert cred.get_api_key() == "AIzaSyD-TestKey-987654321"
    assert cred.masked_key == "AIz...4321"


# ---------------------------------------------------------------------------
# 3. Quota Management & Capping
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_daily_quota_status_and_capping(auth_user):
    status = get_daily_quota_status(auth_user)
    assert status["has_byok"] is False
    assert status["used"] == 0
    assert status["limit"] == 5
    assert status["remaining"] == 5
    assert status["is_capped"] is False

    # Simulate 5 personalized calls
    today = timezone.now().date()
    quota_row = DailyPersonalizedQuota.objects.create(user=auth_user, date=today, call_count=5)
    status = get_daily_quota_status(auth_user)
    assert status["used"] == 5
    assert status["remaining"] == 0
    assert status["is_capped"] is True

    # When user adds a BYOK key, is_capped becomes False (unlimited)
    cred = LLMCredential(user=auth_user, provider="groq", is_default=True)
    cred.set_api_key("gsk_test1234567890")
    cred.save()

    status = get_daily_quota_status(auth_user)
    assert status["has_byok"] is True
    assert status["is_capped"] is False  # BYOK bypasses cap


# ---------------------------------------------------------------------------
# 4. Personalized Execution & Cost Split Routing
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_execute_personalized_with_byok_key(auth_user):
    cred = LLMCredential(user=auth_user, provider="groq", is_default=True)
    cred.set_api_key("gsk_mock_valid_key")
    cred.save()

    req = LLMRequest(messages=[{"role": "user", "content": "Explain attention"}])

    mock_response = LLMResponse(content="Attention is all you need.", provider="groq")
    with patch("core.llm.providers.groq.GroqProvider.complete", return_value=mock_response):
        res = execute_personalized_task(req, user=auth_user)
        assert res.provider == "byok_groq"
        assert res.content == "Attention is all you need."

    # Verify shared quota usage was NOT consumed
    status = get_daily_quota_status(auth_user)
    assert status["used"] == 0


@pytest.mark.django_db
def test_execute_personalized_shared_quota_exhausted_raises(auth_user):
    today = timezone.now().date()
    DailyPersonalizedQuota.objects.create(user=auth_user, date=today, call_count=5)

    req = LLMRequest(messages=[{"role": "user", "content": "Hello"}])

    with pytest.raises(QuotaExceededError) as exc_info:
        execute_personalized_task(req, user=auth_user)

    assert "Daily free personalized quota reached (5/5)" in str(exc_info.value)
    assert "BYOK" in str(exc_info.value)


@pytest.mark.django_db
def test_byok_key_failure_falls_back_to_shared_quota_under_cap(auth_user):
    """Fallback Matrix §14.1: If BYOK key fails, fall back to shared quota while under cap."""
    cred = LLMCredential(user=auth_user, provider="groq", is_default=True)
    cred.set_api_key("gsk_invalid_test_key")
    cred.save()

    req = LLMRequest(messages=[{"role": "user", "content": "Explain LoRA"}])

    shared_mock_resp = LLMResponse(content="LoRA is parameter-efficient fine tuning.", provider="gemini_1")

    # When BYOK throws RateLimitError or LLMProviderError
    with patch("core.llm.providers.groq.GroqProvider.complete", side_effect=RateLimitError("groq", "Quota exceeded")):
        with patch("core.llm.router.LLMRouter.complete", return_value=shared_mock_resp):
            res = execute_personalized_task(req, user=auth_user)
            assert res.content == "LoRA is parameter-efficient fine tuning."

    # Shared quota was incremented due to fallback
    status = get_daily_quota_status(auth_user)
    assert status["used"] == 1


# ---------------------------------------------------------------------------
# 5. REST API Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_api_credentials_crud(api_client, auth_user):
    # 1. List is initially empty
    resp = api_client.get("/api/v1/core/credentials/")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Create new Gemini BYOK key
    resp = api_client.post(
        "/api/v1/core/credentials/",
        {"provider": "gemini", "api_key": "AIzaSyD-secret-key-12345", "is_default": True},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "gemini"
    assert data["masked_key"] == "AIz...2345"
    assert "api_key" not in data  # Never expose raw key
    cred_id = data["id"]

    # 3. Quota endpoint reflects BYOK active
    q_resp = api_client.get("/api/v1/core/credentials/quota/")
    assert q_resp.status_code == 200
    assert q_resp.json()["has_byok"] is True

    # 4. Delete credential
    del_resp = api_client.delete(f"/api/v1/core/credentials/{cred_id}/")
    assert del_resp.status_code == 204
    assert LLMCredential.objects.filter(id=cred_id).count() == 0

