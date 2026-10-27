"""
Django settings for AI News App.
All secrets come from environment variables; see .env.example.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key-change-in-production-ai-news")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    # Project apps — modules depend on core; core never depends on a module
    "core",
    "research.apps.ResearchConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ai_news.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ai_news.wsgi.application"

# ---------------------------------------------------------------------------
# Database — Postgres + pgvector in prod; SQLite fallback for local test
# ---------------------------------------------------------------------------
_db_url = os.getenv("DATABASE_URL", "")

if _db_url.startswith("postgres://") or _db_url.startswith("postgresql://"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db_url.split("/")[-1],
            "USER": _db_url.split("://")[1].split(":")[0],
            "PASSWORD": _db_url.split(":")[2].split("@")[0],
            "HOST": _db_url.split("@")[1].split(":")[0] if "@" in _db_url else "localhost",
            "PORT": _db_url.split("@")[1].split(":")[1].split("/")[0] if "@" in _db_url else "5432",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Internationalization / static
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
}

# ---------------------------------------------------------------------------
# CORS (Flutter client on localhost during dev)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
]
CORS_ALLOW_ALL_ORIGINS = DEBUG  # permissive in dev only

# ---------------------------------------------------------------------------
# LLM router config (read by core.llm.router)
# ---------------------------------------------------------------------------
LLM_PROVIDER_PRIORITY = os.getenv(
    "LLM_PROVIDER_PRIORITY", "gemini_1,gemini_2,groq,anthropic"
).split(",")

LLM_PROVIDER_CONFIG = {
    "gemini_1": {
        "api_key_env": "GEMINI_API_KEY_1",
        "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest"),
        "max_tokens": 8192,
    },
    "gemini_2": {
        "api_key_env": "GEMINI_API_KEY_2",
        "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest"),
        "max_tokens": 8192,
    },
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        "max_tokens": 8192,
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
        "max_tokens": 4096,
    },
    "fake": {
        "api_key_env": None,
        "model": "fake-model",
        "max_tokens": 4096,
    },
}

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("LLM_CIRCUIT_BREAKER_THRESHOLD", "3"))

# ---------------------------------------------------------------------------
# Embedding service
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# ---------------------------------------------------------------------------
# External APIs
# ---------------------------------------------------------------------------
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

# ---------------------------------------------------------------------------
# arXiv fetcher
# ---------------------------------------------------------------------------
ARXIV_CATEGORIES = os.getenv("ARXIV_CATEGORIES", "cs.AI,cs.LG,cs.CL").split(",")
ARXIV_BASE_URL = os.getenv("ARXIV_BASE_URL", "https://export.arxiv.org")
ARXIV_RATE_LIMIT_SECONDS = float(os.getenv("ARXIV_RATE_LIMIT_SECONDS", "3"))

# ---------------------------------------------------------------------------
# Daily ingestion budgets
# ---------------------------------------------------------------------------
DAILY_CARD_BUDGET = int(os.getenv("DAILY_CARD_BUDGET", "50"))
DAILY_TOKEN_BUDGET = int(os.getenv("DAILY_TOKEN_BUDGET", "500000"))

# ---------------------------------------------------------------------------
# Retention windows (days)
# ---------------------------------------------------------------------------
RAW_CONTENT_GRACE_DAYS = int(os.getenv("RAW_CONTENT_GRACE_DAYS", "7"))
RAW_EMBEDDING_RETENTION_DAYS = int(os.getenv("RAW_EMBEDDING_RETENTION_DAYS", "90"))
AGENT_RUNS_FULL_RETENTION_DAYS = int(os.getenv("AGENT_RUNS_FULL_RETENTION_DAYS", "14"))
DB_USAGE_ALERT_PCT = int(os.getenv("DB_USAGE_ALERT_PCT", "80"))

# ---------------------------------------------------------------------------
# Feature flags (bootstrap defaults; overridden by DB rows at runtime)
# ---------------------------------------------------------------------------
FEATURE_FLAGS_DEFAULT = {
    "research_module": os.getenv("FEATURE_RESEARCH_MODULE", "true").lower() == "true",
}
