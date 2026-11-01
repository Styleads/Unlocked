"""Unit tests for agent4/office_chat_models.py data structures and serialization."""
import json
from datetime import datetime, timezone
import pytest

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
    VerificationStatus,
)


def test_office_contact_defaults():
    contact = OfficeContact(
        office_name="Social Welfare Department",
        office_address="5th Floor, M.S. Building, Bengaluru",
        email="help@karnataka.gov.in",
        reception_number="080-22634300",
        whatsapp_number="+918277712345",
        verification_status=VerificationStatus.verified,
    )
    assert contact.office_id.startswith("office_")
    assert contact.office_name == "Social Welfare Department"
    assert contact.verification_status == VerificationStatus.verified
    assert contact.contact_source == ContactSource.website

    data = contact.model_dump()
    assert data["email"] == "help@karnataka.gov.in"
    assert data["whatsapp_number"] == "+918277712345"


def test_user_appointment_preferences_normalization():
    # Comma-separated string normalization
    prefs = UserAppointmentPreferences(
        preferred_days="Monday, Wednesday, Friday",
        preferred_windows=[TimeWindow(start="09:00", end="12:00")],
        pre_authorized_confirmation=True,
    )
    assert prefs.preferred_days == ["monday", "wednesday", "friday"]
    assert prefs.pre_authorized_confirmation is True
    assert len(prefs.preferred_windows) == 1
    assert prefs.preferred_windows[0].start == "09:00"


def test_office_chat_session_and_messages():
    session = OfficeChatSession(
        session_id="sess_123",
        scheme_id="scheme_ssp_01",
        scenario_id="scenario_a_success",
    )
    assert session.chat_status == ChatStatus.created
    assert session.appointment_status == AppointmentStatus.not_requested
    assert session.simulation_mode is True

    msg = OfficeChatMessage(
        chat_id=session.chat_id,
        sender="unlocked",
        message_text="Hello, I am enquiring about appointment availability.",
        turn_index=1,
    )
    assert msg.sender == "unlocked"
    assert msg.turn_index == 1
    assert msg.message_id.startswith("msg_")


def test_unresolved_question_and_draft():
    uq = UnresolvedQuestion(
        chat_id="chat_1",
        session_id="sess_1",
        question_text="Please provide mother's Aadhaar RD linkage number.",
        receiver_whatsapp_number="+919845012345",
        contact_source=ContactSource.receiver_provided,
    )
    assert uq.status == UnresolvedQuestionStatus.open
    assert uq.receiver_whatsapp_number == "+919845012345"
    assert uq.question_id.startswith("uq_")


def test_assistant_chat_turn_decision():
    decision = AssistantChatTurnDecision(
        assistant_message="Could you confirm Monday at 11:00 AM?",
        conversation_status=ChatStatus.in_progress,
        next_action="request_confirmation",
        appointment_offer=AppointmentOffer(
            date="2026-11-02",
            time="11:00",
            status=AppointmentStatus.offered,
        ),
        unresolved_questions=[],
        contact_handoff=ContactHandoff(
            whatsapp_number="+919845012345",
            click_to_chat_url="https://wa.me/919845012345?text=Hello",
        ),
    )
    assert decision.conversation_status == ChatStatus.in_progress
    assert decision.appointment_offer is not None
    assert decision.appointment_offer.date == "2026-11-02"
    assert decision.contact_handoff.whatsapp_number == "+919845012345"
