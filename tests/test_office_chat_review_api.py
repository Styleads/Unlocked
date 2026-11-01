"""API regression tests for the review of feat/whatsappsim: nothing is invented, nothing happens twice, nothing is
decided for the applicant."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from tests.test_office_chat_api import _seed_session

SCHEME = "fallback-ssp-scst-001"


async def _start(client, session_id, scenario, **extra):
    body = {"scheme_id": SCHEME, "scenario_id": scenario, **extra}
    res = await client.post(f"/api/sessions/{session_id}/office-chats", json=body)
    assert res.status_code == 201, res.text
    return res.json()["chat_id"]


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    db_file = str(tmp_path / "review.db")
    monkeypatch.setenv("DB_PATH", db_file)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    session_id = await _seed_session(db_file)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, session_id


@pytest.mark.asyncio
async def test_a_confirmed_appointment_is_recorded_once_even_if_approved_twice(ctx):
    client, sid = ctx
    chat = await _start(client, sid, "scenario_a_success", preferred_days=["monday"], pre_authorized_confirmation=False)
    await client.post(f"/api/office-chats/{chat}/advance")  # the office offers a slot
    adv = (await client.post(f"/api/office-chats/{chat}/advance")).json()  # and confirms it
    assert adv["appointment_status"] == "awaiting_user_approval"
    ok = await client.post(f"/api/office-chats/{chat}/user-input", json={"action": "approve_slot", "user_approved_slot": True})
    assert ok.status_code == 200 and ok.json()["chat_status"] == "completed"
    again = await client.post(f"/api/office-chats/{chat}/user-input", json={"action": "approve_slot", "user_approved_slot": True})
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_approving_with_nothing_offered_is_refused(ctx):
    client, sid = ctx
    chat = await _start(client, sid, "scenario_a_success")
    res = await client.post(f"/api/office-chats/{chat}/user-input", json={"action": "approve_slot", "user_approved_slot": True})
    assert res.status_code == 409
    view = (await client.get(f"/api/office-chats/{chat}")).json()
    assert view["appointment_status"] != "simulated_confirmed" and view["appointment"] is None


@pytest.mark.asyncio
async def test_the_chat_waits_for_the_applicant_before_it_goes_on(ctx):
    client, sid = ctx
    chat = await _start(client, sid, "scenario_a_success", preferred_days=["monday"])
    await client.post(f"/api/office-chats/{chat}/advance")
    await client.post(f"/api/office-chats/{chat}/advance")
    res = await client.post(f"/api/office-chats/{chat}/advance")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_finishing_early_without_an_appointment_is_a_cancellation_not_a_success(ctx):
    client, sid = ctx
    chat = await _start(client, sid, "scenario_a_success")
    done = (await client.post(f"/api/office-chats/{chat}/finish")).json()
    assert done["chat_status"] == "cancelled"
    outcome = (await client.get(f"/api/office-chats/{chat}/outcome")).json()
    assert "ChatStatus" not in outcome["summary"]


@pytest.mark.asyncio
async def test_finishing_does_not_relabel_a_no_availability_result(ctx):
    client, sid = ctx
    chat = await _start(client, sid, "scenario_b_no_availability")
    await client.post(f"/api/office-chats/{chat}/advance")
    done = (await client.post(f"/api/office-chats/{chat}/finish")).json()
    assert done["chat_status"] == "no_availability"


@pytest.mark.asyncio
async def test_no_availability_given_means_no_invented_preferences(ctx):
    client, sid = ctx
    chat = await _start(client, sid, "scenario_a_success")
    first = (await client.get(f"/api/office-chats/{chat}")).json()["messages"][0]["message_text"]
    assert "monday" not in first.lower() and "tuesday" not in first.lower()


@pytest.mark.asyncio
async def test_the_whatsapp_link_uses_only_the_number_the_office_gave(ctx):
    client, sid = ctx
    chat = await _start(client, sid, "scenario_c_missing_info")
    for _ in range(4):
        view = (await client.post(f"/api/office-chats/{chat}/advance")).json()
    questions = view["unresolved_questions"]
    for q in questions:
        link = q.get("click_to_chat_url")
        if link:
            assert q["receiver_whatsapp_number"] and link.startswith("https://wa.me/" + q["receiver_whatsapp_number"].lstrip("+"))
    given = [m["metadata"].get("receiver_whatsapp_number") for m in view["messages"] if m["sender"] == "simulated_office"]
    assert any(given), "the simulated office states a number in this scenario"
    assert {q["receiver_whatsapp_number"] for q in questions if q.get("receiver_whatsapp_number")} <= set(given)


@pytest.mark.asyncio
async def test_a_question_from_another_chat_cannot_be_resolved_here(ctx):
    client, sid = ctx
    chat_c = await _start(client, sid, "scenario_c_missing_info")
    for _ in range(3):
        view = (await client.post(f"/api/office-chats/{chat_c}/advance")).json()
    if not view["unresolved_questions"]:
        pytest.skip("scenario produced no question")
    other = await _start(client, sid, "scenario_a_success")
    res = await client.post(f"/api/office-chats/{other}/user-input", json={"action": "submit_info", "unresolved_question_id": view["unresolved_questions"][0]["question_id"]})
    assert res.status_code == 404
