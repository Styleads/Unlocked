"""Unit tests for api/office_simulator.py scenario engine and availability matching."""
from datetime import time
import pytest

from agent4.office_chat_models import OfficeContact, TimeWindow, UserAppointmentPreferences
from api.office_simulator import (
    OfficeSimulatorService,
    is_time_within_range,
    parse_time_str,
)


@pytest.fixture
def simulator():
    return OfficeSimulatorService()


def test_time_parsing():
    assert parse_time_str("11:00") == time(11, 0)
    assert parse_time_str("11:30 AM") == time(11, 30)
    assert parse_time_str("02:45 PM") == time(14, 45)
    assert parse_time_str("invalid") is None


def test_time_within_range():
    assert is_time_within_range(time(11, 0), time(10, 0), time(13, 0)) is True
    assert is_time_within_range(time(9, 30), time(10, 0), time(13, 0)) is False
    assert is_time_within_range(time(13, 0), time(10, 0), time(13, 0)) is True


def test_office_hours_and_preferences_matching(simulator):
    office_hours = {
        "monday": {"open": "10:00", "close": "17:30"},
        "tuesday": {"open": "10:00", "close": "17:30"},
        "timezone": "Asia/Kolkata",
    }

    # Within Monday hours
    assert simulator.is_slot_within_office_hours("monday", time(11, 0), office_hours) is True
    # Before Monday hours
    assert simulator.is_slot_within_office_hours("monday", time(9, 0), office_hours) is False
    # Outside working days (Sunday)
    assert simulator.is_slot_within_office_hours("sunday", time(11, 0), office_hours) is False

    prefs = UserAppointmentPreferences(
        preferred_days=["monday", "tuesday"],
        preferred_windows=[TimeWindow(start="10:00", end="12:00")],
    )

    # Monday 11:00 AM matches
    assert simulator.is_slot_within_user_preferences("monday", time(11, 0), prefs) is True
    # Monday 14:00 PM outside preferred window
    assert simulator.is_slot_within_user_preferences("monday", time(14, 0), prefs) is False
    # Wednesday 11:00 AM outside preferred days
    assert simulator.is_slot_within_user_preferences("wednesday", time(11, 0), prefs) is False


def test_scenario_a_success(simulator):
    prefs = UserAppointmentPreferences(
        preferred_days=["monday"],
        preferred_windows=[TimeWindow(start="10:00", end="13:00")],
    )
    office = OfficeContact(
        office_hours={"monday": {"open": "10:00", "close": "17:30"}, "timezone": "Asia/Kolkata"}
    )

    # Turn 2: Representative offers slot
    res2 = simulator.process_turn(
        scenario_id="scenario_a_success",
        turn_index=2,
        assistant_message="Hello, enquiring about appointment availability.",
        preferences=prefs,
        office=office,
    )
    assert res2.turn_index == 2
    assert res2.intent == "offer_slot"
    assert res2.offered_slot is not None
    assert res2.offered_slot["day"] == "monday"
    assert res2.offered_slot["time"] == "11:00"
    assert res2.metadata.get("within_office_hours") is True
    assert res2.metadata.get("within_user_preferences") is True

    # Turn 4: Representative explicitly confirms
    res4 = simulator.process_turn(
        scenario_id="scenario_a_success",
        turn_index=4,
        assistant_message="Could you please confirm Monday at 11:00 AM?",
        preferences=prefs,
        office=office,
    )
    assert res4.turn_index == 4
    assert res4.intent == "explicit_confirmation"
    assert res4.confirmed_slot is not None
    assert "confirmed" in res4.message.lower()


def test_scenario_b_no_availability(simulator):
    res2 = simulator.process_turn(
        scenario_id="scenario_b_no_availability",
        turn_index=2,
        assistant_message="Hello, enquiring about appointment availability.",
    )
    assert res2.intent == "no_availability"
    assert res2.offered_slot is None
    assert "no appointment slots" in res2.message.lower()


def test_scenario_c_missing_info(simulator):
    # Turn 2: Requests info
    res2 = simulator.process_turn(
        scenario_id="scenario_c_missing_info",
        turn_index=2,
        assistant_message="Hello, enquiring about verification.",
    )
    assert res2.intent == "request_missing_info"
    assert res2.requested_info is not None

    # Turn 4: Provides WhatsApp contact
    res4 = simulator.process_turn(
        scenario_id="scenario_c_missing_info",
        turn_index=4,
        assistant_message="The applicant will provide these details directly. Could you share an office WhatsApp number?",
    )
    assert res4.intent == "provide_contact"
    assert res4.receiver_whatsapp_number == "+919845012345"
    assert "+919845012345" in res4.message


def test_scenario_d_unsupported(simulator):
    res2 = simulator.process_turn(
        scenario_id="scenario_d_unclear_unsupported",
        turn_index=2,
        assistant_message="Hello, enquiring about verification.",
    )
    assert res2.intent == "unsupported_channel"
    assert "cannot process" in res2.message.lower()


def test_out_of_bounds_turn(simulator):
    res = simulator.process_turn(
        scenario_id="scenario_a_success",
        turn_index=99,
        assistant_message="Any further updates?",
    )
    assert res.is_terminal is True
    assert "concluded" in res.message.lower()
