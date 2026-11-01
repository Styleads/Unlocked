"""Agent 4: Action & Follow-through. Builds user-reviewed artifacts only; it never
sends, submits or calls an application API. Pure Python, no member2 imports.
Any object with `complete_json(system, user) -> str` works as the LLM (e.g.
`member2.default_client()`); without one, everything falls back to templates."""
from .calendar_ics import build_calendar_artifact
from .clarify import ClarificationKind, ClarificationPoint, clarification_points, clarification_request
from .email_draft import build_email_draft
from .facts import facts_from_scheme
from .office_chat_models import (
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
    VerificationStatus,
)
from .models import (
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
    SchemeContext,
    SourcedFact,
)
from .progress import update_progress
from .rejection import analyse_rejection, email_request_for_step

__all__ = [
    "build_email_draft", "facts_from_scheme", "clarification_points", "clarification_request",
    "ClarificationKind", "ClarificationPoint", "build_calendar_artifact", "update_progress", "analyse_rejection", "email_request_for_step",
    "ActionArtifact", "ActionType", "ApplicationProgress", "ArtifactStatus", "CalendarRequest", "DecisionState",
    "EmailPurpose", "EmailRequest", "EventKind", "FactState", "FollowUp", "NextStep", "ProgressResult",
    "ProgressUpdate", "RejectionAnalysis", "RejectionRoute", "SchemeContext", "SourcedFact",
    "AppointmentOffer", "AppointmentStatus", "AssistantChatTurnDecision", "ChatStatus",
    "ContactHandoff", "ContactSource", "OfficeChatMessage", "OfficeChatSession",
    "OfficeContact", "TimeWindow", "UnresolvedQuestion", "UnresolvedQuestionStatus",
    "UserAppointmentPreferences", "VerificationStatus",
]
