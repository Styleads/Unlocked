"""Agent 4 after-appointment follow-up: when to ask, and what follows from the answer. Nothing is inferred."""
from datetime import datetime, timedelta, timezone

from agent4.follow_up import due_follow_ups, parse_reported_date, plan_after_appointment

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def appt(hours_ago=None, status="scheduled", **kw):
    when = (NOW - timedelta(hours=hours_ago)).isoformat() if hours_ago is not None else None
    return {"appointment_id": kw.pop("aid", "a1"), "purpose": "Document verification", "scheduled_at_utc": when, "status": status, **kw}


# --- when to ask --------------------------------------------------------------------------------------------------------

def test_asks_only_once_the_appointment_is_over():
    assert due_follow_ups([appt(hours_ago=0.5)], now=NOW) == []  # still in progress
    assert [f.appointment_id for f in due_follow_ups([appt(hours_ago=2)], now=NOW)] == ["a1"]
    assert due_follow_ups([appt(hours_ago=-24)], now=NOW) == []  # tomorrow


def test_never_asks_about_an_appointment_without_a_time():
    assert due_follow_ups([appt()], now=NOW) == []


def test_does_not_ask_again_once_answered_or_cancelled():
    for st in ("attended", "missed", "cancelled", "outcome_unknown", "rescheduled"):
        assert due_follow_ups([appt(hours_ago=3, status=st)], now=NOW) == []


def test_oldest_first_and_options_come_from_the_enums():
    due = due_follow_ups([appt(hours_ago=2, aid="new"), appt(hours_ago=48, aid="old")], now=NOW)
    assert [d.appointment_id for d in due] == ["old", "new"]
    assert {c.value for c in due[0].attended_options} == {"yes", "rescheduled", "missed", "cancelled", "unknown"}


def test_a_naive_stored_time_is_read_as_utc():
    due = due_follow_ups([{"appointment_id": "a", "purpose": "x", "scheduled_at_utc": "2026-11-10T09:00:00"}], now=NOW)
    assert due and due[0].scheduled_at_utc.tzinfo is not None


# --- what follows ---------------------------------------------------------------------------------------------------------

def plan(**report):
    return plan_after_appointment(appt(hours_ago=3), report, now=NOW)


def test_not_sure_changes_nothing():
    p = plan(attended="unknown")
    assert p.new_status == "outcome_unknown" and p.progress_updates == [] and p.ask_later == []


def test_documents_requested_become_steps_only_when_named():
    p = plan(attended="yes", outcome="additional_documents_requested", additional_documents="Caste certificate, caste certificate , Bank passbook")
    assert p.documents_to_add == ["Caste certificate", "Bank passbook"]
    assert [s.document for s in p.next_steps if s.kind == "collect_document"] == ["Caste certificate", "Bank passbook"]
    empty = plan(attended="yes", outcome="additional_documents_requested")
    assert empty.documents_to_add == [] and empty.warnings


def test_approval_asks_later_whether_the_benefit_arrived_and_never_assumes_it():
    p = plan(attended="yes", outcome="approved")
    assert [q.field for q in p.ask_later] == ["benefit_received"]
    assert {(u.field, u.state) for u in p.progress_updates} == {("appointment_attended", "yes"), ("submitted", "yes"), ("decision", "approved")}
    assert all(u.field != "benefit_received" for u in p.progress_updates)


def test_rejection_points_to_recovery():
    p = plan(attended="yes", outcome="rejected")
    assert any(s.kind == "recovery" for s in p.next_steps)


def test_a_moved_appointment_with_a_date_is_asked_about_again_later():
    p = plan(attended="rescheduled", rescheduled_date="2026-11-20T10:30")
    assert p.new_status == "scheduled"
    assert p.rescheduled_at_utc == datetime(2026, 11, 20, 5, 0, tzinfo=timezone.utc)  # 10:30 IST


def test_a_moved_appointment_without_a_date_asks_for_it():
    p = plan(attended="rescheduled")
    assert p.new_status == "rescheduled" and p.rescheduled_at_utc is None
    assert any(s.kind == "ask_date" for s in p.next_steps)


def test_a_past_or_unreadable_new_date_is_not_saved():
    assert parse_reported_date("2026-11-01", now=NOW) == (None, "The new date is in the past, so it wasn't saved.")
    when, problem = parse_reported_date("next tuesday", now=NOW)
    assert when is None and problem


def test_a_date_without_a_time_gets_no_invented_hour():
    when, _ = parse_reported_date("2026-11-20", now=NOW)
    assert when == datetime(2026, 11, 19, 18, 30, tzinfo=timezone.utc)  # midnight IST, i.e. "that day"


def test_missed_records_attendance_no_and_suggests_rebooking():
    p = plan(attended="missed")
    assert p.new_status == "missed" and [(u.field, u.state) for u in p.progress_updates] == [("appointment_attended", "no")]


def test_a_simulated_appointment_says_so():
    p = plan_after_appointment(appt(hours_ago=3, simulated=True), {"attended": "yes", "outcome": "documents_accepted"}, now=NOW)
    assert "simulation" in p.summary and all(u.simulated for u in p.progress_updates)
