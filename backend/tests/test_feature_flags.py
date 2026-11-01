"""Tests for feature flags mechanism (DB overrides settings default)."""

import pytest
from core.flags import feature_flags
from core.models import FeatureFlag


@pytest.fixture(autouse=True)
def clear_flag_cache():
    with feature_flags._lock:
        feature_flags._cache.clear()
    yield
    with feature_flags._lock:
        feature_flags._cache.clear()


@pytest.mark.django_db
def test_feature_flag_default_fallback():
    # research_module default in settings is True
    assert feature_flags.is_enabled("research_module") is True

    # Unknown flag defaults to False
    assert feature_flags.is_enabled("unregistered_feature") is False


@pytest.mark.django_db
def test_feature_flag_db_override():
    # Override default by inserting a disabled flag in DB
    FeatureFlag.objects.create(name="research_module", enabled=False)

    with feature_flags._lock:
        feature_flags._cache.clear()

    assert feature_flags.is_enabled("research_module") is False

    # Enable flag
    feature_flags.enable("research_module")
    assert feature_flags.is_enabled("research_module") is True
