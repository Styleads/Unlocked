# Member 2 — Potential Issues, Flaws & Imbalances Log

> **Context:** As of October 31, 2026, Member 2 (M2) has completed the baseline implementations of **Agent 2 (Eligibility & Verification)** and **Agent 3 (Document & Planning)** in `member2/`.  
> Per team agreement, **M2's implementation is established as the priority and source of truth** for Agents 2 & 3 interfaces, data structures, and downstream contracts.  
> This document tracks identified flaws, edge cases, and imbalances to be patched or accommodated by teammates during integration.

---

## 1. Document & Planning Agent (Agent 3) Issues

### Issue 3.1: Sourceless Documents Discarded from Checklist
* **Location:** [`member2/planning.py`](file:///home/kruthik/coding/Unlocked/member2/planning.py#L67-L71)
* **Severity:** High
* **Symptom:** Documents listed without an explicit, distinct `source_url` on the document itself are excluded from the action plan with a warning: `"{doc.name} was left out: no source confirms it is required."`
* **Root Cause:** In real portal extraction, schemes usually list required documents on the scheme page without individual per-document URLs. Converting string documents via `_coerce_string_documents` yields `source_url=None`, causing Agent 3 to drop every document.
* **Resolution / Status:** Mitigated in Review Round 1. Member 1 updated `fallback_schemes.py` to instantiate `DocumentRequirement` objects with verified `source_url` and `evidence`. Member 1 also implemented `discovery_agent/adapter.py` which preserves document source URLs from scheme official sources.
* **Recommended Follow-up:** Add defensive fallback in `member2/planning.py` to inherit `scheme.official_sources[0]` if `doc.source_url` is absent.

### Issue 3.2: Omission of Karnataka Baseline Document Prerequisites
* **Location:** [`member2/planning.py`](file:///home/kruthik/coding/Unlocked/member2/planning.py#L78-L90)
* **Severity:** Medium
* **Symptom:** Action plans currently contain **zero document-to-document prerequisite edges** (`prerequisite_of`).
* **Root Cause:** M2 constructs prerequisite edges strictly from `doc.dependencies` inside `scheme.documents`. Because upstream discovery modules and the normalizer only extract flat document lists, `doc.dependencies` is always empty.
* **Specification Conflict:** [`docs/agents.md` §4.2](file:///home/kruthik/coding/Unlocked/docs/agents.md#L316-L320) specified a known verified Karnataka prerequisite baseline (`KNOWN_PREREQUISITES`):
  - `doc_rd_income_cert` $\rightarrow$ depends on Aadhaar and Ration Card.
  - `doc_ssp_eattestation` $\rightarrow$ depends on RD Number, Marks Card, Aadhaar.
  - `doc_domicile_cert` $\rightarrow$ depends on Aadhaar, School Study Certificate.
* **Resolution / Status:** Logged for Coding Round 2 DAG refinement. Baseline `KNOWN_PREREQUISITES` to be added into `planning.py`.

### Issue 3.3: Missing `issuing_authority` in `ChecklistItem`
* **Location:** [`member2/models.py`](file:///home/kruthik/coding/Unlocked/member2/models.py#L214) & [`member2/documents.py`](file:///home/kruthik/coding/Unlocked/member2/documents.py)
* **Severity:** Low
* **Symptom:** `ChecklistItem` omits `issuing_authority: str` which was in [`docs/agents.md` §4.1](file:///home/kruthik/coding/Unlocked/docs/agents.md#L288).
* **Impact:** Citizens lose context on *where* to obtain each certificate (e.g. Nadakacheri, Tahsildar, UIDAI, College Administration).
* **Recommended Fix:** Add `issuing_authority: Optional[str]` to `DocumentSpec` and populate it in `ChecklistItem`.

---

## 2. Eligibility & Verification Agent (Agent 2) Issues

### Issue 2.1: Unverified Criteria Suppress Question Generation
* **Location:** [`member2/questions.py`](file:///home/kruthik/coding/Unlocked/member2/questions.py#L69-L76) (`_useful_usage`)
* **Severity:** High
* **Symptom:** If discovered candidate schemes have criteria marked with `status: "unverified"` or `"uncertain"`, `generate_consolidated_questions()` returns an empty list (`[]`).
* **Root Cause:** M2's scoring logic strictly ignores requirements unless `req.status == RequirementVerification.verified` (per `DECISIONS.md #31`). In real-world discovery, initial search or fallback results frequently contain `unverified` criteria.
* **Recommended Fix:** Allow unverified candidate requirements to be scored for consolidated question batches, optionally with a lower weighting or sensitivity penalty.

### Issue 2.2: Numeric String Inputs Fail Range Cleaning
* **Location:** [`member2/questions.py`](file:///home/kruthik/coding/Unlocked/member2/questions.py#L204-L213) (`_clean_value`)
* **Severity:** High
* **Symptom:** If a citizen types an income as a numeric string (e.g., `"200000"`, `"2,00,000"`, or `"250000"`), it fails to match preset band labels and is silently converted to `(AnswerState.unknown, None)`.
* **Root Cause:** String branch only checks `band.label.casefold() == value.strip().casefold()`.
* **Recommended Fix:** If string input is not a band label, attempt parsing with `_to_float(value)` to set `{"min": val, "max": val}` before defaulting to `unknown`.

### Issue 2.3: Tiered/Category-Specific Criteria Misclassified as Contradictions
* **Location:** [`member2/assess.py`](file:///home/kruthik/coding/Unlocked/member2/assess.py#L90-L102) (`contradictory_requirement_ids`)
* **Severity:** Medium
* **Symptom:** Valid government rules with multiple tiers (e.g., income ceiling of ₹2.5 Lakhs for SC/ST, but ₹1.0 Lakh for OBC under SSP) are flagged as internal contradictions. Both requirements receive `needs_clarification`, setting the overall scheme status to `uncertain`.
* **Root Cause:** `contradictory_requirement_ids` groups solely by `(attribute, operator)`.
* **Recommended Fix:** Allow distinct values when accompanying evidence or criteria indicate conditional/category qualifiers.

### Issue 2.4: Unforgiving `user_answers` Signature in `assess_schemes`
* **Location:** [`member2/assess.py`](file:///home/kruthik/coding/Unlocked/member2/assess.py#L34-L42) (`as_answer_map`)
* **Severity:** Medium
* **Symptom:** If Member 3 passes a flat dictionary of `{attribute: value}` (e.g., `{"annual_family_income": 150000}`) directly to `assess_schemes()`, Pydantic raises a `ValidationError` because it expects `Answer` objects.
* **Recommended Fix:** Add a guard in `as_answer_map` to automatically convert raw scalar values into `Answer(attribute=k, state=AnswerState.answered, value=v)`.

### Issue 2.5: Missing Attribute Aliases
* **Location:** [`member2/attributes.py`](file:///home/kruthik/coding/Unlocked/member2/attributes.py#L170-L245)
* **Severity:** Low
* **Details:**
  - `has_disability` does not list `"disability_status"` in its aliases (used in [`docs/agents.md` L237](file:///home/kruthik/coding/Unlocked/docs/agents.md#L237)).
  - `state` / `domicile_karnataka` does not list `"is_karnataka_resident"`.
* **Recommended Fix:** Add these common aliases to `_SPECS`.

### Issue 2.6: Brittle Substring Matching in LLM Extraction
* **Location:** [`member2/normalize.py`](file:///home/kruthik/coding/Unlocked/member2/normalize.py#L271-L275)
* **Severity:** Low
* **Symptom:** Valid rules extracted from `eligibility_text` may be discarded if the LLM slightly normalizes punctuation, newlines, or Unicode quotes (`'` vs `’`), because of `if evidence not in haystack`.
* **Recommended Fix:** Normalize whitespace and punctuation in both `evidence` and `haystack` before evaluating containment.

---

## 3. LLM Integration Alignment

### Issue 3.1: Primary Model and SDK Alignment
* **Location:** [`member2/llm.py`](file:///home/kruthik/coding/Unlocked/member2/llm.py) & [`requirements-member2.txt`](file:///home/kruthik/coding/Unlocked/requirements-member2.txt)
* **Specification Target:** Gemini Flash (`gemini-2.5-flash` / `gemini-1.5-flash`) via Google SDK.
* **Current State:**
  - `AnthropicClient` (`claude-sonnet-5-5`) is featured as default in documentation.
  - `GeminiClient` is implemented using stdlib `urllib.request` targeting `gemini-flash-lite-latest`.
* **Action:** Keep `GeminiClient` as the primary default client when running in the production environment.

---

## 4. Contract Guide for Incoming Members (Priority: M2)

To ensure incoming modules integrate seamlessly with M2:

### For Member 1 (Discovery & Extraction):
Produce `SchemeRecord` dictionaries conforming to M2's expectations:
- `requirements`: List of objects with `criterion: str`, `source_url: str`, and `evidence: str` (verbatim quote).
- `documents`: List of objects with `name: str`, `source_url: str`, and `evidence: str`.
- `summary`: Scheme overview string.
- `official_sources`: List of official `.gov.in` / `.nic.in` URLs.

### For Member 3 (Backend Orchestration):
Follow the pipeline conventions established in [`member2/README.md`](file:///home/kruthik/coding/Unlocked/member2/README.md):
- Normalize schemes once at discovery time; persist `normalized_by` markers.
- Seed initial answers from the context form using `apply_answers(..., state=AnswerState.answered)`.
- Always pass arguments to `build_action_plan(selected_schemes, ...)` with keyword arguments: `user_documents=...`, `assessments=...`.

### For Member 4 (Frontend UI):
- Question options for selects must be submitted matching `Question.options`.
- Range answers can be submitted either as band label strings (from `Question.ranges`) or as numeric dictionaries `{"min": ..., "max": ...}`.
- Skips and "not sure" responses must be submitted as state objects: `{"attribute": "...", "state": "skipped" | "unknown" | "prefer_not_to_answer"}`.

