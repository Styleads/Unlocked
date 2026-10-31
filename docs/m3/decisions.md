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

