"""
tests/test_api_actions.py — Integration tests for Phase 8 Agent 4 REST Endpoints.

Tests email drafting, RFC 5545 iCalendar generation & download, decoupled application
progress tracking with SQLite persistence, rejection assistance, and standalone endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.database import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_actions.db")
    monkeypatch.setenv("DB_PATH", test_db)
    monkeypatch.setattr("api.database.DEFAULT_DB_PATH", test_db)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def active_session(client):
    """Create a session and execute discovery with fallback schemes."""
    resp = client.post(
        "/api/sessions",
        json={
            "context": {
                "name": "Ramesh Kumar",
                "occupation": "farmer",
                "state": "Karnataka",
                "district": "Mandya",
                "annual_income": 120000,
            },
            "scope": "guided",
            "preferred_language": "en",
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    # Run discovery using offline fallback collection
    disc_resp = client.post(
        f"/api/sessions/{session_id}/discover",
        json={"search_scope": "fallback", "enable_fallback": True},
    )
    assert disc_resp.status_code == 200
    schemes = disc_resp.json()["schemes"]
    assert len(schemes) > 0
    scheme_id = schemes[0]["id"]
    return session_id, scheme_id, schemes[0]


def test_session_email_draft_action(client, active_session):
    session_id, scheme_id, scheme = active_session

    resp = client.post(
        f"/api/sessions/{session_id}/actions/email",
        json={
            "scheme_id": scheme_id,
            "purpose": "clarification",
            "question": "Does my family income certificate from Nadakacheri count for this scheme?",
            "attributes": ["annual_family_income"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_type"] == "email_draft"
    assert data["status"] == "ready"
    assert scheme["name"] in data["title"]
    assert "Nadakacheri" in data["body_content"]
    assert data["user_review_confirmed"] is False
    # PII user context automatically seeded
    assert "Ramesh Kumar" in data["body_content"]
    assert "Mandya" in data["body_content"]


def test_session_calendar_action_and_download(client, active_session):
    session_id, scheme_id, scheme = active_session

    # 1. Generate calendar action
    resp = client.post(
        f"/api/sessions/{session_id}/actions/calendar",
        json={
            "scheme_id": scheme_id,
            "kind": "appointment",
            "event_date": "2026-11-20",
            "date_confirmed_by_user": True,
            "start_time": "10:30:00",
            "location": "Taluk Office, Mandya",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_type"] == "calendar_ics"
    assert data["status"] == "ready"
    assert "BEGIN:VCALENDAR" in data["body_content"]
    assert "Mandya" in data["body_content"]
    assert data["filename"].endswith(".ics")

    # 2. Download endpoint
    dl_resp = client.get(
        f"/api/sessions/{session_id}/actions/calendar/{scheme_id}/download?kind=deadline",
    )
    # If fallback scheme has deadline with source url it is ready, otherwise status checked
    if dl_resp.status_code == 200:
        assert dl_resp.headers["content-type"].startswith("text/calendar")
        assert "BEGIN:VCALENDAR" in dl_resp.text
    else:
        assert dl_resp.status_code == 400
        assert "missing fields" in dl_resp.json()["detail"]


def test_session_progress_tracking_lifecycle(client, active_session):
    session_id, scheme_id, _ = active_session

    # Step 1: User reports submitted
    p1 = client.post(
        f"/api/sessions/{session_id}/progress",
        json={
            "scheme_id": scheme_id,
            "updates": [{"field": "submitted", "state": "yes"}],
        },
    )
    assert p1.status_code == 200
    d1 = p1.json()
    assert d1["progress"]["submitted"]["state"] == "yes"
    assert "submitted the application" in d1["summary"]
    # Follow up for decision
    assert any(fu["field"] == "decision" for fu in d1["follow_ups"])

    # Step 2: User reports approved, but benefit not received
    p2 = client.post(
        f"/api/sessions/{session_id}/progress",
        json={
            "scheme_id": scheme_id,
            "updates": [
                {"field": "decision", "state": "approved"},
                {"field": "benefit_received", "state": "no"},
            ],
        },
    )
    assert p2.status_code == 200
    d2 = p2.json()
    assert d2["progress"]["decision"]["state"] == "approved"
    assert d2["progress"]["benefit_received"]["state"] == "no"
    assert "Approved, but you haven't received the benefit yet" in d2["summary"]

    # Step 3: Verify persistence via GET /api/sessions/{session_id}/progress/{scheme_id}
    get_resp = client.get(f"/api/sessions/{session_id}/progress/{scheme_id}")
    assert get_resp.status_code == 200
    d_get = get_resp.json()
    assert d_get["progress"]["submitted"]["state"] == "yes"
    assert d_get["progress"]["decision"]["state"] == "approved"
    assert len(d_get["progress"]["history"]) == 3

    # Step 4: Verify full session restore includes progress
    sess_resp = client.get(f"/api/sessions/{session_id}")
    assert sess_resp.status_code == 200
    sess_data = sess_resp.json()
    assert scheme_id in sess_data["progress"]
    assert sess_data["progress"][scheme_id]["decision"]["state"] == "approved"


def test_session_rejection_analysis(client, active_session):
    session_id, scheme_id, scheme = active_session

    resp = client.post(
        f"/api/sessions/{session_id}/actions/rejection",
        json={
            "scheme_id": scheme_id,
            "notice_text": "Your application was rejected due to lack of land records in Mandya district.",
            "simulated": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheme_id"] == scheme_id
    assert "explanation" in data
    assert data["simulated"] is True


def test_standalone_action_endpoints(client):
    # Standalone Email
    resp = client.post(
        "/api/actions/email",
        json={
            "scheme": {
                "id": "standalone_scheme",
                "name": "PM Krishi Sinchayee Yojana",
                "contact_email": "helpdesk@pmksy.gov.in",
                "contact_email_source_url": "https://pmksy.gov.in",
            },
            "purpose": "document_query",
            "question": "Can I submit an RTC extract instead of Pahani?",
            "user_details": {"Name": "Suresh", "Application No": "KA-9912"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_destination"] == "helpdesk@pmksy.gov.in"
    assert "Suresh" in data["body_content"]
    assert "KA-9912" in data["body_content"]

    # Standalone Calendar
    cal_resp = client.post(
        "/api/actions/calendar",
        json={
            "scheme": {
                "id": "standalone_scheme",
                "name": "PM Krishi Sinchayee Yojana",
                "deadline": "2026-12-15",
                "deadline_source_url": "https://pmksy.gov.in/dates",
            },
            "kind": "deadline",
        },
    )
    assert cal_resp.status_code == 200
    cal_data = cal_resp.json()
    assert cal_data["status"] == "ready"
    assert "BEGIN:VCALENDAR" in cal_data["body_content"]

    # Standalone Progress
    prog_resp = client.post(
        "/api/progress",
        json={
            "scheme_id": "standalone_scheme",
            "updates": [{"field": "submitted", "state": "yes"}],
        },
    )
    assert prog_resp.status_code == 200
    prog_data = prog_resp.json()
    assert prog_data["progress"]["submitted"]["state"] == "yes"
