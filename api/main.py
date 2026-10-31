"""
api/main.py — FastAPI Application for Project Unlocked.

Exposes REST endpoints for session management, scheme discovery, consolidated
questionnaire flows, reassessment, and document DAG action planning.
Consumed by Member 4 (Frontend).
"""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from api.database import (
    create_session,
    delete_session,
    get_session,
    init_db,
)
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
    CreateSessionRequest,
    DeleteSessionResponse,
    DiscoverOptions,
    DiscoveryResult,
    EventKind,
    FullSessionState,
    HealthResponse,
    ProgressResult,
    Question,
    ReassessmentResult,
    RejectionAnalysis,
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
    UpdateDocStatusRequest,
    UserProfileInput,
)
from agent4 import (
    analyse_rejection,
    build_calendar_artifact,
    build_email_draft,
    update_progress,
)
from member2 import default_client

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
    llm = default_client()
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
    llm = default_client()
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("api.main:app", host=host, port=port, reload=True)

