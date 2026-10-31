# Member 2 — Eligibility, Verification & Planning Engineer

* **Assigned Modules:**
  * **Agent 2: Eligibility & Verification Agent (P0 — Core MVP)**
  * **Agent 3: Document & Planning Agent (P0 — Core MVP)**
* **Technical Contact:** Member 2
* **Shared Contract:** [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md)

---

## 1. Responsibilities & Goals

### Agent 2: Eligibility & Verification Agent (P0)
- [x] Implement requirement normalization: extract structured criteria (attributes, thresholds, operators) from raw scheme texts.
- [x] Build deterministic comparison engine for unambiguous attributes (age, district, income limits).
- [x] Integrate constrained LLM evaluator for complex or nuanced criteria.
- [x] Build consolidated question generator:
  - Aggregate all missing attributes across returned candidate schemes.
  - Deduplicate equivalent questions (e.g., annual income).
  - Rank by scheme impact, sensitivity, and answerability.
  - Generate clean 3–5 question batch.
- [x] Ensure non-destructive skip semantics: skipped questions must remain `status: "unknown"` and **never** fail eligibility.
- [x] Implement candidate reassessment with clear human-readable explanations.
- [x] Deliverable: `normalize_requirements()`, `generate_consolidated_questions()`, `assess_schemes()`

### Agent 3: Document & Planning Agent (P0)
- [x] Aggregate verified required documents across active candidate schemes.
- [x] Normalize document identities (e.g., "RD Income Certificate", "Caste Certificate", "Marks Card").
- [x] Build Directed Acyclic Graph (DAG) of document procurement prerequisites.
- [x] Ensure graph edges are strictly backed by source evidence.
- [x] Compute deterministic topological sort / checklist sequence to prioritize high-leverage prerequisites.
- [x] Deliverable: `build_action_plan(schemes, user_docs) -> ActionPlan`

---

## 2. Checkpoints Timeline

| Time | Target | Status |
|---|---|---|
| Oct 31, 5:30 PM | Requirement & Assessment schemas tested on 1 mock scheme | Done |
| Oct 31, 7:00 PM | Review Round 1: Assessment result with missing info explanation ready | Done |
| Oct 31, 12:05 AM | Consolidated question deduplication, ranking, skip semantics, and reassessment working | Done |
| Nov 1, 3:00 AM | Document DAG construction and ordered action plan working | Done |


---

## 3. Status (2026-10-31)

All Member 2 deliverables are built and tested: `python -m pytest tests/member2 -q` gives 282 passed, offline, no API key.

* **Code:** `member2/` (package, relative imports, so it can move under `backend/`), `tests/member2/`, `requirements-member2.txt`.
* **How to call it (Member 3):** `member2/README.md`.
* **Full decision log (54 entries):** `member2/DECISIONS.md`. **Status and open issues:** `member2/STATUS.md`.
* **LLM:** Gemini (free tier) if `GEMINI_API_KEY` is set, else Claude. Confirmed live on Gemini.
* **Check Member 1 output:** `python -m member2.check_member1 path/to/schemes.json`.

**Blocked on:** a sample of Member 1's scheme JSON; wiring into Member 3's backend.
