"""A confirmed simulated appointment: confirmation email sent at once, reminder and follow-up scheduled, appointment
listed (and later asked about)."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from tests.test_office_chat_api import _seed_session


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    db_file = str(tmp_path / "confirm.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.setenv("DEMO_MODE", "true")  # demo provider: nothing leaves the machine
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sid = await _seed_session(db_file)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, sid


async def confirm(client, sid):
    res = await client.post(f"/api/sessions/{sid}/office-chats", json={"scheme_id": "fallback-ssp-scst-001", "scenario_id": "scenario_a_success", "pre_authorized_confirmation": True})
    chat = res.json()["chat_id"]
    for _ in range(2):
        view = (await client.post(f"/api/office-chats/{chat}/advance")).json()
    assert view["appointment_status"] == "simulated_confirmed"


@pytest.mark.asyncio
async def test_confirmation_is_emailed_at_once_and_reminders_are_scheduled(ctx):
    client, sid = ctx
    await client.post(f"/api/sessions/{sid}/notifications/preferences", json={"email": "demo@example.com", "email_enabled": True, "categories": {}, "consent_version": "step1"})
    await confirm(client, sid)
    notes = (await client.get(f"/api/sessions/{sid}/notifications")).json()
    kinds = {n["notification_type"]: n for n in notes}
    assert kinds["simulated_appointment_confirmed"]["status"] in ("sent", "accepted", "delivered")
    assert "appointment_follow_up" in kinds  # after the appointment
    appts = (await client.get(f"/api/sessions/{sid}/appointments")).json()
    assert len(appts) == 1 and appts[0]["purpose"].startswith("[SIMULATED]") and appts[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_without_an_email_nothing_is_sent_but_the_appointment_is_kept(ctx):
    client, sid = ctx
    await confirm(client, sid)
    notes = (await client.get(f"/api/sessions/{sid}/notifications")).json()
    assert all(n["status"] not in ("sent", "accepted") for n in notes)
    assert len((await client.get(f"/api/sessions/{sid}/appointments")).json()) == 1


@pytest.mark.asyncio
async def test_force_fallback_switch(ctx, monkeypatch):
    client, sid = ctx
    monkeypatch.setenv("UNLOCKED_FORCE_FALLBACK", "1")
    res = await client.post("/api/sessions", json={"context": {"state": "Karnataka", "age": 20}, "scope": "guided"})
    new = res.json()["session_id"]
    found = (await client.post(f"/api/sessions/{new}/discover", json={"enable_fallback": True})).json()
    assert found["source_mode"] == "fallback" and found["schemes"]
