"""
Tests for Project Unlocked FastAPI Application.

Covers:
- GET /health endpoint (readiness, version, credential checks, security)
- POST /discover endpoint:
  - English discovery
  - Kannada discovery (preferred_language='kn')
  - Flat user profile input
  - Nested user profile input
  - Search scopes ('guided', 'all', 'fallback')
  - Validation errors (HTTP 422 for invalid scope/language)
  - Timeout handling (HTTP 504)
  - Internal server error handling (HTTP 500 without leaking secrets)
  - CORS header validation
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from api.main import app
from discovery_agent.scheme_schema import SchemeRecord, SourceEvidence


@pytest.fixture
def client():
    """Create a TestClient instance for testing API endpoints."""
    return TestClient(app)


# ============================================================
# 1. HEALTH CHECK ENDPOINT
# ============================================================

def test_health_endpoint_returns_expected_structure(client):
    """GET /health returns 200 with operational status and no leaked secrets."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert data["application"] == "Project Unlocked - Discovery Engine API"
    assert data["version"] == "1.0.0"
    assert "operational" in data
    assert "services" in data
    assert "gemini_configured" in data["services"]
    assert "tavily_configured" in data["services"]

    # Security check: Ensure no secret strings or API keys are leaked in health payload
    dumped = str(data)
    assert "AIza" not in dumped  # Common Google API key prefix
    assert "tvly-" not in dumped  # Common Tavily API key prefix


# ============================================================
# 2. DISCOVER ENDPOINT — BASIC USAGE
# ============================================================

def test_discover_fallback_english(client):
    """POST /discover with scope='fallback' and lang='en' returns 200 and English schemes."""
    payload = {
        "user_profile": {
            "occupation": "farmer",
            "state": "Karnataka",
            "district": "Mandya",
            "interests": ["crop insurance"]
        },
        "search_scope": "fallback",
        "preferred_language": "en"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["preferred_language"] == "en"
    assert data["actual_response_language"] == "en"
    assert data["translation_status"] == "not_requested"
    assert data["total_schemes"] >= 1
    assert len(data["schemes"]) == data["total_schemes"]
    assert data["errors"] == []

    # Verify scheme attributes
    first_scheme = data["schemes"][0]
    assert "name" in first_scheme
    assert "description" in first_scheme
    assert "eligibility_criteria" in first_scheme
    assert "required_documents" in first_scheme
    assert "benefits" in first_scheme
    assert first_scheme["discovery_source"] == "fallback"


def test_discover_fallback_kannada(client):
    """POST /discover with scope='fallback' and lang='kn' returns Kannada scheme content."""
    payload = {
        "user_profile": {
            "occupation": "farmer",
            "state": "Karnataka",
            "district": "Mandya",
            "interests": ["crop insurance"]
        },
        "search_scope": "fallback",
        "preferred_language": "kn"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["preferred_language"] == "kn"
    assert data["actual_response_language"] == "kn"
    assert data["translation_status"] == "complete"
    assert data["total_schemes"] >= 1

    # Check for Kannada characters in the scheme name
    names = [s["name"] for s in data["schemes"]]
    # At least one scheme should contain Kannada Unicode range (\u0C80-\u0CFF)
    has_kannada = any(
        any("\u0C80" <= char <= "\u0CFF" for char in name)
        for name in names
    )
    assert has_kannada is True


# ============================================================
# 3. INPUT PROFILES & NORMALIZATION
# ============================================================

def test_discover_accepts_flat_profile(client):
    """POST /discover correctly parses and normalizes a flat profile structure."""
    payload = {
        "user_profile": {
            "occupation": "student",
            "state": "Karnataka",
            "district": "Mysuru",
            "annual_income": 80000,
            "interests": ["scholarships"]
        },
        "search_scope": "fallback",
        "preferred_language": "en"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_discover_accepts_nested_profile(client):
    """POST /discover correctly parses a nested profile matching user_profile.json."""
    payload = {
        "user_profile": {
            "employment": {"occupation": "weaver"},
            "location": {"district": "Bagalkot", "state": "Karnataka"},
            "interests": ["handloom subsidy"]
        },
        "search_scope": "fallback",
        "preferred_language": "en"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_discover_kannada_translation_failure_reports_failed_metadata(client, monkeypatch):
    """When translation service fails on live schemes, actual_response_language is 'en' and status is 'failed'."""
    from discovery_agent.scheme_schema import SchemeRecord

    live_scheme = SchemeRecord(
        id="live-test-001",
        name="Karnataka Solar Pump Scheme",
        description="Subsidies for agricultural solar pumps.",
        discovery_source="live_search"
    )

    async def mock_discovery(*args, **kwargs):
        return [live_scheme]

    async def mock_failing_trans(*args, **kwargs):
        from discovery_agent.kannada_translator import TranslationResult
        return TranslationResult([live_scheme], ["Translation service error"], translation_status="failed", actual_response_language="en")

    monkeypatch.setattr("api.main.discover_schemes", mock_discovery)
    monkeypatch.setattr("api.main.translate_schemes_to_kannada", mock_failing_trans)

    payload = {
        "user_profile": {"occupation": "farmer"},
        "search_scope": "guided",
        "preferred_language": "kn"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["preferred_language"] == "kn"
    assert data["actual_response_language"] == "en"
    assert data["translation_status"] == "failed"
    assert data["schemes"][0]["name"] == "Karnataka Solar Pump Scheme"


# ============================================================
# 4. REQUEST VALIDATION (HTTP 422)
# ============================================================

def test_discover_rejects_invalid_search_scope(client):
    """Invalid search_scope returns HTTP 422 Unprocessable Entity."""
    payload = {
        "user_profile": {"occupation": "farmer"},
        "search_scope": "invalid_scope_xyz",
        "preferred_language": "en"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert len(data["errors"]) > 0


def test_discover_rejects_invalid_language_code(client):
    """Invalid preferred_language returns HTTP 422 Unprocessable Entity."""
    payload = {
        "user_profile": {"occupation": "farmer"},
        "search_scope": "guided",
        "preferred_language": "french"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert len(data["errors"]) > 0


# ============================================================
# 5. TIMEOUT AND ERROR RESILIENCE
# ============================================================

def test_discover_handles_timeout_gracefully(client, monkeypatch):
    """When discovery times out, API returns HTTP 504 with clean error message."""
    async def mock_timeout(*args, **kwargs):
        await asyncio.sleep(2.0)
        return []

    # Patch timeout in api.main to 0.05 seconds for immediate test execution
    monkeypatch.setattr("api.main.DISCOVERY_TIMEOUT", 0.05)
    monkeypatch.setattr("api.main.discover_schemes", mock_timeout)

    payload = {
        "user_profile": {"occupation": "farmer"},
        "search_scope": "guided",
        "preferred_language": "en"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 504
    data = response.json()
    assert data["success"] is False
    assert any("timed out" in err.lower() for err in data["errors"])


def test_discover_handles_pipeline_exception_without_leaking_traces(client, monkeypatch):
    """Internal exceptions return HTTP 500 without leaking stack traces or internal secrets."""
    async def mock_crash(*args, **kwargs):
        raise RuntimeError("SecretDatabaseFailure: API_KEY_SECRET_12345")

    monkeypatch.setattr("api.main.discover_schemes", mock_crash)

    payload = {
        "user_profile": {"occupation": "farmer"},
        "search_scope": "guided",
        "preferred_language": "en"
    }
    response = client.post("/discover", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert "API_KEY_SECRET_12345" not in str(data)
    assert any("error" in err.lower() for err in data["errors"])


# ============================================================
# 6. CORS HEADERS
# ============================================================

def test_cors_headers_present(client):
    """Verify CORS middleware responds with correct headers for allowed origin."""
    response = client.options(
        "/discover",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

