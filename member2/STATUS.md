# Member 2 — Status & Session Log

Handoff file. A new session reads this first, then `DECISIONS.md`, then the code.
Update it at the end of every working session (and whenever a feature, bug or open question changes).

- **Features / state** → this file, sections below.
- **Design decisions & deviations from the spec** → `DECISIONS.md` (numbered; never renumber).
- **Session history** → "Session log" at the bottom, newest first.

## Current state (2026-10-31)

- All phases built: 0, 1, 2, 3, 5 (questions), 4 (normalizer), 6 (planning), plus a wording-polish pass.
- `python -m pytest tests/member2 -q` → **282 passed**, offline, no API key.
- Final review: **Nov 1, 8:30 AM** (plan.md).

## Features

| Area | Module | Status |
|---|---|---|
| Models (Answer state separate from value, SchemeRecord, Requirement, ChecklistItem…) | `models.py` | Done |
| Attribute registry + income bands + documents | `attributes.py`, `documents.py` | Done |
| Comparators (interval logic, Indian digit grouping, booleans ≠ numbers) | `comparators.py` | Done |
| Assessment + roll-up + contradictions (`assess_schemes`, `reassess_schemes`) | `assess.py` | Done |
| Questions: consolidated + scheme-specific, dedup, ranking, LLM rephrase; `apply_answers` | `questions.py` | Done |
| Normalizer: structure Member 1 criteria + extract from `eligibility_text`, number check | `normalize.py`, `llm.py` | Done |
| Action plan: document graph, sourced edges only, deterministic order (`build_action_plan`) | `planning.py` | Done |
| Demo script | `demo.py` | Done |
| LLM clients: Claude + Gemini (free tier), `default_client()` | `llm.py` | Done (DECISIONS #53) |
| Member 1 JSON contract checker (`python -m member2.check_member1 file.json`) | `check_member1.py` | Done; tested on fixtures + a broken file |
| Live LLM check on a fictional scheme | `live_check.py` | Confirmed on real Gemini (2026-10-31): 4 rules extracted, all verified, correct attributes |
| Usage docs for Member 3 | `README.md` | Done |

## Open issues / risks

- [x] Live LLM path confirmed with Gemini (`gemini-flash-lite-latest`). Claude path still untested live (no key).
- [x] Domicile question drifted to "native" under rephrase: fixed with `keep_wording` (DECISIONS #54).
- [x] **Integration with Member 1's output confirmed:** Member 1 built `discovery_agent/adapter.py` and updated `fallback_schemes.py` to output canonical `member2.models.SchemeRecord` instances with sourced documents.
- [x] **Integration with Member 3's backend planned:** M3 updated `M3_Coding_Round_1_Plan.md` adopting `apply_answers` context seeding, `history_json` persistence, and keyword arguments on `build_action_plan`.
- [ ] `residence_area` and `household_card_type` attributes (DECISIONS #20): remove if the real demo schemes never use them.

## Known bugs

None open.

## Next steps

1. Validate live extraction through `discovery_agent/adapter.py` using `python -m member2.check_member1`.
2. Support Member 3 during end-to-end API wiring and SQLite session persistence tests.

## Session log

### 2026-11-01 (What would change a rejection)
- `member2/what_if.py` + `GET /schemes/{id}/what-if`; a "rejected" follow-up answer returns it immediately. Frontend: the "How did it go?" card asks which scheme and the reason, then shows what decided it, other answers that would meet each rule with their effect on every scheme, and schemes that already fit; "This is true for me: update my answer" re-assesses in place (`live.updateAnswer`).

### 2026-11-01 (Demo flow)
- Email on step 1 (Start page) turns emails on for the session; consent checkbox removed. Office chat runs inline in every Next-steps scheme card: pick the office's response, it auto-plays and confirms. Confirmation -> email now + reminder + follow-up + appointment row (agent4/DECISIONS.md 25-26).
- Demo fallback: `?fallback=1` in the site URL or `UNLOCKED_FORCE_FALLBACK=1` for the backend.

### 2026-11-01 (After-appointment follow-up)
- Agent 4 `follow_up.py`: decides when an appointment is over and needs a "How did it go?", and turns the answer into next steps (agent4/DECISIONS.md 23-24). API: `GET /api/sessions/{id}/follow-ups`; the outcome endpoint now applies the plan (status, new date, return visit, documents to the checklist) and stores it in `outcome_details.plan`.
- Frontend: "How did it go?" card at the top of the Plan page (`pages/AfterAppointment.tsx`), next steps shown after answering, in the Appointments list, and on the email follow-up page.
- Fixed: `ZoneInfo("Asia/Kolkata")` failed on Windows, so confirmed simulated appointments were never saved; now a fixed +05:30 offset.
- Open: "ask later" questions (decision, benefit received) are stored in the plan but not yet asked again on a schedule.

### 2026-11-01 (Review of feat/whatsappsim + Office Chat in the frontend)
- Merged `origin/feat/whatsappsim` onto main on branch `fix/whatsappsim-review` and fixed what the review found: model-decided statuses (now deterministic, model rewords only), invented slot/hours/preferences/phone numbers, invented fallback office contacts (now `simulated`/`unverified`), no guards on advance/user-input/finish, IST stamped as UTC, enum text in the outcome, duplicate confirmations, broken `interactive_cli` office chat (now drives the real endpoints). See `agent4/DECISIONS.md` 20-22. 665 backend tests pass.
- Frontend: new `/office-chat` page (`pages/OfficeChat.tsx`), `api.ts` calls, entry button "Try an office chat (simulated)" in Next steps. 66 frontend tests pass (7 new in `office-chat.test.tsx`).
- Open: the document list in the simulated appointment email is empty unless `documents` is passed (not yet wired from the plan checklist); scenario ids are the backend's fixed script names (no listing endpoint).

### 2026-10-31 (Option A Feature Freeze & Backend Ready for Frontend Integration)
- Member 3 froze backend feature work per Option A: 455 tests passing 100% green offline.
- Backend is hardened, durable, and ready for full end-to-end integration testing with Member 4 (Frontend).
- Cleaned up temporary planning documents and synchronized all agent logs.

### 2026-10-31 (Phase 8 Agent 4 REST Integration Complete)
- Member 3 implemented Phase 8: mounted all Agent 4 Action & Follow-Through routes in `api/main.py` and `api/orchestrator.py` (`POST /api/sessions/{id}/actions/email`, `/calendar`, `/progress`, `/rejection` and standalone endpoints).
- Added `progress_json` SQLite persistence to `api/database.py` with multi-state application tracking and follow-up generation.
- Added 5 integration tests in `tests/test_api_actions.py`. Total unified test suite reached **455 passed tests** (100% green offline in 1.91s).

### 2026-10-31 (Integrated Backend & Agent 4 Synchronization)
- Full multi-agent suite verified on branch `backend`: 450 tests passing offline in ~1.8s (M1: 79 tests, M2: 282 tests, M3 backend: 28 tests, Agent 4: 61 tests).
- Synchronized `M3_Coding_Round_1_Plan.md` with active branch `backend`, unified package tree including `agent4/`, `anthropic>=0.40.0`, canonical `discover_schemes` return type (`list[member2.models.SchemeRecord]`), and Phase 8–10 roadmap.
- Hardened database connection with 30s busy timeout and tightened CORS allowed origins in `api/`.
- All contracts between M1, M2, M3 backend, and Agent 4 confirmed 100% aligned.

### 2026-10-31 (Member 3 Phase 1 & Phase 2 Integration)
- Member 3 completed Phase 1 (frozen contracts in `api/schemas.py`, adapter verification) and Phase 2 (aiosqlite persistence in `api/database.py`).
- Phase 3 master orchestrator implemented in `api/orchestrator.py` executing discovery -> normalization -> assessment -> consolidated questions -> document planning DAG.
- Phase 4 FastAPI REST application implemented in `api/main.py` exposing session CRUD, discovery, questions, answers, and action planning endpoints to Member 4.
- All 6 HTTP integration tests in `tests/test_api.py` passing 100%. Total repository test suite: 366 passed.

### 2026-10-31 (Review Round 1)
- Harmonized contracts across team: `docs/agents.md` updated to treat `plan.md §5` and `member2` as the single source of truth.
- Member 1 built `discovery_agent/adapter.py` and converted `fallback_schemes.py` to produce canonical `member2.models.SchemeRecord` records with sourced `DocumentRequirement` objects.
- Member 3 updated `M3_Coding_Round_1_Plan.md` to directly orchestrate Member 2's `normalize_requirements`, `assess_schemes`, `generate_consolidated_questions`, and `build_action_plan`.
- Merged branches into `feat/agent1v2` and `main`. 282 offline tests remain 100% green.

### 2026-10-31 (later)
- Pushed to team repo `Styleads/Unlocked`, branch `feat/agent2&agent3` (first pushed as `member2`, since deleted): code at repo root, plus docs/m2 updates (ADR-003..005, debugging log). No PR opened yet.
- Added `check_member1.py` + tests (282 passed). Gemini key saved with `setx` on Varun's machine; live check passes with no setup.
- Fixed domicile rephrase drift (`keep_wording`, DECISIONS #54).
- Live check passed on Gemini after model-name fixes (404/503); default model now `gemini-flash-lite-latest`.
- Added `GeminiClient`, `default_client`, `live_check.py`, `tests/member2/test_gemini.py`. 275 passed.

### 2026-10-31
- Reviewed the project from files (no saved memory existed). Tests: 266 passed.
- Created this `STATUS.md` as the session handoff file and added the update rule to `CLAUDE.md`.
