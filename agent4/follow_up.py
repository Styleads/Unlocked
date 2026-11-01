"""After an appointment: when to ask the user how it went, and what follows from their answer.

Pure and deterministic. Nothing here is inferred: a step, a document or a date appears only because the user reported
it. The caller stores appointments and passes them in; this module never reads a database or sends anything."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field, field_validator

from .models import ProgressUpdate

IST = timezone(timedelta(hours=5, minutes=30))  # India has no daylight saving; zoneinfo needs tzdata on Windows
# Same default length the calendar uses when only a start time is known (DECISIONS 9): the appointment is treated as
# over one hour after it starts, so the user is never asked mid-appointment.
DEFAULT_APPOINTMENT_LENGTH = timedelta(hours=1)
# Statuses meaning "booked, no outcome reported yet". Everything else has been answered or withdrawn.
OPEN_STATUSES = {"scheduled", "confirmed"}


class Attended(str, Enum):
    yes = "yes"
    rescheduled = "rescheduled"
    missed = "missed"
    cancelled = "cancelled"
    unknown = "unknown"


class Outcome(str, Enum):
    documents_accepted = "documents_accepted"
    additional_documents_requested = "additional_documents_requested"
    application_submitted = "application_submitted"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    return_scheduled = "return_scheduled"
    unknown = "unknown"


# The wording the user sees for each answer. The options themselves are the enums above, so nothing is listed twice.
ATTENDED_LABELS = {
    Attended.yes: "I went",
    Attended.rescheduled: "It was moved to another day",
    Attended.missed: "I couldn't go",
    Attended.cancelled: "It was cancelled",
    Attended.unknown: "Not sure",
}
OUTCOME_LABELS = {
    Outcome.documents_accepted: "My documents were accepted",
    Outcome.additional_documents_requested: "They asked for more documents",
    Outcome.application_submitted: "I submitted the application",
    Outcome.pending_review: "It is under review",
    Outcome.approved: "It was approved",
    Outcome.rejected: "It was rejected",
    Outcome.return_scheduled: "I have to go back",
    Outcome.unknown: "Not sure",
}


class AppointmentRecord(BaseModel):
    """What the caller knows about one appointment."""
    appointment_id: str
    purpose: str
    scheme_id: Optional[str] = None  # when the caller knows which scheme it was for
    scheduled_at_utc: Optional[datetime] = None
    status: str = "scheduled"
    location: Optional[str] = None
    simulated: bool = False

    @field_validator("scheduled_at_utc", mode="before")
    @classmethod
    def _parse(cls, v: Any) -> Any:
        if isinstance(v, str):
            if not v.strip():
                return None
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime) and v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)  # stored times are UTC
        return v


class Choice(BaseModel):
    value: str
    label: str


class AppointmentFollowUp(BaseModel):
    """A question to put to the user about an appointment that has passed."""
    appointment_id: str
    purpose: str
    scheduled_at_utc: Optional[datetime] = None
    location: Optional[str] = None
    scheme_id: Optional[str] = None
    question: str
    attended_options: list[Choice]
    outcome_options: list[Choice]
    simulated: bool = False


class AppointmentReport(BaseModel):
    """What the user said happened."""
    attended: Attended = Attended.unknown
    outcome: Optional[Outcome] = None
    additional_documents: list[str] = Field(default_factory=list)
    rescheduled_date: Optional[str] = None  # a date or date-time the user gave, in Indian time unless it says otherwise
    notes: Optional[str] = None
    scheme_id: Optional[str] = None  # which scheme it was for, so a rejection can be explained
    reason: Optional[str] = None  # the reason the office gave, in the user's words

    @field_validator("attended", mode="before")
    @classmethod
    def _attended(cls, v: Any) -> Any:
        v = (v or "unknown").strip().lower() if isinstance(v, str) else v
        return "yes" if v == "attended" else v

    @field_validator("outcome", mode="before")
    @classmethod
    def _outcome(cls, v: Any) -> Any:
        return None if v in ("", None) else v

    @field_validator("additional_documents", mode="before")
    @classmethod
    def _docs(cls, v: Any) -> Any:
        items = v.split(",") if isinstance(v, str) else (v or [])
        seen: dict[str, str] = {}
        for d in items:
            name = re.sub(r"\s+", " ", str(d)).strip()
            if name and name.lower() not in seen:
                seen[name.lower()] = name
        return list(seen.values())


class NextStep(BaseModel):
    kind: str  # collect_document | apply | wait | rebook | ask_date | recovery | none
    text: str
    document: Optional[str] = None


class LaterQuestion(BaseModel):
    """A question worth asking later (for example, whether the benefit arrived), never answered for the user."""
    field: str
    question: str
    options: list[str]


class AfterAppointmentPlan(BaseModel):
    appointment_id: str
    new_status: str
    summary: str
    next_steps: list[NextStep] = Field(default_factory=list)
    ask_later: list[LaterQuestion] = Field(default_factory=list)
    documents_to_add: list[str] = Field(default_factory=list)
    rescheduled_at_utc: Optional[datetime] = None
    progress_updates: list[ProgressUpdate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _choices(labels: dict) -> list[Choice]:
    return [Choice(value=k.value, label=v) for k, v in labels.items()]


def due_follow_ups(
    appointments: Iterable[AppointmentRecord | dict],
    *,
    now: Optional[datetime] = None,
    length: timedelta = DEFAULT_APPOINTMENT_LENGTH,
) -> list[AppointmentFollowUp]:
    """Appointments that are over and have no outcome yet, oldest first. One without a time is never "due": we can't
    know it has happened, so the user reports it when they choose."""
    now = now or datetime.now(timezone.utc)
    due: list[AppointmentFollowUp] = []
    for raw in appointments:
        a = raw if isinstance(raw, AppointmentRecord) else AppointmentRecord.model_validate(raw)
        if a.status not in OPEN_STATUSES or a.scheduled_at_utc is None:
            continue
        if now < a.scheduled_at_utc + length:
            continue
        due.append(AppointmentFollowUp(
            appointment_id=a.appointment_id,
            purpose=a.purpose,
            scheduled_at_utc=a.scheduled_at_utc,
            location=a.location,
            scheme_id=a.scheme_id,
            question=f"How did it go? {a.purpose}",
            attended_options=_choices(ATTENDED_LABELS),
            outcome_options=_choices(OUTCOME_LABELS),
            simulated=a.simulated,
        ))
    return sorted(due, key=lambda f: f.scheduled_at_utc or now)


def parse_reported_date(text: Optional[str], *, now: Optional[datetime] = None) -> tuple[Optional[datetime], Optional[str]]:
    """A date the user typed, as UTC. A date without a time is kept at the start of that day in India, so it sorts
    correctly but is not given an invented hour; the caller treats it as "time not known". Returns (when, problem)."""
    if not text or not text.strip():
        return None, None
    raw = text.strip()
    try:
        if len(raw) == 10:
            d = date.fromisoformat(raw)
            when = datetime.combine(d, time(0, 0), tzinfo=IST)
        else:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=IST)  # people type local times
    except ValueError:
        return None, "We couldn't read the new date, so it wasn't saved. Please enter it again."
    now = now or datetime.now(timezone.utc)
    if when.astimezone(IST).date() < now.astimezone(IST).date():
        return None, "The new date is in the past, so it wasn't saved."
    return when.astimezone(timezone.utc), None


def plan_after_appointment(
    appointment: AppointmentRecord | dict,
    report: AppointmentReport | dict,
    *,
    now: Optional[datetime] = None,
) -> AfterAppointmentPlan:
    """Turn the user's report into the next steps. Every step follows from something they said; anything they didn't
    say stays open (a later question), never filled in."""
    a = appointment if isinstance(appointment, AppointmentRecord) else AppointmentRecord.model_validate(appointment)
    r = report if isinstance(report, AppointmentReport) else AppointmentReport.model_validate(report)
    steps: list[NextStep] = []
    later: list[LaterQuestion] = []
    progress: list[ProgressUpdate] = []
    warnings: list[str] = []
    docs: list[str] = []
    resched: Optional[datetime] = None
    sim = a.simulated

    def ask_date(why: str) -> None:
        steps.append(NextStep(kind="ask_date", text=why))

    def take_new_date() -> None:
        nonlocal resched
        resched, problem = parse_reported_date(r.rescheduled_date, now=now)
        if problem:
            warnings.append(problem)

    if r.attended == Attended.cancelled:
        return AfterAppointmentPlan(appointment_id=a.appointment_id, new_status="cancelled",
                                    summary="You reported that the appointment was cancelled.",
                                    next_steps=[NextStep(kind="rebook", text="If you still need it, book a new appointment and add it to your plan.")])

    if r.attended == Attended.unknown:
        return AfterAppointmentPlan(appointment_id=a.appointment_id, new_status="outcome_unknown",
                                    summary="You weren't sure how it went, so nothing has been changed.",
                                    next_steps=[NextStep(kind="none", text="You can report what happened here whenever you know.")])

    if r.attended == Attended.missed:
        progress.append(ProgressUpdate(field="appointment_attended", state="no", simulated=sim))
        return AfterAppointmentPlan(appointment_id=a.appointment_id, new_status="missed",
                                    summary="You reported that you couldn't go.",
                                    next_steps=[NextStep(kind="rebook", text="Contact the office to book another slot, then add the new date to your plan.")],
                                    progress_updates=progress)

    if r.attended == Attended.rescheduled:
        take_new_date()
        if resched:
            return AfterAppointmentPlan(appointment_id=a.appointment_id, new_status="scheduled", rescheduled_at_utc=resched,
                                        summary="You reported that the appointment was moved. We've saved the new date and will ask again afterwards.",
                                        next_steps=[NextStep(kind="wait", text="Keep your documents ready for the new date.")],
                                        warnings=warnings)
        ask_date("Add the new date when you have it, so we can ask how it went afterwards.")
        return AfterAppointmentPlan(appointment_id=a.appointment_id, new_status="rescheduled",
                                    summary="You reported that the appointment was moved.", next_steps=steps, warnings=warnings)

    # They went.
    progress.append(ProgressUpdate(field="appointment_attended", state="yes", simulated=sim))
    o = r.outcome or Outcome.unknown
    if o == Outcome.documents_accepted:
        steps.append(NextStep(kind="apply", text="Your documents were accepted. If you haven't applied yet, you can now submit the application."))
        later.append(LaterQuestion(field="submitted", question="Have you submitted your application?", options=["yes", "no", "unknown"]))
    elif o == Outcome.additional_documents_requested:
        docs = r.additional_documents
        if docs:
            steps += [NextStep(kind="collect_document", text=f"Get: {d}", document=d) for d in docs]
            steps.append(NextStep(kind="rebook", text="When you have them, book a return visit and add it to your plan."))
        else:
            steps.append(NextStep(kind="collect_document", text="Note which documents they asked for, so they can be added to your checklist."))
            warnings.append("No document names were given, so none were added to your checklist.")
    elif o == Outcome.application_submitted:
        progress.append(ProgressUpdate(field="submitted", state="yes", simulated=sim))
        steps.append(NextStep(kind="wait", text="Keep your acknowledgement or application number safe; you'll need it to check the status."))
        later.append(LaterQuestion(field="decision", question="Have you received a decision on your application?", options=["pending", "approved", "rejected", "unknown"]))
    elif o == Outcome.pending_review:
        progress += [ProgressUpdate(field="submitted", state="yes", simulated=sim), ProgressUpdate(field="decision", state="pending", simulated=sim)]
        steps.append(NextStep(kind="wait", text="It's under review. Check the status on the official portal from time to time."))
        later.append(LaterQuestion(field="decision", question="Have you received a decision on your application?", options=["pending", "approved", "rejected", "unknown"]))
    elif o == Outcome.approved:
        progress += [ProgressUpdate(field="submitted", state="yes", simulated=sim), ProgressUpdate(field="decision", state="approved", simulated=sim)]
        steps.append(NextStep(kind="wait", text="It was approved. Check that the benefit reaches you, for example in your bank account."))
        later.append(LaterQuestion(field="benefit_received", question="Have you actually received the benefit?", options=["yes", "no", "unknown"]))
    elif o == Outcome.rejected:
        progress += [ProgressUpdate(field="submitted", state="yes", simulated=sim), ProgressUpdate(field="decision", state="rejected", simulated=sim)]
        if r.scheme_id:
            steps.append(NextStep(kind="what_if", text="See which of your answers didn't meet the scheme's rules, what would change that, and which schemes already fit you."))
        steps.append(NextStep(kind="recovery", text="Ask for the reason in writing. With the reason, Unlocked can help you see whether a correction, reapplication or appeal is possible."))
    elif o == Outcome.return_scheduled:
        take_new_date()
        if not resched:
            ask_date("Add the date of your return visit, so we can remind you and ask how it went.")
    else:
        steps.append(NextStep(kind="none", text="You can add what happened here whenever you know."))

    summary = "You reported that you went." + {
        Outcome.documents_accepted: " Your documents were accepted.",
        Outcome.additional_documents_requested: " They asked for more documents.",
        Outcome.application_submitted: " You submitted the application.",
        Outcome.pending_review: " It is under review.",
        Outcome.approved: " It was approved.",
        Outcome.rejected: " It was rejected.",
        Outcome.return_scheduled: " You have to go back" + (", and we've saved the date." if resched else "."),
    }.get(o, "")
    if sim:
        summary += " (This appointment came from a simulation.)"
    return AfterAppointmentPlan(
        appointment_id=a.appointment_id, new_status="attended", summary=summary, next_steps=steps, ask_later=later,
        documents_to_add=docs, rescheduled_at_utc=resched, progress_updates=progress, warnings=warnings,
    )
