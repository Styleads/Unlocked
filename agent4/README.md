# agent4: Action & Follow-through

Agent 4 from `plan.md` (P1). It builds **artifacts the user reviews and uses themselves**. It never sends an email, submits an application or calls an official API.

Pure, synchronous Python. No database and no imports from `member2`. Member 3 stores everything and passes it back in.

```
python -m pytest tests/agent4 -q     # offline, no API key
python -m agent4.demo                # all four actions, templates only
python -m agent4.demo --live         # same, wording by Gemini/Claude
```

## Usage (Member 3)

```python
from agent4 import (build_email_draft, build_calendar_artifact, update_progress,
                    analyse_rejection, email_request_for_step, facts_from_scheme)
from member2 import default_client          # any object with complete_json(system, user) -> str

llm = default_client()                      # optional; None gives the deterministic template

# POST /api/actions {type: "email_draft"}
artifact = build_email_draft({"scheme": scheme, "purpose": "clarification",
                              "question": user_text, "user_details": {"Name": "..."},
                              # verified rules' exact quotes + links; optional topic filter
                              "facts": facts_from_scheme(scheme, attributes=["annual_family_income"])},
                             llm=llm)

# POST /api/actions {type: "calendar_ics"}  ->  if artifact.status == "needs_input", ask for artifact.missing_fields
artifact = build_calendar_artifact({"scheme": scheme, "kind": "deadline"})

# POST /api/progress
result = update_progress(saved_progress_or_None, scheme_id, [{"field": "decision", "state": "approved"}])
save(result.progress.model_dump(mode="json")); show(result.summary, result.follow_ups, result.warnings)

# POST /api/actions {type: "rejection_assist"}
analysis = analyse_rejection(scheme, notice_text, guidance_passages, llm=llm, simulated=is_demo)
draft = build_email_draft(email_request_for_step(scheme, analysis.next_steps[0] if analysis.supported else None,
                                                 user_text, user_details), llm=llm)
```

`scheme` may be a member2 `SchemeRecord`, its dict, or any dict with `id` and `name`. Unknown fields are ignored.

## What it guarantees

| Action | Guarantee |
|---|---|
| Email | No email address, link or phone number unless it comes from a **sourced** scheme field or the user's own question; anything else becomes a `[placeholder]`. An LLM draft containing any number not in the sources (an invented date, amount or id) is thrown away and the template is used. The LLM never sees the user's detail values; they are `{{tokens}}` until after the checks. |
| Calendar | A date is used only if the user confirmed it or it has a source. A scheme deadline is used only with `deadline_source_url`. Missing pieces are returned in `missing_fields`, never guessed. Deadlines are all-day; appointments are timed in Asia/Kolkata. Valid RFC 5545 (CRLF, folding, escaping, stable UID, reminders 3 days and 1 day before). |
| Progress | `submitted`, `decision`, `benefit_received` and `appointment_attended` are separate facts. None is inferred from another; an implied-but-unknown stage becomes a follow-up question. Contradictions are kept as reported and flagged. |
| Rejection | The notice is redacted (ID numbers, phones, emails) before the LLM sees it. A next step is kept only if its evidence is a verbatim quote from the guidance passages given, with that passage's source URL. No supported route means `supported: false` and an offer to draft a clarification email, never an invented appeal. Simulated notices are labelled. |

Every function returns a result; LLM failures never raise.

## Fields Member 1 could add to scheme records

Agent 4 reads these optional fields if present: `contact_email` + `contact_email_source_url`, `contact_phone` + `contact_phone_source_url`, `deadline` + `deadline_source_url`. Without a source URL a contact is not used.
