"""API: the app asks how an appointment went once it is over, and applies Agent 4's plan to the answer."""
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.clock import now_utc
from api.main import app
from tests.test_office_chat_api import _seed_session


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    db_file = str(tmp_path / "followup.db")
    monkeypatch.setenv("DB_PATH", db_file)
    sid = await _seed_session(db_file)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, sid


async def add(client, sid, hours_from_now, purpose="Document verification"):
    body = {"purpose": purpose, "remind_email": False}
    if hours_from_now is not None:
        body["scheduled_at_utc"] = (now_utc() + timedelta(hours=hours_from_now)).isoformat()
    res = await client.post(f"/api/sessions/{sid}/appointments", json=body)
    assert res.status_code in (200, 201), res.text
    return res.json()["appointment_id"]


@pytest.mark.asyncio
async def test_only_finished_appointments_are_asked_about(ctx):
    client, sid = ctx
    past = await add(client, sid, -3)
    await add(client, sid, 24)
    await add(client, sid, None)
    due = (await client.get(f"/api/sessions/{sid}/follow-ups")).json()
    assert [d["appointment_id"] for d in due] == [past]


@pytest.mark.asyncio
async def test_answering_stops_the_question_and_returns_next_steps(ctx):
    client, sid = ctx
    aid = await add(client, sid, -3)
    res = await client.post(f"/api/sessions/{sid}/appointments/{aid}/outcome", json={"attended": "yes", "outcome": "approved"})
    assert res.status_code == 200
    plan = res.json()["outcome_details"]["plan"]
    assert plan["new_status"] == "attended" and plan["ask_later"][0]["field"] == "benefit_received"
    assert (await client.get(f"/api/sessions/{sid}/follow-ups")).json() == []


@pytest.mark.asyncio
async def test_a_moved_appointment_is_asked_about_again_after_the_new_date(ctx):
    client, sid = ctx
    aid = await add(client, sid, -3)
    new_day = (now_utc() + timedelta(days=5)).strftime("%Y-%m-%dT10:00")
    res = (await client.post(f"/api/sessions/{sid}/appointments/{aid}/outcome", json={"attended": "rescheduled", "rescheduled_date": new_day})).json()
    assert res["status"] == "scheduled" and res["scheduled_at_utc"].startswith((now_utc() + timedelta(days=5)).strftime("%Y-%m-%d"))
    assert (await client.get(f"/api/sessions/{sid}/follow-ups")).json() == []  # not until the new date has passed


@pytest.mark.asyncio
async def test_a_return_visit_becomes_its_own_appointment(ctx):
    client, sid = ctx
    aid = await add(client, sid, -3)
    day = (now_utc() + timedelta(days=3)).strftime("%Y-%m-%d")
    await client.post(f"/api/sessions/{sid}/appointments/{aid}/outcome", json={"attended": "yes", "outcome": "return_scheduled", "rescheduled_date": day})
    appts = (await client.get(f"/api/sessions/{sid}/appointments")).json()
    assert any(a["purpose"] == "Return visit: Document verification" and a["status"] == "scheduled" for a in appts)


@pytest.mark.asyncio
async def test_an_unrecognised_answer_is_refused(ctx):
    client, sid = ctx
    aid = await add(client, sid, -3)
    res = await client.post(f"/api/sessions/{sid}/appointments/{aid}/outcome", json={"attended": "maybe"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_a_rejection_is_explained_immediately(ctx):
    client, sid = ctx
    # answers that fail the SSP scholarship's verified category and income rules
    await client.post(f"/api/sessions/{sid}/answers", json={"answers": [
        {"attribute": "social_category", "state": "answered", "value": "OBC"},
        {"attribute": "annual_family_income", "state": "answered", "value": {"min": 250001, "max": 500000}},
    ]})
    aid = await add(client, sid, -3)
    res = (await client.post(f"/api/sessions/{sid}/appointments/{aid}/outcome", json={
        "attended": "yes", "outcome": "rejected", "scheme_id": "fallback-ssp-scst-001", "reason": "Income too high"})).json()
    wi = res["outcome_details"]["what_if"]
    assert {f["attribute"] for f in wi["failed"]} >= {"social_category", "annual_family_income"}
    assert wi["changes"] and all(c["value"] is not None for c in wi["changes"])
    assert any(s["kind"] == "what_if" for s in res["outcome_details"]["plan"]["next_steps"])
    direct = (await client.get(f"/api/sessions/{sid}/schemes/fallback-ssp-scst-001/what-if")).json()
    assert direct["failed"] == wi["failed"]
