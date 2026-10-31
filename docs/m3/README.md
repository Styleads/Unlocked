# Member 3 — Tech Lead, Backend, SQLite & Integration

* **Assigned Modules:**
  * **FastAPI Backend & REST Endpoints**
  * **SQLite Database Models & Persistence**
  * **Workflow Orchestration Engine (`orchestrator.py`)**
  * **Shared Contracts & End-to-End Reliability**
* **Technical Contact:** Member 3 (Team Lead)
* **Master Architecture Plan:** [`plan.md`](file:///home/kruthik/coding/Unlocked/plan.md)
* **Shared Contract:** [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md)

---

## 1. Responsibilities & Goals

### Backend & Persistence (P0)
- [ ] Initialize Python repository structure, poetry/uv or requirements.txt, and FastAPI app.
- [ ] Build health check endpoint (`GET /api/health`).
- [ ] Configure SQLite database (WAL mode, async support via SQLAlchemy/aiosqlite or standard sqlite3).
- [ ] Define session lifecycle:
  - Generate UUID `session_id`.
  - Persist user context, discovery scope, candidate schemes.
  - Persist questions, answers, skipped states.
  - Persist scheme assessments and generated plans.
  - Support session reset / deletion (`DELETE /api/sessions/{session_id}`).
- [ ] Ensure privacy: no storage of Aadhaar numbers, biometric scans, or passwords.

### Central Orchestration (P0)
- [ ] Coordinate Agent 1 (Discovery), Agent 2 (Eligibility & Verification), and Agent 3 (Planning) in deterministic sequence.
- [ ] Provide mock responses to Member 4 immediately so frontend development isn't blocked.
- [ ] Expose stable REST API endpoints:
  - `POST /api/sessions`
  - `GET /api/sessions/{session_id}`
  - `POST /api/discover`
  - `GET /api/schemes`
  - `GET /api/schemes/{scheme_id}`
  - `GET /api/questions`
  - `POST /api/answers`
  - `GET /api/plan`
  - `POST /api/checklist/{item_id}`
  - `POST /api/actions` (P1)

---

## 2. Checkpoints Timeline

| Time | Target | Status |
|---|---|---|
| Oct 31, 5:30 PM | FastAPI runs, SQLite initializes, session created, contracts agreed | Pending |
| Oct 31, 7:00 PM | Review Round 1: Orchestrator connects context -> discovery -> initial result | Pending |
| Oct 31, 12:05 AM | Complete flow: discovery -> question storage -> reassessment persistence | Pending |
| Nov 1, 3:00 AM | End-to-end integration with frontend; document plan persisted | Pending |
| Nov 1, 6:30 AM | Code freeze, tag demo commit, dry-run rehearsed | Pending |

