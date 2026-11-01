"""
agent4/office_chat_models.py — Data contracts and models for the in-website
Office Chat Simulator (WhatsApp-style).

Defines the core domain entities:
- ChatStatus, AppointmentStatus, UnresolvedQuestionStatus
- OfficeContact, TimeWindow, UserAppointmentPreferences
- OfficeChatMessage, OfficeChatSession, UnresolvedQuestion
- ContactHandoff, AppointmentOffer, AssistantChatTurnDecision
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatStatus(str, Enum):
    created = "created"
    in_progress = "in_progress"
    awaiting_user_input = "awaiting_user_input"
    appointment_offered = "appointment_offered"
    completed = "completed"
    no_availability = "no_availability"
    manual_followup_required = "manual_followup_required"
    unable_to_resolve = "unable_to_resolve"
    cancelled = "cancelled"


class AppointmentStatus(str, Enum):
    not_requested = "not_requested"
    requested = "requested"
    offered = "offered"
    awaiting_user_approval = "awaiting_user_approval"
    simulated_confirmed = "simulated_confirmed"
    no_availability = "no_availability"
    cancelled = "cancelled"


class UnresolvedQuestionStatus(str, Enum):
    open = "open"
    shown_to_user = "shown_to_user"
    draft_prepared = "draft_prepared"
    user_marked_sent = "user_marked_sent"
    resolved = "resolved"
    dismissed = "dismissed"


class ContactSource(str, Enum):
    website = "website"
    receiver_provided = "receiver_provided"
    user_provided = "user_provided"


class VerificationStatus(str, Enum):
    verified = "verified"
    unverified = "unverified"
    uncertain = "uncertain"


class TimeWindow(BaseModel):
    """A time window within a day, e.g. 09:00 to 12:00."""
    start: str = "10:00"  # HH:MM
    end: str = "13:00"    # HH:MM


class OfficeContact(BaseModel):
    """Enriched contact and operating hour information for a government office."""
    model_config = ConfigDict(extra="ignore")

    office_id: str = Field(default_factory=lambda: f"office_{uuid.uuid4().hex[:8]}")
    scheme_id: Optional[str] = None
    office_name: Optional[str] = None
    office_address: Optional[str] = None
    office_hours: Optional[dict[str, Any]] = None  # e.g. {"monday": {"open": "10:00", "close": "17:30"}, ...}
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    reception_number: Optional[str] = None
    source_url: Optional[str] = None
    contact_source: ContactSource = ContactSource.website
    verification_status: VerificationStatus = VerificationStatus.unverified
    last_checked: Optional[datetime] = None


class UserAppointmentPreferences(BaseModel):
    """Citizen's preferred days, time windows, and pre-authorization consent."""
    model_config = ConfigDict(extra="ignore")

    preference_id: str = Field(default_factory=lambda: f"pref_{uuid.uuid4().hex[:8]}")
    session_id: str = ""
    scheme_id: Optional[str] = None
    office_id: Optional[str] = None
    preferred_days: List[str] = Field(default_factory=lambda: ["monday", "tuesday"])
    preferred_windows: List[TimeWindow] = Field(
        default_factory=lambda: [TimeWindow(start="10:00", end="13:00")]
    )
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    pre_authorized_confirmation: bool = False
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("preferred_days", mode="before")
    @classmethod
    def normalize_preferred_days(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = [d.strip().lower() for d in v.split(",") if d.strip()]
        elif isinstance(v, list):
            v = [str(d).strip().lower() for d in v if str(d).strip()]
        return v or ["monday", "tuesday"]


class AppointmentOffer(BaseModel):
    """Details of a simulated appointment offer or confirmed booking."""
    model_config = ConfigDict(extra="ignore")

    date: Optional[str] = None  # YYYY-MM-DD or formatted day
    time: Optional[str] = None  # HH:MM
    status: AppointmentStatus = AppointmentStatus.offered
    location: Optional[str] = None
    notes: Optional[str] = None
    calendar_ics: Optional[str] = None


class OfficeChatMessage(BaseModel):
    """A single turn in the simulated WhatsApp-style conversation."""
    model_config = ConfigDict(extra="ignore")

    message_id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    chat_id: str
    sender: str  # "unlocked" | "simulated_office"
    message_text: str
    turn_index: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class OfficeChatSession(BaseModel):
    """The persistent state of a simulated office dialogue."""
    model_config = ConfigDict(extra="ignore")

    chat_id: str = Field(default_factory=lambda: f"chat_{uuid.uuid4().hex[:8]}")
    session_id: str
    scheme_id: str
    office_id: Optional[str] = None
    scenario_id: Optional[str] = None
    simulation_mode: bool = True  # Always True for in-website simulation
    chat_status: ChatStatus = ChatStatus.created
    appointment_status: AppointmentStatus = AppointmentStatus.not_requested
    appointment: Optional[AppointmentOffer] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class UnresolvedQuestion(BaseModel):
    """A question raised by the representative that requires user action/clarification."""
    model_config = ConfigDict(extra="ignore")

    question_id: str = Field(default_factory=lambda: f"uq_{uuid.uuid4().hex[:8]}")
    chat_id: str
    session_id: str
    question_text: str
    context: dict[str, Any] = Field(default_factory=dict)
    receiver_whatsapp_number: Optional[str] = None
    contact_source: ContactSource = ContactSource.receiver_provided
    status: UnresolvedQuestionStatus = UnresolvedQuestionStatus.open
    draft_message: Optional[str] = None
    click_to_chat_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContactHandoff(BaseModel):
    """Contact handoff information for following up outside the automated enquiry."""
    channel: str = "whatsapp"
    whatsapp_number: Optional[str] = None
    contact_source: ContactSource = ContactSource.receiver_provided
    suggested_draft: Optional[str] = None
    click_to_chat_url: Optional[str] = None


class AssistantChatTurnDecision(BaseModel):
    """Structured reasoning output from the Action Agent during conversation."""
    assistant_message: str
    conversation_status: ChatStatus
    next_action: str
    appointment_offer: Optional[AppointmentOffer] = None
    unresolved_questions: List[str] = Field(default_factory=list)
    contact_handoff: Optional[ContactHandoff] = None
    outcome: Optional[str] = None

