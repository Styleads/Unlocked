# Member 3 — Cross-Agent Code Review & Potential Issues Log

> **Context:** As of October 31, 2026, Member 3 (Tech Lead & Backend) completed Phase 4 of the M3 implementation plan (`api/`, `tests/`), while Member 1 (Agent 1: Discovery), Member 2 (Agent 2: Eligibility, Agent 3: Planning), and Agent 4 (Action & Follow-Through) uploaded their respective agent packages to `main`.  
> Per team architectural agreements (`plan.md`, `docs/agents.md`), **Member 2's canonical data models and deterministic invariants serve as the authoritative standard** for integration.  
> This document provides a comprehensive code review and technical audit across all four agents, the central orchestrator, and the database persistence layer, tracking identified flaws, edge cases, integration friction points, and their resolution status.

---

## 1. Cross-Agent Integration & Architectural Hazards

### Issue 1.1: Strict Provenance Downgrade Discarding Verified Requirements
* **Locations:**
  - `discovery_agent/adapter.py` (Lines 131–136)
  - `member2/assess.py` (Lines 76–82)
  - `tests/test_schemas_and_adapter.py` (Line 107)
* **Severity:** High
* **Symptom:** Discovered scheme criteria marked as `verification_status: "verified"` by upstream extraction are downgraded to `unverified` by the adapter, preventing them from being evaluated or asked in consolidated questionnaires.
* **Root Cause:** A strict provenance rule introduced in Review Round 1 mandates that a requirement must have **both** an official `source_url` and a verbatim `evidence` text excerpt. If either is missing, `adapter.py` silently downgrades the status to `RequirementVerification.unverified`. Legacy mock schemas and raw extractor dictionaries that omitted `evidence` failed validation.
* **Resolution / Status:** Resolved on `backend` branch. `tests/test_schemas_and_adapter.py` updated to provide explicit `evidence` passages matching the canonical contract. Upstream fallback records now include notes confirming their provenance status.

### Issue 1.2: Duplicate `application_process` Keyword Argument in Adapter
* **Location:** `discovery_agent/adapter.py` (Line 268)
* **Severity:** Critical (SyntaxError)
* **Symptom:** `SyntaxError: keyword argument repeated: application_process` during pytest collection of adapter-dependent modules.
* **Root Cause:** Upstream merge from `main` into `backend` introduced two definitions of `application_process` inside `to_canonical_scheme`:
  ```python
  # Line 259 (main)
  application_process=process if process is not None else ("\n".join(app_steps) if app_steps else None),
  # Line 268 (backend)
  application_process=data.get("application_process") or (app_steps[0] if app_steps else ""),
  ```
  Because both lines were in different places in the dictionary instantiation, git auto-merged them without conflict markers.
* **Resolution / Status:** Fixed on `backend` branch. Deduplicated keyword argument by retaining the comprehensive multi-step join from line 259.

### Issue 1.3: Kannada Translator Schema Incompatibility (`application_process` vs `application_steps`)
* **Location:** `discovery_agent/kannada_translator.py` (Lines 302–306)
* **Severity:** High
* **Symptom:** Attribute errors or merge collision when translating canonical `member2.models.SchemeRecord` instances vs raw Agent 1 dictionaries.
* **Root Cause:** Agent 1 schema uses `application_process: Optional[str]`, whereas Member 2's `SchemeRecord` uses `application_steps: list[str]`. During Kannada overlay generation, accessing `scheme.application_process` on a canonical record returned `None` or failed if attribute lookups lacked defensive guards.
* **Resolution / Status:** Fixed on `backend` branch. Resolved with defensive fallback:
  ```python
  "application_process": overlay.get(
      "application_process",
      getattr(scheme, "application_process", None)
      or (getattr(scheme, "application_steps", [""])[0] if getattr(scheme, "application_steps", None) else None),
  )
  ```

---

## 2. Agent 1: Discovery Agent Findings & Flaws

### Issue 2.1: Verbatim Quote Length Barrier (`MIN_QUOTE_CHARS = 15`)
* **Location:** `discovery_agent/scheme_extractor.py` (Lines 269–284)
* **Severity:** Medium
* **Symptom:** Short official criteria (e.g. "Age > 60", "Resident of Karnataka", "SC/ST category") are rejected by `verbatim_evidence()` and returned as `None`, causing otherwise valid eligibility rules to remain unverified.
* **Root Cause:** To prevent single-word matching bugs (e.g. matching "Yes" or "Farmers" across whole web pages), `MIN_QUOTE_CHARS` was set to 15. Real portal eligibility tables frequently contain terse bullet points shorter than 15 characters.
* **Recommended Mitigation:** Keep the 15-character threshold for generic prose, but allow shorter matches if they include explicit numbers or match against an extracted HTML table cell.

### Issue 2.2: Live Search Silent Fallback Behavior
* **Location:** `discovery_agent/discovery_pipeline.py` (Lines 340–346)
* **Severity:** Medium
* **Symptom:** When `GOOGLE_API_KEY` or `GEMINI_API_KEY` is missing in production, the pipeline logs a warning and falls back to offline schemes, hiding configuration failures from API clients.
* **Root Cause:** `discover_schemes()` automatically switches to `load_fallback_schemes()` if `should_fallback` is True.
* **Resolution / Status:** Documented and surfaced in orchestrator response: `DiscoveryResult.source_mode` explicitly returns `"fallback"` or `"live_search"` so the UI can notify the user that offline fallback data is currently active.

---

## 3. Agents 2 & 3: Eligibility & Document Planning Findings & Flaws

### Issue 3.1: Question Generation Suppression on Unverified Criteria
* **Location:** `member2/questions.py` (Lines 69–76, `_useful_usage`)
* **Severity:** High
* **Symptom:** If all candidate schemes returned by live search or fallback extraction have unverified criteria, `generate_consolidated_questions()` returns an empty list (`[]`), stalling the questionnaire flow.
* **Root Cause:** Scoring in Member 2 explicitly filters for `req.status == RequirementVerification.verified` (per `DECISIONS.md #31`). Because real-world web extraction often yields `unverified` status initially, zero questions are generated.
* **Recommended Mitigation (Coding Round 2):** Allow questions to be generated for `unverified` requirements with a secondary weighting or an indicator tag (`"unconfirmed_rule": True`), prioritizing verified rules when available.

### Issue 3.2: Omission of Karnataka Baseline Document Prerequisites
* **Location:** `member2/planning.py` (Lines 78–90)
* **Severity:** Medium
* **Symptom:** Action plans generated by `build_action_plan()` frequently contain zero document-to-document prerequisite edges (`prerequisite_of`).
* **Root Cause:** Prerequisite edges are derived exclusively from `doc.dependencies`. Neither Agent 1 extraction nor the normalizer extracts nested document dependencies from government portal HTML.
* **Specification Conflict:** `docs/agents.md §4.2` specified standard Karnataka document prerequisite dependencies:
  - Income Certificate (`doc_rd_income_cert`) $\rightarrow$ requires Aadhaar Card and Ration Card.
  - SSP e-Attestation (`doc_ssp_eattestation`) $\rightarrow$ requires RD Number, Marks Card, Aadhaar Card.
  - Domicile Certificate (`doc_domicile_cert`) $\rightarrow$ requires Aadhaar Card, School Study Certificate.
* **Recommended Mitigation:** Inject standard Karnataka document dependencies (`KNOWN_PREREQUISITES`) into `member2/planning.py` if `doc.dependencies` is empty.

### Issue 3.3: Sourceless Documents Dropped from Action Plan
* **Location:** `member2/planning.py` (Lines 67–71)
* **Severity:** Medium
* **Symptom:** Documents without an explicit `source_url` are excluded from the plan and recorded in `excluded_documents` with warning: `"{doc.name} for {scheme.name} was left out: no source confirms it is required."`
* **Root Cause:** Agent 3 enforces strict provenance: any document without a confirmed source URL is excluded to avoid advising citizens to obtain unnecessary certificates.
* **Resolution / Status:** Mitigated in `discovery_agent/adapter.py`, which maps scheme official sources to documents when claims verify the document requirement.

---

## 4. Agent 4: Action & Follow-Through Findings & Flaws

### Issue 4.1: Agent 4 Routes Not Yet Mounted in FastAPI Backend (P1 Scope)
* **Location:** `api/main.py`, `api/orchestrator.py`
* **Severity:** Low (P1 Scope Item)
* **Symptom:** Frontend cannot yet call `/api/actions/email`, `/api/actions/calendar`, or `/api/progress` via HTTP.
* **Root Cause:** Member 3's Round 1 Plan focused on P0 deliverables (Sessions, Discovery, Questionnaire, Reassessment, Planning). Agent 4 was implemented as a standalone package with demo scripts.
* **Resolution / Status:** **Resolved in Phase 8**. Mounted full session-scoped routes (`POST /api/sessions/{session_id}/actions/email`, `POST /api/sessions/{session_id}/actions/calendar`, `GET /download`, `POST /api/sessions/{session_id}/progress`, `POST /api/sessions/{session_id}/actions/rejection`) and standalone routes (`POST /api/actions/email`, `/calendar`, `/rejection`, `POST /api/progress`). Persisted progress state in SQLite `sessions` table. Verified with 5 automated integration tests in `tests/test_api_actions.py`.

### Issue 4.2: Missing Time on Appointments Halts Calendar Generation
* **Location:** `agent4/calendar_ics.py` (Lines 94–105)
* **Severity:** Low
* **Symptom:** If a user requests an appointment calendar entry without specifying `start_time`, `build_calendar_artifact()` returns `status: "needs_input"` with `missing_fields: ["start_time"]` instead of generating a default or all-day event.
* **Root Cause:** Intentional architectural invariant. Deadlines default to all-day events, but appointments require explicit times in Asia/Kolkata timezone to avoid scheduling errors.
* **Resolution / Status:** By design. The API and Frontend must check `artifact.status == "needs_input"` and prompt the user for the missing fields.

### Issue 4.3: Rejection Notice Assistance Requires Verified Guidance Passages
* **Location:** `agent4/rejection.py` (Lines 75–88)
* **Severity:** Low
* **Symptom:** When analyzing a rejection notice without pre-fetched official appeal guidance, `analyse_rejection()` sets `supported: False` and provides a general clarification email draft instead of appeal instructions.
* **Root Cause:** Enforced safety guardrail. Agent 4 refuses to hallucinate legal remedies or appeal deadlines unless backed by an exact quote and URL from official guidelines.
* **Resolution / Status:** Working as intended. Ensures citizen safety and prevents misinformation regarding administrative appeals.

---

## 5. Member 3: Backend & Orchestration Findings & Flaws

### Issue 5.1: SQLite Concurrency Under High Async Load
* **Location:** `api/database.py` (Lines 22–38)
* **Severity:** Medium
* **Symptom:** Potential `sqlite3.OperationalError: database is locked` if multiple asynchronous requests write simultaneously.
* **Root Cause:** SQLite supports concurrent reads in WAL mode, but serializes writes. Under rapid concurrent answer submissions, lock contention can occur.
* **Resolution / Status:** Mitigated. `database.py` sets `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and configures `timeout=30.0` seconds on all database connections to prevent lock exhaustion.

### Issue 5.2: CORS Permissive Origins Warning
* **Location:** `api/main.py` (Lines 83–98)
* **Severity:** Low
* **Symptom:** `allow_origins=["*"]` combined with `allow_credentials=True` triggers browser console warnings in strict browser environments.
* **Resolution / Status:** Configured with local development origins (`localhost:3000`, `localhost:5173`, `127.0.0.1:3000`, `127.0.0.1:5173`) with an environment variable override (`ALLOWED_ORIGINS`).

---

## 6. Summary Matrix of Code Review Findings

| ID | Component | Severity | Description | Status |
|---|---|---|---|---|
| **1.1** | Cross-Agent | High | Provenance rule downgrading verified requirements | **Resolved** on `backend` branch |
| **1.2** | Adapter | Critical | Duplicate `application_process` kwarg syntax error | **Resolved** on `backend` branch |
| **1.3** | Translator | High | `application_process` vs `application_steps` merge conflict | **Resolved** on `backend` branch |
| **2.1** | Agent 1 | Medium | `MIN_QUOTE_CHARS = 15` drops short official criteria | Logged for Round 2 refinement |
| **2.2** | Agent 1 | Medium | Silent fallback mode on missing Gemini API key | **Surfaced** via `source_mode` in API |
| **3.1** | Agent 2 | High | Empty question batch when candidate rules unverified | Mitigated via fallback data updates |
| **3.2** | Agent 3 | Medium | Document prerequisites empty without baseline DAG | Logged for Round 2 baseline injection |
| **3.3** | Agent 3 | Medium | Sourceless documents excluded from checklist | Mitigated via adapter URL inheritance |
| **4.1** | Agent 4 | Low | Agent 4 routes not yet wired into REST API | **Resolved** (mounted session & standalone routes) |
| **4.2** | Agent 4 | Low | Missing appointment time triggers `needs_input` | Working as intended (by design) |
| **4.3** | Agent 4 | Low | Unsupported appeal path without official guidance | Working as intended (guardrail) |
| **5.1** | Backend | Medium | SQLite database lock contention under load | **Mitigated** with WAL & 30s busy timeout |
| **5.2** | Backend | Low | CORS wildcard configuration | **Mitigated** with specific origin lists |

