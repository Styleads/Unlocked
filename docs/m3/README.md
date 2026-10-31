# Member 3 — Tech Lead, Backend, SQLite & Integration

* **Assigned Modules:**
  * **FastAPI Backend & REST Endpoints**
  * **SQLite Database Models & Persistence**
  * **Workflow Orchestration Engine (`orchestrator.py`)**
  * **Shared Contracts & End-to-End Reliability**
* **Technical Contact:** Member 3 (Team Lead)
* **Master Architecture Plan:** [`plan.md`](file:///home/kruthik/coding/Unlocked/plan.md)
* **Shared Contract:** [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md)
* **Potential Issues & Code Review Log:** [`docs/m3/potential_issues.md`](file:///home/kruthik/coding/Unlocked/docs/m3/potential_issues.md)
* **Test Status:** 455 tests passed offline (100% green in ~1.9s)
* **Integration Status:** Backend feature freeze (Option A) — 100% complete & ready for Frontend Integration

---

## 1. Responsibilities & Goals

### Backend & Persistence (P0)
- [x] Initialize Python repository structure, poetry/uv or requirements.txt, virtualenv, and base packages (Phase 0).
- [x] Build health check endpoint (`GET /api/health` and `GET /health`, Phase 4).
- [x] Configure SQLite database (WAL mode, async support via aiosqlite, Phase 2).
- [x] Define session lifecycle & persistence (Phase 2):
  - Generate UUID `session_id`.
  - Persist user context, discovery scope, candidate schemes.
  - Persist questions, answers, skipped states.
  - Persist scheme assessments and generated plans.
  - Support session reset / deletion (`DELETE /api/sessions/{session_id}`).
- [x] Ensure privacy: no storage of Aadhaar numbers, biometric scans, or passwords.

### Central Orchestration (P0)
- [x] Coordinate Agent 1 (Discovery), Agent 2 (Eligibility & Verification), and Agent 3 (Planning) in deterministic sequence (Phase 3).
- [x] Provide mock/live responses to Member 4 immediately so frontend development isn't blocked.
- [x] Expose stable REST API endpoints (Phase 4):
  - `POST /api/sessions`
  - `GET /api/sessions/{session_id}`
  - `DELETE /api/sessions/{session_id}`
  - `POST /api/sessions/{session_id}/discover`
  - `GET /api/sessions/{session_id}/schemes`
  - `GET /api/sessions/{session_id}/schemes/{scheme_id}`
  - `GET /api/sessions/{session_id}/questions`
  - `POST /api/sessions/{session_id}/answers`
  - `GET /api/sessions/{session_id}/plan`
  - `POST /api/sessions/{session_id}/checklist/{item_id}`
  - `POST /api/sessions/{session_id}/actions/email` (Phase 8)
  - `POST /api/sessions/{session_id}/actions/calendar` and `/download` (Phase 8)
  - `POST /api/sessions/{session_id}/progress` and `GET` (Phase 8)
  - `POST /api/sessions/{session_id}/actions/rejection` (Phase 8)
  - `POST /api/actions/email`, `/calendar`, `/rejection`, `/progress` (Standalone, Phase 8)

> [!IMPORTANT]
> **Orchestrator Rules for Calling Member 2's Modules:**
> 1. **Normalize once per discovery run and save the result:**
>    ```python
>    normalized_schemes = normalize_requirements(raw_schemes, llm=default_client())
>    await db.save_schemes(session_id, normalized_schemes)
>    ```
>    Schemes carry a `normalized_by` marker that stops repeat LLM calls. Pass `normalized_schemes` to all subsequent assessment and planning calls.
> 2. **Seed answers from the context form with `apply_answers`:**
>    ```python
>    answers, history = apply_answers({}, {}, context_form_answers)
>    ```
>    Without this, attributes already gathered during context initialization will be re-asked in consolidated questions.
> 3. **Preserve `answers` and `history`:**
>    When the user submits answers, call `apply_answers(answers, history, submitted)` and persist both. Do not merge into a flat dict `{**session.context, **answers}` because skips (`AnswerState.skipped`) and "not sure" (`AnswerState.unknown`) must remain distinct from answered values.
> 4. **Call `build_action_plan` with keyword arguments:**
>    The first argument is `selected_schemes`. All subsequent arguments must be named:
>    ```python
>    plan = build_action_plan(schemes, user_documents=docs, assessments=assessments)
>    ```

---

## 2. Checkpoints Timeline

| Time | Target | Status |
|---|---|---|
| Oct 31, 5:30 PM | FastAPI runs, SQLite initializes, session created, contracts agreed | Done |
| Oct 31, 7:00 PM | Review Round 1: Orchestrator connects context -> discovery -> initial result (M3 Plan updated) | Done |
| Oct 31, 10:20 PM | Review Round 1 Complete: All 6 stages implemented & verified (450 tests passing); Agent 4 merged | Done |
| Oct 31, 10:45 PM | Phase 8 Complete: Agent 4 REST routes (`/api/actions`, `/api/progress`) & SQLite persistence (455 tests passing) | Done |
| Oct 31, 12:05 AM | Coding Session 2: Frontend live wireup & bilingual translation parity | Up Next |
| Nov 1, 3:00 AM | Coding Session 3: End-to-end integration with frontend; document plan persisted | Pending |
| Nov 1, 6:30 AM | Code freeze, tag demo commit, dry-run rehearsed | Pending |

