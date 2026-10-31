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


### [2026-10-31] ADR-003: Detailed decision log lives with the code
* **Status:** Accepted
* **Context:** Member 2 made 54 small contract and design decisions while building.
* **Decision:** The full numbered list is in `member2/DECISIONS.md`. This file keeps only the ones teammates need.
* **Consequences:** One place to look for detail; nothing duplicated here.

### [2026-10-31] ADR-004: Canonical attribute ids
* **Status:** Accepted (refines ADR-001)
* **Context:** ADR-001 named `is_karnataka_resident` as an example id.
* **Decision:** The canonical ids are the ones in `member2/attributes.py`. Residence and legal domicile are separate facts: `state` and `domicile_karnataka`. Ranking also weighs effort and only asks questions whose answer could change an assessment.
* **Consequences:** Member 1 should extract toward these ids. Unknown ids become `unmapped:*` and give *Needs clarification*, never a rejection.

### [2026-10-31] ADR-005: Gemini as the free LLM provider
* **Status:** Accepted
* **Context:** Anthropic API is paid; the team needs a free option.
* **Decision:** `GeminiClient` (REST `v1beta`, standard library only), model alias `gemini-flash-lite-latest`, retries on 429/5xx. Used automatically when `GEMINI_API_KEY` is set.
* **Consequences:** Free and no extra install. The alias can move to a newer model; pinned names get retired.
