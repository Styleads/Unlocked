"""RFC 5545 calendar files for a deadline or appointment.

Dates come only from the user or a sourced field; anything missing is reported in
`missing_fields` for the UI to ask about. Deadlines are all-day events (a deadline
has no time of day), appointments are timed in Asia/Kolkata."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .models import ActionArtifact, ActionType, ArtifactStatus, CalendarRequest, EventKind

PRODID = "-//Unlocked//Karnataka Benefits Assistant//EN"
_UID_NS = uuid.UUID("6f1c2b1e-4a7d-4c55-9a3e-2f0d7b8e5a10")

# India has no daylight saving, so one fixed STANDARD block is exact.
VTIMEZONE_IST = [
    "BEGIN:VTIMEZONE",
    "TZID:Asia/Kolkata",
    "BEGIN:STANDARD",
    "DTSTART:19700101T000000",
    "TZOFFSETFROM:+0530",
    "TZOFFSETTO:+0530",
    "TZNAME:IST",
    "END:STANDARD",
    "END:VTIMEZONE",
]

INSTRUCTIONS = (
    "Download the .ics file and open it to add the event to your calendar (Google Calendar, Outlook, "
    "Apple Calendar). Check the date against the official source before relying on it."
)


def escape_text(value: str) -> str:
    """TEXT escaping (RFC 5545 §3.3.11)."""
    return (value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def fold(line: str) -> str:
    """Fold at 75 octets without splitting a UTF-8 character (§3.1)."""
    out, current, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        limit = 75 if not out else 74  # continuation lines start with a space
        if size + n > limit:
            out.append(current)
            current, size = ch, n
        else:
            current += ch
            size += n
    out.append(current)
    return "\r\n ".join(out)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "event"


def _resolve_date(req: CalendarRequest) -> tuple[Optional[date], Optional[str], list[str]]:
    """Return (date, source_url, missing). A deadline may come from the scheme
    record, but only when that deadline carries its own source."""
    if req.event_date is not None:
        if req.date_confirmed_by_user or req.date_source_url:
            return req.event_date, req.date_source_url, []
        return req.event_date, None, ["date_confirmation"]
    s = req.scheme
    if req.kind is EventKind.deadline and s.deadline and s.deadline_source_url:
        try:
            return date.fromisoformat(s.deadline), s.deadline_source_url, []
        except ValueError:
            pass
    return None, None, ["event_date"]


def build_calendar_artifact(request: CalendarRequest | dict, *, now: Optional[datetime] = None) -> ActionArtifact:
    req = request if isinstance(request, CalendarRequest) else CalendarRequest.model_validate(request)
    s = req.scheme
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    warnings: list[str] = []

    when, source_url, missing = _resolve_date(req)
    if req.kind is EventKind.appointment and req.start_time is None:
        missing.append("start_time")
    if req.end_time is not None and req.start_time is not None and req.end_time <= req.start_time:
        missing.append("end_time")
        warnings.append("The end time must be after the start time.")

    label = "Application deadline" if req.kind is EventKind.deadline else "Appointment"
    title = f"{label}: {s.name}"
    if missing:
        return ActionArtifact(
            action_type=ActionType.calendar_ics, status=ArtifactStatus.needs_input, title=title,
            instructions="We need a few details before we can make the calendar file. We never guess a date.",
            missing_fields=missing, warnings=warnings,
        )

    assert when is not None
    if when < now.astimezone(timezone(timedelta(hours=5, minutes=30))).date():
        warnings.append("This date is in the past.")

    uid = f"{uuid.uuid5(_UID_NS, f'{s.id}|{req.kind.value}|{when.isoformat()}')}@unlocked.local"
    desc = [f"{label} for {s.name}."]
    if s.application_url and req.kind is EventKind.deadline:
        desc.append(f"Apply on the official portal: {s.application_url}")
    if source_url:
        desc.append(f"Date source: {source_url}")
    elif req.date_confirmed_by_user:
        desc.append("Date entered by you.")
    if req.notes:
        desc.append(req.notes)
    if req.kind is EventKind.deadline:
        desc.append("Have all required documents ready before this date.")

    event = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
    ]
    if req.start_time is None:
        event += [f"DTSTART;VALUE=DATE:{when.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(when + timedelta(days=1)).strftime('%Y%m%d')}",
                  "TRANSP:TRANSPARENT"]
    else:
        start = datetime.combine(when, req.start_time)
        end = datetime.combine(when, req.end_time) if req.end_time else start + timedelta(hours=1)
        event += [f"DTSTART;TZID=Asia/Kolkata:{start.strftime('%Y%m%dT%H%M%S')}",
                  f"DTEND;TZID=Asia/Kolkata:{end.strftime('%Y%m%dT%H%M%S')}"]
    event += [f"SUMMARY:{escape_text(title)}", f"DESCRIPTION:{escape_text(chr(10).join(desc))}"]
    if req.location:
        event.append(f"LOCATION:{escape_text(req.location)}")
    if s.application_url:
        event.append(f"URL:{s.application_url}")
    event.append("STATUS:CONFIRMED")
    for days in sorted({d for d in req.remind_days_before if 0 <= d <= 60}, reverse=True):
        event += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{escape_text(title)}",
                  f"TRIGGER:-P{days}D" if days else "TRIGGER:PT0M", "END:VALARM"]
    event.append("END:VEVENT")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    if req.start_time is not None:
        lines += VTIMEZONE_IST
    lines += event + ["END:VCALENDAR"]
    body = "\r\n".join(fold(line) for line in lines) + "\r\n"

    return ActionArtifact(
        action_type=ActionType.calendar_ics, status=ArtifactStatus.ready, title=title, body_content=body,
        instructions=INSTRUCTIONS, filename=f"{_slug(s.name)}-{req.kind.value}-{when.isoformat()}.ics",
        mime_type="text/calendar", source_urls=[source_url] if source_url else [], warnings=warnings,
    )
