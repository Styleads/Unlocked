# Backend Integration Guide for Member 3 (Partha — Orchestration & Backend Lead)

## 1. Overview
The Discovery Agent discovers and verifies government welfare and benefit schemes for citizens, with a focus on Karnataka and Central schemes. It searches only official government domains (`.gov.in`, `.nic.in`), extracts structured schemes, and independently verifies claims against exact official text evidence.

You can integrate with Project Unlocked in **two ways**:
1. **HTTP REST API** (Recommended for multi-service or microservice architectures).
2. **Direct Python In-Process Call** (Recommended for monolithic async Python backends).

---

## 2. Option A: FastAPI REST API Integration (Recommended)

### Server Startup Command
```powershell
# Start the FastAPI server with uvicorn
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
Or run directly via python:
```powershell
python -m api.main
```

### Environment Variables
Configure these in your environment or `.env` file:
```env
GOOGLE_API_KEY=your_google_gemini_api_key_here
TAVILY_API_KEY=your_tavily_search_api_key_here
PORT=8000
HOST=0.0.0.0
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000
DISCOVERY_TIMEOUT_SECONDS=45.0
```

---

### Endpoints

#### 1. GET `/health`
Check service operational status and credentials readiness.

**Request:**
```http
GET /health HTTP/1.1
Host: localhost:8000
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "application": "Project Unlocked - Discovery Engine API",
  "version": "1.0.0",
  "operational": true,
  "services": {
    "gemini_configured": true,
    "tavily_configured": true
  }
}
```

---

#### 2. POST `/discover`
Discover, verify, and optionally translate schemes matching a citizen's profile.

**Request Headers:**
`Content-Type: application/json`

**Request Body (English):**
```json
{
  "user_profile": {
    "occupation": "farmer",
    "state": "Karnataka",
    "district": "Mandya",
    "annual_income": 150000,
    "interests": ["crop insurance", "irrigation subsidy"]
  },
  "search_scope": "all",
  "preferred_language": "en"
}
```

**Request Body (Kannada / ಕನ್ನಡ):**
```json
{
  "user_profile": {
    "occupation": "farmer",
    "state": "Karnataka",
    "district": "Mandya",
    "annual_income": 150000,
    "interests": ["agriculture", "subsidies"]
  },
  "search_scope": "all",
  "preferred_language": "kn"
}
```

**Response (200 OK — Kannada example):**
```json
{
  "success": true,
  "preferred_language": "kn",
  "actual_response_language": "kn",
  "translation_status": "complete",
  "total_schemes": 2,
  "schemes": [
    {
      "id": "pmfby-crop-insurance-2026",
      "name": "ಪ್ರಧಾನ ಮಂತ್ರಿ ಫಸಲ್ ಬಿಮಾ ಯೋಜನೆ (PMFBY)",
      "description": "ನೈಸರ್ಗಿಕ ವಿಕೋಪಗಳು, ಕೀಟಗಳು ಮತ್ತು ರೋಗಗಳಿಂದ ಬೆಳೆ ನಷ್ಟ ಅಥವಾ ಹಾನಿಯನ್ನು ಅನುಭವಿಸುವ ರೈತರಿಗೆ ಸಮಗ್ರ ಆರ್ಥಿಕ ನೆರವು ನೀಡುವ ರಾಷ್ಟ್ರೀಯ ಬೆಳೆ ವಿಮಾ ಯೋಜನೆ.",
      "target_groups": ["ರೈತರು", "ಪಾಲುದಾರ ರೈತರು", "ಗೇಣಿದಾರ ರೈತರು"],
      "benefits": [
        "ನೈಸರ್ಗಿಕ ವಿಕೋಪಗಳಿಂದ ಉಂಟಾಗುವ ಬೆಳೆ ನಷ್ಟಕ್ಕೆ ವಿಮಾ ರಕ್ಷಣೆ",
        "ರೈತರಿಗೆ ಕಡಿಮೆ ಪ್ರೀಮಿಯಂ ದರಗಳು (ಆಹಾರ ಮತ್ತು ಎಣ್ಣೆಕಾಳುಗಳಿಗೆ 1.5% - 2%)"
      ],
      "eligibility_criteria": [
        {
          "description": "ಅಧಿಸೂಚಿತ ಪ್ರದೇಶಗಳಲ್ಲಿ ಅಧಿಸೂಚಿತ ಬೆಳೆಗಳನ್ನು ಬೆಳೆಯುವ ಎಲ್ಲಾ ರೈತರು",
          "related_attribute": "occupation",
          "source_url": "https://pmfby.gov.in",
          "verification_status": "verified"
        }
      ],
      "required_documents": [
        "ಆಧಾರ್ ಕಾರ್ಡ್",
        "ಭೂ ದಾಖಲೆಗಳು / ಪಹಣಿ (RTC)",
        "ಬ್ಯಾಂಕ್ ಪಾಸ್‌ಬುಕ್ ವಿವರಗಳು"
      ],
      "application_process": "ಹತ್ತಿರದ ಬ್ಯಾಂಕ್ ಶಾಖೆ, ಸಾಮಾನ್ಯ ಸೇವಾ ಕೇಂದ್ರ (CSC) ಅಥವಾ pmfby.gov.in ಪೋರ್ಟಲ್ ಮೂಲಕ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ.",
      "application_url": "https://pmfby.gov.in/farmerLogin",
      "official_url": "https://pmfby.gov.in",
      "government_level": "central",
      "department": "ಕೃಷಿ ಮತ್ತು ರೈತರ ಕಲ್ಯಾಣ ಸಚಿವಾಲಯ",
      "source_evidence": [
        {
          "title": "PMFBY Official Portal",
          "url": "https://pmfby.gov.in",
          "excerpt": "Pradhan Mantri Fasal Bima Yojana provides financial support to farmers suffering crop loss or damage.",
          "is_official": true
        }
      ],
      "claims": [
        {
          "category": "benefit",
          "claim": "ಬೆಳೆ ನಷ್ಟಕ್ಕೆ ಆರ್ಥಿಕ ಬೆಂಬಲ",
          "source_url": "https://pmfby.gov.in",
          "supporting_excerpt": "financial support to farmers suffering crop loss",
          "verification_status": "verified",
          "verification_reason": "ಅಧಿಕೃತ ಮೂಲದಲ್ಲಿ ಕಂಡುಬಂದಿದೆ"
        }
      ],
      "verification_status": "verified",
      "discovery_source": "live_search",
      "relevance": "direct_match",
      "match_reasons": ["ಕೃಷಿ ಆಸಕ್ತಿಗೆ ಹೊಂದಿಕೆಯಾಗುತ್ತದೆ"],
      "missing_information": [],
      "last_verified": "2026-10-31T03:08:40.123456+00:00"
    }
  ],
  "warnings": [],
  "errors": []
}
```

---

### Python Integration Snippet (Calling FastAPI from Partha's Backend)

```python
import httpx

DISCOVERY_API_URL = "http://localhost:8000/discover"

async def get_user_schemes(user_profile: dict, language: str = "kn") -> dict:
    payload = {
        "user_profile": user_profile,
        "search_scope": "all",
        "preferred_language": language
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(DISCOVERY_API_URL, json=payload)
        response.raise_for_status()
        return response.json()
```

---

## 3. Option B: Direct Python Library Integration (In-Process)

```python
import asyncio
from discovery_agent import discover_schemes, SchemeRecord
from discovery_agent.kannada_translator import translate_schemes_to_kannada

user_profile = {
    "employment": {"occupation": "farmer"},
    "location": {
        "district": "Mandya",
        "state": "Karnataka"
    },
    "interests": ["crop insurance", "irrigation subsidy"],
    "agriculture": {
        "land_ownership": "3 acres"
    }
}

async def main():
    # 1. Discover schemes
    schemes = await discover_schemes(
        user_context=user_profile,
        search_scope="all",
        enable_fallback=True
    )

    # 2. Translate to Kannada if requested
    translated_schemes, warnings = await translate_schemes_to_kannada(schemes)

    for scheme in translated_schemes:
        print(f"[{scheme.verification_status}] {scheme.name} -> {scheme.official_url}")

asyncio.run(main())
```

---

## 4. SchemeRecord Schema Specification

```python
class SchemeRecord(BaseModel):
    id: str                                  # Unique identifier
    name: str                                # Official scheme name (English or Kannada)
    description: str = ""                    # Summary description
    target_groups: list[str] = []            # Beneficiary categories (e.g. ["farmers", "students"])
    benefits: list[str] = []                 # Key benefits provided
    eligibility_criteria: list[SchemeCriterion] = [] # Specific eligibility conditions
    required_documents: list[str] = []       # Documents needed (e.g. ["Aadhaar", "RTC"])
    application_process: str | None = None   # Instructions on how to apply
    application_url: str | None = None       # Direct link to application portal
    official_url: str | None = None          # Official scheme information page
    government_level: Literal["central", "state", "local", "unknown"] = "unknown"
    department: str | None = None            # Responsible ministry/department
    source_evidence: list[SourceEvidence] = [] # Evidence documents supporting claims
    claims: list[SchemeClaim] = []           # Individual claims and their verification
    verification_status: Literal["verified", "partially_verified", "unverified"] = "unverified"
    discovery_source: Literal["live_search", "fallback"] = "live_search"
    relevance: Literal["direct_match", "related", "additional"] = "additional"
    match_reasons: list[str] = []            # Why this matches the user profile
    missing_information: list[str] = []      # Items that need rechecking or are unknown
    last_verified: str | None = None         # ISO 8601 timestamp (e.g. 2026-10-31T03:00:00Z)
```

---

## 5. Error Handling & Timeout Strategy
- **HTTP 422 Unprocessable Content**: Raised if `search_scope` is not in `["guided", "all", "fallback"]` or `preferred_language` is not in `["en", "kn"]`.
- **HTTP 504 Gateway Timeout**: Raised if live discovery exceeds `DISCOVERY_TIMEOUT_SECONDS` (default: 45s).
- **HTTP 500 Internal Server Error**: Internal issues return a clean JSON payload without leaking stack traces or API keys.
- **Graceful Translation Fallback**: If Gemini translation service fails or times out, the original English schemes are returned with an explanatory message in `warnings`.
