"""Agent 4 data models. Scheme input is a small, permissive view of plan.md §5.1 so
this package needs nothing from member2 and accepts its records or plain dicts."""
from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

PLACEHOLDER_EMAIL = "[Insert Department Helpdesk Email]"
PLACEHOLDER_PHONE = "[Insert Department Helpline Number]"
PLACEHOLDER_LINK = "[Insert Official Link]"


class ActionType(str, Enum):
    email_draft = "email_draft"
    calendar_ics = "calendar_ics"
    progress_update = "progress_update"
    rejection_assist = "rejection_assist"


class ArtifactStatus(str, Enum):
    ready = "ready"  # complete; the user still reviews it before using it
    needs_input = "needs_input"  # essential details missing; see missing_fields


class ActionArtifact(BaseModel):
    """agents.md §5.1 fields, plus what the UI needs to show warnings and sources."""

    action_type: ActionType
    status: ArtifactStatus = ArtifactStatus.ready
    title: str
    body_content: str = ""  # email text or an RFC 5545 calendar
    subject: Optional[str] = None
    target_destination: Optional[str] = None  # only a sourced official address
    instructions: str
    user_review_confirmed: bool = False  # Unlocked never sends or submits anything
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_by: str = "template"  # "template" | "llm"


class SchemeContext(BaseModel):
    """The scheme fields Agent 4 reads. Extra fields are ignored, not rejected."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    department: Optional[str] = None
    application_url: Optional[str] = None
    official_sources: list[str] = Field(default_factory=list)
    deadline: Optional[str] = None  # ISO date
    deadline_source_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_email_source_url: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_phone_source_url: Optional[str] = None


# --- email -------------------------------------------------------------------

class EmailPurpose(str, Enum):
    inquiry = "inquiry"  # general question about the scheme
    clarification = "clarification"  # a rule or requirement is unclear
    document_query = "document_query"  # which document / which format
    status_query = "status_query"  # application status after submitting
    correction_request = "correction_request"  # fix an error on an application
    appeal = "appeal"  # only with an officially supported route (rejection.py)


class EmailRequest(BaseModel):
    scheme: SchemeContext
    purpose: EmailPurpose = EmailPurpose.inquiry
    question: str = Field(min_length=1, max_length=2000)  # the user's own words
    # Only details the user has confirmed for this email, e.g. {"Name": "...", "Application ID": "..."}.
    user_details: dict[str, str] = Field(default_factory=dict)
    # Official sentences the email may cite, each with its source.
    facts: list["SourcedFact"] = Field(default_factory=list)


class SourcedFact(BaseModel):
    text: str
    source_url: str


# --- calendar ----------------------------------------------------------------

class EventKind(str, Enum):
    deadline = "deadline"
    appointment = "appointment"


class CalendarRequest(BaseModel):
    scheme: SchemeContext
    kind: EventKind = EventKind.deadline
    # A date must be confirmed by the user or carry a source; never guessed.
    event_date: Optional[date] = None
    date_confirmed_by_user: bool = False
    date_source_url: Optional[str] = None
    start_time: Optional[time] = None  # appointments need one; deadlines are all-day
    end_time: Optional[time] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    remind_days_before: list[int] = Field(default_factory=lambda: [3, 1])


# --- progress ----------------------------------------------------------------

class FactState(str, Enum):
    unknown = "unknown"
    yes = "yes"
    no = "no"


class DecisionState(str, Enum):
    unknown = "unknown"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Reported(BaseModel):
    """One user-reported fact. Never filled by inference from another fact."""

    state: str = "unknown"
    reported_at: Optional[datetime] = None
    simulated: bool = False  # demo scenario, shown as such


class ApplicationProgress(BaseModel):
    scheme_id: str
    submitted: Reported = Field(default_factory=Reported)
    decision: Reported = Field(default_factory=Reported)
    benefit_received: Reported = Field(default_factory=Reported)
    appointment_attended: Reported = Field(default_factory=Reported)
    history: list[dict[str, Any]] = Field(default_factory=list)  # {field, state, at, simulated}


class ProgressUpdate(BaseModel):
    field: str  # submitted | decision | benefit_received | appointment_attended
    state: str
    simulated: bool = False


class FollowUp(BaseModel):
    id: str
    question: str
    field: str
    options: list[str]


class ProgressResult(BaseModel):
    progress: ApplicationProgress
    follow_ups: list[FollowUp] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str


# --- rejection ---------------------------------------------------------------

class RejectionRoute(str, Enum):
    correction = "correction"
    reapplication = "reapplication"
    appeal = "appeal"
    clarification = "clarification"


class NextStep(BaseModel):
    route: RejectionRoute
    description: str
    evidence: str  # verbatim from official guidance
    source_url: str
    deadline_text: Optional[str] = None  # verbatim, if the guidance states one


class RejectionAnalysis(BaseModel):
    scheme_id: str
    reason_quote: Optional[str] = None  # verbatim from the user's notice
    reason_summary: Optional[str] = None
    next_steps: list[NextStep] = Field(default_factory=list)
    supported: bool = False  # True only if at least one next step is sourced
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    simulated: bool = False
    analysed_by: str = "none"  # "llm" | "none"


EmailRequest.model_rebuild()
