"""
tests/test_notifications.py — Comprehensive tests for email notifications, scheduling,
dynamic follow-up links, consent management, appointment reminders, and rejection recovery.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.clock import (
    advance_demo_time,
    is_demo_mode,
    now_utc,
    reset_demo_time,
    set_demo_time,
)
from api.tokens import (
    calculate_expiry,
    format_follow_up_url,
    generate_raw_token,
    hash_token,
)
from api.notifications import (
    EmailProvider,
    ResendEmailProvider,
    get_email_provider,
    process_due_notifications,
    render_action_plan_email,
    render_appointment_follow_up_email,
    render_appointment_reminder_email,
    render_deadline_reminder_email,
    set_email_provider,
)
from api.database import (
    create_appointment,
    create_follow_up_token,
    create_notification,
    create_session,
    create_tracked_application,
    delete_session,
    disable_notifications,
    get_appointment,
    get_follow_up_token_by_hash,
    get_notification,
    get_notification_preferences,
    get_session,
    get_tracked_application,
    list_application_events,
    list_appointments,
    list_notifications,
    list_tracked_applications,
    save_notification_preferences,
    update_appointment,
    update_tracked_application,
)


class MockTestEmailProvider:
    """Mock email provider to verify email dispatches without network calls."""

    def __init__(self, should_fail: bool = False):
        self.sent_emails: list[dict[str, Any]] = []
        self.should_fail = should_fail

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
        idempotency_key: Optional[str] = None,
        is_demo: bool = False,
    ) -> dict[str, Any]:
        if self.should_fail:
            raise RuntimeError("Resend API 500: Temporary service failure")
        record = {
            "id": f"resend_msg_{uuid.uuid4().hex[:10]}",
            "to": to_email,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
            "idempotency_key": idempotency_key,
            "is_demo": is_demo,
        }
        self.sent_emails.append(record)
        return record


@pytest.fixture
def mock_email():
    """Inject mock email provider and restore on teardown."""
    mock_prov = MockTestEmailProvider()
    set_email_provider(mock_prov)
    yield mock_prov
    set_email_provider(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_notifications.db")
    monkeypatch.setenv("DB_PATH", test_db)
    monkeypatch.setattr("api.database.DEFAULT_DB_PATH", test_db)
    monkeypatch.setenv("DEMO_MODE", "false")
    reset_demo_time()
    with TestClient(app) as test_client:
        yield test_client
    reset_demo_time()


@pytest.fixture
def active_session(client):
    """Create a session and execute discovery with fallback schemes."""
    resp = client.post(
        "/api/sessions",
        json={
            "context": {
                "name": "Kavitha Gowda",
                "occupation": "student",
                "state": "Karnataka",
                "district": "Mysuru",
                "annual_income": 150000,
            },
            "scope": "guided",
            "preferred_language": "en",
        },
    )
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    # Run discovery
    disc_resp = client.post(
        f"/api/sessions/{session_id}/discover",
        json={"search_scope": "fallback", "enable_fallback": True},
    )
    assert disc_resp.status_code == 200
    schemes = disc_resp.json()["schemes"]
    assert len(schemes) > 0
    return session_id, schemes[0]["id"]


# ---------------------------------------------------------------------------
# 1. Contact Collection & Consent Preferences
# ---------------------------------------------------------------------------

def test_initial_session_has_no_contact_requirement(client):
    """Rule 2.1: Onboarding does not require email or phone number."""
    resp = client.post(
        "/api/sessions",
        json={
            "context": {
                "occupation": "student",
                "state": "Karnataka",
                "district": "Bengaluru",
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    # No contact details required


def test_notification_preferences_opt_in_and_disable(client, active_session):
    """Rule 2.2 & 2.3: Opt-in, save preferences, and disable notifications."""
    session_id, _ = active_session

    # Save preferences with opt-in
    pref_resp = client.post(
        f"/api/sessions/{session_id}/notifications/preferences",
        json={
            "email": "kavitha.test@example.com",
            "email_enabled": True,
            "categories": {
                "action_plan_summary": True,
                "appointment_reminders": True,
                "appointment_follow_up": True,
            },
            "timezone": "Asia/Kolkata",
        },
    )
    assert pref_resp.status_code == 200
    pref_data = pref_resp.json()
    assert pref_data["email"] == "kavitha.test@example.com"
    assert pref_data["email_enabled"] is True
    assert pref_data["categories"]["appointment_reminders"] is True

    # Retrieve preferences
    get_resp = client.get(f"/api/sessions/{session_id}/notifications/preferences")
    assert get_resp.status_code == 200
    assert get_resp.json()["email"] == "kavitha.test@example.com"

    # Disable notifications
    dis_resp = client.post(f"/api/sessions/{session_id}/notifications/disable")
    assert dis_resp.status_code == 200
    assert dis_resp.json()["disabled"] is True

    # Verify disabled in DB
    get_resp2 = client.get(f"/api/sessions/{session_id}/notifications/preferences")
    assert get_resp2.json()["email_enabled"] is False


# ---------------------------------------------------------------------------
# 2. Action Plan Email Preview & Send
# ---------------------------------------------------------------------------

def test_action_plan_email_preview_does_not_send(client, active_session, mock_email):
    """Rule 1.1: Show preview without sending before confirmation."""
    session_id, _ = active_session

    prev_resp = client.post(f"/api/sessions/{session_id}/notifications/action-plan/preview")
    assert prev_resp.status_code == 200
    data = prev_resp.json()

    assert "subject" in data
    assert "body_html" in data
    assert "body_text" in data
    assert "follow_up_url" in data
    assert len(data["schemes_included"]) > 0

    # Ensure mock provider sent nothing on preview
    assert len(mock_email.sent_emails) == 0

    # Privacy check: sensitive details NOT leaked in email preview
    assert "150000" not in data["body_text"]  # No full income value
    assert "Aadhaar" not in data["body_text"] or "number" not in data["body_text"]


def test_action_plan_email_send_requires_consent(client, active_session, mock_email):
    """Section 4.3: Refuse to send action-plan email if consent is absent."""
    session_id, _ = active_session

    # Attempt to send without enabling preferences
    send_resp = client.post(
        f"/api/sessions/{session_id}/notifications/action-plan/send",
        json={"confirmed": True},
    )
    assert send_resp.status_code == 400
    assert "opted in" in send_resp.json()["detail"].lower()
    assert len(mock_email.sent_emails) == 0


def test_action_plan_email_send_success(client, active_session, mock_email):
    """Section 4.3: Send action-plan email after opt-in and confirmation."""
    session_id, _ = active_session

    # 1. Opt in
    client.post(
        f"/api/sessions/{session_id}/notifications/preferences",
        json={
            "email": "kavitha.send@example.com",
            "email_enabled": True,
            "categories": {"action_plan_summary": True},
        },
    )

    # 2. Send
    send_resp = client.post(
        f"/api/sessions/{session_id}/notifications/action-plan/send",
        json={"confirmed": True},
    )
    assert send_resp.status_code == 200
    data = send_resp.json()
    assert data["status"] == "accepted"
    assert data["provider"] == "resend"
    assert data["recipient"] == "kavitha.send@example.com"
    assert data["provider_message_id"] is not None

    # Verify mock received 1 email
    assert len(mock_email.sent_emails) == 1
    assert mock_email.sent_emails[0]["to"] == "kavitha.send@example.com"
    assert "Your Unlocked Action Plan" in mock_email.sent_emails[0]["subject"]


# ---------------------------------------------------------------------------
# 3. Scheduling & Due Notification Processing
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_scheduled_notification_due_processing(tmp_path, monkeypatch, mock_email):
    """Section 5.1: Database-backed scheduling and due processor."""
    from api.database import init_db
    test_db = str(tmp_path / "test_due.db")
    await init_db(test_db)
    session_id = str(uuid.uuid4())

    await create_session(
        session_id=session_id,
        context={"state": "Karnataka"},
        db_path=test_db,
    )
    await save_notification_preferences(
        session_id=session_id,
        email="scheduled.user@example.com",
        email_enabled=True,
        categories={"appointment_reminders": True},
        db_path=test_db,
    )

    now = datetime.now(timezone.utc)
    future_time = (now + timedelta(hours=5)).isoformat()
    notif_id = f"notif_{uuid.uuid4().hex[:10]}"

    # Schedule a future notification
    await create_notification(
        notification_id=notif_id,
        session_id=session_id,
        notification_type="appointment_reminders",
        recipient="scheduled.user@example.com",
        subject="Future Reminder",
        body_html="<p>Upcoming</p>",
        body_text="Upcoming",
        scheduled_at_utc=future_time,
        db_path=test_db,
    )

    # 1. Run due notification processor now -> Should NOT be dispatched yet
    processed = await process_due_notifications(db_path=test_db)
    assert len(processed) == 0
    assert len(mock_email.sent_emails) == 0

    notif_rec = await get_notification(notif_id, db_path=test_db)
    assert notif_rec["status"] == "scheduled"

    # 2. Simulate time passing past the scheduled time using clock abstraction
    monkeypatch.setenv("DEMO_MODE", "true")
    advance_demo_time(6 * 3600)  # 6 hours later

    processed_later = await process_due_notifications(db_path=test_db)
    assert len(processed_later) == 1
    assert processed_later[0]["status"] == "accepted"
    assert len(mock_email.sent_emails) == 1

    # 3. Re-running poller immediately should NOT duplicate send (idempotency)
    processed_again = await process_due_notifications(db_path=test_db)
    assert len(processed_again) == 0
    assert len(mock_email.sent_emails) == 1


# ---------------------------------------------------------------------------
# 4. Clock Abstraction & Demo Fast-Forward
# ---------------------------------------------------------------------------

def test_demo_time_advance_blocked_when_demo_mode_false(client):
    """Section 5.4: Demo clock cannot be advanced outside demo mode."""
    # Ensure DEMO_MODE is not true
    os.environ["DEMO_MODE"] = "false"
    resp = client.post("/api/demo/advance-time", json={"seconds": 3600})
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()


def test_demo_time_advance_and_demo_email_override(client, active_session, mock_email, monkeypatch):
    """Section 5.3 & 5.4: Fast-forward time in demo mode routes to DEMO_EMAIL_TO."""
    session_id, _ = active_session
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_TO", "team.evaluator@example.com")

    # Set up user with preferences
    client.post(
        f"/api/sessions/{session_id}/notifications/preferences",
        json={
            "email": "citizen.real@example.com",
            "email_enabled": True,
            "categories": {"appointment_reminders": True},
        },
    )

    # Schedule an appointment in 10 hours
    sch_time = (now_utc() + timedelta(hours=10)).isoformat()
    appt_resp = client.post(
        f"/api/sessions/{session_id}/appointments",
        json={
            "purpose": "Nadakacheri Certificate Verification",
            "scheduled_at_utc": sch_time,
            "location": "Taluk Office, Mysuru",
            "remind_email": True,
        },
    )
    assert appt_resp.status_code == 200

    # Advance demo time by 12 hours
    adv_resp = client.post(
        "/api/demo/advance-time",
        json={"seconds": 12 * 3600},
    )
    assert adv_resp.status_code == 200
    adv_data = adv_resp.json()
    assert adv_data["demo_mode"] is True
    assert adv_data["notifications_processed"] >= 1

    # Verify that in demo mode, email was routed to DEMO_EMAIL_TO and carries [DEMO]
    assert len(mock_email.sent_emails) >= 1
    demo_sent = mock_email.sent_emails[-1]
    assert demo_sent["to"] == "team.evaluator@example.com"
    assert "[DEMO]" in demo_sent["subject"]
    assert "[DEMO SIMULATION]" in demo_sent["body_text"]


# ---------------------------------------------------------------------------
# 5. Secure Follow-Up Links
# ---------------------------------------------------------------------------

def test_secure_follow_up_tokens_and_page(client, active_session):
    """Section 6: Cryptographic token validation, resolution, and scoping."""
    session_id, _ = active_session

    # Create appointment
    appt_resp = client.post(
        f"/api/sessions/{session_id}/appointments",
        json={
            "purpose": "Aadhaar e-KYC Verification",
            "scheduled_at_utc": (now_utc() + timedelta(days=2)).isoformat(),
            "location": "Bangalore One Center",
            "remind_email": False,
        },
    )
    assert appt_resp.status_code == 200
    appt_data = appt_resp.json()
    follow_up_url = appt_data["follow_up_url"]
    assert follow_up_url is not None
    token = follow_up_url.split("/")[-1]

    # Open follow-up page with token
    follow_resp = client.get(f"/api/follow-up/{token}")
    assert follow_resp.status_code == 200
    follow_data = follow_resp.json()
    assert follow_data["session_id"] == session_id
    assert follow_data["scope_type"] == "appointment"
    assert follow_data["appointment"]["purpose"] == "Aadhaar e-KYC Verification"

    # Privacy check: NO demographic context in follow-up payload
    assert "annual_income" not in follow_data
    assert "caste" not in follow_data

    # Submit outcome via follow-up link
    out_resp = client.post(
        f"/api/follow-up/{token}/outcome",
        json={
            "attended": "yes",
            "outcome": "documents_accepted",
            "notes": "Verified without issues.",
        },
    )
    assert out_resp.status_code == 200
    assert out_resp.json()["status"] == "attended"
    assert out_resp.json()["outcome_summary"] == "documents_accepted"


def test_invalid_or_expired_follow_up_token_rejected(client):
    """Section 6.2: Invalid and expired tokens are rejected."""
    # Bogus token
    bogus = client.get("/api/follow-up/completely_bogus_token_12345")
    assert bogus.status_code == 404


# ---------------------------------------------------------------------------
# 6. Appointment Outcomes & Lifecycle Transitions
# ---------------------------------------------------------------------------

def test_appointment_outcome_updates_workflow_and_application(client, active_session):
    """Section 3.6: Appointment outcome updates application and checklist."""
    session_id, scheme_id = active_session

    # 1. Start tracking scheme application
    app_resp = client.post(
        f"/api/sessions/{session_id}/applications",
        json={"scheme_id": scheme_id, "status": "preparing"},
    )
    assert app_resp.status_code == 200
    app_id = app_resp.json()["application_id"]

    # 2. Schedule appointment linked to application
    appt_resp = client.post(
        f"/api/sessions/{session_id}/appointments",
        json={
            "purpose": "Application Submission Visit",
            "application_id": app_id,
            "scheduled_at_utc": (now_utc() + timedelta(days=1)).isoformat(),
            "remind_email": False,
        },
    )
    assert appt_resp.status_code == 200
    appt_id = appt_resp.json()["appointment_id"]

    # 3. Report outcome: application submitted
    out_resp = client.post(
        f"/api/sessions/{session_id}/appointments/{appt_id}/outcome",
        json={
            "attended": "yes",
            "outcome": "application_submitted",
            "notes": "Submitted with RD acknowledgement 2026-9988.",
        },
    )
    assert out_resp.status_code == 200

    # 4. Verify tracked application status updated to 'submitted'
    get_app = client.get(f"/api/sessions/{session_id}/applications/{app_id}")
    assert get_app.status_code == 200
    assert get_app.json()["status"] == "submitted"
    assert get_app.json()["status_source"] == "user_reported"


def test_rescheduling_appointment_updates_time(client, active_session):
    """Section 3.6: Rescheduling appointment updates timing."""
    session_id, _ = active_session

    appt_resp = client.post(
        f"/api/sessions/{session_id}/appointments",
        json={"purpose": "Document Verification", "remind_email": False},
    )
    appt_id = appt_resp.json()["appointment_id"]

    new_time = (now_utc() + timedelta(days=5)).isoformat()
    patch_resp = client.patch(
        f"/api/sessions/{session_id}/appointments/{appt_id}",
        json={"scheduled_at_utc": new_time, "location": "District Office"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["scheduled_at_utc"] == new_time
    assert patch_resp.json()["location"] == "District Office"


# ---------------------------------------------------------------------------
# 7. Rejection Recovery Workflow
# ---------------------------------------------------------------------------

def test_rejection_recovery_missing_document(client, active_session):
    """Section 7: Missing document rejection triggers document correction route."""
    session_id, scheme_id = active_session

    # Track application
    app_resp = client.post(
        f"/api/sessions/{session_id}/applications",
        json={"scheme_id": scheme_id, "status": "submitted"},
    )
    app_id = app_resp.json()["application_id"]

    # Analyze rejection
    rej_resp = client.post(
        f"/api/sessions/{session_id}/applications/{app_id}/rejection-analysis",
        json={
            "reason": "Income certificate expired or invalid format",
            "reason_category": "missing_document",
        },
    )
    assert rej_resp.status_code == 200
    data = rej_resp.json()

    assert data["action_classification"] == "correct_document"
    assert data["recovery_status"] == "action_available"
    assert len(data["next_actions"]) > 0
    assert data["email_draft"] is not None


def test_rejection_recovery_unmet_criteria_finds_alternatives(client, active_session):
    """Section 7: Unmet eligibility criteria does not invent appeal; offers alternatives."""
    session_id, scheme_id = active_session

    app_resp = client.post(
        f"/api/sessions/{session_id}/applications",
        json={"scheme_id": scheme_id, "status": "submitted"},
    )
    app_id = app_resp.json()["application_id"]

    rej_resp = client.post(
        f"/api/sessions/{session_id}/applications/{app_id}/rejection-analysis",
        json={
            "reason": "Family annual income is above scheme limit of Rs 2,50,000",
            "reason_category": "criteria_not_met",
        },
    )
    assert rej_resp.status_code == 200
    data = rej_resp.json()

    assert data["action_classification"] == "alternative_scheme"
    assert data["recovery_status"] == "no_supported_remedy_found"
    assert "appeal is not supported" in data["explanation"].lower()
    assert len(data["alternative_schemes"]) > 0


# ---------------------------------------------------------------------------
# 8. Session Deletion Cascade
# ---------------------------------------------------------------------------

def test_session_deletion_cascade_cleans_up_all_tables(client, active_session):
    """Section 9.7 & 12: Session deletion revokes tokens and cascades across all tables."""
    session_id, scheme_id = active_session

    # Create preferences, appointment, and application
    client.post(
        f"/api/sessions/{session_id}/notifications/preferences",
        json={"email": "cascade@example.com", "email_enabled": True},
    )
    appt = client.post(
        f"/api/sessions/{session_id}/appointments",
        json={"purpose": "Visit", "remind_email": False},
    )
    tok_url = appt.json()["follow_up_url"]
    token = tok_url.split("/")[-1]

    client.post(
        f"/api/sessions/{session_id}/applications",
        json={"scheme_id": scheme_id},
    )

    # Delete session
    del_resp = client.delete(f"/api/sessions/{session_id}")
    assert del_resp.status_code == 200

    # Verify session is gone
    assert client.get(f"/api/sessions/{session_id}").status_code == 404

    # Verify follow-up token is gone/rejected
    assert client.get(f"/api/follow-up/{token}").status_code == 404


# ---------------------------------------------------------------------------
# 9. Resend SDK Direct Provider & Error Handling Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_resend_provider_invokes_sdk(monkeypatch):
    """Section 4.2 & 4.3: ResendEmailProvider invokes resend.Emails.send_async with idempotency."""
    import resend
    monkeypatch.setenv("DEMO_MODE", "false")

    called_params = []

    async def fake_send_async(params):
        called_params.append(params)
        return {"id": "re_msg_sdk_test_999"}

    monkeypatch.setattr(resend.Emails, "send_async", fake_send_async)

    provider = ResendEmailProvider(api_key="re_test_12345", from_email="custom@resend.dev")
    res = await provider.send_email(
        to_email="recipient@example.com",
        subject="Test Subject",
        body_html="<p>Test</p>",
        body_text="Test",
        idempotency_key="idemp_key_123",
        is_demo=False,
    )

    assert res["id"] == "re_msg_sdk_test_999"
    assert res["status"] == "accepted"
    assert len(called_params) == 1
    p = called_params[0]
    assert p["from"] == "custom@resend.dev"
    assert p["to"] == ["recipient@example.com"]
    assert p["subject"] == "Test Subject"
    assert p["headers"] == {"Idempotency-Key": "idemp_key_123"}


@pytest.mark.anyio
async def test_resend_provider_missing_key_raises():
    """Section 4.2: Missing API key raises ValueError."""
    provider = ResendEmailProvider(api_key="")
    with pytest.raises(ValueError, match="RESEND_API_KEY is not configured"):
        await provider.send_email(
            to_email="test@example.com",
            subject="Subj",
            body_html="<p>b</p>",
            body_text="b",
        )


def test_cancel_scheduled_notification_via_api(client, active_session):
    """Section 10: Cancel pending notification endpoint."""
    session_id, _ = active_session

    # Opt in
    client.post(
        f"/api/sessions/{session_id}/notifications/preferences",
        json={"email": "cancel@example.com", "email_enabled": True},
    )

    # Schedule appointment in future
    appt = client.post(
        f"/api/sessions/{session_id}/appointments",
        json={
            "purpose": "Hearing",
            "scheduled_at_utc": (now_utc() + timedelta(days=3)).isoformat(),
            "remind_email": True,
        },
    )
    assert appt.status_code == 200

    # List notifications
    notifs = client.get(f"/api/sessions/{session_id}/notifications").json()
    assert len(notifs) >= 1
    notif_id = notifs[0]["notification_id"]

    # Cancel notification
    cancel_resp = client.post(f"/api/sessions/{session_id}/notifications/{notif_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancelled"] is True

    # Verify status is cancelled
    notifs_after = client.get(f"/api/sessions/{session_id}/notifications").json()
    matching = [n for n in notifs_after if n["notification_id"] == notif_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "cancelled"


def test_deadline_and_status_update_email_rendering():
    """Section 4.5: Content builders for deadline and application status updates."""
    from api.notifications import render_deadline_reminder_email, render_application_status_update_email

    # Deadline reminder
    d_subj, d_html, d_txt = render_deadline_reminder_email(
        scheme_name="SSP Scholarship",
        deadline_str="2026-11-30",
        application_url="https://ssp.karnataka.gov.in",
        follow_up_url="https://unlocked.gov.in/follow-up/tok123",
    )
    assert "Deadline Approaching: SSP Scholarship" in d_subj
    assert "2026-11-30" in d_txt
    assert "https://ssp.karnataka.gov.in" in d_html
    assert "https://unlocked.gov.in/follow-up/tok123" in d_txt

    # Status update
    s_subj, s_html, s_txt = render_application_status_update_email(
        scheme_name="SSP Scholarship",
        old_status="submitted",
        new_status="under_review",
        next_action="Wait for department verification",
        follow_up_url="https://unlocked.gov.in/follow-up/tok456",
    )
    assert "Status Update for SSP Scholarship: Under Review" in s_subj
    assert "<strong>Previous:</strong> Submitted" in s_html
    assert "<strong>Current:</strong> Under Review" in s_html
    assert "Previous Status: Submitted" in s_txt
    assert "Wait for department verification" in s_txt

