from datetime import datetime, timezone

from agent4 import update_progress

NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


def test_new_record_is_all_unknown():
    r = update_progress(None, "demo_a", now=NOW)
    assert r.progress.submitted.state == r.progress.decision.state == r.progress.benefit_received.state == "unknown"
    assert r.follow_ups == []


def test_approval_does_not_imply_submission_or_receipt():
    r = update_progress(None, "demo_a", [{"field": "decision", "state": "approved"}], now=NOW)
    assert r.progress.submitted.state == "unknown"
    assert r.progress.benefit_received.state == "unknown"
    assert {f.field for f in r.follow_ups} == {"submitted", "benefit_received"}


def test_submitted_asks_for_decision():
    r = update_progress(None, "demo_a", [{"field": "submitted", "state": "yes"}], now=NOW)
    assert [f.id for f in r.follow_ups] == ["fu_decision"]


def test_contradictions_are_kept_and_flagged():
    r = update_progress(None, "demo_a", [{"field": "submitted", "state": "no"}, {"field": "decision", "state": "approved"}], now=NOW)
    assert r.progress.submitted.state == "no" and r.progress.decision.state == "approved"
    assert any("check both answers" in w for w in r.warnings)


def test_invalid_updates_are_ignored():
    r = update_progress(None, "demo_a", [{"field": "decision", "state": "maybe"}, {"field": "aadhaar", "state": "yes"}], now=NOW)
    assert r.progress.decision.state == "unknown"
    assert len(r.warnings) == 2


def test_input_not_mutated_and_history_kept():
    first = update_progress(None, "demo_a", [{"field": "submitted", "state": "yes"}], now=NOW).progress
    second = update_progress(first, "demo_a", [{"field": "decision", "state": "rejected", "simulated": True}], now=NOW)
    assert first.decision.state == "unknown"
    assert [h["field"] for h in second.progress.history] == ["submitted", "decision"]
    assert "simulated" in second.summary


def test_round_trip_through_json():
    r = update_progress(None, "demo_a", [{"field": "submitted", "state": "YES"}], now=NOW)
    again = update_progress(r.progress.model_dump(mode="json"), "demo_a", now=NOW)
    assert again.progress.submitted.state == "yes"
