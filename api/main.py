"""
Project Unlocked — FastAPI REST Backend Service.

Exposes the Discovery Engine and Evidence Verification pipeline
over HTTP for integration with external backends and frontends.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import (
    DiscoverRequest,
    DiscoverResponse,
    HealthResponse,
)
from discovery_agent.discovery_pipeline import discover_schemes
from discovery_agent.kannada_translator import translate_schemes_to_kannada

# --------------------------------------------------
# Logging & Configuration
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("unlocked.api")

load_dotenv()

APP_NAME = "Project Unlocked - Discovery Engine API"
APP_VERSION = "1.0.0"

# Default request timeout in seconds (configurable via env)
DEFAULT_TIMEOUT = 45.0
try:
    DISCOVERY_TIMEOUT = float(os.getenv("DISCOVERY_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT)))
except ValueError:
    DISCOVERY_TIMEOUT = DEFAULT_TIMEOUT


# --------------------------------------------------
# Application Lifespan
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Initializing %s v%s", APP_NAME, APP_VERSION)
    gemini_key = bool(os.getenv("GOOGLE_API_KEY"))
    tavily_key = bool(os.getenv("TAVILY_API_KEY"))
    logger.info(
        "Service credentials check: Gemini=%s, Tavily=%s",
        "Configured" if gemini_key else "Missing",
        "Configured" if tavily_key else "Missing",
    )
    yield
    logger.info("Shutting down %s", APP_NAME)


# --------------------------------------------------
# FastAPI Initialization
# --------------------------------------------------

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Autonomous AI engine for Indian government scheme discovery "
        "and evidence-based verification, focusing on Karnataka and Central schemes."
    ),
    lifespan=lifespan,
)

# --------------------------------------------------
# CORS Configuration
# --------------------------------------------------

raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:8000"
)
allowed_origins = [orig.strip() for orig in raw_origins.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Exception Handlers
# --------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors cleanly with HTTP 422."""
    error_messages = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        error_messages.append(f"{loc}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "preferred_language": "en",
            "total_schemes": 0,
            "schemes": [],
            "warnings": [],
            "errors": error_messages,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Catch unhandled exceptions without leaking stack traces or internal secrets.
    """
    logger.error("Unhandled API error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "preferred_language": "en",
            "total_schemes": 0,
            "schemes": [],
            "warnings": [],
            "errors": ["An internal error occurred while processing the request."],
        },
    )


# --------------------------------------------------
# Endpoints
# --------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Monitoring"],
    summary="Health and Readiness Check",
)
async def health_check() -> HealthResponse:
    """
    Return operational readiness, service version, and credential status.
    Never exposes internal secrets.
    """
    gemini_ready = bool(os.getenv("GOOGLE_API_KEY"))
    tavily_ready = bool(os.getenv("TAVILY_API_KEY"))

    is_operational = gemini_ready and tavily_ready

    return HealthResponse(
        status="healthy" if is_operational else "degraded",
        application=APP_NAME,
        version=APP_VERSION,
        operational=is_operational,
        services={
            "gemini_configured": gemini_ready,
            "tavily_configured": tavily_ready,
        },
    )


@app.post(
    "/discover",
    response_model=DiscoverResponse,
    tags=["Discovery"],
    summary="Discover Government Schemes",
)
async def discover(request: DiscoverRequest) -> DiscoverResponse:
    """
    Discover and verify government welfare schemes matching a citizen's profile.

    - **user_profile**: Citizen demographics, location, occupation, and interests.
    - **search_scope**: 'guided' (interest-focused), 'all' (broad), or 'fallback' (offline).
    - **preferred_language**: 'en' (English) or 'kn' (Kannada).
    """
    user_context = request.user_profile.to_user_context()
    logger.info(
        "Received discovery request: occupation=%s, state=%s, district=%s, scope=%s, lang=%s",
        user_context.get("employment", {}).get("occupation"),
        user_context.get("location", {}).get("state"),
        user_context.get("location", {}).get("district"),
        request.search_scope,
        request.preferred_language,
    )

    warnings: list[str] = []

    try:
        # Execute asynchronous discovery with configured timeout
        schemes = await asyncio.wait_for(
            discover_schemes(
                user_context=user_context,
                search_scope=request.search_scope,
                enable_fallback=True,
            ),
            timeout=DISCOVERY_TIMEOUT,
        )

        logger.info("Discovery pipeline retrieved %d schemes", len(schemes))

    except asyncio.TimeoutError:
        logger.warning(
            "Discovery pipeline timed out after %.1f seconds", DISCOVERY_TIMEOUT
        )
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "success": False,
                "preferred_language": request.preferred_language,
                "actual_response_language": "en",
                "translation_status": "failed",
                "total_schemes": 0,
                "schemes": [],
                "warnings": [],
                "errors": [
                    f"Discovery operation timed out after {DISCOVERY_TIMEOUT} seconds."
                ],
            },
        )

    except Exception as error:
        logger.error("Discovery error: %s", error, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "preferred_language": request.preferred_language,
                "actual_response_language": "en",
                "translation_status": "failed",
                "total_schemes": 0,
                "schemes": [],
                "warnings": [],
                "errors": [
                    "Failed to complete scheme discovery due to an upstream service error."
                ],
            },
        )

    actual_response_lang = "en"
    trans_status = "not_requested"

    # Apply Kannada translation if requested
    if request.preferred_language == "kn":
        try:
            trans_result = await translate_schemes_to_kannada(schemes)
            schemes, trans_warnings = trans_result
            warnings.extend(trans_warnings)
            trans_status = getattr(trans_result, "translation_status", "complete")
            actual_response_lang = getattr(trans_result, "actual_response_language", "kn")
        except Exception as trans_err:
            logger.warning("Translation error: %s", trans_err)
            warnings.append(
                "Kannada translation encountered an issue; schemes presented in English."
            )
            trans_status = "failed"
            actual_response_lang = "en"

    return DiscoverResponse(
        success=True,
        preferred_language=request.preferred_language,
        actual_response_language=actual_response_lang,
        translation_status=trans_status,
        total_schemes=len(schemes),
        schemes=schemes,
        warnings=warnings,
        errors=[],
    )


# --------------------------------------------------
# Direct Execution Helper
# --------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api.main:app", host=host, port=port, reload=True)

