# Agent 4 — Decisions

`plan.md` §2.6 and the Member 1 section B are the spec; `docs/agents.md` §5 is the team's sketch. Where they differ, `plan.md` wins.

1. **Built in this repo by Member 2** (Varun's call, 2026-10-31), though plan.md assigns Agent 4 to Member 1. Standalone package, no `member2` imports (the demo's `--live` flag is the one exception, and it is a script).
2. **All four plan items** built: email draft, `.ics`, progress tracking, rejection help.
3. **`ActionArtifact` keeps agents.md §5.1 fields** (`action_type`, `title`, `body_content`, `target_destination`, `instructions`, `user_review_confirmed`) and adds `status`, `subject`, `filename`, `mime_type`, `missing_fields`, `source_urls`, `warnings`, `generated_by`. `ActionType` adds `progress_update`.
4. **The LLM only words emails and reads rejection notices.** Python decides what may appear: contacts must be sourced, numbers must be in the sources, quotes must be verbatim.
5. **Email numbers rule:** any number of two or more digits in an LLM draft that isn't in the scheme name, department, question, deadline, facts or allowed URLs rejects the whole draft (template used). Stricter than patching, and an invented date is worse than plain wording.
6. **User detail values never reach the LLM.** They are `{{Key}}` tokens, filled in after validation, so the checks never alter or flag them. Tokens the LLM drops are appended under "My details".
7. **The user's own question is theirs.** Contacts typed in it are kept; it is redacted (Aadhaar-like 12-digit numbers, phones, emails) before reaching an LLM.
8. **agents.md §5.3 `.ics` replaced**: its DTSTAMP was the deadline, it timed deadlines at 09:00 UTC (2:30 PM IST), didn't escape commas/semicolons, used LF and could exceed 75 octets. Ours: all-day deadlines, IST appointments with a VTIMEZONE (no DST in India), real DTSTAMP, uuid5 UID stable per scheme+kind+date.
9. **Calendar never guesses.** No time for an appointment → `needs_input` with `start_time`; default appointment length 1 hour when only a start is given.
10. **Progress is four independent facts**, each with `reported_at` and `simulated`. Follow-ups ask about the earliest implied-but-unknown stage. Contradictions are kept and warned about, never corrected.
11. **Rejection next steps need verbatim evidence** from a provided guidance passage, a valid route (`correction | reapplication | appeal | clarification`), and a description with no unsourced numbers. A reason summary is shown only with a verified reason quote.
12. **Logging:** task name, scheme id and exception type only.
