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

### [2026-10-31] ADR-006: Contract Harmonization across agents.md and plan.md §5
* **Status:** Accepted
* **Context:** Discrepancies between initial pseudocode sketches in `docs/agents.md` and the final schemas in `plan.md §5` risked breaking integration across Members 1, 2, 3, and 4.
* **Decision:**
  1. Updated `docs/agents.md` to treat `plan.md §5` and `member2` as the authoritative source of truth.
  2. Aligned `SchemeRecord`, `Requirement`, `DocumentRequirement`, `Question`, `Answer`, `Assessment`, and `ActionPlan` models.
  3. Documented real function signatures for orchestrator (`normalize_requirements`, `apply_answers`, `generate_consolidated_questions`, `build_action_plan`).
* **Consequences:** All team members share a unified, verified specification before wiring frontend and backend services.

### [2026-10-31] ADR-007: Review Round 1 Integration & Compliance Validation
* **Status:** Accepted
* **Context:** Review Round 1 confirmed integration with Member 1's discovery output and Member 3's orchestration plan.
* **Decision:**
  1. Validated Member 1's `discovery_agent/adapter.py` and updated `fallback_schemes.py` against `check_member1.py`.
  2. Confirmed documents now arrive with verified `source_url` and `evidence`, resolving the issue of sourceless documents being dropped in planning.
  3. Coordinated with Member 3 on keyword argument expectations for `build_action_plan` and `apply_answers` state persistence.
* **Consequences:** Member 2's 282 offline tests remain 100% green; pipeline integration is unblocked.

### [2026-11-01] ADR-008: Geographical Applicability Normalization and Auto-Assessment
* **Status:** Accepted
* **Context:** State conditions (e.g. Haryana) were previously turning into `unmapped:haryana` and prompting citizens with "Does this apply to you: 'haryana'?". In addition, document requirements lacked mandatory vs optional tracking into the action plan checklist.
* **Decision:**
  1. Added `INDIAN_STATES` catalog in `member2/attributes.py` and canonical rule mapping in `member2/normalize.py` to `attribute="state", operator=Operator.eq, value="<State>"`.
  2. In `member2/assess.py`, established bidirectional inference between `state == 'Karnataka'` and `domicile_karnataka == True`, and automatically evaluated requirements or unmapped conditions mentioning other states to `RequirementStatus.not_satisfied`.
  3. In `member2/questions.py`, filtered out candidate questions mentioning other states if the citizen's residency is known.
  4. Added `mandatory: bool = True` to `DocumentRequirement` and `ChecklistItem`, carrying the mandatory/optional status into the action plan graph.
* **Consequences:** Never asks citizens about other states; accurately disqualifies other-state conditions; action plan distinguishes mandatory documents from optional ones.

