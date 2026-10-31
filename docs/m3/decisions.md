# Member 3 — Architecture Decisions & Trade-offs (ADRs)

Document decisions regarding backend framework, SQLite schemas, session management, and API design.

---

### Template
```markdown
## [YYYY-MM-DD] ADR-00X: Title
* **Status:** [Proposed | Accepted | Superseded]
* **Context:** What problem were you solving?
* **Decision:** What did you choose and why?
* **Consequences / Trade-offs:** What are the pros and cons?
```

---

## Decisions Log

### [2026-10-31] ADR-001: SQLite Schema Strategy (JSON vs Relational)
* **Status:** Accepted
* **Context:** Need quick, flexible schema evolution during 24h hackathon while preserving queries for sessions and question history.
* **Decision:** Use relational columns for primary session keys (`session_id`, `created_at`, `status`) and JSON columns (`context_data`, `schemes_data`, `answers_data`, `plan_data`) inside SQLite.
* **Consequences:** Avoids frequent migration lockups while retaining clean Pydantic serialization.

### [2026-10-31] ADR-002: Orchestration Model
* **Status:** Accepted
* **Context:** Whether to use LangChain / LangGraph vs plain async Python functions.
* **Decision:** Use plain async Python functions for the master orchestrator.
* **Consequences:** Eliminates external framework debugging overhead; makes state transitions 100% transparent and deterministic.

### [2026-10-31] ADR-003: Member 2 Integration & State Contract
* **Status:** Accepted
* **Context:** M2 delivers synchronous, side-effect-free algorithms (`normalize_requirements`, `assess_schemes`, `generate_consolidated_questions`, `apply_answers`, `build_action_plan`). The orchestrator must handle persistence and avoid state collapse.
* **Decision:**
  1. Store `answers_json` (attribute -> `Answer` object) and `history_json` (question ID -> `AnswerState`) in SQLite.
  2. Use `apply_answers` to seed from context and to process question submissions. Never merge into a flat dictionary `{**context, **answers}` so non-destructive skip semantics are preserved.
  3. Normalize once per discovery run and persist the normalized schemes with their `normalized_by` tag.
  4. Pass keyword arguments to `build_action_plan(schemes, user_documents=..., assessments=...)`.
* **Consequences:** Clean separation of concerns: Member 2 owns pure business and graph logic; Member 3 owns persistence, concurrency, and REST routing.

### [2026-10-31] ADR-004: Review Round 1 Plan Harmonization & Adapter Adoption
* **Status:** Accepted
* **Context:** Initial Coding Round 1 plan for M3 assumed Member 1 and Member 2 modules had not landed and relied on placeholder stubs. In reality, M2 landed 282 passed tests and M1 delivered the Discovery engine with `discovery_agent/adapter.py`.
* **Decision:**
  1. Updated `M3_Coding_Round_1_Plan.md` into an active, live orchestration plan connecting M1's `discover_schemes()` and M2's `normalize_requirements()`, `assess_schemes()`, `generate_consolidated_questions()`, and `build_action_plan()`.
  2. Adopted `discovery_agent/adapter.py` as the canonical transformer between M1 raw extraction schemas and M2 canonical models.
  3. Formally consolidated backend REST and persistence ownership under Member 3 (`api/` and `data/unlocked.db`).
* **Consequences:** Member 3's deliverable for Review Round 1 is a live end-to-end 6-stage slice rather than an isolated mock.

### [2026-10-31] ADR-005: Workspace & Unified Package Layout (Phase 0)
* **Status:** Accepted
* **Context:** Need a standardized virtual environment, consolidated package dependencies, and package boundary for the backend orchestrator (`api/`) and database storage (`data/`).
* **Decision:**
  1. Created virtual environment `.venv/` running Python 3.14 with unified requirements including FastAPI, aiosqlite, pydantic, google-genai, networkx, and anthropic.
  2. Initialized `api/` package with `api/__init__.py` and `api/adapter.py` referencing `discovery_agent.adapter`.
  3. Created `data/` directory for SQLite session database and added it along with `*.db` to `.gitignore`.
  4. Created `.env` from `.env.example`.
* **Consequences:** All test suites (282 M2 tests, 61 M1 tests) run 100% green; local environment is ready for Phase 1 contracts and Phase 2 persistence implementation.

### [2026-10-31] ADR-006: Frozen Schema Contracts and Asynchronous SQLite Persistence (Phase 1 & Phase 2)
* **Status:** Accepted
* **Context:** Need public request/response models for Member 4 (`api/schemas.py`) and durable asynchronous SQLite session persistence (`api/database.py`) in compliance with the shared architectural contract.
* **Decision:**
  1. Implemented `api/schemas.py` defining `UserProfileInput`, `CreateSessionRequest`, `SessionResponse`, `FullSessionState`, `DiscoverOptions`, `SchemeView`, `DiscoveryResult`, `AnswerInput`, `SubmitAnswersRequest`, `ReassessmentResult`, and `UpdateDocStatusRequest`, directly re-exporting Member 2 models (`Question`, `Answer`, `Assessment`, `ActionPlan`, `ChecklistItem`).
  2. Implemented `api/database.py` with `aiosqlite` in WAL mode (`PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;`).
  3. Context Seeding: In `create_session()`, initial profile demographic facts are mapped to canonical attributes and seeded via `member2.apply_answers({}, {}, seed_list)`, recording them as `answered` in both `answers` and `history` (`"q_" + attr`).
  4. Strongly typed `SessionRecord` encapsulates full deserialization into Member 2 models.
  5. Implemented async CRUD operations: `init_db`, `create_session`, `get_session`, `update_discovery_results`, `update_answers_and_assessments`, `update_plan`, `update_user_documents`, and `delete_session`.
* **Consequences:** 100% durable persistence layer ready to be driven by the orchestrator and consumed by FastAPI endpoints. All 7 persistence tests pass.

### [2026-10-31] ADR-007: Phase 3 Master Orchestrator Pipeline Integration
* **Status:** Accepted
* **Context:** Need a master coordinator (`api/orchestrator.py`) executing the deterministic sequence: Context Seed $\rightarrow$ M1 Discovery $\rightarrow$ Kannada Translation $\rightarrow$ Adapter $\rightarrow$ M2 Normalization $\rightarrow$ M2 Preliminary Assessment $\rightarrow$ Consolidated Questions $\rightarrow$ SQLite Persistence.
* **Decision:**
  1. Implemented `run_discovery()` orchestrating M1 search/fallback (`discover_schemes`), M1 Kannada translation (`translate_schemes_to_kannada`), M1-to-M2 schema mapping (`adapt_m1_to_m2_schemes`), M2 normalization (`normalize_requirements`), M2 assessment (`assess_schemes`), and question generation (`generate_consolidated_questions`).
  2. Implemented `build_scheme_views()` providing a unified view of scheme metadata combined with assessment statuses, explanation strings, and requirement results for Member 4.
  3. Implemented question answering and reassessment coordinator (`process_answers`), document action planning (`generate_action_plan`), and document procurement toggling (`update_checklist_status`).
* **Consequences:** End-to-end integration slice verified in `tests/test_orchestrator.py`. Total test suite reached 360 passed tests.

### [2026-10-31] ADR-008: Phase 4 FastAPI REST API Endpoints & Question Answering Flow
* **Status:** Accepted
* **Context:** Need production-grade HTTP REST endpoints in `api/main.py` enabling Member 4 (Frontend) to interact with the backend service.
* **Decision:**
  1. Implemented FastAPI application with CORS middleware, startup lifespan (`init_db`), and Pydantic request/response validation.
  2. Exposed operational endpoints: `GET /health` and `GET /api/health`.
  3. Exposed session management: `POST /api/sessions` (with context seeding), `GET /api/sessions/{session_id}`, `DELETE /api/sessions/{session_id}`.
  4. Exposed discovery and scheme details: `POST /api/sessions/{session_id}/discover`, `GET /api/sessions/{session_id}/schemes`, `GET /api/sessions/{session_id}/schemes/{scheme_id}`.
  5. Exposed consolidated questionnaire and reassessment flow: `GET /api/sessions/{session_id}/questions` and `POST /api/sessions/{session_id}/answers`.
  6. Exposed document action planning DAG: `GET /api/sessions/{session_id}/plan` and `POST /api/sessions/{session_id}/checklist/{doc_id}`.
* **Consequences:** Member 4 frontend has a fully live, tested HTTP backend. 6 new HTTP integration tests passing in `tests/test_api.py`. Total test count: 366 passing.


