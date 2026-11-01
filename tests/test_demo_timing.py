"""UNLOCKED_DEMO_APPOINTMENT_MINUTES: appointments land N minutes after booking, with the reminder before and the
follow-up after on the same short scale, so a live demo sees every email."""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.clock import now_utc
from api.main import app
from tests.test_office_chat_api import _seed_session


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    db_file = str(tmp_path / "demo.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("DEMO_MODE", "true")  # demo email provider: nothing leaves the machine
    monkeypatch.setenv("UNLOCKED_DEMO_APPOINTMENT_MINUTES", "2")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sid = await _seed_session(db_file)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/sessions/{sid}/notifications/preferences", json={"email": "demo@example.com", "email_enabled": True, "categories": {}, "consent_version": "step1"})
        yield client, sid


def at(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def close(a, b, seconds=20):
    return abs((a - b).total_seconds()) <= seconds


@pytest.mark.asyncio
async def test_an_added_appointment_is_two_minutes_out_whatever_time_was_typed(ctx):
    client, sid = ctx
    start = now_utc()
    appt = (await client.post(f"/api/sessions/{sid}/appointments", json={"purpose": "Verification", "scheduled_at_utc": "2027-01-01T05:00:00+00:00", "remind_email": True})).json()
    when = at(appt["scheduled_at_utc"])
    assert close(when, start + timedelta(minutes=2))
    notes = {n["notification_type"]: at(n["scheduled_at_utc"]) for n in (await client.get(f"/api/sessions/{sid}/notifications")).json()}
    assert close(notes["appointment_reminders"], when - timedelta(minutes=1))
    assert close(notes["appointment_follow_up"], when + timedelta(minutes=1))


@pytest.mark.asyncio
async def test_a_confirmed_office_chat_slot_is_two_minutes_out_everywhere(ctx):
    client, sid = ctx
    start = now_utc()
    chat = (await client.post(f"/api/sessions/{sid}/office-chats", json={"scheme_id": "fallback-ssp-scst-001", "scenario_id": "scenario_a_success", "pre_authorized_confirmation": True})).json()["chat_id"]
    for _ in range(2):
        view = (await client.post(f"/api/office-chats/{chat}/advance")).json()
    assert view["appointment_status"] == "simulated_confirmed"
    appt = (await client.get(f"/api/sessions/{sid}/appointments")).json()[0]
    assert close(at(appt["scheduled_at_utc"]), start + timedelta(minutes=2), seconds=70)
    # the chat's own result shows the same slot (Indian time, to the minute)
    assert view["appointment"]["date"] and view["appointment"]["time"]
    kinds = {n["notification_type"]: n["status"] for n in (await client.get(f"/api/sessions/{sid}/notifications")).json()}
    assert kinds["simulated_appointment_confirmed"] in ("sent", "accepted", "delivered")
    assert {"appointment_reminders", "appointment_follow_up"} <= set(kinds)


@pytest.mark.asyncio
async def test_without_the_switch_nothing_changes(ctx, monkeypatch):
    client, sid = ctx
    monkeypatch.delenv("UNLOCKED_DEMO_APPOINTMENT_MINUTES")
    appt = (await client.post(f"/api/sessions/{sid}/appointments", json={"purpose": "Verification", "scheduled_at_utc": "2027-01-01T05:00:00+00:00", "remind_email": False})).json()
    assert at(appt["scheduled_at_utc"]) == at("2027-01-01T05:00:00+00:00")
