# AI News App 📰🤖

A scroll-based AI/ML news feed where each item is a 60-second card with a source link, a deep-dive, and per-paper chat.

- **Backend**: Django + Django REST Framework + PostgreSQL / pgvector (SQLite fallback for local tests)
- **Orchestration**: LangGraph (embedded library workflow, not a service)
- **Client**: Flutter
- **LLM Layer**: Multi-provider router — Google Gemini (2 free-tier keys), Groq (free tier), Anthropic (paid fallback)

---

## 🛠️ Environment Setup

All dependencies live inside `backend/.venv`. **Never install into the global Python.**

```powershell
# Activate (Windows PowerShell)
cd backend
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Run tests
pytest

# Check import boundaries
lint-imports --config .importlinter
```

---

## 🗺️ Phases

Phases follow [`Agent/phases.md`](Agent/phases.md) (derived from section 16 of the system design doc). Architecture is scale-shaped from day one; what is phased is feature scope.

| Phase | Description | Status |
| :--- | :--- | :---: |
| **Step 0** | Platform Core | ✅ Complete |
| **Step 1** | Papers-only Vertical Slice | 🔄 Backend Done / Flutter Pending SDK |
| Step 2 | Knowledge Calibration & Personalization | ⏳ Planned |
| Step 3 | Per-Paper Grounded Chat (RAG) | ⏳ Planned |
| Step 4 | Multi-provider & BYOK | ⏳ Planned |
| Step 5 | Widen Source Taxonomy | ⏳ Planned |
| Step 6 | Trend & Authenticity Signals | ⏳ Planned |
| Step 7 | Trending-Technique Grounding | ⏳ Planned |
| Step 8 | Research Assistant | ⏳ Planned |
| Step 9 | Curated Concept Graph | ⏳ Planned |
| Step 10 | Behavioral Personalization & Growth | ⏳ Planned |

---

## ✅ Step 0 — Platform Core

**Status**: Complete. 23/23 tests passing. Import boundary contract enforced.

This step produces no user-facing features. Its job is to give every future module a consistent, rule-enforced foundation: one way to call an LLM, one way to track what has been processed, one way to store and enforce retention, and one way to run evals.

---

### Files Created in Step 0

#### `backend/requirements.txt`
Lists every dependency with compatible version ranges. Split into: core framework (Django, DRF, CORS), database (psycopg2, pgvector), LLM providers (google-generativeai, anthropic, groq), orchestration (langgraph, langchain-core), embeddings (sentence-transformers, torch), HTTP/fetching (httpx, aiohttp, sickle), utilities (python-dotenv, pydantic, tenacity, cachetools), testing (pytest, pytest-django, responses, factory-boy, freezegun), and CI tooling (import-linter, black, ruff).
**Why**: Single source of truth for all Python dependencies so any developer or CI runner can reproduce the exact environment with `pip install -r requirements.txt`.

#### `backend/.env.example`
Documents every environment variable the app reads — Django `SECRET_KEY`, `DATABASE_URL`, LLM API keys (`GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`), model names, budget caps, retention windows, and feature flag defaults. No actual secrets; this file is committed.
**Why**: Any developer can `cp .env.example .env`, fill in their keys, and the app runs. Nothing is hardcoded.

#### `backend/.importlinter`
Declares one import-linter contract: `core` must never import from `research` (or any other module package). Enforced via `lint-imports --config .importlinter` in CI.
**Why**: Enforces Rule 29 ("modules depend on core; core never depends on a module") mechanically so the boundary cannot erode quietly.

#### `backend/pytest.ini`
Sets `DJANGO_SETTINGS_MODULE = ai_news.settings`, marks test file patterns, and passes `-v --tb=short` by default.
**Why**: Lets `pytest` find and run all tests without any extra flags.

#### `backend/.venv/`
Isolated Python virtual environment created with `python -m venv --system-site-packages .venv`. The `--system-site-packages` flag reuses large pre-installed wheels (torch, sentence-transformers) from the system Python instead of re-downloading gigabytes. All new installs go only inside `.venv`.
**Why**: Keeps the developer's system Python clean. Packages installed here do not affect any other project or the global environment.

---

#### `backend/manage.py`
Standard Django management entry-point. Runs `python manage.py migrate`, `python manage.py runserver`, `python manage.py makemigrations`, etc.
**Why**: Required by Django; unchanged from the standard scaffold.

#### `backend/ai_news/__init__.py`
Empty package marker for the `ai_news` Django project package.

#### `backend/ai_news/settings.py`
All settings read from environment variables (loaded via `python-dotenv`). Key sections:
- `SECRET_KEY`: falls back to an insecure dev key if env var is missing (raises clearly in production via `DEBUG=False` checks).
- `DATABASES`: uses Postgres when `DATABASE_URL` starts with `postgres://`; falls back to SQLite otherwise — this makes unit tests work without a running Postgres instance.
- `INSTALLED_APPS`: only `core` registered here. The `research` app will add itself when it is scaffolded.
- `LLM_PROVIDER_CONFIG`: maps provider names (`gemini_1`, `gemini_2`, `groq`, `anthropic`, `fake`) to their API key env vars and model names. The router reads this at startup.
- `FEATURE_FLAGS_DEFAULT`: bootstrap defaults for flags before any DB row exists.
- Retention windows (`RAW_CONTENT_GRACE_DAYS`, `AGENT_RUNS_FULL_RETENTION_DAYS`, etc.) and budget caps (`DAILY_CARD_BUDGET`, `DAILY_TOKEN_BUDGET`) all configurable via env.
**Why**: No hardcoded secrets or environment-specific values anywhere in code.

#### `backend/ai_news/urls.py`
Root URL config. Currently only wires `admin/`. The research module's routes are added conditionally via `try: import research.urls` so the project starts cleanly before the research app exists.
**Why**: Avoids import errors during Step 0 before the `research` app is scaffolded.

#### `backend/ai_news/wsgi.py` / `backend/ai_news/asgi.py`
Standard WSGI and ASGI entry-points generated by Django.
**Why**: Required for deploying with gunicorn (WSGI) or uvicorn (ASGI).

---

#### `backend/core/__init__.py`
Empty package marker.

#### `backend/core/apps.py`
`CoreConfig(AppConfig)` — registers the `core` app with Django. On `ready()`, the embedding model is warmed up lazily so startup stays fast.
**Why**: Required by Django's app registry. The `ready()` hook is the correct place for one-time startup work.

#### `backend/core/models.py`
Five models that form the platform's operational backbone:

| Model | Table | Purpose |
| :--- | :--- | :--- |
| `AgentRun` | `agent_runs` | One row per LLM call. Stores agent name, input ref, output, latency, provider used, token counts, fallback flag, and status. Used for observability and weekly token-cost reviews (Rule 22). Output is cleared after `AGENT_RUNS_FULL_RETENTION_DAYS` by the retention runner — only metadata stays. |
| `PipelineStageLedger` | `pipeline_stage_ledger` | One row per `(item_type, item_id, stage, input_hash, logic_version)`. DB UNIQUE constraint enforces the never-reprocess rule (Rules 4–6). A stage calls `ledger.check()` before running; if a `done` row exists, it skips entirely. |
| `EvalRun` | `eval_runs` | One row per metric per suite run. Always records `n_items` alongside the score (Rule 43). Enables regression queries across `logic_version` bumps. |
| `FeatureFlag` | `feature_flags` | Runtime toggles. Modules ship with `enabled=False`. A flag is flipped to `True` by a human after evals pass (Rule 31). |
| `RetentionRule` | `retention_rules` | Each module registers its cleanup policies here. The runner reads these and dispatches to registered handlers. |

**Why**: Every growing table must have a registered retention rule (Rule 38). Every LLM step must be logged (Rule 22). Idempotency must be enforced at the DB level, not in application logic alone.

#### `backend/core/migrations/0001_initial.py`
Auto-generated by `python manage.py makemigrations core`. Creates all five tables with their indexes and constraints.

#### `backend/core/admin.py`
Registers all five core models in the Django admin with read-only fields and list filters so the project's state can be inspected without writing queries.

---

#### `backend/core/llm/__init__.py`
Empty package marker.

#### `backend/core/llm/providers/__init__.py`
Empty package marker.

#### `backend/core/llm/providers/base.py`
Defines the canonical data shapes and error hierarchy all providers share:
- `LLMRequest`: messages list, optional JSON schema, max_tokens, temperature, recipe_name, logic_version.
- `LLMResponse`: content string, token counts, provider name, model name.
- `LLMProviderError` → `RateLimitError` → `SchemaError`: error hierarchy so the router can make routing decisions based on error type.
- `BaseProvider(ABC)`: abstract interface with `is_available()` and `complete(request) -> LLMResponse`. Every provider adapter implements this.
**Why**: Feature code never touches a provider SDK directly. The router and `run_step()` only know about these abstractions. Swapping or adding a provider requires no changes outside the `providers/` directory.

#### `backend/core/llm/providers/gemini.py`
Adapter for Google Gemini (free tier: `gemini-1.5-flash-latest`). Reads its API key from the env var named in settings (e.g. `GEMINI_API_KEY_1`). Converts `LLMRequest` messages into Gemini's `contents` format, handles system-role separation (Gemini has no `system` role — it is prepended to the first user message), applies JSON schema enforcement when `request.schema` is set, and wraps all SDK errors into `LLMProviderError` subclasses.
**Why**: Two instances of this class (`gemini_1` and `gemini_2`) pool quota across two different free-tier API keys.

#### `backend/core/llm/providers/groq.py`
Adapter for Groq (free tier: `llama-3.1-8b-instant`). Groq's API is OpenAI-compatible so the adapter constructs the request manually over `httpx`. Handles `429 TooManyRequests` → `RateLimitError` and other HTTP errors → `LLMProviderError`.
**Why**: Provides a fast, free fallback when both Gemini keys are rate-limited or down.

#### `backend/core/llm/providers/anthropic.py`
Adapter for Anthropic Claude (paid; premium fallback). Separates the system message from user/assistant turns (required by the Anthropic API format). Gracefully marks itself unavailable if `ANTHROPIC_API_KEY` is not set, so the router skips it rather than error.
**Why**: Provides a reliable paid fallback. The `is_available()` guard means leaving the key unset in dev/CI is safe — the router just skips it.

#### `backend/core/llm/providers/fake.py`
A deterministic, zero-network mock provider for tests. Accepts a `canned_responses` list; each call pops the next response. Supports `always_fail=True` to simulate outages. Records all requests in `self.recorded_requests` for assertion in tests. Multiple instances can be named differently (`name="fake_primary"`, `name="fake_secondary"`) to test fallback chains.
**Why**: Without this, testing the circuit breaker, fallback chain, schema-retry logic, and budget guards would require real network calls that are non-deterministic, consume quota, and cannot run offline.

#### `backend/core/llm/router.py`
The central routing layer. Every LLM call in the entire system goes through here.
- `CircuitBreaker`: per-provider failure counter. After `LLM_CIRCUIT_BREAKER_THRESHOLD` consecutive failures it opens (skips the provider). After `cooldown_s` it half-opens (allows one probe).
- `LLMRouter.complete(request)`: iterates the priority list, skips open circuits, calls `provider.complete()`, retries up to `LLM_MAX_RETRIES` times with exponential backoff, falls through to the next provider on failure, raises `AllProvidersFailedError` if none succeed.
- `get_router()`: singleton; built once from settings on first call.
- `reset_router()`: clears the singleton for use in tests that swap out providers.
**Why**: No feature code ever calls a provider SDK directly. All retry, fallback, and observability logic lives in one place.

---

#### `backend/core/pipeline/__init__.py`
Empty package marker.

#### `backend/core/pipeline/context.py`
Implements `build_context()` and the Recipe registry.
- `Recipe`: a dataclass holding the versioned prompt template (`name`, `logic_version`, `system_template`, `input_budget_tokens`, `output_reserve_tokens`, `schema`, `temperature`). Bumping `logic_version` triggers evals and a shadow comparison before reprocessing (Rule 7).
- `register_recipe()` / `get_recipe()`: module-level registry. Modules call `register_recipe()` at import time.
- `wrap_data_block(label, content)`: wraps untrusted fetched text between `<<<DATA_BLOCK_START>>>` and `<<<DATA_BLOCK_END>>>` markers. The system message always includes an instruction never to follow directives found inside these blocks (Rule 16).
- `build_context(recipe, *, evidence, history, memory, extra_system)`: assembles the message list in the mandated order — system template → evidence → history → memory. Enforces the overflow drop order: oldest history first, then lowest-ranked evidence chunks, then cross-chat memory. The system template and rank-0 evidence are never dropped (Rule 15).
- `ContextPiece`: a `rank`-tagged piece of evidence. Lower rank = higher priority.
**Why**: Every prompt must be assembled by `build_context()` (Rule 13). Inline string concatenation is forbidden.

#### `backend/core/pipeline/ledger.py`
Wraps the `PipelineStageLedger` model.
- `StageLedger.check(item_type, item_id, stage, input_payload, logic_version) -> bool`: hashes `input_payload` with SHA-256 and checks if a `done` row already exists for that combination. If `True` the caller must skip.
- `StageLedger.mark_done(...)`: creates the ledger row. Wrapped in `transaction.atomic()` so that an `IntegrityError` on a duplicate insert is caught cleanly even inside a larger atomic test transaction.
- `StageLedger.mark_failed(...)`: records a failed attempt so the daily job can retry it next run (Rule 6).
**Why**: The never-reprocess rule (Rules 4–6) is enforced at the DB level, not in application memory.

#### `backend/core/pipeline/run_step.py`
The thin wrapper around every single LLM call in the pipeline. Nothing calls a provider directly; everything goes through `run_step()`.
- `BudgetExceededError`: raised if estimated input token cost exceeds `token_budget_remaining` before the call is made.
- `FailedGenerationError`: raised when structured output fails schema validation on both the first attempt and the single retry (Rule 11).
- `run_step(recipe, messages, *, input_ref, agent_name, token_budget_remaining, iteration_cap)`:
  1. Pre-call budget check (Rule 19).
  2. Calls `router.complete(request)`.
  3. If `recipe.schema` is set, validates the response JSON against it. On failure, retries once with the validation error appended to the messages (Rule 11). If the retry also fails → `FailedGenerationError`.
  4. Logs to `AgentRun` regardless of success or failure.
  5. Returns `(content_string, metadata_dict)`.
**Why**: All schema validation, retries, budget enforcement, and observability logging are in one place. Individual pipeline nodes stay small and testable.

---

#### `backend/core/embedding/__init__.py`
Empty package marker.

#### `backend/core/embedding/service.py`
`EmbeddingService`: wraps `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, L2-normalized output).
- Model is loaded lazily on first `embed()` call so Django startup stays fast.
- On load, verifies the model's actual output dimension matches `settings.EMBEDDING_DIM`. Raises `RuntimeError` if they diverge — this catches accidental model name changes.
- `embed(text) -> list[float]`: single text embedding.
- `embed_batch(texts, batch_size=32) -> list[list[float]]`: batch embedding.
- `model_version` property: returns a string stored on every vector row as `embedding_model_version`. Changing the model requires a deliberate re-embed migration; it is never an automatic fallover (Rule 23).
- `cosine_similarity(a, b) -> float`: dot product of two already-normalized vectors.
**Why**: One pinned embedding model. Never routes through the provider fallback. Every vector knows which model created it so re-embed migrations are auditable.

---

#### `backend/core/flags/__init__.py`
Empty package marker.

#### `backend/core/flags/feature_flags.py`
`is_enabled(name) -> bool`: thread-safe feature flag lookup with a 60-second in-process TTL cache.
- Lookup order: (1) DB row in `feature_flags` table → (2) `settings.FEATURE_FLAGS_DEFAULT` → (3) `False`.
- `enable(name)` / `disable(name)`: update the DB row and clear the cache.
**Why**: Modules ship dormant (`enabled=False`). A human enables the flag in the DB after evals pass (Rule 31). The TTL cache means no DB hit on every request without stale reads lasting more than 60 seconds.

---

#### `backend/core/eval/__init__.py`
Empty package marker.

#### `backend/core/eval/harness.py`
`run_suite(*, suite, module, logic_version, cases, metric, scorer, threshold, judge_model, save) -> SuiteResult`
- `EvalCase`: id, input dict, expected value, optional tags and notes.
- `EvalResult`: case id, passed bool, score float, actual output, details string.
- `SuiteResult`: aggregate metric value, n_items, per-case results, optional judge info.
- `run_suite()` runs every case through `scorer`, aggregates `value = mean(scores)`, logs a warning if `value < threshold`, and — when `save=True` — writes one row to `EvalRun` with `n_items` recorded (Rule 43).
- Raises `ValueError` if `cases` is empty (Rule 41: "a module cannot ship an LLM step without golden examples").
**Why**: Provides a standard, consistent way to measure and persist eval results across every LLM step. The harness is separate from pytest so it can run in production on live data without the test overhead.

---

#### `backend/core/retention/__init__.py`
Empty package marker.

#### `backend/core/retention/runner.py`
- `register_handler(rule_key, handler)`: modules register their cleanup callables here.
- Built-in handlers registered at import time:
  - `clear_agent_runs_output`: clears `output` and `tool_calls` from `AgentRun` rows older than `full_retention_days` days, keeping only metadata (Rule 37).
  - `prune_ledger`: deletes `PipelineStageLedger` rows older than `max_age_days` days, **excluding** `stage="ingest"` rows which must stay permanently to block re-fetching.
- `run_all()`: queries `RetentionRule` for all active rules, looks up the registered handler, calls it, and updates `last_run_at`.
**Why**: Rule 38 — every table that grows must have a registered retention rule. This runner is called by a management command on schedule.

---

#### `backend/core/fetcher/__init__.py`
Empty package marker.

#### `backend/core/fetcher/rate_limiter.py`
Token-bucket rate limiter. `RateLimiter(calls_per_second)` exposes `acquire()` which blocks (with `time.sleep`) until a token is available. Thread-safe via a `Lock`.
**Why**: Rule 24 — one central rate limiter driven by `sources.rate_limit_policy`. arXiv requires 1 request / 3 seconds. This class enforces it so no fetcher can accidentally over-request.

#### `backend/core/fetcher/robots.py`
`RobotsChecker`: caches `robots.txt` per host (TTL 24h). `is_allowed(url, user_agent) -> bool` returns whether the given user-agent is permitted to fetch the URL.
**Why**: Rule 25 — scrapers must obey `robots.txt`. This is enforced in the base fetcher before any request is made.

#### `backend/core/fetcher/base.py`
`BaseFetcher(ABC)`: abstract base for all source fetchers. Provides:
- `fetch(url) -> str`: calls `_check_robots()`, then `_fetch_with_retry()`. On `robots.txt` disallowed → `RobotsDisallowedError`. On HTTP failure after retries → `FetchError`. On schema validation failure → quarantines the item and raises `QuarantineError`.
- `_fetch_with_retry()`: honors `Retry-After` on 429, exponential backoff, per-source page caps, and 3–5 second wait between requests (Rule 25).
- Concrete fetchers (`ArxivFetcher` etc.) implement `_parse(raw) -> dict` and register a JSON schema to validate output before ingestion (Rule 26).
**Why**: Rule 26 — scraper output is schema-validated before ingestion. Mismatch: quarantine the item, set `active=false` after repeated failures. The base class enforces this uniformly across all sources.

---

### Tests Created in Step 0

All tests live in `backend/tests/` and run against an in-memory SQLite database (no Postgres required for unit tests).

| File | What It Tests |
| :--- | :--- |
| `tests/test_llm_router.py` | `CircuitBreaker` trips after N failures and resets on success. `LLMRouter` uses the primary provider first, falls back to secondary on failure, raises `AllProvidersFailedError` when all fail. |
| `tests/test_run_step.py` | `run_step()` happy path logs correct `AgentRun`. Budget pre-check raises `BudgetExceededError`. Schema retry succeeds on second attempt. Schema retry failure raises `FailedGenerationError` and logs `status=failed_generation`. |
| `tests/test_context_builder.py` | `wrap_data_block()` output contains markers. Recipe registry stores and retrieves correctly. `build_context()` prepends `DATA_BLOCK_INSTRUCTION` to system. Evidence overflow drops lower-rank pieces. History overflow drops oldest turns first. |
| `tests/test_stage_ledger.py` | `mark_done()` idempotency: duplicate write is silently ignored; only one DB row exists. `logic_version` bump allows reprocessing (new version → `check()` returns `False`). |
| `tests/test_feature_flags.py` | Default falls back to `settings.FEATURE_FLAGS_DEFAULT`. DB row overrides the default. `enable()` flips to `True` and clears cache. |
| `tests/test_retention.py` | `clear_agent_runs_output` clears old rows, leaves recent ones. `prune_ledger` deletes old non-ingest rows, keeps ingest rows permanently. |
| `tests/test_eval_harness.py` | `run_suite()` persists one `EvalRun` row with correct `module`, `metric`, `value`, and `n_items`. |
| `tests/test_embedding_service.py` | `EmbeddingService` properties (model name, version string). Cosine similarity of identical normalized vectors = 1.0, orthogonal = 0.0. `embed()` calls the underlying model correctly when mocked. |

**Test results**: `23 passed in 3.00s`

**Import boundary check**: `Contracts: 1 kept, 0 broken` (`Core never imports from modules KEPT`)

---

## 🔄 Step 1 — Papers-only Vertical Slice

**Status**: Backend Complete (51/51 tests passing, import boundary kept). Client Code Scaffolded (Runtime UI validation pending Flutter SDK installation).

This step implements the complete backend vertical slice (arXiv incremental fetching, identity dedup, cosine similarity dedup, triage LLM gate, daily card budgeting, 60-second summarization, entity/number verification, paper validity signals, DRF REST API endpoints, evaluation suites, and fallback matrix fault-injection tests) and scaffolds the client-side Flutter architecture matching `Agent/design.md`.

> [!NOTE]
> **Flutter SDK Note**: The Flutter codebase (`client/`) has been created according to design specifications (Dusk/Overcast theme tokens, models, services, and reel card layout). However, the Flutter SDK is not currently installed in the host environment, so runtime widget rendering and on-device UI checks cannot be executed until Flutter is installed. All 51 passing tests belong to the backend pytest suite.

---

### Files Modified from Parent Step (Step 0)

#### `backend/ai_news/settings.py`
- **Created in**: Step 0 (initial platform core configuration).
- **Modified in Step 1**:
  - Registered `'research.apps.ResearchConfig'` in `INSTALLED_APPS`.
  - Added arXiv fetcher settings (`ARXIV_CATEGORIES`, `ARXIV_BASE_URL`, `ARXIV_RATE_LIMIT_SECONDS`).
  - Added daily ingestion budgets (`DAILY_CARD_BUDGET=50`, `DAILY_TOKEN_BUDGET=500000`).
  - Added retention parameters (`RAW_CONTENT_GRACE_DAYS=7`, `RAW_EMBEDDING_RETENTION_DAYS=90`).
  - Added default feature flag for `FEATURE_RESEARCH_MODULE`.
- **Reason for modification**: Needed so Django discovers the research module models, migrations, and management commands, while configuring source fetch limits, budgets, and retention policies.

#### `backend/ai_news/urls.py`
- **Created in**: Step 0 (root routing).
- **Modified in Step 1**: Connected `path("api/v1/research/", include("research.urls"))`.
- **Reason for modification**: Needed to expose REST API endpoints for the research module (`cards/`, `cards/{id}/`, `cards/{id}/report/`, `sources/`).

---

### Files Created in Step 1

#### Backend — Domain Models & Storage

##### `backend/research/apps.py`
`ResearchConfig(AppConfig)` — registers the `research` Django app. On `ready()`, registers research-specific retention rules (`raw_content` clearance after grace period) and registers all prompt recipes into the central recipe registry.
**Why**: Centralized startup registration required by Django without side-effects on import.

##### `backend/research/models.py`
Six models representing the data pipeline and feed storage:
- `Source`: Ingestion source metadata (`fetch_interval_min`, `trust_tier`, `fetch_method`, `rate_limit_policy`, `daily_request_cap`).
- `RawItem`: One row per fetched paper. Indexed unique together `(source, external_id)` acts as the primary dedup gate. `raw_content` is transient (cleared after `grace_period_expires_at`). `embedding` is kept for 90 days.
- `Card`: The published 60-second card. Stores `headline`, `summary_60s` (3–4 bullets), `tags`, `candidate_techniques`, `needs_review` flag, and `embedding` (for coarse search).
- `CardSource`: Attaches multiple source URLs to a single card when multiple outlets cover the same paper (dedup threshold > 0.92).
- `PaperValiditySignal`: Per-paper venue tier and affiliation tier. Shown as an informative fact line; never used to penalize or hide papers.
- `ContentReport`: Reader-submitted issue reports (`factual_error`, `wrong_summary`, `broken_link`, `other`).
**Why**: Scale-shaped data model matching system design §6; enforces transient storage rules and multi-source attribution.

##### `backend/research/fields.py`
`VectorField`: Custom Django model field. Uses native `pgvector` vector type on PostgreSQL databases, and gracefully falls back to JSON text serialization on SQLite for local test suites.
**Why**: Enables developers and CI to run tests on SQLite without requiring a running PostgreSQL instance with pgvector.

##### `backend/research/retention.py`
Registers retention cleanup handlers for `research_raw_content` (nulling `raw_content` on `RawItem`s older than grace period) and `research_embeddings` (nulling embeddings older than 90 days).
**Why**: Enforces Rule 37 & 38 — every table that grows has an automated retention policy to prevent unbounded disk growth.

---

#### Backend — Prompt Recipes & Fetchers

##### `backend/research/recipes.py`
Defines versioned prompt recipes:
- `TRIAGE_RECIPE` (`logic_version="1"`): Cheap classifier checking if a title + abstract describes genuine AI/ML research.
- `SUMMARIZE_RECIPE` (`logic_version="1"`): Generates headline, 3-4 bullet 60-second summary, tags, candidate techniques, and JSON schema validation.
- `NUMBER_CHECK_RECIPE` (`logic_version="1"`): Critic verifying every number and entity in the summary against the abstract.
**Why**: Enforces Rule 13 (all prompts are versioned `Recipe` dataclasses) and Rule 18 (cheap triage before expensive summarization).

##### `backend/research/fetchers/arxiv.py`
arXiv Atom API incremental fetcher:
- Queries categories `cs.AI`, `cs.LG`, `cs.CL`.
- Incremental date-range querying based on `source.last_successful_run_at`.
- Obey `robots.txt` per host (cached 24h).
- Rate limits requests to 1 request / 3.0s using central token-bucket rate limiter.
- Supports `dry_run=True` to bypass network during automated tests.
**Why**: Reliable, polite ingestion adhering to arXiv API policies and system design §9.

---

#### Backend — LangGraph Ingestion Pipeline

##### `backend/research/pipeline/state.py`
`PipelineState(TypedDict)`: Defines the state flowing through the graph (`source_id`, `token_budget`, `tokens_used`, `dry_run`, `raw_items_fetched`, `raw_item_ids`, `dedup_ids`, `triage_ids`, `budgeted_ids`, `card_ids`, `errors`, `run_summary`).
**Why**: Explicit typed state keeps nodes isolated and testable without running LangGraph.

##### `backend/research/pipeline/nodes.py`
The 9 pipeline node functions following the `(state) -> dict` contract:
1. `fetch_node`: Fetches incremental papers via registered fetcher (respects `dry_run`).
2. `persist_node`: Saves new `RawItem`s, setting `grace_period_expires_at`.
3. `dedup_node`: Computes cosine similarity (0.92 threshold) against existing cards; attaches duplicates to `CardSource`.
4. `triage_node`: Runs cheap LLM classifier; discards non-AI papers; fails open on LLM error.
5. `budget_node`: Caps daily cards written to `DAILY_CARD_BUDGET`.
6. `summarize_node`: Generates 60s card via `SUMMARIZE_RECIPE`. Falls back to extractive summary with `needs_review=True` on repeated schema failure.
7. `number_check_node`: Entity/number critic. Marks card `needs_review=True` on mismatch.
8. `validity_node`: Creates `PaperValiditySignal` from paper metadata.
9. `report_node`: Compiles run summary dict and updates `source.last_successful_run_at`.
**Why**: Implements workflow A (system design §5.6), enforces Rules 18, 19, 26, 31, and 37.

##### `backend/research/graph.py`
Builds and compiles the LangGraph `StateGraph(PipelineState)`. Exposes `run_daily_research(source_id, dry_run=False)` as an in-process library function.
**Why**: Embedded, lightweight orchestration that runs safely within Celery or scheduled management commands.

##### `backend/research/management/commands/research_run.py`
Django management command: `python manage.py research_run [--source-id N] [--dry-run] [--all-sources]`.
**Why**: Provides an operational CLI for crontab, schedulers, and developer smoke-testing.

---

#### Backend — REST API Views & Serializers

##### `backend/research/serializers.py`
DRF serializers:
- `CardListSerializer`: Serializes cards for feed with nested validity signals and card sources.
- `CardDetailSerializer`: Detailed serializer including `deep_dive_base`.
- `ContentReportCreateSerializer`: Validates and saves reader issue reports.
- `ValiditySignalSerializer`: Serializes venue and affiliation metrics.
**Why**: Clean JSON presentation adhering to mobile app contract.

##### `backend/research/views.py`
- `CardFeedView`: Cursor-paginated feed ordering by `(-published_at, -id)` for stable reel-feed scrolling.
- `CardDetailView`: Single card view.
- `CardReportView`: POST endpoint submitting reader reports to `content_reports`.
- `SourceListView`: Active sources list for health checks.
**Why**: Stable cursor pagination prevents feed jumping when new cards are ingested mid-scroll.

##### `backend/research/urls.py`
Maps routes to views (`cards/`, `cards/<id>/`, `cards/<id>/report/`, `sources/`).

---

#### Backend — Golden Evals & Tests

##### `backend/research/evals/golden_summaries.py`
Golden dataset containing landmark AI papers (Attention, LoRA, FlashAttention) with verified techniques, key numerical metrics, and ground-truth expectations.
**Why**: Enforces Rule 41 ("a module cannot ship an LLM step without golden examples").

##### `backend/tests/test_research_pipeline.py`
15 unit and smoke tests covering each node in isolation and the compiled LangGraph in dry-run mode.

##### `backend/tests/test_research_api.py`
6 integration tests verifying DRF cursor pagination, category filtering, detail view, report submission, and source listing.

##### `backend/tests/test_research_evals.py`
Runs golden dataset through `core.eval.harness.run_suite()` and asserts metric exceeds 0.85 threshold, persisting results to `EvalRun`.

##### `backend/tests/test_fallback_matrix.py`
Fault-injection tests verifying the 6 key rows of the fallback matrix:
1. Primary provider 429 rate limit -> router switches to secondary provider.
2. Primary provider 500 server error -> router switches to secondary provider.
3. All providers fail -> item status remains `new` for retry next run.
4. Schema validation fails twice -> extractive fallback triggers and card is marked `needs_review=True`.
5. Triage LLM call fails -> fail-open policy passes item through rather than silently dropping papers.
6. Token budget exceeded before step -> `BudgetExceededError` raised safely.

---

#### Client (Flutter) — Design System & Feed UI

##### `client/pubspec.yaml`
Client manifest with dependencies: `http` (networking), `google_fonts` (typography), and `url_launcher` (external papers).

##### `client/lib/theme/tokens.dart`
Palette token definitions matching `Agent/design.md` §7b:
- **Dusk (Default)**: Light (`#F6F5F1` background, `#FFFFFF` card, `#3B6E71` primary teal, `#8B7E74` secondary accent) and Dark (`#15181C` background, `#1E2227` card, `#5FA3A6` teal, `#A79C91` secondary accent).
- **Overcast (Alternative)**: Light (`#F4F5F7` background, `#FFFFFF` card, `#4A5B7C` slate) and Dark (`#14161A` background, `#1D2024` card, `#7C8FB0` slate).

##### `client/lib/theme/app_theme.dart`
Builds `ThemeData` enforcing humanist serif headlines (**Source Serif 4**) for editorial trust and clean sans (**Inter**, line-height 1.55) for body readability.

##### `client/lib/models/validity_signal.dart` & `client/lib/models/card_model.dart`
Data models parsing backend DRF cards, bullet points, and validity fact lines.

##### `client/lib/services/api_service.dart`
API client connecting to `/api/v1/research/cards/` with cursor pagination support and curated offline mock fallback for immediate visual preview.

##### `client/lib/widgets/news_card.dart`
Full-screen reel card widget implementing:
- Serif headline and bullet-formatted 60-second summary.
- Validity badge fact line ("NeurIPS 2026 · Tier 1 Venue").
- `needs_review` alert banner when extractive fallback is in use.
- Source button (opens original arXiv paper via `url_launcher`).
- Deep-dive bottom sheet preview.
- Paper chat entry point (Step 3 teaser).
- Issue reporting modal dialog posting to backend `/report/`.

##### `client/lib/widgets/feed_view.dart`
Vertical `PageView.builder` for reel-style swiping, pull-to-refresh, endless cursor pagination, and runtime theme/dark-mode switcher.

##### `client/lib/main.dart`
Flutter app entry point managing dynamic palette and brightness state.

---

### Step 1 Test Results

```
collected 51 items
tests/test_eval_harness.py .                                             [  1%]
tests/test_fallback_matrix.py ......                                     [ 13%]
tests/test_feature_flags.py ..                                           [ 17%]
tests/test_research_api.py ......                                        [ 29%]
tests/test_research_evals.py .                                           [ 31%]
tests/test_research_pipeline.py ...............                          [ 60%]
tests/test_retention.py ..                                               [ 64%]
tests/test_run_step.py ....                                              [ 72%]
tests/test_stage_ledger.py ..                                            [ 76%]
tests/test_context_builder.py .....                                      [ 86%]
tests/test_embedding_service.py ...                                      [ 92%]
tests/test_llm_router.py ....                                            [100%]

======================== 51 passed, 1 warning in 4.77s ========================
```

**Import Boundary Check**:
```
Contracts: 1 kept, 0 broken. (Core never imports from modules KEPT)
```

---

## ⏳ Steps 2–10

These sections will be written as each step is performed.

#   B o d h  
 