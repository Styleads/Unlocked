"""
api/main.py — FastAPI Application for Project Unlocked.

Exposes REST endpoints for session management, scheme discovery, consolidated
questionnaire flows, reassessment, and document DAG action planning.
Consumed by Member 4 (Frontend).
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from api.database import (
    cancel_notification,
    cancel_pending_notifications_for_appointment,
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
    init_db,
    list_appointments,
    list_notifications,
    list_tracked_applications,
    record_application_event,
    save_notification_preferences,
    update_appointment,
    update_tracked_application,
)
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
    process_due_notifications,
    render_action_plan_email,
    render_application_status_update_email,
    render_appointment_follow_up_email,
    render_appointment_reminder_email,
    render_deadline_reminder_email,
)
from api.recovery import investigate_rejection
from api.orchestrator import (
    analyze_scheme_rejection,
    generate_action_plan,
    generate_calendar_action,
    generate_email_action,
    get_application_progress,
    get_session_questions,
    get_session_scheme,
    get_session_schemes,
    process_answers,
    record_application_progress,
    run_discovery,
    update_checklist_status,
)
from api.schemas import (
    ActionArtifact,
    ActionPlan,
    ActionPlanEmailPreview,
    ActionPlanEmailSendRequest,
    ActionPlanEmailSendResponse,
    AdvanceTimeRequest,
    AdvanceTimeResponse,
    AppointmentOutcomeRequest,
    AppointmentView,
    CreateAppointmentRequest,
    CreateSessionRequest,
    DeleteSessionResponse,
    DiscoverOptions,
    DiscoveryResult,
    EventKind,
    FollowUpOutcomeRequest,
    FollowUpPageView,
    FullSessionState,
    HealthResponse,
    NotificationPreferencesInput,
    NotificationPreferencesView,
    NotificationView,
    ProgressResult,
    Question,
    ReassessmentResult,
    RejectionAnalysis,
    RejectionInvestigationRequest,
    RejectionRecoveryView,
    SchemeView,
    SessionCalendarActionRequest,
    SessionEmailActionRequest,
    SessionProgressRequest,
    SessionRejectionActionRequest,
    SessionResponse,
    StandaloneCalendarRequest,
    StandaloneEmailRequest,
    StandaloneProgressRequest,
    StandaloneRejectionRequest,
    SubmitAnswersRequest,
    TrackedApplicationCreateRequest,
    TrackedApplicationOutcomeRequest,
    TrackedApplicationView,
    UpdateAppointmentRequest,
    UpdateDocStatusRequest,
    UserProfileInput,
)
from agent4 import (
    analyse_rejection,
    build_calendar_artifact,
    build_email_draft,
    update_progress,
)
from api.orchestrator import _normalizer_llm

# Load environment configuration
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("unlocked.api")


# ---------------------------------------------------------------------------
# Lifespan & Application Setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables and WAL mode on application startup."""
    await init_db()
    logger.info("Database initialized in WAL mode. Service is operationally ready.")
    yield
    logger.info("Service shutting down.")


app = FastAPI(
    title="Project Unlocked API",
    description="Universal Government Benefits Discovery & Planning Assistant for Karnataka citizens.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for local development and frontend clients
raw_origins = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()] or [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Operational & Health Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Operational"])
@app.get("/api/health", response_model=HealthResponse, tags=["Operational"])
async def get_health():
    """Service health check and API credentials verification without leaking secrets."""
    gemini_ok = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    tavily_ok = bool(os.getenv("TAVILY_API_KEY"))

    return HealthResponse(
        status="healthy",
        application="Project Unlocked — Government Benefits Assistant",
        version="1.0.0",
        operational=True,
        services={
            "gemini_configured": gemini_ok,
            "tavily_configured": tavily_ok,
            "sqlite_connected": True,
        },
    )


# ---------------------------------------------------------------------------
# Session Management Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sessions"],
)
async def api_create_session(payload: CreateSessionRequest):
    """
    Initialize a new session, persist user demographic context, and seed initial
    answers so known profile attributes are never re-asked.
    """
    session_id = str(uuid.uuid4())
    try:
        session = await create_session(
            session_id=session_id,
            context=payload.context,
            scope=payload.scope,
            preferred_language=payload.preferred_language,
        )
        return SessionResponse(
            session_id=session.session_id,
            status="initialized",
            scope=session.scope,
            preferred_language=session.preferred_language,
            created_at=session.created_at,
        )
    except Exception as exc:
        logger.error("Failed to create session: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize session: {exc}",
        )


@app.get(
    "/api/sessions/{session_id}",
    response_model=FullSessionState,
    tags=["Sessions"],
)
async def api_get_session(session_id: str = PathParam(..., description="UUID of session")):
    """Restore and return complete durable session state from SQLite."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session.to_state_dict()


@app.delete(
    "/api/sessions/{session_id}",
    response_model=DeleteSessionResponse,
    tags=["Sessions"],
)
async def api_delete_session(session_id: str = PathParam(..., description="UUID of session")):
    """Reset / delete session and all associated citizen profile data."""
    deleted = await delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return DeleteSessionResponse(deleted=True, session_id=session_id)


# ---------------------------------------------------------------------------
# Discovery Pipeline Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/sessions/{session_id}/discover",
    response_model=DiscoveryResult,
    tags=["Discovery"],
)
async def api_run_discovery(
    session_id: str = PathParam(..., description="UUID of session"),
    options: Optional[DiscoverOptions] = None,
):
    """
    Execute discovery: M1 Search/Fallback -> M1 Kannada Translation -> Adapter ->
    M2 Normalization -> M2 Preliminary Assessment -> Consolidated Questions -> SQLite.
    """
    opts = options or DiscoverOptions()
    try:
        result = await run_discovery(
            session_id=session_id,
            search_scope=opts.search_scope,
            preferred_language=opts.preferred_language,
            enable_fallback=opts.enable_fallback,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Discovery execution failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery pipeline failed: {exc}",
        )


@app.get(
    "/api/sessions/{session_id}/schemes",
    response_model=list[SchemeView],
    tags=["Schemes"],
)
async def api_get_schemes(session_id: str = PathParam(..., description="UUID of session")):
    """Retrieve candidate schemes with current assessment overlays for a session."""
    try:
        return await get_session_schemes(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get(
    "/api/sessions/{session_id}/schemes/{scheme_id}",
    response_model=SchemeView,
    tags=["Schemes"],
)
async def api_get_scheme(
    session_id: str = PathParam(..., description="UUID of session"),
    scheme_id: str = PathParam(..., description="Slug ID of scheme"),
):
    """Retrieve full details, official sources, and assessment breakdown for a single scheme."""
    try:
        scheme = await get_session_scheme(session_id, scheme_id)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme '{scheme_id}' not found in session '{session_id}'.",
            )
        return scheme
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Phase 4: Consolidated Questions & Reassessment Flow Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/api/sessions/{session_id}/questions",
    response_model=list[Question],
    tags=["Questions & Answers"],
)
async def api_get_questions(session_id: str = PathParam(..., description="UUID of session")):
    """
    Retrieve active consolidated cross-scheme questions. Known context attributes
    and previously answered/skipped questions are excluded.
    """
    try:
        return await get_session_questions(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.post(
    "/api/sessions/{session_id}/answers",
    response_model=ReassessmentResult,
    tags=["Questions & Answers"],
)
async def api_submit_answers(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: SubmitAnswersRequest = ...,
):
    """
    Submit answers, skips, or 'not sure' selections. Triggers deterministic
    reassessment across all schemes without coercing unknowns into negative results.
    """
    try:
        result = await process_answers(
            session_id=session_id,
            submitted_answers=payload.answers,
        )
        return result
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Answer submission failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process answers: {exc}",
        )


# ---------------------------------------------------------------------------
# Phase 5: Document Action Plan DAG & Checklist Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/api/sessions/{session_id}/plan",
    response_model=ActionPlan,
    tags=["Action Plan"],
)
async def api_get_plan(session_id: str = PathParam(..., description="UUID of session")):
    """Compute and return the deterministic topological document procurement action plan."""
    try:
        return await generate_action_plan(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Plan generation failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate action plan: {exc}",
        )


@app.post(
    "/api/sessions/{session_id}/checklist/{doc_id}",
    response_model=ActionPlan,
    tags=["Action Plan"],
)
async def api_update_checklist_item(
    session_id: str = PathParam(..., description="UUID of session"),
    doc_id: str = PathParam(..., description="Canonical document ID (e.g. doc_income_certificate)"),
    payload: UpdateDocStatusRequest = ...,
):
    """
    Update document procurement status (have/obtained/needed) and dynamically
    recompute remaining dependent checklist items.
    """
    try:
        updated_plan = await update_checklist_status(
            session_id=session_id,
            doc_id=doc_id,
            status=payload.status,
        )
        return updated_plan
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Checklist update failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update checklist item: {exc}",
        )


# ---------------------------------------------------------------------------
# Phase 8: Action & Follow-Through Endpoints (Agent 4)
# ---------------------------------------------------------------------------

@app.post(
    "/api/sessions/{session_id}/actions/email",
    response_model=ActionArtifact,
    tags=["Actions & Follow-Through"],
)
async def api_generate_email_action(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: SessionEmailActionRequest = ...,
):
    """
    Generate an inquiry, clarification, or document query email draft for a scheme.
    PII details (names, IDs) are safely tokenized before reaching the LLM and
    citations are grounded strictly in verified scheme facts.
    """
    try:
        return await generate_email_action(session_id=session_id, request=payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Email draft generation failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate email draft: {exc}",
        )


@app.post(
    "/api/sessions/{session_id}/actions/calendar",
    response_model=ActionArtifact,
    tags=["Actions & Follow-Through"],
)
async def api_generate_calendar_action(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: SessionCalendarActionRequest = ...,
):
    """
    Generate an RFC 5545 standard .ics calendar artifact for application deadlines
    or in-person appointments in Asia/Kolkata timezone.
    """
    try:
        return await generate_calendar_action(session_id=session_id, request=payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Calendar generation failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate calendar event: {exc}",
        )


@app.get(
    "/api/sessions/{session_id}/actions/calendar/{scheme_id}/download",
    tags=["Actions & Follow-Through"],
)
async def api_download_calendar_ics(
    session_id: str = PathParam(..., description="UUID of session"),
    scheme_id: str = PathParam(..., description="Scheme ID"),
    kind: EventKind = Query(EventKind.deadline, description="deadline or appointment"),
):
    """
    Download the generated RFC 5545 .ics file directly as an attachment.
    """
    try:
        req = SessionCalendarActionRequest(scheme_id=scheme_id, kind=kind)
        artifact = await generate_calendar_action(session_id=session_id, request=req)
        if artifact.status.value != "ready" or not artifact.body_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Calendar artifact not ready: missing fields: {artifact.missing_fields}",
            )
        filename = artifact.filename or f"{scheme_id}.ics"
        return Response(
            content=artifact.body_content,
            media_type="text/calendar",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.post(
    "/api/sessions/{session_id}/progress",
    response_model=ProgressResult,
    tags=["Actions & Follow-Through"],
)
async def api_record_progress(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: SessionProgressRequest = ...,
):
    """
    Record user-reported application lifecycle states (submitted, decision, benefit_received,
    appointment_attended) with decoupled state machine, follow-ups, and contradiction detection.
    """
    try:
        return await record_application_progress(
            session_id=session_id,
            scheme_id=payload.scheme_id,
            updates=payload.updates,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Progress recording failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record application progress: {exc}",
        )


@app.get(
    "/api/sessions/{session_id}/progress",
    tags=["Actions & Follow-Through"],
)
async def api_get_all_progress(
    session_id: str = PathParam(..., description="UUID of session"),
):
    """Retrieve progress tracking state for all schemes in the current session."""
    try:
        return await get_application_progress(session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get(
    "/api/sessions/{session_id}/progress/{scheme_id}",
    response_model=ProgressResult,
    tags=["Actions & Follow-Through"],
)
async def api_get_scheme_progress(
    session_id: str = PathParam(..., description="UUID of session"),
    scheme_id: str = PathParam(..., description="Scheme ID"),
):
    """Retrieve progress tracking summary, follow-up questions, and warnings for a scheme."""
    try:
        return await get_application_progress(session_id=session_id, scheme_id=scheme_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.post(
    "/api/sessions/{session_id}/actions/rejection",
    response_model=RejectionAnalysis,
    tags=["Actions & Follow-Through"],
)
async def api_analyze_rejection(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: SessionRejectionActionRequest = ...,
):
    """
    Analyze an official rejection notice text, automatically redact private identifiers,
    extract verbatim rejection reasons, and recommend officially supported next steps.
    """
    try:
        return await analyze_scheme_rejection(session_id=session_id, request=payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Rejection analysis failed for session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze rejection notice: {exc}",
        )


# ---------------------------------------------------------------------------
# Standalone Action Endpoints (Unscoped, matching agent4/README.md)
# ---------------------------------------------------------------------------

@app.post(
    "/api/actions/email",
    response_model=ActionArtifact,
    tags=["Actions & Follow-Through"],
)
async def api_standalone_email(payload: StandaloneEmailRequest):
    """Generate email draft without requiring an existing session."""
    llm = _normalizer_llm()  # None without a key: Agent 4 uses its template
    return build_email_draft(payload.model_dump(), llm=llm)


@app.post(
    "/api/actions/calendar",
    response_model=ActionArtifact,
    tags=["Actions & Follow-Through"],
)
async def api_standalone_calendar(payload: StandaloneCalendarRequest):
    """Generate calendar .ics event without requiring an existing session."""
    return build_calendar_artifact(payload.model_dump())


@app.post(
    "/api/actions/rejection",
    response_model=RejectionAnalysis,
    tags=["Actions & Follow-Through"],
)
async def api_standalone_rejection(payload: StandaloneRejectionRequest):
    """Analyze rejection notice without requiring an existing session."""
    llm = _normalizer_llm()  # None without a key: Agent 4 uses its template
    return analyse_rejection(
        payload.scheme,
        payload.notice_text,
        guidance=payload.guidance_passages,
        llm=llm,
        simulated=payload.simulated,
    )


@app.post(
    "/api/progress",
    response_model=ProgressResult,
    tags=["Actions & Follow-Through"],
)
async def api_standalone_progress(payload: StandaloneProgressRequest):
    """Update progress state without requiring an existing session."""
    return update_progress(
        payload.current_progress,
        payload.scheme_id,
        payload.updates,
    )


# ---------------------------------------------------------------------------
# Phase 9: Notification Preferences & Action Plan Emails
# ---------------------------------------------------------------------------

@app.post(
    "/api/sessions/{session_id}/notifications/preferences",
    response_model=NotificationPreferencesView,
    tags=["Notifications & Email"],
)
async def api_save_notification_preferences(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: NotificationPreferencesInput = ...,
):
    """Save email follow-through opt-in, email address, time zone, and category choices."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    res = await save_notification_preferences(
        session_id=session_id,
        email=payload.email,
        email_enabled=payload.email_enabled,
        categories=payload.categories,
        consent_version=payload.consent_version,
        timezone_str=payload.timezone,
    )
    return NotificationPreferencesView(
        session_id=session_id,
        email=res.get("email"),
        email_enabled=bool(res.get("email_enabled", False)),
        categories=res.get("categories") or {},
        consent_version=res.get("consent_version") or "v1",
        consent_at=res.get("consent_at"),
        disabled_at=res.get("disabled_at"),
        timezone=res.get("timezone") or "Asia/Kolkata",
    )


@app.get(
    "/api/sessions/{session_id}/notifications/preferences",
    response_model=NotificationPreferencesView,
    tags=["Notifications & Email"],
)
async def api_get_notification_preferences(
    session_id: str = PathParam(..., description="UUID of session"),
):
    """Retrieve saved email follow-through notification preferences for a session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    res = await get_notification_preferences(session_id)
    if not res:
        return NotificationPreferencesView(session_id=session_id)
    return NotificationPreferencesView(
        session_id=session_id,
        email=res.get("email"),
        email_enabled=bool(res.get("email_enabled", False)),
        categories=res.get("categories") or {},
        consent_version=res.get("consent_version") or "v1",
        consent_at=res.get("consent_at"),
        disabled_at=res.get("disabled_at"),
        timezone=res.get("timezone") or "Asia/Kolkata",
    )


@app.post(
    "/api/sessions/{session_id}/notifications/action-plan/preview",
    response_model=ActionPlanEmailPreview,
    tags=["Notifications & Email"],
)
async def api_preview_action_plan_email(
    session_id: str = PathParam(..., description="UUID of session"),
):
    """
    Generate preview of the initial action plan email with verified scheme summaries,
    immediate tasks, and secure link without sending anything.
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    plan = session.plan
    if not plan:
        plan = await generate_action_plan(session_id)

    prefs = await get_notification_preferences(session_id)
    to_email = (prefs and prefs.get("email")) or "citizen@example.com"

    # Create scoped follow-up token for link
    raw_token = generate_raw_token()
    tok_hash = hash_token(raw_token)
    exp = calculate_expiry().isoformat()
    await create_follow_up_token(
        token_id=str(uuid.uuid4()),
        session_id=session_id,
        token_hash=tok_hash,
        expires_at_utc=exp,
    )
    follow_up_url = format_follow_up_url(raw_token)

    schemes_data = [s.model_dump(mode="json") for s in session.normalized_schemes]
    checklist_data = [c.model_dump(mode="json") for c in (plan.checklist if plan else [])]
    subject, html_body, text_body = render_action_plan_email(schemes_data, checklist_data, follow_up_url=follow_up_url)

    return ActionPlanEmailPreview(
        to_email=to_email,
        subject=subject,
        body_html=html_body,
        body_text=text_body,
        schemes_included=[s.get("name", "") for s in schemes_data[:5]],
        checklist_tasks=[c.get("name", "") for c in checklist_data[:5]],
        follow_up_url=follow_up_url,
    )


@app.post(
    "/api/sessions/{session_id}/notifications/action-plan/send",
    response_model=ActionPlanEmailSendResponse,
    tags=["Notifications & Email"],
)
async def api_send_action_plan_email(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: ActionPlanEmailSendRequest = ...,
):
    """
    Explicitly confirm and send the action plan summary email through Resend.
    Enforces consent opt-in check.
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    prefs = await get_notification_preferences(session_id)
    if not prefs or not prefs.get("email_enabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send: user has not opted in to email notifications.",
        )

    to_email = (payload.to_email or prefs.get("email") or "").strip()
    if not to_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email address on file. Please save notification preferences first.",
        )

    plan = session.plan
    if not plan:
        plan = await generate_action_plan(session_id)

    raw_token = generate_raw_token()
    tok_hash = hash_token(raw_token)
    exp = calculate_expiry().isoformat()
    await create_follow_up_token(
        token_id=str(uuid.uuid4()),
        session_id=session_id,
        token_hash=tok_hash,
        expires_at_utc=exp,
    )
    follow_up_url = format_follow_up_url(raw_token)

    schemes_data = [s.model_dump(mode="json") for s in session.normalized_schemes]
    checklist_data = [c.model_dump(mode="json") for c in (plan.checklist if plan else [])]
    subject, html_body, text_body = render_action_plan_email(schemes_data, checklist_data, follow_up_url=follow_up_url)

    notif_id = f"notif_{uuid.uuid4().hex[:12]}"
    idempotency_key = f"plan_{session_id}_{uuid.uuid4().hex[:8]}"

    await create_notification(
        notification_id=notif_id,
        session_id=session_id,
        notification_type="action_plan_summary",
        recipient=to_email,
        subject=subject,
        body_html=html_body,
        body_text=text_body,
        scheduled_at_utc=now_utc().isoformat(),
        idempotency_key=idempotency_key,
        is_demo=is_demo_mode(),
        status="scheduled",
    )

    # Process immediately
    await process_due_notifications()
    updated = await get_notification(notif_id)

    return ActionPlanEmailSendResponse(
        notification_id=notif_id,
        status=updated.get("status", "scheduled") if updated else "scheduled",
        provider=updated.get("provider", "resend") if updated else "resend",
        provider_message_id=updated.get("provider_message_id") if updated else None,
        recipient=to_email,
        sent_at=updated.get("sent_at_utc") if updated else None,
    )


@app.get(
    "/api/sessions/{session_id}/notifications",
    response_model=list[NotificationView],
    tags=["Notifications & Email"],
)
async def api_list_notifications(
    session_id: str = PathParam(..., description="UUID of session"),
):
    """List recent and scheduled notifications for a session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    rows = await list_notifications(session_id)
    return [
        NotificationView(
            notification_id=r["notification_id"],
            session_id=r["session_id"],
            notification_type=r["notification_type"],
            channel=r.get("channel", "email"),
            recipient=r["recipient"],
            subject=r["subject"],
            scheduled_at_utc=r.get("scheduled_at_utc"),
            status=r.get("status", "scheduled"),
            provider=r.get("provider", "resend"),
            provider_message_id=r.get("provider_message_id"),
            sent_at_utc=r.get("sent_at_utc"),
            delivered_at_utc=r.get("delivered_at_utc"),
            last_error=r.get("last_error"),
            is_demo=bool(r.get("is_demo", 0)),
            created_at=r.get("created_at", ""),
        )
        for r in rows
    ]


@app.post(
    "/api/sessions/{session_id}/notifications/{notification_id}/cancel",
    tags=["Notifications & Email"],
)
async def api_cancel_notification(
    session_id: str = PathParam(..., description="UUID of session"),
    notification_id: str = PathParam(..., description="ID of notification"),
):
    """Cancel a pending/scheduled notification."""
    notif = await get_notification(notification_id)
    if not notif or notif.get("session_id") != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    cancelled = await cancel_notification(notification_id)
    return {"cancelled": cancelled, "notification_id": notification_id}


@app.post(
    "/api/sessions/{session_id}/notifications/disable",
    tags=["Notifications & Email"],
)
async def api_disable_notifications(
    session_id: str = PathParam(..., description="UUID of session"),
):
    """Disable all future notifications and cancel all pending reminder jobs."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    await disable_notifications(session_id)
    return {"disabled": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# Phase 9: Appointments & Follow-up Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/sessions/{session_id}/appointments",
    response_model=AppointmentView,
    tags=["Appointments"],
)
async def api_create_appointment(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: CreateAppointmentRequest = ...,
):
    """Create an appointment and schedule pre/post reminders if opted in."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    appt_id = str(uuid.uuid4())
    follow_up_time = None
    if payload.scheduled_at_utc:
        try:
            sch_dt = datetime.fromisoformat(payload.scheduled_at_utc.replace("Z", "+00:00"))
            follow_up_time = (sch_dt + timedelta(hours=2)).isoformat()
        except Exception:
            pass

    appt = await create_appointment(
        appointment_id=appt_id,
        session_id=session_id,
        purpose=payload.purpose,
        scheduled_at_utc=payload.scheduled_at_utc,
        timezone_str=payload.timezone,
        location=payload.location,
        application_id=payload.application_id,
        related_task_id=payload.related_task_id,
        status="scheduled",
        status_source="user_reported",
        follow_up_at_utc=follow_up_time,
    )

    # Generate follow-up token
    raw_token = generate_raw_token()
    tok_hash = hash_token(raw_token)
    exp = calculate_expiry().isoformat()
    await create_follow_up_token(
        token_id=str(uuid.uuid4()),
        session_id=session_id,
        appointment_id=appt_id,
        application_id=payload.application_id,
        token_hash=tok_hash,
        expires_at_utc=exp,
    )
    follow_up_url = format_follow_up_url(raw_token)

    # Schedule reminder emails if opted in and reminder requested
    if payload.remind_email and payload.scheduled_at_utc:
        prefs = await get_notification_preferences(session_id)
        if prefs and prefs.get("email_enabled") and prefs.get("email"):
            email_addr = prefs["email"]
            try:
                sch_dt = datetime.fromisoformat(payload.scheduled_at_utc.replace("Z", "+00:00"))
                curr_now = now_utc()
                # 24 hours before, or sooner if appointment is in less than 24 hours
                remind_dt = max(curr_now, sch_dt - timedelta(hours=24))
                if sch_dt > curr_now:
                    subj, html_b, txt_b = render_appointment_reminder_email(
                        purpose=payload.purpose,
                        scheduled_at_str=payload.scheduled_at_utc,
                        location=payload.location,
                        follow_up_url=follow_up_url,
                    )
                    await create_notification(
                        notification_id=f"notif_{uuid.uuid4().hex[:12]}",
                        session_id=session_id,
                        appointment_id=appt_id,
                        application_id=payload.application_id,
                        notification_type="appointment_reminders",
                        recipient=email_addr,
                        subject=subj,
                        body_html=html_b,
                        body_text=txt_b,
                        scheduled_at_utc=remind_dt.isoformat(),
                        idempotency_key=f"remind_{appt_id}_{uuid.uuid4().hex[:8]}",
                        is_demo=is_demo_mode(),
                    )

                # Post-appointment follow-up email 2 hours after scheduled time
                post_dt = sch_dt + timedelta(hours=2)
                p_subj, p_html, p_txt = render_appointment_follow_up_email(
                    purpose=payload.purpose,
                    follow_up_url=follow_up_url,
                )
                await create_notification(
                    notification_id=f"notif_{uuid.uuid4().hex[:12]}",
                    session_id=session_id,
                    appointment_id=appt_id,
                    application_id=payload.application_id,
                    notification_type="appointment_follow_up",
                    recipient=email_addr,
                    subject=p_subj,
                    body_html=p_html,
                    body_text=p_txt,
                    scheduled_at_utc=post_dt.isoformat(),
                    idempotency_key=f"fu_{appt_id}_{uuid.uuid4().hex[:8]}",
                    is_demo=is_demo_mode(),
                )
            except Exception as exc:
                logger.warning("Failed to schedule appointment reminders: %s", exc)

    # Record event
    await record_application_event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        appointment_id=appt_id,
        application_id=payload.application_id,
        event_type="appointment_scheduled",
        new_status="scheduled",
        source="user_reported",
        details={"purpose": payload.purpose, "scheduled_at": payload.scheduled_at_utc},
    )

    return AppointmentView(
        appointment_id=appt["appointment_id"],
        session_id=session_id,
        application_id=appt.get("application_id"),
        related_task_id=appt.get("related_task_id"),
        purpose=appt["purpose"],
        scheduled_at_utc=appt.get("scheduled_at_utc"),
        timezone=appt.get("timezone", "Asia/Kolkata"),
        location=appt.get("location"),
        status=appt.get("status", "scheduled"),
        outcome_summary=appt.get("outcome_summary"),
        outcome_details=appt.get("outcome_details"),
        status_source=appt.get("status_source", "user_reported"),
        follow_up_url=follow_up_url,
        created_at=appt.get("created_at", ""),
    )


@app.get(
    "/api/sessions/{session_id}/appointments",
    response_model=list[AppointmentView],
    tags=["Appointments"],
)
async def api_list_appointments(
    session_id: str = PathParam(..., description="UUID of session"),
):
    """List appointments recorded for this session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    rows = await list_appointments(session_id)
    return [
        AppointmentView(
            appointment_id=r["appointment_id"],
            session_id=r["session_id"],
            application_id=r.get("application_id"),
            related_task_id=r.get("related_task_id"),
            purpose=r["purpose"],
            scheduled_at_utc=r.get("scheduled_at_utc"),
            timezone=r.get("timezone", "Asia/Kolkata"),
            location=r.get("location"),
            status=r.get("status", "scheduled"),
            outcome_summary=r.get("outcome_summary"),
            outcome_details=r.get("outcome_details"),
            status_source=r.get("status_source", "user_reported"),
            created_at=r.get("created_at", ""),
        )
        for r in rows
    ]


@app.patch(
    "/api/sessions/{session_id}/appointments/{appointment_id}",
    response_model=AppointmentView,
    tags=["Appointments"],
)
async def api_update_appointment(
    session_id: str = PathParam(..., description="UUID of session"),
    appointment_id: str = PathParam(..., description="UUID of appointment"),
    payload: UpdateAppointmentRequest = ...,
):
    """Reschedule or update appointment; cancels obsolete reminders and re-schedules if needed."""
    appt = await get_appointment(appointment_id)
    if not appt or appt.get("session_id") != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    follow_up_time = None
    if payload.scheduled_at_utc:
        # Cancel old pending reminders
        await cancel_pending_notifications_for_appointment(appointment_id)
        try:
            sch_dt = datetime.fromisoformat(payload.scheduled_at_utc.replace("Z", "+00:00"))
            follow_up_time = (sch_dt + timedelta(hours=2)).isoformat()
        except Exception:
            pass

    updated = await update_appointment(
        appointment_id=appointment_id,
        scheduled_at_utc=payload.scheduled_at_utc,
        location=payload.location,
        status=payload.status,
        follow_up_at_utc=follow_up_time,
    )

    await record_application_event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        appointment_id=appointment_id,
        application_id=appt.get("application_id"),
        event_type="appointment_rescheduled" if payload.scheduled_at_utc else "appointment_updated",
        details=payload.model_dump(exclude_unset=True),
    )

    return AppointmentView(
        appointment_id=updated["appointment_id"],
        session_id=session_id,
        application_id=updated.get("application_id"),
        related_task_id=updated.get("related_task_id"),
        purpose=updated["purpose"],
        scheduled_at_utc=updated.get("scheduled_at_utc"),
        timezone=updated.get("timezone", "Asia/Kolkata"),
        location=updated.get("location"),
        status=updated.get("status", "scheduled"),
        outcome_summary=updated.get("outcome_summary"),
        outcome_details=updated.get("outcome_details"),
        status_source=updated.get("status_source", "user_reported"),
        created_at=updated.get("created_at", ""),
    )


@app.post(
    "/api/sessions/{session_id}/appointments/{appointment_id}/outcome",
    response_model=AppointmentView,
    tags=["Appointments"],
)
async def api_submit_appointment_outcome(
    session_id: str = PathParam(..., description="UUID of session"),
    appointment_id: str = PathParam(..., description="UUID of appointment"),
    payload: AppointmentOutcomeRequest = ...,
):
    """
    Submit structured post-appointment report and trigger workflow state transitions.
    Cancels pending post-appointment follow-up notification.
    """
    appt = await get_appointment(appointment_id)
    if not appt or appt.get("session_id") != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")

    # Cancel pending post-appointment follow-up
    await cancel_pending_notifications_for_appointment(
        appointment_id,
        notification_types=["appointment_follow_up"],
    )

    # Determine status
    attended_status = "attended" if payload.attended in ("yes", "attended") else payload.attended
    summary = payload.outcome or payload.notes or attended_status

    updated = await update_appointment(
        appointment_id=appointment_id,
        status=attended_status,
        outcome_summary=summary,
        outcome_details=payload.model_dump(),
        status_source="user_reported",
    )

    # Record event
    await record_application_event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        appointment_id=appointment_id,
        application_id=appt.get("application_id"),
        event_type="appointment_outcome_submitted",
        old_status=appt.get("status"),
        new_status=attended_status,
        source="user_reported",
        details=payload.model_dump(),
    )

    # Apply workflow transitions
    # 1. Documents accepted
    if payload.outcome == "documents_accepted" and appt.get("related_task_id"):
        try:
            await update_checklist_status(
                session_id=session_id,
                doc_id=appt["related_task_id"],
                status="obtained",
            )
        except Exception as exc:
            logger.warning("Could not auto-update checklist item: %s", exc)

    # 2. Additional documents requested
    if payload.outcome == "additional_documents_requested" and payload.additional_documents:
        for doc in payload.additional_documents:
            doc_slug = "doc_" + re.sub(r"[^a-z0-9]+", "_", doc.lower()).strip("_")
            try:
                await update_checklist_status(
                    session_id=session_id,
                    doc_id=doc_slug,
                    status="needed",
                )
            except Exception as exc:
                logger.warning("Could not add additional document requirement: %s", exc)

    # 3. Application submitted / under_review / approved / rejected
    app_id = appt.get("application_id")
    if app_id:
        target_app_status = None
        if payload.outcome == "application_submitted":
            target_app_status = "submitted"
        elif payload.outcome == "pending_review":
            target_app_status = "under_review"
        elif payload.outcome == "approved":
            target_app_status = "approved"
        elif payload.outcome == "rejected":
            target_app_status = "rejected"

        if target_app_status:
            await update_tracked_application(
                application_id=app_id,
                status=target_app_status,
                status_source="user_reported",
            )
            await record_application_event(
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                application_id=app_id,
                appointment_id=appointment_id,
                event_type="application_status_updated_from_appointment",
                new_status=target_app_status,
                source="user_reported",
                details={"reason": payload.outcome},
            )

    return AppointmentView(
        appointment_id=updated["appointment_id"],
        session_id=session_id,
        application_id=updated.get("application_id"),
        related_task_id=updated.get("related_task_id"),
        purpose=updated["purpose"],
        scheduled_at_utc=updated.get("scheduled_at_utc"),
        timezone=updated.get("timezone", "Asia/Kolkata"),
        location=updated.get("location"),
        status=updated.get("status", "scheduled"),
        outcome_summary=updated.get("outcome_summary"),
        outcome_details=updated.get("outcome_details"),
        status_source=updated.get("status_source", "user_reported"),
        created_at=updated.get("created_at", ""),
    )


# ---------------------------------------------------------------------------
# Phase 9: Tracked Applications & Rejection Recovery Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/sessions/{session_id}/applications",
    response_model=TrackedApplicationView,
    tags=["Applications & Progress"],
)
async def api_create_tracked_application(
    session_id: str = PathParam(..., description="UUID of session"),
    payload: TrackedApplicationCreateRequest = ...,
):
    """Start tracking a welfare scheme application."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    app_id = str(uuid.uuid4())
    app_rec = await create_tracked_application(
        application_id=app_id,
        session_id=session_id,
        scheme_id=payload.scheme_id,
        status=payload.status,
        status_source=payload.status_source,
    )

    await record_application_event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        application_id=app_id,
        event_type="tracking_started",
        new_status=payload.status,
        source=payload.status_source,
        details={"scheme_id": payload.scheme_id},
    )

    scheme = await get_session_scheme(session_id, payload.scheme_id)

    return TrackedApplicationView(
        application_id=app_rec["application_id"],
        session_id=session_id,
        scheme_id=app_rec["scheme_id"],
        scheme_name=scheme.name if scheme else None,
        status=app_rec["status"],
        status_source=app_rec["status_source"],
        reported_submission_at=app_rec.get("reported_submission_at"),
        recovery_status=app_rec.get("recovery_status"),
        recovery_data=app_rec.get("recovery_data"),
        last_updated_at=app_rec.get("last_updated_at"),
        created_at=app_rec.get("created_at", ""),
    )


@app.get(
    "/api/sessions/{session_id}/applications",
    response_model=list[TrackedApplicationView],
    tags=["Applications & Progress"],
)
async def api_list_tracked_applications(
    session_id: str = PathParam(..., description="UUID of session"),
):
    """List tracked applications and their current lifecycle states."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session '{session_id}' not found.")

    apps = await list_tracked_applications(session_id)
    schemes_by_id = {s.id: s.name for s in session.normalized_schemes}

    return [
        TrackedApplicationView(
            application_id=a["application_id"],
            session_id=session_id,
            scheme_id=a["scheme_id"],
            scheme_name=schemes_by_id.get(a["scheme_id"]),
            status=a["status"],
            status_source=a.get("status_source", "user_reported"),
            reported_submission_at=a.get("reported_submission_at"),
            recovery_status=a.get("recovery_status"),
            recovery_data=a.get("recovery_data"),
            last_updated_at=a.get("last_updated_at"),
            created_at=a.get("created_at", ""),
        )
        for a in apps
    ]


@app.get(
    "/api/sessions/{session_id}/applications/{application_id}",
    response_model=TrackedApplicationView,
    tags=["Applications & Progress"],
)
async def api_get_tracked_application(
    session_id: str = PathParam(..., description="UUID of session"),
    application_id: str = PathParam(..., description="UUID of tracked application"),
):
    """Get single tracked application record."""
    a = await get_tracked_application(application_id)
    if not a or a.get("session_id") != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked application not found.")

    scheme = await get_session_scheme(session_id, a["scheme_id"])
    return TrackedApplicationView(
        application_id=a["application_id"],
        session_id=session_id,
        scheme_id=a["scheme_id"],
        scheme_name=scheme.name if scheme else None,
        status=a["status"],
        status_source=a.get("status_source", "user_reported"),
        reported_submission_at=a.get("reported_submission_at"),
        recovery_status=a.get("recovery_status"),
        recovery_data=a.get("recovery_data"),
        last_updated_at=a.get("last_updated_at"),
        created_at=a.get("created_at", ""),
    )


@app.post(
    "/api/sessions/{session_id}/applications/{application_id}/outcome",
    response_model=TrackedApplicationView,
    tags=["Applications & Progress"],
)
async def api_update_application_outcome(
    session_id: str = PathParam(..., description="UUID of session"),
    application_id: str = PathParam(..., description="UUID of tracked application"),
    payload: TrackedApplicationOutcomeRequest = ...,
):
    """Update application progress status (submitted, under_review, approved, rejected, etc.)."""
    a = await get_tracked_application(application_id)
    if not a or a.get("session_id") != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked application not found.")

    old_status = a.get("status", "not_started")
    updated = await update_tracked_application(
        application_id=application_id,
        status=payload.status,
        status_source=payload.status_source,
        reported_submission_at=payload.submission_date,
    )

    await record_application_event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        application_id=application_id,
        event_type="application_status_updated",
        old_status=old_status,
        new_status=payload.status,
        source=payload.status_source,
        details={"notes": payload.notes},
    )

    # If status is updated to rejected, trigger investigation automatically
    if payload.status == "rejected":
        scheme = await get_session_scheme(session_id, a["scheme_id"])
        if scheme:
            rec_result = await investigate_rejection(
                scheme=scheme,
                reported_reason=payload.notes or "Application rejected",
                llm=_normalizer_llm(),
                simulated=(payload.status_source == "demo_simulated"),
            )
            updated = await update_tracked_application(
                application_id=application_id,
                recovery_status=rec_result["recovery_status"],
                recovery_data=rec_result,
            )

    scheme = await get_session_scheme(session_id, updated["scheme_id"])
    return TrackedApplicationView(
        application_id=updated["application_id"],
        session_id=session_id,
        scheme_id=updated["scheme_id"],
        scheme_name=scheme.name if scheme else None,
        status=updated["status"],
        status_source=updated.get("status_source", "user_reported"),
        reported_submission_at=updated.get("reported_submission_at"),
        recovery_status=updated.get("recovery_status"),
        recovery_data=updated.get("recovery_data"),
        last_updated_at=updated.get("last_updated_at"),
        created_at=updated.get("created_at", ""),
    )


@app.post(
    "/api/sessions/{session_id}/applications/{application_id}/rejection-analysis",
    response_model=RejectionRecoveryView,
    tags=["Applications & Progress"],
)
async def api_analyze_application_rejection(
    session_id: str = PathParam(..., description="UUID of session"),
    application_id: str = PathParam(..., description="UUID of tracked application"),
    payload: RejectionInvestigationRequest = ...,
):
    """
    Run source-grounded rejection investigation on official guidelines, verify
    remedy procedures, and propose user-reviewed next steps.
    """
    a = await get_tracked_application(application_id)
    if not a or a.get("session_id") != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked application not found.")

    scheme = await get_session_scheme(session_id, a["scheme_id"])
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheme not found for application.")

    rec_result = await investigate_rejection(
        scheme=scheme,
        notice_text=payload.notice_text,
        reported_reason=payload.reason,
        reason_category=payload.reason_category,
        llm=_normalizer_llm(),
        simulated=payload.simulated,
    )

    await update_tracked_application(
        application_id=application_id,
        status="rejected",
        status_source="demo_simulated" if payload.simulated else "user_reported",
        recovery_status=rec_result["recovery_status"],
        recovery_data=rec_result,
    )

    await record_application_event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        application_id=application_id,
        event_type="rejection_investigation_run",
        details=rec_result,
    )

    return RejectionRecoveryView(**rec_result)


@app.get(
    "/api/sessions/{session_id}/applications/{application_id}/recovery",
    response_model=RejectionRecoveryView,
    tags=["Applications & Progress"],
)
async def api_get_application_recovery(
    session_id: str = PathParam(..., description="UUID of session"),
    application_id: str = PathParam(..., description="UUID of tracked application"),
):
    """Retrieve current rejection recovery status and evidence for an application."""
    a = await get_tracked_application(application_id)
    if not a or a.get("session_id") != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked application not found.")

    rec_data = a.get("recovery_data")
    if not rec_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No rejection recovery analysis on file.")

    return RejectionRecoveryView(**rec_data)


# ---------------------------------------------------------------------------
# Phase 9: Secure Follow-up Link & Demo Fast-Forward Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/api/follow-up/{token}",
    response_model=FollowUpPageView,
    tags=["Follow-Up Links"],
)
async def api_load_follow_up_page(
    token: str = PathParam(..., description="Cryptographic follow-up bearer token"),
):
    """Load scoped follow-up screen without leaking private demographic context."""
    tok_hash = hash_token(token)
    tok = await get_follow_up_token_by_hash(tok_hash)
    if not tok or tok.get("revoked_at_utc") is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or revoked follow-up link.")

    exp_iso = tok.get("expires_at_utc", "")
    if exp_iso and exp_iso < now_utc().isoformat():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This follow-up link has expired.")

    session_id = tok["session_id"]
    appt_id = tok.get("appointment_id")
    app_id = tok.get("application_id")

    appt_view = None
    app_view = None
    scheme_name = None

    if appt_id:
        appt = await get_appointment(appt_id)
        if appt:
            appt_view = AppointmentView(
                appointment_id=appt["appointment_id"],
                session_id=session_id,
                application_id=appt.get("application_id"),
                related_task_id=appt.get("related_task_id"),
                purpose=appt["purpose"],
                scheduled_at_utc=appt.get("scheduled_at_utc"),
                timezone=appt.get("timezone", "Asia/Kolkata"),
                location=appt.get("location"),
                status=appt.get("status", "scheduled"),
                outcome_summary=appt.get("outcome_summary"),
                outcome_details=appt.get("outcome_details"),
                status_source=appt.get("status_source", "user_reported"),
                created_at=appt.get("created_at", ""),
            )

    if app_id:
        appl = await get_tracked_application(app_id)
        if appl:
            app_view = TrackedApplicationView(
                application_id=appl["application_id"],
                session_id=session_id,
                scheme_id=appl["scheme_id"],
                status=appl["status"],
                status_source=appl.get("status_source", "user_reported"),
                reported_submission_at=appl.get("reported_submission_at"),
                recovery_status=appl.get("recovery_status"),
                recovery_data=appl.get("recovery_data"),
                last_updated_at=appl.get("last_updated_at"),
                created_at=appl.get("created_at", ""),
            )
            scheme = await get_session_scheme(session_id, appl["scheme_id"])
            if scheme:
                scheme_name = scheme.name

    scope = "appointment" if appt_id else ("application" if app_id else "session")
    return FollowUpPageView(
        session_id=session_id,
        token_id=tok["token_id"],
        scope_type=scope,
        appointment=appt_view,
        application=app_view,
        scheme_name=scheme_name,
        expires_at=exp_iso,
    )


@app.post(
    "/api/follow-up/{token}/outcome",
    tags=["Follow-Up Links"],
)
async def api_submit_follow_up_outcome(
    token: str = PathParam(..., description="Cryptographic follow-up bearer token"),
    payload: FollowUpOutcomeRequest = ...,
):
    """Submit outcome through secure bearer link."""
    tok_hash = hash_token(token)
    tok = await get_follow_up_token_by_hash(tok_hash)
    if not tok or tok.get("revoked_at_utc") is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or revoked follow-up link.")

    exp_iso = tok.get("expires_at_utc", "")
    if exp_iso and exp_iso < now_utc().isoformat():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This follow-up link has expired.")

    session_id = tok["session_id"]
    appt_id = tok.get("appointment_id")
    app_id = tok.get("application_id")

    if appt_id:
        req = AppointmentOutcomeRequest(
            attended=payload.attended or "yes",
            outcome=payload.outcome,
            notes=payload.notes,
            rescheduled_date=payload.rescheduled_date,
            additional_documents=payload.additional_documents,
        )
        return await api_submit_appointment_outcome(
            session_id=session_id,
            appointment_id=appt_id,
            payload=req,
        )

    if app_id:
        req2 = TrackedApplicationOutcomeRequest(
            status=payload.application_status or "under_review",
            status_source="user_reported",
            notes=payload.notes,
        )
        return await api_update_application_outcome(
            session_id=session_id,
            application_id=app_id,
            payload=req2,
        )

    return {"updated": True, "session_id": session_id}


@app.post(
    "/api/demo/advance-time",
    response_model=AdvanceTimeResponse,
    tags=["Demo Fast-Forward"],
)
async def api_demo_advance_time(
    payload: Optional[AdvanceTimeRequest] = None,
):
    """
    Demo Fast-Forward: Advance simulated application clock and run due notification processor.
    Strictly blocked when DEMO_MODE is false.
    """
    if not is_demo_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demo mode is disabled. Clock advance endpoints are strictly disabled outside demo mode.",
        )

    p = payload or AdvanceTimeRequest()
    if p.target_utc:
        try:
            target_dt = datetime.fromisoformat(p.target_utc.replace("Z", "+00:00"))
            set_demo_time(target_dt)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid target_utc timestamp: {exc}")
    else:
        seconds = p.seconds if p.seconds is not None else 86400.0  # default 24 hours
        advance_demo_time(seconds)

    current_simulated = now_utc().isoformat()
    processed = await process_due_notifications()

    return AdvanceTimeResponse(
        demo_mode=True,
        simulated_now_utc=current_simulated,
        notifications_processed=len(processed),
        processed_notifications=processed,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("api.main:app", host=host, port=port, reload=True)

