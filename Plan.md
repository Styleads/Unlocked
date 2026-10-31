# Project Unlocked — Discovery Agent Architecture & Execution Plan

## 1. Objective
Transform the existing prototype into a robust, production-minded, evidence-grounded Discovery Agent for Karnataka and Indian government benefits.

## 2. Key Architecture Pillars
1. **Public Interface Integrity**:
   - `async def discover_schemes(user_context: dict, search_scope: str = "guided", enable_fallback: bool = False) -> list[SchemeRecord]`
2. **Strict Verification**:
   - Extraction -> Claim Extraction -> Independent Claim Verification against exact official excerpts.
   - Verification status: `verified`, `partially_verified`, `unverified`.
3. **Resilience & Fault Tolerance**:
   - Exponential backoff with jitter on transient network/rate limits (HTTP 429, 5xx, timeouts).
   - Partial success preservation (if 1 query fails, others still yield results).
   - Safe parsing of corrupt/malformed search results and non-standard JSON responses.
4. **Offline Fallback Collection**:
   - Manually verified Karnataka & Central schemes (`PMFBY`, `PM-KISAN`, `Raitha Siri`, `Vidyasiri`, `PMKSY`).
   - Clear labeling: `discovery_source="fallback"`, `verification_status="unverified"`, preserved source URLs, review timestamps, and missing info flags.
5. **Clean Modular Boundaries**:
   - `discovery_pipeline.py`: Orchestration
   - `search_provider.py`: Tavily search wrapper with domain filtering & backoff
   - `scheme_extractor.py`: Gemini extraction & claim verification
   - `scheme_schema.py`: Pydantic models
   - `fallback_schemes.py`: High-quality fallback collection
   - `terminal_ui.py`: Rich visual console rendering
   - `profile_manager.py`: User profile CRUD
   - `profile_extractor.py`: Conversational profile extraction

## 3. Test Coverage Summary
52 automated tests in `tests/test_discovery.py` and `tests/test_extended_discovery.py`:
- 100% pass rate covering all 17 mandatory criteria (guided discovery, discover all, multiple demographics, timeouts, rate limits, malformed inputs, deduplication, official domain checks, claim verification, partial results, fallback behavior, invalid profiles, and timestamps).

