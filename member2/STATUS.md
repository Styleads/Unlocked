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
