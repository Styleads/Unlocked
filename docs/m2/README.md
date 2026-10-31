# Member 2 — Eligibility, Verification & Planning Engineer

* **Assigned Modules:**
  * **Agent 2: Eligibility & Verification Agent (P0 — Core MVP)**
  * **Agent 3: Document & Planning Agent (P0 — Core MVP)**
* **Technical Contact:** Member 2
* **Shared Contract:** [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md)

---

## 1. Responsibilities & Goals

### Agent 2: Eligibility & Verification Agent (P0)
- [ ] Implement requirement normalization: extract structured criteria (attributes, thresholds, operators) from raw scheme texts.
- [ ] Build deterministic comparison engine for unambiguous attributes (age, district, income limits).
- [ ] Integrate constrained LLM evaluator for complex or nuanced criteria.
- [ ] Build consolidated question generator:
  - Aggregate all missing attributes across returned candidate schemes.
  - Deduplicate equivalent questions (e.g., annual income).
  - Rank by scheme impact, sensitivity, and answerability.
  - Generate clean 3–5 question batch.
- [ ] Ensure non-destructive skip semantics: skipped questions must remain `status: "unknown"` and **never** fail eligibility.
- [ ] Implement candidate reassessment with clear human-readable explanations.
- [ ] Deliverable: `normalize_requirements()`, `generate_consolidated_questions()`, `assess_schemes()`

### Agent 3: Document & Planning Agent (P0)
- [ ] Aggregate verified required documents across active candidate schemes.
- [ ] Normalize document identities (e.g., "RD Income Certificate", "Caste Certificate", "Marks Card").
- [ ] Build Directed Acyclic Graph (DAG) of document procurement prerequisites.
- [ ] Ensure graph edges are strictly backed by source evidence.
- [ ] Compute deterministic topological sort / checklist sequence to prioritize high-leverage prerequisites.
- [ ] Deliverable: `build_action_plan(schemes, user_docs) -> ActionPlan`

---

## 2. Checkpoints Timeline

| Time | Target | Status |
|---|---|---|
| Oct 31, 5:30 PM | Requirement & Assessment schemas tested on 1 mock scheme | Pending |
| Oct 31, 7:00 PM | Review Round 1: Assessment result with missing info explanation ready | Pending |
| Oct 31, 12:05 AM | Consolidated question deduplication, ranking, skip semantics, and reassessment working | Pending |
| Nov 1, 3:00 AM | Document DAG construction and ordered action plan working | Pending |

