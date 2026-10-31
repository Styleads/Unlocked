# Project Unlocked — Persistent Development Memory & Project Log

---

## 1. Project Overview

**Project Unlocked** is an AI-powered discovery and evidence-based verification engine for Indian government schemes, with a special focus on Karnataka and Central Government public benefits. It enables citizens across diverse backgrounds (farmers, students, job seekers, small business owners, senior citizens, and women entrepreneurs) to discover social welfare and financial assistance programs using verifiable, official-domain sources (`.gov.in`, `.nic.in`) in both English and Kannada.

---

## 2. Current Architecture

### Architecture Snapshot
- **API Framework**: FastAPI 0.162.0 with asynchronous route handlers (`GET /health`, `POST /discover`), configurable CORS, input validation, and timeout control.
- **Language Support**: Bilingual discovery (English `en` and Kannada `kn`). Authentic Kannada overlays for fallback schemes; structured Gemini translation for live schemes.
- **Core Orchestration**: Python 3.14 asynchronous pipeline (`asyncio`). Searches run concurrently via `asyncio.gather`.
- **Search Engine**: Tavily Search API with strict domain restriction (`include_domains=["gov.in", "nic.in", ...]`) and secondary hostname validation. Features exponential backoff and jitter for HTTP 429 and network timeouts.
- **LLM Engine**: Google Gemini via the official `google-genai` SDK (`gemini-flash-lite-latest`). Direct API integration using `generate_content` and `chats.create`.
- **Verification Engine**: Multi-stage claim-level evidence verification. Every extracted claim must be explicitly supported by an exact literal quotation found in the raw excerpt of an authorized official domain.
- **Fallback Engine**: Local collection of 5 pre-verified Karnataka/Central schemes (`PMFBY`, `PM-KISAN`, `Raitha Siri`, `Vidyasiri`, `PMKSY`), labeled `discovery_source="fallback"`.
- **Data Schemas**: Strict Pydantic v2 schemas (`SchemeRecord`, `SchemeClaim`, `SchemeCriterion`, `SourceEvidence`, `DiscoverRequest`, `DiscoverResponse`, `HealthResponse`).
- **Profile Storage**: Local profile management via `profile_manager.py` for CLI; API accepts profile directly in request payload for backend persistence.
- **User Interface**: Web-ready REST API, Rich terminal UI (`terminal_ui.py`), and interactive Gemini-powered conversational loop (`agent.py`).
- **Orchestration Framework Status**: LangChain, LangGraph, and n8n are **not implemented** in the active codebase. Direct Python async code handles all agent logic.

---

## 3. Implemented Features

### Feature 1: Guided & Broad Scheme Discovery
- **Details**: `build_search_queries()` constructs queries using occupation, confirmed location (district, state), and stated interests. `guided` scope targets specific interests; `all` scope expands to general welfare, subsidies, and assistance programs.
- **Files**: `discovery_agent/discovery_pipeline.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_build_search_queries`, `test_guided_discovery_queries_focused_on_interests`, `test_discover_all_broadens_queries_beyond_interests`, `test_queries_for_diverse_user_profiles`.

### Feature 2: Official Domain Restriction & Source Classification
- **Details**: Two-tier domain defense. Tavily restricts search to official domains; `is_official_government_url()` validates that hostnames match or end with `.gov.in` or `.nic.in`. `classify_source()` distinguishes official from secondary domains.
- **Files**: `discovery_agent/search_provider.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_rejects_unknown_source_url`, `test_official_source_classification`.

### Feature 3: Search Resiliency & Exponential Backoff
- **Details**: `search_web()` catches transient network errors, HTTP 429 rate limits, and 5xx server errors, retrying up to 3 times with exponential backoff and randomized jitter.
- **Files**: `discovery_agent/search_provider.py`, `discovery_agent/discovery_pipeline.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_search_timeout_handled_gracefully`, `test_search_rate_limit_handled_without_crashing`, `test_partial_search_failure_returns_surviving_results`.

### Feature 4: Structured Scheme Extraction
- **Details**: Calls Gemini (`gemini-flash-lite-latest`) with JSON schema enforcement to parse search excerpts into structured schemes, target groups, benefits, criteria, required documents, and individual factual claims.
- **Files**: `discovery_agent/scheme_extractor.py`, `discovery_agent/prompts.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_multiple_schemes_extracted`, `test_discovery_returns_multiple_schemes_in_one_run`, `live_api_test.py`.

### Feature 5: Triple-Gate Claim Verification
- **Details**: Secondary Gemini call prompts verification of each factual claim. Claim is verified only if: (1) LLM marks `supported=True`, (2) Source URL belongs to accepted official sources, and (3) Quotation is a normalized literal substring of the source excerpt.
- **Files**: `discovery_agent/scheme_extractor.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_verify_claims_accepts_exact_official_evidence`, `test_verify_claims_rejects_fake_evidence`, `test_verify_claims_requires_exact_substring_in_source`.

### Feature 6: Deduplication Engine
- **Details**: Deduplicates raw search results by normalizing URLs (removing query parameters, fragments, trailing slashes). Deduplicates extracted schemes by normalizing scheme titles.
- **Files**: `discovery_agent/discovery_pipeline.py`, `discovery_agent/scheme_extractor.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_deduplicate_results`, `test_deduplicate_results_handles_malformed_inputs`, `test_scheme_deduplication_removes_duplicate_names`.

### Feature 7: Offline Verified Fallback Collection
- **Details**: Manually verified Karnataka/Central schemes (`fallback_schemes.py`) used when live search returns zero results or when `search_scope="fallback"`. Clearly marked `discovery_source="fallback"`, `verification_status="unverified"`, and includes review timestamps.
- **Files**: `discovery_agent/fallback_schemes.py`, `discovery_agent/discovery_pipeline.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_fallback_collection_has_valid_attributes`, `test_fallback_returned_when_live_search_yields_no_results`, `test_direct_fallback_search_scope`.

### Feature 8: Rich Terminal UI
- **Details**: Formats discovered schemes as Rich cards and summary tables, displaying verification badges, target groups, documents, sources, and missing information.
- **Files**: `discovery_agent/terminal_ui.py`, `test_terminal_ui.py`
- **Current Status**: Implemented & verified.
- **Evidence**: `test_terminal_ui.py` execution verified.

### Feature 9: Conversational Profile Manager
- **Details**: Multi-turn chat loop in `agent.py` using Gemini chat sessions. Calls `extract_profile_update` to parse facts from user messages and merges them into `user_profile.json`.
- **Files**: `discovery_agent/agent.py`, `discovery_agent/profile_extractor.py`, `discovery_agent/profile_manager.py`
- **Current Status**: Implemented & verified.
- **Evidence**: Tested locally.

### Feature 10: FastAPI REST Integration Layer
- **Details**: Asynchronous HTTP API exposing `GET /health` and `POST /discover`. Supports input validation, flat & nested profile normalization, CORS configuration, configurable timeout management, and graceful error masking.
- **Files**: `api/main.py`, `api/schemas.py`, `api/__init__.py`
- **Current Status**: Implemented & verified.
- **Evidence**: 10 automated tests in `tests/test_api.py` covering health check, English & Kannada responses, flat vs nested profiles, 422 validations, 504 timeouts, 500 error masking, and CORS headers.

### Feature 11: Native Kannada Language Support (ಕನ್ನಡ) & Translation Hardening
- **Details**: Translates scheme records to authentic Kannada. Uses pre-translated official terminology for offline fallback schemes and structured Gemini JSON calls for live search results. Hardened with:
  - Strict JSON validation checking types, non-empty text, and list integrity.
  - Verification that expected scheme IDs are returned exactly once with duplicate rejection.
  - Explicit metadata: `translation_status` (`"complete"`, `"partial"`, `"failed"`) and `actual_response_language` (`"kn"`, `"en"`).
  - Absolute preservation of URLs, IDs, numbers, and verification quotation strings unchanged.
  - Strict rule that translation can never upgrade an unverified scheme into a verified scheme.
  - Indirect prompt injection protection via boundary framing `<untrusted_schemes_to_translate>` and security directives.
  - Sanitized user-facing error messages preventing raw API or exception leaks.
- **Files**: `discovery_agent/kannada_translator.py`, `api/main.py`, `api/schemas.py`
- **Current Status**: Implemented, hardened & verified.
- **Evidence**: 9 automated tests in `tests/test_kannada.py` covering fallback overlays, live scheme translation, duplicate ID rejection, missing field detection, URL/evidence preservation, status upgrade prevention, partial translation, malformed JSON, and prompt injection resilience.

---

## 4. Bugs and Issues

### Issue 1: Coroutine Not Awaited in Original Test Suite
- **Description**: `test_discovery_across_scopes_and_user_contexts` was failing with `assert False where False = isinstance(<coroutine object>, list)`.
- **Root Cause**: The test was decorated with `@pytest.mark.anyio` but declared as synchronous `def` instead of `async def`, calling `discover_schemes()` without `await`.
- **Files Affected**: `tests/test_discovery.py`
- **Fix Applied**: Updated function signature to `async def` and added `await` to `discover_schemes()`.
- **Current Status**: Fixed & verified.

### Issue 2: Crash on Malformed / Non-Dict Search Results
- **Description**: `deduplicate_results()` threw `AttributeError: 'NoneType' object has no attribute 'get'` when search providers returned `None` or non-dict items.
- **Root Cause**: Missing type guard before calling `.get("url")`.
- **Files Affected**: `discovery_agent/discovery_pipeline.py`
- **Fix Applied**: Added `if not isinstance(result, dict): continue` and validated `url` is a non-empty string.
- **Current Status**: Fixed & verified.

### Issue 3: Import-Time Crash on Missing API Keys
- **Description**: Importing `search_provider.py` or `agent.py` threw `ValueError` if environment variables were not pre-configured.
- **Root Cause**: Top-level eager client instantiation at module import time.
- **Files Affected**: `discovery_agent/search_provider.py`, `discovery_agent/agent.py`
- **Fix Applied**: Deferred client initialization to function runtime.
- **Current Status**: Fixed & verified.

### Issue 4: Root Test Collection Hang on `test_gemini.py`
- **Description**: Running `pytest` without path arguments hangs indefinitely.
- **Root Cause**: `test_gemini.py` in the root folder starts with `test_` but contains an un-guarded `while True: input(...)` loop at top level.
- **Files Affected**: `test_gemini.py`
- **Fix Applied**: Documented in audit and README. Users and CI must execute `pytest tests/` rather than bare `pytest`.
- **Current Status**: Documented.

---

## 5. Technical Decisions

### Decision 1: Direct Gemini SDK over LangChain
- **Decision**: Used the official Google GenAI SDK (`google.genai`) directly rather than introducing LangChain chains or agents.
- **Reason**: The direct SDK provides lower memory overhead, native structured JSON output support, and eliminates brittle dependency version conflicts.
- **Consequences**: LangChain is not utilized, despite being installed in `venv`.

### Decision 2: Authentic Pre-Translated Overlays for Fallback Schemes
- **Decision**: Maintained pre-translated Kannada overlays in `kannada_translator.py` for the 5 fallback schemes.
- **Reason**: Guarantees instant (0ms latency), 100% reliable, zero-API-cost translation for fallback schemes even when running completely offline or under rate limits.
- **Consequences**: Fast, robust Kannada responses during network dropouts.

### Decision 3: Flexible Profile Adapter in API
- **Decision**: Designed `UserProfileInput` with `.to_user_context()` supporting both flat profile dictionaries (e.g. `{"occupation": "farmer", "state": "Karnataka"}`) and nested dictionaries (e.g. `{"employment": {"occupation": "farmer"}}`).
- **Reason**: Allows Member 3's backend to supply either format without needing custom serialization logic.
- **Consequences**: Zero friction integration for external consumers.

### Decision 4: Strict Error Masking on API Layer
- **Decision**: Caught internal exceptions and timeouts at the FastAPI boundary, returning clean JSON payloads and standard status codes (422, 504, 500) without exposing stack traces, API keys, or raw exceptions.
- **Reason**: Security and API stability; internal diagnostic details must never leak to clients.
- **Consequences**: Safe for production frontend consumption.

---

## 6. Pending Tasks & Technical Debt

1. **Move Root Interactive Scripts**: Move `test_gemini.py` into a `scripts/` directory to prevent pytest from attempting collection.
2. **Populate `.gitignore`**: Add `.env`, `venv/`, `__pycache__/`, `*.pyc`, and `.pytest_cache/` to `.gitignore`.
3. **Database Integration**: Once Member 3 connects the orchestrator, verify database-backed user profile persistence.
4. **Multilingual Speech**: Future audio I/O for voice-driven Kannada citizen queries.

---

## 7. Development History

- **2026-10-30**: Initial prototype created in `Agent 1` workspace. Baseline tests established (22 passed, 5 failed).
- **2026-10-31 03:00**: Workspace copied to `Agent 1 - Copy`. Refactored pipeline, enhanced schema, created fallback schemes, added backoff logic, and populated stub files.
- **2026-10-31 03:10**: Fixed test suite async defect in `test_discovery.py`. Created `test_extended_discovery.py` (25 new tests). Total 52 tests passing (100%).
- **2026-10-31 03:38**: Live API test executed successfully with Tavily and Gemini.
- **2026-10-31 11:05**: Independent technical audit completed. Generated `README.md`, `PROJECT_LOG.md`, `AUDIT_REPORT.md`.
- **2026-10-31 11:25**: **FastAPI Integration & Kannada Support**:
  - Implemented `api/main.py` with `GET /health` and `POST /discover`.
  - Implemented `api/schemas.py` with `DiscoverRequest`, `DiscoverResponse`, `HealthResponse`.
  - Implemented `discovery_agent/kannada_translator.py` with authentic overlays and Gemini structured translation.
  - Added 10 tests in `tests/test_api.py` and 4 tests in `tests/test_kannada.py`. Total test count: 66 passed / 0 failed (100%).
  - Updated `HANDOFF_MEMBER3.md` with complete REST API specifications.
- **2026-10-31 11:40**: **Kannada Translation Hardening**:
  - Added strict JSON payload validation (`validate_gemini_translation_payload`).
  - Added expected ID verification and duplicate ID rejection.
  - Added `translation_status` (`complete`, `partial`, `failed`) and `actual_response_language` (`kn`, `en`) metadata.
  - Enforced strict invariants: verification status cannot be upgraded by translation; URLs and evidence excerpts are unalterable.
  - Added security framing against indirect prompt injections.
  - Added sanitized user-facing error messages.
  - Added 6 new hardened unit tests (9 in `test_kannada.py`, 11 in `test_api.py`). Total test count: 72 passed / 0 failed (100%).

---

## 8. Next Session Handover

### Completed
- Production-conscious FastAPI REST API in `api/main.py`.
- Kannada language translation service in `discovery_agent/kannada_translator.py`.
- 14 new automated tests (66 total tests passing).
- Comprehensive integration documentation in `HANDOFF_MEMBER3.md` and `README.md`.

### What Was Changed
- Created: `api/main.py`, `api/schemas.py`, `api/__init__.py`, `discovery_agent/kannada_translator.py`, `tests/test_api.py`, `tests/test_kannada.py`.
- Updated: `discovery_agent/__init__.py`, `requirements.txt`, `README.md`, `PROJECT_LOG.md`, `AUDIT_REPORT.md`, `HANDOFF_MEMBER3.md`.

### What Remains
- Deploy the service or run containerization (Dockerfile) if Partha requires container deployment.
- Connect frontend UI to `http://localhost:8000/discover`.

### Important Setup & Execution Commands
```powershell
# Run the FastAPI REST Server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Run all 66 automated tests
.\venv\Scripts\python.exe -m pytest tests/ -v

# Run API tests specifically
.\venv\Scripts\python.exe -m pytest tests/test_api.py -v

# Run Kannada translation tests specifically
.\venv\Scripts\python.exe -m pytest tests/test_kannada.py -v
```

---

## Session 5 — Git Security Hardening & Credential Audit

### Summary of Changes
1. **`.gitignore` Hardening**:
   - Replaced empty `.gitignore` with comprehensive exclusions:
     - `.env*` with strict exception for `!.env.example` and `!.env.template`
     - Virtual environments: `venv/`, `.venv/`, `env/`, `ENV/`
     - Python caches: `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.coverage`
     - User personal data (PII): `user_profile.json`, `*user_profile*.json`, `profiles/`, `user_data/`
     - IDE artifacts: `.vscode/`, `.idea/`, `*.swp`
     - OS and local scratch files: `*.log`, `scratch/`, `tmp/`
2. **Environment Template**:
   - Created `.env.example` containing only safe placeholder variables and onboarding documentation.
3. **Repository Secret Scan**:
   - Conducted deep scan for Gemini, Tavily, AWS, OpenAI, and generic credentials.
   - Confirmed zero credentials exist anywhere in tracked code, tests, docs, or scripts.
   - Identified that credentials only exist in local development `.env`.
4. **Git Tracking Status**:
   - Verified that no sensitive files or credentials were ever staged or tracked by Git (`git ls-files` is empty).
   - Validated that `git status --short` properly ignores `.env`, `user_profile.json`, `venv/`, and `.pytest_cache/`.

---

## Session 6 — Review Round 1 Contract Harmonization & Compliance Audit

### Summary of Changes
1. **Model String Normalization**: Replaced fictional `"gemini-3.5-flash-lite"` with valid free-tier model `"gemini-flash-lite-latest"` across `discovery_agent/agent.py`, `discovery_pipeline.py`, `kannada_translator.py`, and test scripts.
2. **Compliance Adapter Created**: Implemented `discovery_agent/adapter.py` providing bidirectional schema transformation between Member 1's `SchemeRecord` and Member 2's canonical model.
3. **Fallback Dataset Harmonization**: Updated `discovery_agent/fallback_schemes.py` to instantiate `DocumentRequirement` objects with verified `source_url` and `evidence`, preventing document drop-off in Member 2's planning engine.
4. **Backend Role Clarification**: Removed prototype `api/` and `tests/test_api.py`, confirming Member 3's sole ownership of backend orchestration and SQLite persistence.
5. **Interactive Script Cleanup**: Renamed `test_gemini.py` to `demo_gemini_interactive.py` to prevent pytest freezing on user inputs during test discovery.
6. **Documentation Relocation**: Organized root audit documents into `docs/m1/` (`AUDIT_REPORT.md`, `DECISIONS.md`, `HANDOFF_MEMBER3.md`, `PROJECT_LOG.md`) and removed obsolete `Plan.md`.


