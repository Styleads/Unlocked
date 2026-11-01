"""
api/schemas.py — Public Pydantic schemas for Project Unlocked REST API.

Defines all request and response models consumed by Member 4 (Frontend),
adhering strictly to docs/agents.md and plan.md.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

# Re-export core Member 2 models for full structural typing and serialization
from member2.models import (
    ActionPlan,
    Answer,
    AnswerState,
    Assessment,
    ChecklistItem,
    DocStatus,
    DocumentDependency,
    DocumentRequirement,
    GraphEdge,
    GraphNode,
    InputType,
    Operator,
    Question,
    RangeOption,
    Requirement,
    RequirementResult,
    RequirementStatus,
    RequirementVerification,
    SchemeRecord,
    SchemeStatus,
    Sensitivity,
    VerificationStatus,
)
from member2.attributes import resolve_attribute, ATTRIBUTES


# ---------------------------------------------------------------------------
# 1. Operational & Health Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health and operational readiness status of the backend service."""
    status: str = "healthy"
    application: str = "Project Unlocked — Government Benefits Assistant"
    version: str = "1.0.0"
    operational: bool = True
    services: dict[str, bool] = Field(
        default_factory=lambda: {
            "gemini_configured": False,
            "tavily_configured": False,
            "sqlite_connected": True,
        }
    )


# ---------------------------------------------------------------------------
# 2. User Context & Profile Schemas
# ---------------------------------------------------------------------------

class UserProfileInput(BaseModel):
    """
    Flexible citizen profile input for session creation.
    Supports flat attributes and optional nested sections.
    """
    model_config = ConfigDict(extra="allow")

    # Common flat attributes
    occupation: Optional[str] = None
    state: Optional[str] = "Karnataka"
    district: Optional[str] = None
    annual_income: Optional[Union[float, int, str, dict]] = None
    annual_family_income: Optional[Union[float, int, str, dict]] = None
    age: Optional[Union[int, float]] = None
    gender: Optional[str] = None
    social_category: Optional[str] = None
    caste_category: Optional[str] = None
    education_level: Optional[str] = None
    interests: list[str] = Field(default_factory=list)

    # Optional nested sections (aligned with profile_manager format)
    personal: Optional[dict[str, Any]] = None
    location: Optional[dict[str, Any]] = None
    education: Optional[dict[str, Any]] = None
    employment: Optional[dict[str, Any]] = None
    agriculture: Optional[dict[str, Any]] = None
    household: Optional[dict[str, Any]] = None
    other_details: Optional[dict[str, Any]] = None

    def to_user_context(self) -> dict[str, Any]:
        """Convert input into dictionary expected by Discovery Agent."""
        data = self.model_dump()
        extra_fields = {
            k: v for k, v in data.items()
            if k not in (
                "occupation", "state", "district", "annual_income",
                "annual_family_income", "age", "gender", "social_category",
                "caste_category", "education_level", "interests",
                "personal", "location", "education", "employment",
                "agriculture", "household", "other_details"
            ) and v is not None
        }

        employment = dict(data.get("employment") or {})
        if self.occupation and "occupation" not in employment:
            employment["occupation"] = self.occupation

        location = dict(data.get("location") or {})
        from member2.attributes import is_karnataka_district
        if is_karnataka_district(self.district) or is_karnataka_district(location.get("district")):
            location["state"] = "Karnataka"
            if not self.state:
                self.state = "Karnataka"
        if self.state and "state" not in location:
            location["state"] = self.state
        if self.district and "district" not in location:
            location["district"] = self.district

        household = dict(data.get("household") or {})
        income = self.annual_family_income if self.annual_family_income is not None else self.annual_income
        if income is not None and "annual_income" not in household:
            household["annual_income"] = income

        interests = self.interests
        if isinstance(interests, str):
            interests = [interests]

        context: dict[str, Any] = {
            "employment": employment,
            "location": location,
            "household": household,
            "interests": interests,
            "personal": dict(data.get("personal") or {}),
            "education": dict(data.get("education") or {}),
            "agriculture": dict(data.get("agriculture") or {}),
            "other_details": dict(data.get("other_details") or {}),
            **extra_fields,
        }
        if self.age is not None:
            context["personal"]["age"] = self.age
        if self.gender is not None:
            context["personal"]["gender"] = self.gender
        if self.social_category or self.caste_category:
            context["personal"]["social_category"] = self.social_category or self.caste_category

        return context

    def extract_seedable_attributes(self) -> list[dict[str, Any]]:
        """
        Extract canonical attributes present in the profile so they can be
        seeded as answered in Member 2's answer map and history, preventing
        redundant questions for already known facts.
        """
        seedable: list[dict[str, Any]] = []

        def _add(attr_name: str, val: Any) -> None:
            if val is None or val == "":
                return
            canonical = resolve_attribute(attr_name) or attr_name
            if canonical in ATTRIBUTES:
                seedable.append({
                    "attribute": canonical,
                    "state": AnswerState.answered.value,
                    "value": val,
                })

        # Check Karnataka residency / district
        from member2.attributes import is_karnataka_district
        is_kar = (
            (self.state and str(self.state).strip().lower() == "karnataka")
            or is_karnataka_district(self.district)
            or (self.location and is_karnataka_district(self.location.get("district")))
            or (self.location and str(self.location.get("state") or "").strip().lower() == "karnataka")
        )
        if is_kar:
            _add("state", "Karnataka")
            _add("domicile_karnataka", True)
            _add("domicile_state", "Karnataka")
        elif self.state:
            _add("state", self.state)  # where they live is not where they are domiciled

        _add("district", self.district)
        _add("annual_family_income", self.annual_family_income or self.annual_income)
        _add("age", self.age)
        _add("gender", self.gender)
        _add("social_category", self.social_category or self.caste_category)
        _add("education_level", self.education_level)
        _add("occupation", self.occupation)

        emp_status = self.model_dump().get("employment_status")
        if not emp_status and self.occupation:
            occ_lower = self.occupation.lower().strip()
            if any(w in occ_lower for w in ("tailor", "artisan", "weaver", "craftsperson", "self-employed", "self employed", "carpenter", "blacksmith", "potter", "cobbler")):
                emp_status = None  # a trade does not say whether they run their own business or work for someone: ask
            elif occ_lower in ("farmer", "agriculturist", "cultivator", "business"):
                emp_status = "Self-employed"
            elif occ_lower in ("student", "employed", "unemployed", "other"):
                emp_status = self.occupation.capitalize()
            else:
                emp_status = "Other"
        if emp_status:
            _add("employment_status", emp_status)

        if self.caste_category:
            caste_lower = self.caste_category.lower().strip()
            if "2a" in caste_lower:
                _add("karnataka_caste_category", "Category 2A")
            elif "2b" in caste_lower:
                _add("karnataka_caste_category", "Category 2B")
            elif "3a" in caste_lower:
                _add("karnataka_caste_category", "Category 3A")
            elif "3b" in caste_lower:
                _add("karnataka_caste_category", "Category 3B")
            elif re.fullmatch(r"(cat(egory)?[\s.\-]*)?1", caste_lower):
                _add("karnataka_caste_category", "Category 1")

        # Inspect extra attributes
        for k, v in self.model_dump().items():
            if k not in (
                "personal", "location", "education", "employment",
                "agriculture", "household", "other_details", "interests"
            ):
                _add(k, v)

        # Inspect nested sections
        if self.location:
            _add("state", self.location.get("state"))
            _add("district", self.location.get("district"))
        if self.employment:
            _add("employment_status", self.employment.get("occupation") or self.employment.get("employment_status"))
        if self.household:
            _add("annual_family_income", self.household.get("annual_income") or self.household.get("annual_family_income"))
        if self.personal:
            _add("age", self.personal.get("age"))
            _add("gender", self.personal.get("gender"))
            _add("social_category", self.personal.get("social_category") or self.personal.get("caste_category"))

        # Deduplicate by attribute name
        seen = set()
        unique_seeds = []
        for s in seedable:
            if s["attribute"] not in seen:
                seen.add(s["attribute"])
                unique_seeds.append(s)

        return unique_seeds


# ---------------------------------------------------------------------------
# 3. Session Management Schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    """Payload to initialize a new session with citizen context."""
    context: Union[UserProfileInput, dict[str, Any]] = Field(default_factory=dict)
    scope: Literal["guided", "all", "fallback"] = "guided"
    preferred_language: Literal["en", "kn"] = "en"


class SessionResponse(BaseModel):
    """Initial response returned upon session creation."""
    session_id: str
    status: str = "initialized"
    scope: str = "guided"
    preferred_language: str = "en"
    created_at: str


class FullSessionState(BaseModel):
    """Complete durable session snapshot restored from SQLite."""
    session_id: str
    scope: str
    preferred_language: str
    state_status: str
    context: dict[str, Any]
    raw_schemes: list[dict[str, Any]] = Field(default_factory=list)
    normalized_schemes: list[dict[str, Any]] = Field(default_factory=list)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    answers: dict[str, Any] = Field(default_factory=dict)
    history: dict[str, Any] = Field(default_factory=dict)
    assessments: list[dict[str, Any]] = Field(default_factory=list)
    plan: Optional[dict[str, Any]] = None
    user_documents: dict[str, str] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class DeleteSessionResponse(BaseModel):
    """Response confirming session deletion."""
    deleted: bool = True
    session_id: str


# ---------------------------------------------------------------------------
# 4. Discovery Schemas
# ---------------------------------------------------------------------------

class DiscoverOptions(BaseModel):
    """Optional override parameters for discovery execution."""
    search_scope: Optional[Literal["guided", "all", "fallback"]] = None
    preferred_language: Optional[Literal["en", "kn"]] = None
    enable_fallback: bool = True


class SchemeView(BaseModel):
    """
    Consolidated frontend view of a scheme combining official metadata
    with current assessment results.
    """
    id: str
    name: str
    summary: Optional[str] = None
    government_level: Optional[str] = None
    department: Optional[str] = None
    benefit: Any = None
    target_group: list[str] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)
    application_url: Optional[str] = None
    deadline: Optional[str] = None
    deadline_status: Optional[str] = None
    deadline_source_url: Optional[str] = None
    official_sources: list[str] = Field(default_factory=list)
    source_type: str = "live_search"
    # Office contact information
    office_name: Optional[str] = None
    office_address: Optional[str] = None
    office_hours: Optional[Any] = None
    whatsapp_number: Optional[str] = None
    contact_email: Optional[str] = None
    reception_number: Optional[str] = None
    office_contact: Optional[dict[str, Any]] = None
    # Assessment overlays
    assessment_status: Optional[str] = None
    assessment_explanation: Optional[str] = None
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    """Response returned upon discovery pipeline completion."""
    session_id: str
    status: str = "discovery_complete"
    total_schemes: int
    schemes: list[SchemeView] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    source_mode: Literal["live_search", "fallback"] = "live_search"
    preferred_language: str = "en"
    translation_status: str = "not_requested"
    warnings: list[str] = Field(default_factory=list)
    diagnostics: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 5. Question & Answer Schemas
# ---------------------------------------------------------------------------

class AnswerInput(BaseModel):
    """Individual answer submitted by the citizen."""
    attribute: str
    value: Any = None
    state: Optional[Union[AnswerState, str]] = None


class SubmitAnswersRequest(BaseModel):
    """Batch of citizen answers/skips submitted for reassessment."""
    answers: list[Union[AnswerInput, dict[str, Any]]] = Field(default_factory=list)


class ReassessmentResult(BaseModel):
    """Result returned after answering questions and recalculating eligibility."""
    session_id: str
    status: str = "reassessed"
    assessments: list[Assessment] = Field(default_factory=list)
    next_questions: list[Question] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6. Document & Action Plan Schemas
# ---------------------------------------------------------------------------

class UpdateDocStatusRequest(BaseModel):
    """Request to update procurement status of a document."""
    status: Union[DocStatus, str]


# ---------------------------------------------------------------------------
# 7. Action & Follow-Through Schemas (Agent 4)
# ---------------------------------------------------------------------------

from agent4.models import (
    ActionArtifact,
    ActionType,
    ApplicationProgress,
    ArtifactStatus,
    CalendarRequest,
    DecisionState,
    EmailPurpose,
    EmailRequest,
    EventKind,
    FactState,
    FollowUp,
    NextStep,
    ProgressResult,
    ProgressUpdate,
    RejectionAnalysis,
    RejectionRoute,
    Reported,
    SchemeContext,
    SourcedFact,
)


class SessionEmailActionRequest(BaseModel):
    """Request to generate an inquiry or clarification email draft for a session scheme."""
    scheme_id: str
    purpose: EmailPurpose = EmailPurpose.inquiry
    question: str = Field(min_length=1, max_length=2000)
    user_details: dict[str, str] = Field(default_factory=dict)
    attributes: Optional[list[str]] = None
    facts: list[SourcedFact] = Field(default_factory=list)


class SessionCalendarActionRequest(BaseModel):
    """Request to generate an RFC 5545 .ics calendar entry for an application deadline or appointment."""
    scheme_id: str
    kind: EventKind = EventKind.deadline
    event_date: Optional[date] = None
    date_confirmed_by_user: bool = False
    date_source_url: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    remind_days_before: list[int] = Field(default_factory=lambda: [3, 1])


class SessionProgressRequest(BaseModel):
    """Request to report progress updates for a scheme in the current session."""
    scheme_id: str
    updates: list[Union[ProgressUpdate, dict[str, Any]]] = Field(default_factory=list)


class SessionRejectionActionRequest(BaseModel):
    """Request to analyze an official rejection notice and recommend verified next steps."""
    scheme_id: str
    notice_text: str = Field(min_length=1)
    guidance_passages: list[Union[SourcedFact, dict[str, Any]]] = Field(default_factory=list)
    simulated: bool = False


# Standalone / Unscoped Action Request Models (matching agent4/README.md)
class StandaloneEmailRequest(BaseModel):
    scheme: Union[SchemeContext, dict[str, Any]]
    purpose: EmailPurpose = EmailPurpose.inquiry
    question: str = Field(min_length=1, max_length=2000)
    user_details: dict[str, str] = Field(default_factory=dict)
    facts: list[SourcedFact] = Field(default_factory=list)


class StandaloneCalendarRequest(BaseModel):
    scheme: Union[SchemeContext, dict[str, Any]]
    kind: EventKind = EventKind.deadline
    event_date: Optional[date] = None
    date_confirmed_by_user: bool = False
    date_source_url: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    remind_days_before: list[int] = Field(default_factory=lambda: [3, 1])


class StandaloneProgressRequest(BaseModel):
    scheme_id: str
    current_progress: Optional[Union[ApplicationProgress, dict[str, Any]]] = None
    updates: list[Union[ProgressUpdate, dict[str, Any]]] = Field(default_factory=list)


class StandaloneRejectionRequest(BaseModel):
    scheme: Union[SchemeContext, dict[str, Any]]
    notice_text: str = Field(min_length=1)
    guidance_passages: list[Union[SourcedFact, dict[str, Any]]] = Field(default_factory=list)
    simulated: bool = False


# ---------------------------------------------------------------------------
# Phase 9: Follow-Through, Notifications & Recovery Schemas
# ---------------------------------------------------------------------------

class NotificationPreferencesInput(BaseModel):
    email: Optional[str] = None
    email_enabled: bool = True
    categories: Optional[dict[str, bool]] = None
    timezone: str = "Asia/Kolkata"
    consent_version: str = "v1"


class NotificationPreferencesView(BaseModel):
    session_id: str
    email: Optional[str] = None
    email_enabled: bool = False
    categories: dict[str, bool] = Field(default_factory=dict)
    consent_version: str = "v1"
    consent_at: Optional[str] = None
    disabled_at: Optional[str] = None
    timezone: str = "Asia/Kolkata"


class ActionPlanEmailPreview(BaseModel):
    to_email: str
    subject: str
    body_html: str
    body_text: str
    schemes_included: list[str] = Field(default_factory=list)
    checklist_tasks: list[str] = Field(default_factory=list)
    follow_up_url: Optional[str] = None


class ActionPlanEmailSendRequest(BaseModel):
    to_email: Optional[str] = None
    confirmed: bool = True


class ActionPlanEmailSendResponse(BaseModel):
    notification_id: str
    status: str
    provider: str
    provider_message_id: Optional[str] = None
    recipient: str
    sent_at: Optional[str] = None


class NotificationView(BaseModel):
    notification_id: str
    session_id: str
    notification_type: str
    channel: str = "email"
    recipient: str
    subject: str
    scheduled_at_utc: Optional[str] = None
    status: str
    provider: str = "resend"
    provider_message_id: Optional[str] = None
    sent_at_utc: Optional[str] = None
    delivered_at_utc: Optional[str] = None
    last_error: Optional[str] = None
    is_demo: bool = False
    created_at: str


class CreateAppointmentRequest(BaseModel):
    purpose: str = Field(min_length=1, max_length=500)
    scheduled_at_utc: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    location: Optional[str] = None
    application_id: Optional[str] = None
    related_task_id: Optional[str] = None
    remind_email: bool = True
    notes: Optional[str] = None


class UpdateAppointmentRequest(BaseModel):
    scheduled_at_utc: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    remind_email: bool = True


class AppointmentOutcomeRequest(BaseModel):
    attended: str = "yes"  # yes | rescheduled | missed | cancelled | unknown
    outcome: Optional[str] = None  # documents_accepted | additional_documents_requested | application_submitted | pending_review | approved | rejected | return_scheduled | unknown
    notes: Optional[str] = None
    rescheduled_date: Optional[str] = None
    additional_documents: list[str] = Field(default_factory=list)
    scheme_id: Optional[str] = None  # which scheme it was for (lets a rejection be explained at once)
    reason: Optional[str] = Field(default=None, max_length=1000)  # the reason the office gave


class AppointmentView(BaseModel):
    appointment_id: str
    session_id: str
    application_id: Optional[str] = None
    related_task_id: Optional[str] = None
    purpose: str
    scheduled_at_utc: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    location: Optional[str] = None
    status: str = "scheduled"
    outcome_summary: Optional[str] = None
    outcome_details: Optional[dict[str, Any]] = None
    status_source: str = "user_reported"
    follow_up_url: Optional[str] = None
    created_at: str


class TrackedApplicationCreateRequest(BaseModel):
    scheme_id: str
    status: str = "not_started"
    status_source: str = "user_reported"


class TrackedApplicationOutcomeRequest(BaseModel):
    status: str  # not_started | preparing | submitted | under_review | approved | rejected | benefit_received | closed
    status_source: str = "user_reported"  # user_reported | official_verified | demo_simulated
    submission_date: Optional[str] = None
    notes: Optional[str] = None


class TrackedApplicationView(BaseModel):
    application_id: str
    session_id: str
    scheme_id: str
    scheme_name: Optional[str] = None
    status: str
    status_source: str = "user_reported"
    reported_submission_at: Optional[str] = None
    recovery_status: Optional[str] = None
    recovery_data: Optional[dict[str, Any]] = None
    last_updated_at: Optional[str] = None
    created_at: str


class RejectionInvestigationRequest(BaseModel):
    reason: Optional[str] = None
    notice_text: Optional[str] = None
    reason_category: Optional[str] = None
    notice_date: Optional[str] = None
    simulated: bool = False


class RejectionRecoveryView(BaseModel):
    scheme_id: str
    scheme_name: str
    reported_reason: Optional[str] = None
    reason_quote: Optional[str] = None
    reason_summary: Optional[str] = None
    recovery_status: str
    action_classification: str
    explanation: str
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    email_draft: Optional[dict[str, Any]] = None
    alternative_schemes: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    simulated: bool = False


class FollowUpPageView(BaseModel):
    session_id: str
    token_id: str
    scope_type: str
    appointment: Optional[AppointmentView] = None
    application: Optional[TrackedApplicationView] = None
    scheme_name: Optional[str] = None
    expires_at: str


class FollowUpOutcomeRequest(BaseModel):
    attended: Optional[str] = None
    outcome: Optional[str] = None
    application_status: Optional[str] = None
    notes: Optional[str] = None
    rescheduled_date: Optional[str] = None
    additional_documents: list[str] = Field(default_factory=list)


class AdvanceTimeRequest(BaseModel):
    seconds: Optional[float] = None
    target_utc: Optional[str] = None


class AdvanceTimeResponse(BaseModel):
    demo_mode: bool
    simulated_now_utc: str
    notifications_processed: int
    processed_notifications: list[dict[str, Any]] = Field(default_factory=list)


from agent4.office_chat_models import (
    AppointmentOffer,
    AppointmentStatus,
    AssistantChatTurnDecision,
    ChatStatus,
    ContactHandoff,
    ContactSource,
    OfficeChatMessage,
    OfficeChatSession,
    OfficeContact,
    TimeWindow,
    UnresolvedQuestion,
    UnresolvedQuestionStatus,
    UserAppointmentPreferences,
)


# ---------------------------------------------------------------------------
# 10. Office Chat Simulator Schemas
# ---------------------------------------------------------------------------

class CreateOfficeChatRequest(BaseModel):
    """Request to initiate an in-website Office Chat Simulation."""
    scheme_id: str
    office_id: Optional[str] = None
    scenario_id: Optional[str] = None  # e.g. "scenario_a_success"
    availability: Optional[UserAppointmentPreferences] = None
    preferred_days: Optional[list[str]] = None
    preferred_windows: Optional[list[Union[TimeWindow, dict[str, str]]]] = None
    pre_authorized_confirmation: bool = False


class AdvanceOfficeChatRequest(BaseModel):
    """Request to advance dialogue turn in the Office Chat Simulation."""
    scenario_id: Optional[str] = None
    user_message: Optional[str] = None


class UserInputRequest(BaseModel):
    """User approval for offered appointment slot or response to representative question."""
    action: str = "approve_slot"  # "approve_slot" | "reject_slot" | "submit_info"
    user_approved_slot: Optional[bool] = None
    user_provided_info: Optional[str] = None
    unresolved_question_id: Optional[str] = None


class OfficeChatMessageView(BaseModel):
    message_id: str
    chat_id: str
    sender: str
    message_text: str
    turn_index: int
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class OfficeChatView(BaseModel):
    chat_id: str
    session_id: str
    scheme_id: str
    office_id: Optional[str] = None
    scenario_id: Optional[str] = None
    simulation_mode: bool = True
    chat_status: ChatStatus
    appointment_status: AppointmentStatus
    appointment: Optional[AppointmentOffer] = None
    messages: list[OfficeChatMessageView] = Field(default_factory=list)
    unresolved_questions: list[UnresolvedQuestion] = Field(default_factory=list)
    next_action: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class UnresolvedQuestionDraftRequest(BaseModel):
    draft_message: str


class OfficeChatOutcomeView(BaseModel):
    chat_id: str
    session_id: str
    scheme_id: str
    simulation_mode: bool = True
    chat_status: ChatStatus
    appointment_status: AppointmentStatus
    appointment: Optional[AppointmentOffer] = None
    unresolved_questions: list[UnresolvedQuestion] = Field(default_factory=list)
    calendar_ics: Optional[str] = None
    summary: str
    next_steps: list[str] = Field(default_factory=list)


__all__ = [
    # Health
    "HealthResponse",
    # User Profile & Context
    "UserProfileInput",
    # Session
    "CreateSessionRequest",
    "SessionResponse",
    "FullSessionState",
    "DeleteSessionResponse",
    # Discovery
    "DiscoverOptions",
    "SchemeView",
    "DiscoveryResult",
    # Questions & Answers
    "AnswerInput",
    "SubmitAnswersRequest",
    "ReassessmentResult",
    # Document Action Plan
    "UpdateDocStatusRequest",
    # Action & Follow-Through (Agent 4)
    "ActionArtifact",
    "ActionType",
    "ApplicationProgress",
    "ArtifactStatus",
    "CalendarRequest",
    "DecisionState",
    "EmailPurpose",
    "EmailRequest",
    "EventKind",
    "FactState",
    "FollowUp",
    "NextStep",
    "ProgressResult",
    "ProgressUpdate",
    "RejectionAnalysis",
    "RejectionRoute",
    "Reported",
    "SchemeContext",
    "SourcedFact",
    "SessionEmailActionRequest",
    "SessionCalendarActionRequest",
    "SessionProgressRequest",
    "SessionRejectionActionRequest",
    "StandaloneEmailRequest",
    "StandaloneCalendarRequest",
    "StandaloneProgressRequest",
    "StandaloneRejectionRequest",
    # Office Chat Simulator models
    "CreateOfficeChatRequest",
    "AdvanceOfficeChatRequest",
    "UserInputRequest",
    "OfficeChatMessageView",
    "OfficeChatView",
    "UnresolvedQuestionDraftRequest",
    "OfficeChatOutcomeView",
    "OfficeContact",
    "TimeWindow",
    "UserAppointmentPreferences",
    "AppointmentOffer",
    "OfficeChatMessage",
    "OfficeChatSession",
    "UnresolvedQuestion",
    "ContactHandoff",
    "AssistantChatTurnDecision",
    "ChatStatus",
    "AppointmentStatus",
    "UnresolvedQuestionStatus",
    "ContactSource",
    # Re-exported Member 2 models
    "ActionPlan",
    "Answer",
    "AnswerState",
    "Assessment",
    "ChecklistItem",
    "DocStatus",
    "DocumentDependency",
    "DocumentRequirement",
    "GraphEdge",
    "GraphNode",
    "InputType",
    "Operator",
    "Question",
    "RangeOption",
    "Requirement",
    "RequirementResult",
    "RequirementStatus",
    "RequirementVerification",
    "SchemeRecord",
    "SchemeStatus",
    "Sensitivity",
    "VerificationStatus",
]
