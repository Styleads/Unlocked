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
- [ ] **Integration with Member 1's real output not yet checked.** Field names follow plan.md §5; confirm against their actual JSON.
- [ ] **Integration with Member 3's backend not yet checked.** They must normalize once and persist, seed answers from the context form, and pass keyword args to `build_action_plan` (see README).
- [ ] `residence_area` and `household_card_type` attributes (DECISIONS #20): remove if the real demo schemes never use them.

## Known bugs

None open.

## Next steps

1. Get a sample of Member 1's scheme JSON and run `python -m member2.check_member1 <file>`; fix or report every line it prints.
2. Pair with Member 3 on the API wiring.

## Session log

### 2026-10-31 (later)
- Added `check_member1.py` + tests (282 passed). Gemini key saved with `setx` on Varun's machine; live check passes with no setup.
- Fixed domicile rephrase drift (`keep_wording`, DECISIONS #54).
- Live check passed on Gemini after model-name fixes (404/503); default model now `gemini-flash-lite-latest`.
- Added `GeminiClient`, `default_client`, `live_check.py`, `tests/member2/test_gemini.py`. 275 passed.

### 2026-10-31
- Reviewed the project from files (no saved memory existed). Tests: 266 passed.
- Created this `STATUS.md` as the session handoff file and added the update rule to `CLAUDE.md`.
