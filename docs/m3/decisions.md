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


