"""Try all four Agent 4 actions on a fictional scheme. Run from the repo root:
    python -m agent4.demo          # templates only, offline
    python -m agent4.demo --live   # uses Gemini/Claude via member2.default_client()
The rejection is simulated and labelled as such."""
from __future__ import annotations

import sys
from datetime import date, datetime, time, timezone

from . import (
    CalendarRequest,
    EmailRequest,
    EventKind,
    SchemeContext,
    SourcedFact,
    analyse_rejection,
    build_calendar_artifact,
    build_email_draft,
    email_request_for_step,
    update_progress,
)

SCHEME = SchemeContext(
    id="demo_scholarship_a", name="Demo Scholarship A", department="Demo Welfare Department",
    application_url="https://example.gov.in/apply", official_sources=["https://example.gov.in/guidelines"],
    deadline="2026-12-15", deadline_source_url="https://example.gov.in/notice",
)
GUIDANCE = [SourcedFact(
    text="Applicants whose application is rejected for a document error may submit a correction within 15 days "
         "of the rejection notice through the portal.",
    source_url="https://example.gov.in/guidelines#corrections",
)]
NOTICE = "Your application has been rejected. Reason: Income certificate has expired."


def heading(text: str) -> None:
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


def show(a) -> None:
    by = f"  (by {a.generated_by})" if a.action_type.value == "email_draft" else ""
    print(f"[{a.status.value}] {a.title}{by}")
    if a.subject:
        print(f"Subject: {a.subject}")
    if a.target_destination:
        print(f"To: {a.target_destination}")
    if a.missing_fields:
        print(f"Missing: {a.missing_fields}")
    print(a.body_content.replace("\r\n", "\n"))
    for w in a.warnings:
        print(f"WARNING: {w}")


def main(argv: list[str]) -> None:
    llm = None
    if "--live" in argv:
        from member2 import default_client  # demo only; the agent4 package itself never imports member2

        llm = default_client()
        print(f"LLM: {type(llm).__name__} / {llm.model}")

    heading("1. Email draft (clarification)")
    show(build_email_draft(EmailRequest(
        scheme=SCHEME, purpose="clarification", question="Is the income limit for the whole family or only the student?",
        user_details={"Name": "Demo User"},
        facts=[SourcedFact(text="Annual family income must not exceed Rs 2,50,000.", source_url="https://example.gov.in/guidelines")],
    ), llm=llm))

    heading("2. Calendar: deadline from the sourced scheme record")
    show(build_calendar_artifact(CalendarRequest(scheme=SCHEME), now=datetime.now(timezone.utc)))

    heading("3. Calendar: appointment without a time (asks instead of guessing)")
    show(build_calendar_artifact(CalendarRequest(scheme=SCHEME, kind=EventKind.appointment, event_date=date(2026, 11, 20),
                                                 date_confirmed_by_user=True)))

    heading("4. Calendar: appointment with a time")
    show(build_calendar_artifact(CalendarRequest(scheme=SCHEME, kind=EventKind.appointment, event_date=date(2026, 11, 20),
                                                 date_confirmed_by_user=True, start_time=time(10, 30), location="Taluk Office")))

    heading("5. Progress: user reports approval only")
    r = update_progress(None, SCHEME.id, [{"field": "decision", "state": "approved"}])
    print(r.summary)
    for f in r.follow_ups:
        print(f"  follow-up: {f.question} {f.options}")

    heading("6. Rejection help (SIMULATED notice)")
    analysis = analyse_rejection(SCHEME, NOTICE, GUIDANCE, llm=llm, simulated=True)
    print(analysis.explanation)
    if analysis.reason_quote:
        print(f"  Reason (from your notice): {analysis.reason_quote}")
    for st in analysis.next_steps:
        print(f"  [{st.route.value}] {st.description}\n    \"{st.evidence}\" ({st.source_url})")
    for w in analysis.warnings:
        print(f"  WARNING: {w}")
    step = analysis.next_steps[0] if analysis.next_steps else None
    show(build_email_draft(email_request_for_step(SCHEME, step, "I have a renewed income certificate.", {"Name": "Demo User"}), llm=llm))


if __name__ == "__main__":
    main(sys.argv)
