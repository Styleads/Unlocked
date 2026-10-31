"""User-reported application progress. Submission, decision, receipt and
attendance are separate facts: none is ever inferred from another. Odd
combinations are kept as reported and turned into a follow-up question."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from .models import (
    ApplicationProgress,
    DecisionState,
    FactState,
    FollowUp,
    ProgressResult,
    ProgressUpdate,
    Reported,
)

ALLOWED = {
    "submitted": {s.value for s in FactState},
    "decision": {s.value for s in DecisionState},
    "benefit_received": {s.value for s in FactState},
    "appointment_attended": {s.value for s in FactState},
}

QUESTIONS = {
    "submitted": ("Have you submitted your application?", ["yes", "no", "unknown"]),
    "decision": ("Have you received a decision on your application?", ["pending", "approved", "rejected", "unknown"]),
    "benefit_received": ("Have you actually received the benefit (for example, money in your account)?", ["yes", "no", "unknown"]),
}


def _follow_up(field: str) -> FollowUp:
    q, opts = QUESTIONS[field]
    return FollowUp(id=f"fu_{field}", question=q, field=field, options=opts)


def _summary(p: ApplicationProgress) -> str:
    parts = []
    sub, dec, rec = p.submitted.state, p.decision.state, p.benefit_received.state
    parts.append({"yes": "You reported that you submitted the application.",
                  "no": "You reported that you haven't submitted yet."}.get(sub, "Submission not reported yet."))
    parts.append({"pending": "You're waiting for a decision.", "approved": "You reported it was approved.",
                  "rejected": "You reported it was rejected."}.get(dec, "No decision reported yet."))
    if rec == "yes":
        parts.append("You reported receiving the benefit.")
    elif rec == "no" and dec == "approved":
        parts.append("Approved, but you haven't received the benefit yet.")
    if any(f.simulated for f in (p.submitted, p.decision, p.benefit_received, p.appointment_attended)):
        parts.append("(Includes a simulated demo outcome.)")
    return " ".join(parts)


def update_progress(
    progress: Optional[ApplicationProgress | dict],
    scheme_id: str,
    updates: Iterable[ProgressUpdate | dict] = (),
    *,
    now: Optional[datetime] = None,
) -> ProgressResult:
    """Apply user reports and return the new record (input is not mutated),
    follow-up questions and warnings."""
    if progress is None:
        p = ApplicationProgress(scheme_id=scheme_id)
    else:
        p = (progress if isinstance(progress, ApplicationProgress) else ApplicationProgress.model_validate(progress)).model_copy(deep=True)
    now = now or datetime.now(timezone.utc)
    warnings: list[str] = []

    for raw in updates:
        u = raw if isinstance(raw, ProgressUpdate) else ProgressUpdate.model_validate(raw)
        state = u.state.strip().lower()
        if u.field not in ALLOWED or state not in ALLOWED[u.field]:
            warnings.append(f"Ignored an update we don't recognise ({u.field}).")
            continue
        setattr(p, u.field, Reported(state=state, reported_at=now, simulated=u.simulated))
        p.history.append({"field": u.field, "state": state, "at": now.isoformat(), "simulated": u.simulated})

    sub, dec, rec = p.submitted.state, p.decision.state, p.benefit_received.state
    follow_ups: list[FollowUp] = []
    # Ask about the earliest stage that is unknown but implied by a later report;
    # never fill it in ourselves.
    if sub == "unknown" and (dec in {"pending", "approved", "rejected"} or rec == "yes"):
        follow_ups.append(_follow_up("submitted"))
    if sub == "yes" and dec == "unknown":
        follow_ups.append(_follow_up("decision"))
    if dec == "approved" and rec == "unknown":
        follow_ups.append(_follow_up("benefit_received"))
    if rec == "yes" and dec == "unknown" and sub != "unknown":
        follow_ups.append(_follow_up("decision"))

    if sub == "no" and dec in {"approved", "rejected"}:
        warnings.append("You reported a decision but also that you haven't submitted. Please check both answers.")
    if rec == "yes" and dec == "rejected":
        warnings.append("You reported receiving the benefit after a rejection. Please check both answers.")
    if rec == "yes" and sub == "no":
        warnings.append("You reported receiving the benefit but also that you haven't submitted. Please check both answers.")

    return ProgressResult(progress=p, follow_ups=follow_ups, warnings=warnings, summary=_summary(p))
