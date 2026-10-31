from datetime import date, datetime, time, timezone

from agent4 import ArtifactStatus, CalendarRequest, EventKind, build_calendar_artifact
from agent4.calendar_ics import escape_text, fold

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _lines(body: str) -> list[str]:
    assert body.endswith("\r\n")
    return body.replace("\r\n ", "").split("\r\n")[:-1]


def test_deadline_from_sourced_scheme_is_all_day(scheme):
    a = build_calendar_artifact(CalendarRequest(scheme=scheme), now=NOW)
    assert a.status is ArtifactStatus.ready
    lines = _lines(a.body_content)
    assert "DTSTART;VALUE=DATE:20261215" in lines
    assert "DTEND;VALUE=DATE:20261216" in lines
    assert "DTSTAMP:20261031T120000Z" in lines
    assert "BEGIN:VTIMEZONE" not in lines
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-1] == "END:VCALENDAR"
    assert a.source_urls == ["https://example.gov.in/notice"]
    assert a.filename == "demo-scholarship-a-deadline-2026-12-15.ics"
    assert a.mime_type == "text/calendar"
    assert lines.count("BEGIN:VALARM") == 2 and "TRIGGER:-P3D" in lines


def test_unsourced_scheme_deadline_is_never_used(unsourced_scheme):
    a = build_calendar_artifact(CalendarRequest(scheme=unsourced_scheme), now=NOW)
    assert a.status is ArtifactStatus.needs_input
    assert a.missing_fields == ["event_date"]
    assert a.body_content == ""


def test_user_date_needs_confirmation(unsourced_scheme):
    a = build_calendar_artifact(CalendarRequest(scheme=unsourced_scheme, event_date=date(2026, 12, 1)), now=NOW)
    assert a.missing_fields == ["date_confirmation"]
    ok = build_calendar_artifact(CalendarRequest(scheme=unsourced_scheme, event_date=date(2026, 12, 1), date_confirmed_by_user=True), now=NOW)
    assert ok.status is ArtifactStatus.ready
    assert "Date entered by you." in ok.body_content.replace("\r\n ", "")


def test_appointment_is_timed_in_ist(scheme):
    req = CalendarRequest(scheme=scheme, kind=EventKind.appointment, event_date=date(2026, 11, 20), date_confirmed_by_user=True,
                          start_time=time(10, 30), location="Taluk Office, Room 4; Demo Town")
    lines = _lines(build_calendar_artifact(req, now=NOW).body_content)
    assert "DTSTART;TZID=Asia/Kolkata:20261120T103000" in lines
    assert "DTEND;TZID=Asia/Kolkata:20261120T113000" in lines
    assert "TZOFFSETTO:+0530" in lines
    assert "LOCATION:Taluk Office\\, Room 4\\; Demo Town" in lines


def test_appointment_without_time_asks(scheme):
    req = CalendarRequest(scheme=scheme, kind=EventKind.appointment, event_date=date(2026, 11, 20), date_confirmed_by_user=True)
    assert build_calendar_artifact(req, now=NOW).missing_fields == ["start_time"]


def test_end_before_start_is_rejected(scheme):
    req = CalendarRequest(scheme=scheme, kind=EventKind.appointment, event_date=date(2026, 11, 20), date_confirmed_by_user=True,
                          start_time=time(11, 0), end_time=time(10, 0))
    assert "end_time" in build_calendar_artifact(req, now=NOW).missing_fields


def test_past_date_warns(scheme):
    req = CalendarRequest(scheme=scheme, event_date=date(2026, 1, 1), date_confirmed_by_user=True)
    assert any("past" in w for w in build_calendar_artifact(req, now=NOW).warnings)


def test_uid_is_stable(scheme):
    a = build_calendar_artifact(CalendarRequest(scheme=scheme), now=NOW)
    b = build_calendar_artifact(CalendarRequest(scheme=scheme), now=datetime(2026, 11, 2, tzinfo=timezone.utc))
    uid = [line for line in _lines(a.body_content) if line.startswith("UID:")]
    assert uid == [line for line in _lines(b.body_content) if line.startswith("UID:")]


def test_escape_and_fold():
    assert escape_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    long = "DESCRIPTION:" + "ಕನ್ನಡ" * 40
    folded = fold(long)
    assert all(len(part.encode("utf-8")) <= 75 for part in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == long


def test_no_line_exceeds_75_octets(scheme):
    req = CalendarRequest(scheme=scheme, notes="Bring originals and two photocopies of every certificate. " * 5)
    for raw in build_calendar_artifact(req, now=NOW).body_content.split("\r\n"):
        assert len(raw.encode("utf-8")) <= 75
