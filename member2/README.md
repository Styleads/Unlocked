# member2: Eligibility, Verification & Planning

Agents 2 and 3 from `plan.md`. Pure, synchronous Python: no database and no network (except the optional LLM adapter). Member 3 stores everything and passes it back in.

```
pip install -r requirements-member2.txt
python -m pytest tests/member2 -q
```

## Usage (Member 3)

```python
from member2 import (AnthropicClient, normalize_requirements, assess_schemes, generate_consolidated_questions,
                     apply_answers, reassess_schemes, build_action_plan)

schemes = normalize_requirements(member1_records, llm=AnthropicClient())  # once per discovery run; persist the result
answers, history = apply_answers({}, {}, context_form_answers)            # seed from the context form
assessments = assess_schemes(schemes, answers)                             # GET /api/schemes
questions = generate_consolidated_questions(schemes, answers, history)     # GET /api/questions
answers, history = apply_answers(answers, history, submitted)              # POST /api/answers, then persist both
assessments = reassess_schemes(schemes, answers)
plan = build_action_plan(selected, user_documents=docs, assessments=assessments)  # GET /api/plan
```

Every model has `.model_dump(mode="json")`. Inputs may be the models or plain dicts/lists (e.g. straight from SQLite). Inputs are never mutated. `run_pipeline(schemes, answers, history)` does normalize → assess → questions in one call and returns JSON-ready dicts.

## Things Member 3 must do

- **Normalize once per discovery run and save the normalized schemes.** They carry a `normalized_by` marker that stops repeat LLM calls. Normalization never raises; failures show up in `scheme.uncertainties`.
- **Seed answers from the context form** with `apply_answers` (state `answered`). Otherwise those questions get asked again.
- **Persist `answers` and `history` exactly as returned.** `history` maps question id (`"q_" + attribute`) to the last answer state; a question in any state other than `unanswered` is never re-asked in the consolidated flow.
- **Call `build_action_plan` with keyword arguments** after the first one.
- **Checklist progress:** `user_documents` is `{doc_id: "have" | "obtained" | "needed" | "unknown"}`; `ChecklistItem.id` is the doc id.
- **LLM:** set `ANTHROPIC_API_KEY` (or log in with `ant auth login`). The model comes from `UNLOCKED_MODEL` (default `claude-sonnet-5-5`). Without an LLM, everything still works; text-only rules from Member 1 stay unmapped and show as *Uncertain*.

## Answer formats (Members 3 & 4)

| Input type | Submit | Example |
|---|---|---|
| `range` (income) | `{"min", "max"}` (inclusive, either may be `null`) or a band label from `Question.ranges` | `{"min": 100000, "max": 250000}` |
| `select` | one of `Question.options` (case-insensitive) | `"Aided"` |
| `boolean` | `true` / `false` or `"Yes"` / `"No"` | `true` |
| `number` | number or numeric string | `72.5` |
| `text` | string | `"Mysuru"` |

"Not sure", skip and prefer-not-to-answer are **states**, not values: send `{"attribute": "...", "state": "unknown" | "skipped" | "prefer_not_to_answer"}`. A value that can't be read becomes `unknown`, never a failure.

## Statuses

Scheme: `potential_match`, `more_information_needed`, `not_yet_verified`, `unlikely_to_match`, `uncertain`. These are Unlocked's assessment, never an official decision; every `explanation` already says so.
Requirement: `satisfied`, `not_satisfied`, `unknown`, `needs_clarification`, `unverified`.

## Member 1

Extract toward the attribute ids in `attributes.py`. Each requirement needs `criterion`, `source_url` and a verbatim `evidence` quote (`attribute`/`operator`/`value` may be null; the normalizer fills them). Documents should be `{name, source_url, evidence}`; a bare string is accepted but has no source, so it is left out of the plan.

Design choices and deviations from the spec: `DECISIONS.md`.
