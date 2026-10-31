# Member 2 — Architecture Decisions & Trade-offs (ADRs)

Document decisions on requirement normalization, question ranking algorithms, and DAG construction.

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

### [2026-10-31] ADR-001: Question Ranking & Deduplication Strategy
* **Status:** Accepted
* **Context:** A search may return 8 schemes with 20 missing criteria. Asking 20 questions overwhelms the user.
* **Decision:** 
  1. Map string requirements to a canonical attribute dictionary (`annual_family_income`, `caste_category`, `is_karnataka_resident`, etc.).
  2. Score each candidate question: `score = (schemes_impacted * 2) - sensitivity_penalty`.
  3. Pick top 3 to 5 questions per batch.
* **Consequences:** Users get maximum assessment resolution with minimal cognitive load.

### [2026-10-31] ADR-002: Graph Engine Selection
* **Status:** Accepted
* **Context:** Need to represent document dependencies (e.g., Aadhaar -> Caste/Income Certificate -> SSP Application).
* **Decision:** Implement deterministic Python adjacency list / topological sort directly or via NetworkX. Do not rely on LLM to sort tasks.
* **Consequences:** Guaranteed cycle-free, reproducible ordering without non-deterministic prompt variance.

