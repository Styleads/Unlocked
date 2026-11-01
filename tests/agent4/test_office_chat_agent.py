"""Unit tests for agent4/office_chat_agent.py dialogue reasoning and safety rules."""
import pytest
from datetime import time

from agent4.models import SchemeContext
from agent4.office_chat_agent import (
    build_initial_office_enquiry,
    check_slot_in_office_hours,
    check_slot_matches_preferences,
    decide_chat_turn,
    format_whatsapp_click_url,
    normalize_phone_number,
)
from agent4.office_chat_models import (
    AppointmentOffer,
    AppointmentStatus,
    ChatStatus,
    ContactSource,
    OfficeChatMessage,
    OfficeChatSession,
    OfficeContact,
    TimeWindow,
    UserAppointmentPreferences,
)


@pytest.fixture
def mock_scheme():
    return SchemeContext(
        id="fallback-ssp-scst-001",
        name="Karnataka Post-Matric Scholarship for SC/ST Students (SSP)",
        department="Social Welfare Department, Government of Karnataka",
        official_sources=["https://ssp.postmatric.karnataka.gov.in"],
    )


@pytest.fixture
def mock_office():
    return OfficeContact(
        office_id="office_swd_01",
        office_name="Social Welfare Department Helpdesk",
        office_hours={"monday": {"open": "10:00", "close": "17:30"}, "timezone": "Asia/Kolkata"},
        whatsapp_number="+918277712345",
    )


def test_normalize_phone_number():
    assert normalize_phone_number("9845012345") == "919845012345"
    assert normalize_phone_number("+91 98450-12345") == "919845012345"
    assert normalize_phone_number("09845012345") == "919845012345"
    assert normalize_phone_number("919845012345") == "919845012345"
    assert normalize_phone_number("") == ""


def test_format_whatsapp_click_url():
    url = format_whatsapp_click_url("+91 98450 12345", "Hello, following up on verification.")
    assert url.startswith("https://wa.me/919845012345?text=")
    assert "Hello%2C%20following%20up%20on%20verification." in url


def test_build_initial_office_enquiry_zero_pii(mock_scheme, mock_office):
    prefs = UserAppointmentPreferences(
        preferred_days=["monday", "tuesday"],
        preferred_windows=[TimeWindow(start="10:00", end="13:00")],
    )
    enquiry = build_initial_office_enquiry(mock_scheme, mock_office, prefs)

    assert "Karnataka Post-Matric Scholarship" in enquiry
    assert "Monday, Tuesday" in enquiry
    assert "10:00 and 13:00" in enquiry
    # Strict Zero-PII check
    assert "income" not in enquiry.lower()
    assert "aadhaar" not in enquiry.lower()
    assert "caste" not in enquiry.lower()


def test_scenario_a_offer_and_confirmation_with_pre_authorization(mock_scheme, mock_office):
    prefs = UserAppointmentPreferences(
        preferred_days=["monday"],
        preferred_windows=[TimeWindow(start="10:00", end="13:00")],
        pre_authorized_confirmation=True,
    )
    chat_sess = OfficeChatSession(session_id="s1", scheme_id=mock_scheme.id)

    # Turn 2: Representative offers Monday 11:00 AM
    rep_msg_turn2 = "We have an appointment slot available Monday at 11:00 AM. Would you like to schedule?"
    decision2 = decide_chat_turn(
        chat_session=chat_sess,
        preferences=prefs,
        office=mock_office,
        scheme=mock_scheme,
        history=[],
        representative_message=rep_msg_turn2,
        llm=None,
        rep_result={"offered_slot": {"date": "2026-11-02", "day": "monday", "time": "11:00"}},
    )

    assert decision2.conversation_status == ChatStatus.appointment_offered
    assert decision2.next_action == "request_explicit_confirmation"
    assert decision2.appointment_offer is not None
    assert decision2.appointment_offer.date == "2026-11-02"
    assert decision2.appointment_offer.time == "11:00"
    assert "confirm" in decision2.assistant_message.lower()

    # Turn 4: Representative explicitly confirms
    rep_msg_turn4 = "Yes, Monday at 11:00 AM is confirmed for this simulated enquiry."
    decision4 = decide_chat_turn(
        chat_session=chat_sess,
        preferences=prefs,
        office=mock_office,
        scheme=mock_scheme,
        history=[
            OfficeChatMessage(chat_id=chat_sess.chat_id, sender="unlocked", message_text=decision2.assistant_message, turn_index=3)
        ],
        representative_message=rep_msg_turn4,
        llm=None,
    )

    # Pre-authorized -> Accepted directly as simulated_confirmed
    assert decision4.conversation_status == ChatStatus.completed
    assert decision4.appointment_offer.status == AppointmentStatus.simulated_confirmed
    assert decision4.next_action == "conclude_simulation"


def test_scenario_a_confirmation_without_pre_authorization(mock_scheme, mock_office):
    prefs = UserAppointmentPreferences(
        preferred_days=["monday"],
        preferred_windows=[TimeWindow(start="10:00", end="13:00")],
        pre_authorized_confirmation=False,  # NO pre-authorization
    )
    chat_sess = OfficeChatSession(session_id="s1", scheme_id=mock_scheme.id)

    rep_msg = "Yes, Monday at 11:00 AM is confirmed for this simulated enquiry."
    decision = decide_chat_turn(
        chat_session=chat_sess,
        preferences=prefs,
        office=mock_office,
        scheme=mock_scheme,
        history=[],
        representative_message=rep_msg,
        llm=None,
    )

    # Without pre-authorization -> Pauses for user approval
    assert decision.conversation_status == ChatStatus.awaiting_user_input
    assert decision.appointment_offer.status == AppointmentStatus.awaiting_user_approval
    assert decision.next_action == "await_user_slot_approval"
    assert "approval" in decision.assistant_message.lower()


def test_scenario_b_no_availability(mock_scheme, mock_office):
    chat_sess = OfficeChatSession(session_id="s1", scheme_id=mock_scheme.id)
    rep_msg = "We currently have no appointment slots open in that time window this week. All slots are fully booked."

    decision = decide_chat_turn(
        chat_session=chat_sess,
        preferences=UserAppointmentPreferences(),
        office=mock_office,
        scheme=mock_scheme,
        history=[],
        representative_message=rep_msg,
        llm=None,
    )

    assert decision.conversation_status == ChatStatus.no_availability
    assert decision.next_action == "report_no_availability"
    assert decision.appointment_offer is None
    assert "no appointment slots" in decision.assistant_message.lower()


def test_scenario_c_missing_info_and_whatsapp_handoff(mock_scheme, mock_office):
    chat_sess = OfficeChatSession(session_id="s1", scheme_id=mock_scheme.id)

    # Turn 2: Representative asks for personal/academic details
    rep_msg_turn2 = "Please provide the applicant's 11-digit college admission acknowledgment number and Aadhaar RD linkage."
    decision2 = decide_chat_turn(
        chat_session=chat_sess,
        preferences=UserAppointmentPreferences(),
        office=mock_office,
        scheme=mock_scheme,
        history=[],
        representative_message=rep_msg_turn2,
        llm=None,
    )

    assert decision2.conversation_status == ChatStatus.in_progress
    assert decision2.next_action == "collect_receiver_whatsapp"
    assert "applicant will provide these documents and details directly" in decision2.assistant_message
    assert len(decision2.unresolved_questions) == 1

    # Turn 4: Representative provides WhatsApp contact
    rep_msg_turn4 = "The applicant can WhatsApp their acknowledgment details directly to our verification desk at +919845012345."
    decision4 = decide_chat_turn(
        chat_session=chat_sess,
        preferences=UserAppointmentPreferences(),
        office=mock_office,
        scheme=mock_scheme,
        history=[],
        representative_message=rep_msg_turn4,
        llm=None,
    )

    assert decision4.conversation_status == ChatStatus.awaiting_user_input
    assert decision4.next_action == "handoff_unresolved_question"
    assert decision4.contact_handoff is not None
    assert decision4.contact_handoff.whatsapp_number == "+919845012345"
    assert "https://wa.me/919845012345" in decision4.contact_handoff.click_to_chat_url


def test_scenario_d_unsupported_channel(mock_scheme, mock_office):
    chat_sess = OfficeChatSession(session_id="s1", scheme_id=mock_scheme.id)
    rep_msg = "We cannot process verification enquiries through this desk channel. In-person token required."

    decision = decide_chat_turn(
        chat_session=chat_sess,
        preferences=UserAppointmentPreferences(),
        office=mock_office,
        scheme=mock_scheme,
        history=[],
        representative_message=rep_msg,
        llm=None,
    )

    assert decision.conversation_status == ChatStatus.unable_to_resolve
    assert decision.next_action == "recommend_direct_contact"
    assert "official department procedure directly" in decision.assistant_message

