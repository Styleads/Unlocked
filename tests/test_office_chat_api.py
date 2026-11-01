"""End-to-end API tests for Office Chat Simulator endpoints in api/main.py."""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from api.database import get_connection, init_db, _to_json
from api.main import app
from discovery_agent.fallback_schemes import get_fallback_schemes


async def _seed_session(db_path: str) -> str:
    await init_db(db_path=db_path)
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    schemes = get_fallback_schemes()
    schemes_json = _to_json([s.model_dump(mode="json") for s in schemes])

    async with get_connection(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO sessions (
                session_id, scope, preferred_language, state_status, context_json,
                raw_schemes_json, normalized_schemes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (session_id, "guided", "en", "initial", "{}", schemes_json, schemes_json),
        )
        await conn.commit()

    return session_id


@pytest.mark.asyncio
async def test_scenario_a_with_pre_authorization_flow(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setenv("DB_PATH", db_file)
    session_id = await _seed_session(db_file)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create simulated office chat
        create_payload = {
            "scheme_id": "fallback-ssp-scst-001",
            "scenario_id": "scenario_a_success",
            "preferred_days": ["monday"],
            "preferred_windows": [{"start": "10:00", "end": "13:00"}],
            "pre_authorized_confirmation": True,
        }
        res = await client.post(f"/api/sessions/{session_id}/office-chats", json=create_payload)
        assert res.status_code == 201
        data = res.json()
        chat_id = data["chat_id"]
        assert data["simulation_mode"] is True
        assert data["chat_status"] == "in_progress"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["sender"] == "unlocked"

        # 2. Advance turn 1 -> Representative offers slot (turn 2) + Assistant requests confirmation (turn 3)
        res_adv1 = await client.post(f"/api/office-chats/{chat_id}/advance")
        assert res_adv1.status_code == 200
        data_adv1 = res_adv1.json()
        assert len(data_adv1["messages"]) == 3  # Turn 1, Turn 2, Turn 3
        assert data_adv1["chat_status"] == "appointment_offered"
        assert data_adv1["appointment"]["status"] == "offered"

        # 3. Advance turn 2 -> Representative confirms slot (turn 4) + Assistant accepts (pre-authorized)
        res_adv2 = await client.post(f"/api/office-chats/{chat_id}/advance")
        assert res_adv2.status_code == 200
        data_adv2 = res_adv2.json()
        assert len(data_adv2["messages"]) == 5
        assert data_adv2["chat_status"] == "completed"
        assert data_adv2["appointment_status"] == "simulated_confirmed"
        assert "BEGIN:VCALENDAR" in data_adv2["appointment"]["calendar_ics"]
        assert "SIMULATION DEMO" in data_adv2["appointment"]["calendar_ics"]

        # 4. Check outcome endpoint
        res_outcome = await client.get(f"/api/office-chats/{chat_id}/outcome")
        assert res_outcome.status_code == 200
        data_out = res_outcome.json()
        assert data_out["appointment_status"] == "simulated_confirmed"
        assert "Simulated appointment confirmed" in data_out["summary"]
        assert len(data_out["next_steps"]) >= 1


@pytest.mark.asyncio
async def test_scenario_a_without_pre_authorization_requires_user_approval(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setenv("DB_PATH", db_file)
    session_id = await _seed_session(db_file)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create chat without pre-authorization
        create_payload = {
            "scheme_id": "fallback-ssp-scst-001",
            "scenario_id": "scenario_a_success",
            "preferred_days": ["monday"],
            "preferred_windows": [{"start": "10:00", "end": "13:00"}],
            "pre_authorized_confirmation": False,
        }
        res = await client.post(f"/api/sessions/{session_id}/office-chats", json=create_payload)
        chat_id = res.json()["chat_id"]

        # Advance turns
        await client.post(f"/api/office-chats/{chat_id}/advance")
        res_adv2 = await client.post(f"/api/office-chats/{chat_id}/advance")
        data_adv2 = res_adv2.json()

        # Must pause in awaiting_user_input / awaiting_user_approval
        assert data_adv2["chat_status"] == "awaiting_user_input"
        assert data_adv2["appointment_status"] == "awaiting_user_approval"

        # User approves slot
        user_input_res = await client.post(
            f"/api/office-chats/{chat_id}/user-input",
            json={"action": "approve_slot", "user_approved_slot": True},
        )
        assert user_input_res.status_code == 200
        data_approved = user_input_res.json()
        assert data_approved["chat_status"] == "completed"
        assert data_approved["appointment_status"] == "simulated_confirmed"
        assert "BEGIN:VCALENDAR" in data_approved["appointment"]["calendar_ics"]


@pytest.mark.asyncio
async def test_scenario_b_no_availability_flow(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setenv("DB_PATH", db_file)
    session_id = await _seed_session(db_file)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/sessions/{session_id}/office-chats",
            json={"scheme_id": "fallback-ssp-scst-001", "scenario_id": "scenario_b_no_availability"},
        )
        chat_id = res.json()["chat_id"]

        res_adv = await client.post(f"/api/office-chats/{chat_id}/advance")
        data = res_adv.json()
        assert data["chat_status"] == "no_availability"
        assert data["appointment_status"] == "no_availability"
        assert data["appointment"] is None


@pytest.mark.asyncio
async def test_scenario_c_missing_info_and_whatsapp_handoff_flow(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setenv("DB_PATH", db_file)
    session_id = await _seed_session(db_file)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/sessions/{session_id}/office-chats",
            json={"scheme_id": "fallback-ssp-scst-001", "scenario_id": "scenario_c_missing_info"},
        )
        chat_id = res.json()["chat_id"]

        # Advance Turn 2 (representative asks for college admission reference)
        await client.post(f"/api/office-chats/{chat_id}/advance")

        # Advance Turn 4 (representative provides WhatsApp +919845012345)
        res_adv2 = await client.post(f"/api/office-chats/{chat_id}/advance")
        data = res_adv2.json()

        assert data["chat_status"] == "awaiting_user_input"
        assert len(data["unresolved_questions"]) >= 1
        uq = data["unresolved_questions"][-1]
        assert uq["receiver_whatsapp_number"] == "+919845012345"
        assert "https://wa.me/919845012345" in uq["click_to_chat_url"]

        # Test updating draft message
        q_id = uq["question_id"]
        res_draft = await client.post(
            f"/api/unresolved-questions/{q_id}/draft",
            json={"draft_message": "Custom citizen question about e-Attestation."},
        )
        assert res_draft.status_code == 200
        assert res_draft.json()["draft_message"] == "Custom citizen question about e-Attestation."
        assert "e-Attestation" in res_draft.json()["click_to_chat_url"]

        # Test mark-sent
        res_sent = await client.post(f"/api/unresolved-questions/{q_id}/mark-sent")
        assert res_sent.status_code == 200
        assert res_sent.json()["status"] == "user_marked_sent"


@pytest.mark.asyncio
async def test_scenario_d_unsupported_flow(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setenv("DB_PATH", db_file)
    session_id = await _seed_session(db_file)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/sessions/{session_id}/office-chats",
            json={"scheme_id": "fallback-ssp-scst-001", "scenario_id": "scenario_d_unclear_unsupported"},
        )
        chat_id = res.json()["chat_id"]

        res_adv = await client.post(f"/api/office-chats/{chat_id}/advance")
        data = res_adv.json()
        assert data["chat_status"] == "unable_to_resolve"
        assert data["appointment_status"] == "not_requested"


@pytest.mark.asyncio
async def test_calendar_download_endpoint(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setenv("DB_PATH", db_file)
    session_id = await _seed_session(db_file)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create and advance to confirmation
        res = await client.post(
            f"/api/sessions/{session_id}/office-chats",
            json={
                "scheme_id": "fallback-ssp-scst-001",
                "scenario_id": "scenario_a_success",
                "pre_authorized_confirmation": True,
            },
        )
        chat_id = res.json()["chat_id"]
        await client.post(f"/api/office-chats/{chat_id}/advance")
        await client.post(f"/api/office-chats/{chat_id}/advance")

        # Download calendar invite
        dl_res = await client.get(f"/api/office-chats/{chat_id}/calendar/download")
        assert dl_res.status_code == 200
        assert "text/calendar" in dl_res.headers["content-type"]
        assert f"simulated_appointment_{chat_id}.ics" in dl_res.headers["content-disposition"]
        assert "BEGIN:VCALENDAR" in dl_res.text
        assert "SIMULATION DEMO" in dl_res.text


@pytest.mark.asyncio
async def test_simulated_appointment_notification_trigger(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_api.db")
    monkeypatch.setenv("DB_PATH", db_file)
    session_id = await _seed_session(db_file)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Opt-in to email notifications
        await client.post(
            f"/api/sessions/{session_id}/notifications/preferences",
            json={"email": "citizen@example.com", "email_enabled": True},
        )

        # Create and advance chat to confirmation
        res = await client.post(
            f"/api/sessions/{session_id}/office-chats",
            json={
                "scheme_id": "fallback-ssp-scst-001",
                "scenario_id": "scenario_a_success",
                "pre_authorized_confirmation": True,
            },
        )
        chat_id = res.json()["chat_id"]
        await client.post(f"/api/office-chats/{chat_id}/advance")
        await client.post(f"/api/office-chats/{chat_id}/advance")

        # Check notifications list
        notifs_res = await client.get(f"/api/sessions/{session_id}/notifications")
        assert notifs_res.status_code == 200
        notifs = notifs_res.json()
        assert len(notifs) >= 1
        sim_notif = next(n for n in notifs if n["notification_type"] == "simulated_appointment_confirmed")
        assert sim_notif["recipient"] == "citizen@example.com"
        assert "[SIMULATED DEMO]" in sim_notif["subject"]


@pytest.mark.asyncio
async def test_office_chat_simulator_ui_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/office-chat-sim")
        assert r1.status_code == 200
        assert "text/html" in r1.headers["content-type"]
        assert "Unlocked — Office Communication Simulator" in r1.text
        assert "WhatsApp-Style Demo" in r1.text

        r2 = await client.get("/api/office-chats/simulator")
        assert r2.status_code == 200
        assert "text/html" in r2.headers["content-type"]


