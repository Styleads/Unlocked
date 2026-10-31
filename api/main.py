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
from fastapi import FastAPI, HTTPException, Path as PathParam, status
from fastapi.middleware.cors import CORSMiddleware

from api.database import (
    create_session,
    delete_session,
    get_session,
    init_db,
)
from api.orchestrator import (
    generate_action_plan,
    get_session_questions,
    get_session_scheme,
    get_session_schemes,
    process_answers,
    run_discovery,
    update_checklist_status,
)
from api.schemas import (
    ActionPlan,
    CreateSessionRequest,
    DeleteSessionResponse,
    DiscoverOptions,
    DiscoveryResult,
    FullSessionState,
    HealthResponse,
    Question,
    ReassessmentResult,
    SchemeView,
    SessionResponse,
    SubmitAnswersRequest,
    UpdateDocStatusRequest,
    UserProfileInput,
)

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
    "*"
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("api.main:app", host=host, port=port, reload=True)

