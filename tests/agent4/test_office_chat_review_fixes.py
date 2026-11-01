"""Regression tests for the review of feat/whatsappsim: each pins a way the simulator could invent a slot, a contact or a
decision the office never made."""
from __future__ import annotations

from agent4.office_chat_agent import (
    check_slot_in_office_hours,
    decide_chat_turn,
    extract_slot_heuristically,
    parse_time_str,
)
from agent4.office_chat_models import (
    AppointmentStatus,
    ChatStatus,
    ContactSource,
    OfficeChatSession,
    OfficeContact,
    UserAppointmentPreferences,
)
from agent4.models import SchemeContext


def session():
    return OfficeChatSession(chat_id="c1", session_id="s1", scheme_id="demo", scenario_id="x")


def decide(message, prefs=None, office=None, rep_result=None, llm=None):
    return decide_chat_turn(
        chat_session=session(), preferences=prefs, office=office or OfficeContact(scheme_id="demo", office_name="Demo Desk"),
        scheme=SchemeContext(id="demo", name="Demo Scholarship A"), history=[], representative_message=message,
        rep_result=rep_result, llm=llm,
    )


def test_no_preferences_means_no_constraint_not_monday_and_tuesday():
    prefs = UserAppointmentPreferences(session_id="s1", scheme_id="demo")
    assert prefs.preferred_days == [] and prefs.preferred_windows == []
    d = decide("We have a slot available on Friday at 4:00 PM.", prefs)
    assert d.conversation_status == ChatStatus.appointment_offered


def test_a_slot_is_never_invented():
    assert extract_slot_heuristically("Slots are open this week, please check the portal.") is None
    d = decide("We have appointment slots available.")
    assert d.appointment_offer is None and d.next_action == "clarify_slot"


def test_unknown_office_hours_rule_nothing_out():
    office = OfficeContact(scheme_id="demo", office_name="Demo Desk")
    assert check_slot_in_office_hours("saturday", parse_time_str("9 PM"), office)
    noted = OfficeContact(scheme_id="demo", office_name="Demo Desk", office_hours="Mon-Fri 10am to 5pm")
    assert noted.office_hours == {"notes": "Mon-Fri 10am to 5pm"}
    assert check_slot_in_office_hours("saturday", parse_time_str("9 PM"), noted)


def test_published_hours_do_rule_a_slot_out():
    office = OfficeContact(scheme_id="demo", office_name="Demo Desk", office_hours={"monday": {"open": "10:00", "close": "17:00"}})
    assert not check_slot_in_office_hours("monday", parse_time_str("6 PM"), office)
    assert not check_slot_in_office_hours("sunday", parse_time_str("11:00"), office)


def test_times_without_minutes_are_read():
    assert parse_time_str("3 PM").hour == 15 and parse_time_str("3PM").hour == 15 and parse_time_str("3:30PM").minute == 30


def test_not_confirmed_is_not_a_confirmation():
    prefs = UserAppointmentPreferences(session_id="s1", scheme_id="demo", pre_authorized_confirmation=True)
    d = decide("Monday at 11:00 AM is not confirmed yet.", prefs)
    assert d.conversation_status != ChatStatus.completed


def test_a_confirmed_slot_outside_what_was_pre_approved_goes_to_the_applicant():
    prefs = UserAppointmentPreferences(session_id="s1", scheme_id="demo", preferred_days=["monday"], pre_authorized_confirmation=True)
    d = decide("Friday at 11:00 AM is confirmed.", prefs)
    assert d.conversation_status == ChatStatus.awaiting_user_input
    assert d.appointment_offer.status == AppointmentStatus.awaiting_user_approval


def test_a_whatsapp_number_is_only_ever_one_the_office_gave():
    d = decide("Please message us on WhatsApp.")
    assert d.contact_handoff is None and d.next_action == "collect_receiver_whatsapp"
    d = decide("Please message us on WhatsApp at +91 98765 43210.")
    assert d.contact_handoff.whatsapp_number == "+919876543210"
    assert d.contact_handoff.contact_source == ContactSource.receiver_provided
    assert d.contact_handoff.click_to_chat_url.startswith("https://wa.me/919876543210")


class _Model:
    def __init__(self, reply):
        self.reply = reply

    def complete_json(self, system, user):
        return self.reply


def test_the_model_can_reword_but_not_decide_or_add_links():
    # a model trying to force completion and add a link: status stays the deterministic one, and the link is dropped
    llm = _Model('{"assistant_message": "All done, book here https://evil.example/pay now", "conversation_status": "completed"}')
    d = decide("We have no slots available.", llm=llm)
    assert d.conversation_status == ChatStatus.no_availability
    assert "evil.example" not in d.assistant_message


def test_a_model_failure_keeps_the_deterministic_wording():
    class Broken:
        def complete_json(self, system, user):
            raise RuntimeError("quota")
    d = decide("We have no slots available.", llm=Broken())
    assert d.conversation_status == ChatStatus.no_availability and d.assistant_message
