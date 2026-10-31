
from discovery_agent.scheme_extractor import verify_claims


def test_verify_claims_accepts_exact_official_evidence():
    class FakeModels:
        def generate_content(self, **kwargs):
            class Response:
                text = """
                {
                    "claim_checks": [{
                        "claim_index": 0,
                        "supported": true,
                        "source_url": "https://example.gov.in/scheme",
                        "supporting_excerpt": "Farmers owning up to 2 hectares are eligible.",
                        "reason": "The source explicitly supports the claim."
                    }]
                }
                """
            return Response()

    class FakeClient:
        models = FakeModels()

    claims = [{
        "category": "eligibility",
        "claim": "Farmers owning up to 2 hectares are eligible.",
        "source_url": None
    }]

    evidence = [{
        "title": "Official scheme",
        "url": "https://example.gov.in/scheme",
        "excerpt": "Farmers owning up to 2 hectares are eligible.",
        "is_official": True
    }]

    result = verify_claims(FakeClient(), "fake-model", claims, evidence)

    assert 0 in result
    assert result[0]["source_url"] == "https://example.gov.in/scheme"


def test_verify_claims_rejects_fake_evidence():
    class FakeModels:
        def generate_content(self, **kwargs):
            class Response:
                text = """
                {
                    "claim_checks": [{
                        "claim_index": 0,
                        "supported": true,
                        "source_url": "https://example.gov.in/scheme",
                        "supporting_excerpt": "Farmers receive 50000 rupees.",
                        "reason": "Claim supported."
                    }]
                }
                """
            return Response()

    class FakeClient:
        models = FakeModels()

    claims = [{
        "category": "benefit",
        "claim": "Farmers receive 50000 rupees.",
        "source_url": None
    }]

    evidence = [{
        "title": "Official scheme",
        "url": "https://example.gov.in/scheme",
        "excerpt": "Farmers receive agricultural assistance.",
        "is_official": True
    }]

    result = verify_claims(FakeClient(), "fake-model", claims, evidence)

    assert result == {}

def test_rejects_unknown_source_url():
    class FakeModels:
        def generate_content(self, **kwargs):
            class Response:
                text = """
                {
                    "claim_checks": [{
                        "claim_index": 0,
                        "supported": true,
                        "source_url": "https://fake.gov.in/scheme",
                        "supporting_excerpt": "Farmers receive assistance.",
                        "reason": "Supported."
                    }]
                }
                """
            return Response()

    class FakeClient:
        models = FakeModels()

    claims = [{
        "category": "benefit",
        "claim": "Farmers receive assistance.",
        "source_url": None
    }]

    evidence = [{
        "title": "Official scheme",
        "url": "https://real.gov.in/scheme",
        "excerpt": "Farmers receive assistance.",
        "is_official": True
    }]

    assert verify_claims(FakeClient(), "fake-model", claims, evidence) == {}


def test_rejects_empty_source_evidence():
    class FakeClient:
        pass

    claims = [{
        "category": "benefit",
        "claim": "Farmers receive assistance."
    }]

    assert verify_claims(FakeClient(), "fake-model", claims, []) == {}


def test_rejects_invalid_claim_index():
    class FakeModels:
        def generate_content(self, **kwargs):
            class Response:
                text = """
                {
                    "claim_checks": [{
                        "claim_index": 10,
                        "supported": true,
                        "source_url": "https://example.gov.in/scheme",
                        "supporting_excerpt": "Farmers receive assistance.",
                        "reason": "Supported."
                    }]
                }
                """
            return Response()

    class FakeClient:
        models = FakeModels()

    claims = [{
        "category": "benefit",
        "claim": "Farmers receive assistance.",
        "source_url": None
    }]

    evidence = [{
        "title": "Official scheme",
        "url": "https://example.gov.in/scheme",
        "excerpt": "Farmers receive assistance."
    }]

    assert verify_claims(FakeClient(), "fake-model", claims, evidence) == {}

import asyncio

from discovery_agent import discovery_pipeline as pipeline


# TEST 6: Search queries are generated from user interests

def test_build_search_queries():
    profile = {
        "employment": {"occupation": "Farmer"},
        "location": {
            "district": "Mandya",
            "state": "Karnataka"
        },
        "interests": ["crop insurance", "irrigation assistance"]
    }

    queries = pipeline.build_search_queries(profile)

    assert len(queries) == 2
    assert all("Farmer" in query for query in queries)
    assert all("Mandya" in query for query in queries)
    assert any("crop insurance" in query for query in queries)


# TEST 7: Duplicate search results are removed

def test_deduplicate_results():
    results = [
        {"url": "https://example.gov.in/scheme"},
        {"url": "https://example.gov.in/scheme/"},
        {"url": "https://another.gov.in/scheme"},
        {"url": ""}
    ]

    unique = pipeline.deduplicate_results(results)

    assert len(unique) == 2


# TEST 8: Complete pipeline orchestration with mocked services

def test_discovery_pipeline_execution(monkeypatch):
    profile = {
        "employment": {"occupation": "Farmer"},
        "location": {"state": "Karnataka"},
        "interests": ["crop insurance"]
    }

    fake_results = [
        {
            "title": "Official scheme",
            "url": "https://example.gov.in/scheme",
            "content": "Official government scheme information.",
            "is_official": True
        }
    ]

    expected_schemes = [{"name": "Test Scheme"}]

    class FakeClient:
        def close(self):
            pass

    monkeypatch.setenv("GOOGLE_API_KEY", "fake-test-key")

    monkeypatch.setattr(
        pipeline,
        "search_web",
        lambda query, limit: fake_results
    )

    monkeypatch.setattr(
        pipeline.genai,
        "Client",
        lambda api_key: FakeClient()
    )

    monkeypatch.setattr(
        pipeline,
        "extract_schemes",
        lambda client, model, results, context: expected_schemes
    )

    result = asyncio.run(
        pipeline.discover_schemes(profile, search_scope="guided")
    )

    assert result == expected_schemes
    assert len(result) == 1
    assert result[0]["name"] == "Test Scheme"


# TEST 9: Pipeline handles empty search results

def test_discovery_pipeline_empty_results(monkeypatch):
    profile = {
        "employment": {"occupation": "Farmer"},
        "interests": ["crop insurance"]
    }

    monkeypatch.setattr(
        pipeline,
        "search_web",
        lambda query, limit: []
    )

    result = asyncio.run(
        pipeline.discover_schemes(profile)
    )

    assert result == []

def test_full_discovery_pipeline_with_verified_scheme(monkeypatch):
    import asyncio
    from discovery_agent import discovery_pipeline as pipeline

    official_url = "https://example.gov.in/scheme"
    evidence_text = (
        "Farmers owning up to 2 hectares are eligible for this scheme."
    )

    extraction_response = {
        "schemes": [
            {
                "id": "test-farmer-scheme",
                "name": "Example Farmer Support Scheme",
                "description": "Support for eligible farmers.",
                "target_groups": ["farmers"],
                "benefits": ["Financial assistance"],
                "eligibility_criteria": [
                    {
                        "description": "Farmers owning up to 2 hectares",
                        "related_attribute": "land_holding",
                        "source_url": official_url,
                        "verification_status": "unverified"
                    }
                ],
                "required_documents": ["Aadhaar card"],
                "application_process": "Apply through the official portal.",
                "official_url": official_url,
                "source_evidence": [
                    {
                        "title": "Official Scheme Page",
                        "url": official_url,
                        "excerpt": evidence_text,
                        "is_official": True
                    }
                ],
                "claims": [
                    {
                        "category": "eligibility",
                        "claim": "Farmers owning up to 2 hectares are eligible.",
                        "source_url": official_url,
                        "supporting_excerpt": evidence_text,
                        "verification_status": "unverified",
                        "verification_reason": ""
                    }
                ],
                "verification_status": "unverified",
                "discovery_source": "live_search",
                "relevance": "additional",
                "match_reasons": [],
                "missing_information": []
            }
        ]
    }

    verification_response = {
        "claim_checks": [
            {
                "claim_index": 0,
                "supported": True,
                "source_url": official_url,
                "supporting_excerpt": evidence_text,
                "reason": "The official source contains the supporting statement."
            }
        ]
    }

    class FakeResponse:
        def __init__(self, data):
            import json
            self.text = json.dumps(data)

    class FakeModels:
        def __init__(self):
            self.responses = [
                extraction_response,
                verification_response
            ]

        def generate_content(self, **kwargs):
            return FakeResponse(self.responses.pop(0))

    class FakeClient:
        def __init__(self):
            self.models = FakeModels()

        def close(self):
            pass

    monkeypatch.setenv("GOOGLE_API_KEY", "fake-test-key")

    monkeypatch.setattr(
        pipeline.genai,
        "Client",
        lambda **kwargs: FakeClient()
    )

    monkeypatch.setattr(
        pipeline,
        "search_web",
        lambda query, max_results: [
            {
                "title": "Official Scheme Page",
                "url": official_url,
                "content": evidence_text,
                "is_official": True
            }
        ]
    )

    profile = {
        "employment": {"occupation": "farmer"},
        "location": {
            "district": "Mandya",
            "state": "Karnataka"
        },
        "interests": ["crop insurance"]
    }

    schemes = asyncio.run(
        pipeline.discover_schemes(profile)
    )

    assert len(schemes) == 1
    assert schemes[0].name == "Example Farmer Support Scheme"
    assert schemes[0].claims[0].verification_status == "verified"
    assert schemes[0].verification_status == "verified"
    assert schemes[0].claims[0].source_url == official_url

from discovery_agent.scheme_extractor import classify_relevance


def test_relevance_classification():
    # Case 1: Direct interest match
    farmer_profile = {
        "employment": {"occupation": "farmer"},
        "interests": ["crop insurance"]
    }

    pmfby_scheme = {
        "name": "Pradhan Mantri Fasal Bima Yojana",
        "description": "Provides crop insurance coverage.",
        "benefits": ["Protection against crop loss"],
        "target_groups": ["farmers"]
    }

    relevance, reasons = classify_relevance(
        pmfby_scheme, farmer_profile
    )

    assert relevance == "direct_match"
    assert len(reasons) > 0

    # Case 2: Occupation match without interest match
    student_profile = {
        "employment": {"occupation": "farmer"},
        "interests": ["education scholarships"]
    }

    irrigation_scheme = {
        "name": "Agricultural Support Programme",
        "description": "Support for rural agricultural development.",
        "benefits": ["Financial assistance"],
        "target_groups": ["farmer"]
    }

    relevance, reasons = classify_relevance(
        irrigation_scheme, student_profile
    )

    assert relevance == "related"
    assert len(reasons) > 0

    # Case 3: No interest or occupation match
    student_profile = {
        "employment": {"occupation": "student"},
        "interests": ["education scholarships"]
    }

    farmer_scheme = {
        "name": "Crop Insurance Scheme",
        "description": "Insurance protection for agricultural crops.",
        "benefits": ["Crop loss compensation"],
        "target_groups": ["farmers"]
    }

    relevance, reasons = classify_relevance(
        farmer_scheme, student_profile
    )

    assert relevance == "additional"

def test_relevance_handles_missing_or_invalid_profile():
    scheme = {
        "name": "Crop Insurance Scheme",
        "description": "Provides crop insurance to farmers.",
        "benefits": ["Protection against crop loss"],
        "target_groups": ["farmers"]
    }

    # Empty profile
    relevance, reasons = classify_relevance(scheme, {})
    assert relevance == "additional"
    assert isinstance(reasons, list)

    # Missing employment and interests
    profile = {
        "location": {"state": "Karnataka"}
    }

    relevance, reasons = classify_relevance(scheme, profile)
    assert relevance == "additional"

    # Invalid employment and interests types
    profile = {
        "employment": "farmer",
        "interests": "crop insurance"
    }

    relevance, reasons = classify_relevance(scheme, profile)
    assert relevance == "additional"
    assert isinstance(reasons, list)

    # Invalid profile values
    profile = {
        "employment": None,
        "interests": None
    }

    relevance, reasons = classify_relevance(scheme, profile)
    assert relevance == "additional"

def test_irrelevant_scheme_not_classified_as_direct_match():
    profile = {
        "employment": {"occupation": "student"},
        "interests": ["education scholarships"]
    }

    scheme = {
        "name": "Pradhan Mantri Fasal Bima Yojana",
        "description": "Crop insurance protection against crop loss.",
        "benefits": ["Financial compensation for damaged crops"],
        "target_groups": ["farmers"]
    }

    relevance, reasons = classify_relevance(scheme, profile)

    assert relevance == "additional"
    assert not any("education scholarships" in reason for reason in reasons)

def test_multiple_interests_and_keyword_variations():
    profile = {
        "employment": {"occupation": "farmer"},
        "interests": [
            "crop insurance",
            "irrigation assistance"
        ]
    }

    scheme = {
        "name": "Agricultural Water Support",
        "description": "Promotes drip irrigation and sprinkler irrigation.",
        "benefits": ["Improved water use efficiency"],
        "target_groups": ["farmers"]
    }

    relevance, reasons = classify_relevance(scheme, profile)

    assert relevance == "direct_match"
    assert len(reasons) >= 1

    # Test a predefined crop insurance variation
    profile["interests"] = ["crop insurance"]

    scheme["name"] = "Farmer Protection Programme"
    scheme["description"] = "Provides fasal bima coverage against crop damage."

    relevance, reasons = classify_relevance(scheme, profile)

    assert relevance == "direct_match"
    assert len(reasons) >= 1

def test_occupation_matching_variations():
    profile = {
        "employment": {"occupation": "small farmer"},
        "interests": []
    }

    scheme = {
        "name": "Agricultural Support Scheme",
        "description": "Financial assistance for rural development.",
        "benefits": ["Financial support"],
        "target_groups": ["small farmers"]
    }

    relevance, reasons = classify_relevance(scheme, profile)

    assert relevance == "related"
    assert len(reasons) > 0

    # Partial occupation match
    profile["employment"]["occupation"] = "farmer"

    relevance, reasons = classify_relevance(scheme, profile)

    assert relevance == "related"
def test_gemini_failure_closes_client(monkeypatch):
    import asyncio
    from unittest.mock import Mock
    import pytest
    import discovery_agent.discovery_pipeline as pipeline

    # Mock search query generation
    monkeypatch.setattr(
        pipeline,
        "build_search_queries",
        lambda *args: ["test scheme query"]
    )

    # Mock Tavily results
    monkeypatch.setattr(
        pipeline,
        "search_web",
        lambda *args: [
            {
                "title": "Test Scheme",
                "url": "https://example.gov.in/scheme",
                "content": "Test scheme information"
            }
        ]
    )

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    # Mock Gemini client
    mock_client = Mock()

    monkeypatch.setattr(
        pipeline.genai,
        "Client",
        lambda **kwargs: mock_client
    )

    # Simulate Gemini extraction failure
    def fail_extraction(*args, **kwargs):
        raise RuntimeError("Gemini extraction failed")

    monkeypatch.setattr(
        pipeline,
        "extract_schemes",
        fail_extraction
    )

    # Verify exception propagation and client cleanup
    with pytest.raises(
        RuntimeError,
        match="Gemini extraction failed"
    ):
        asyncio.run(
            pipeline.discover_schemes({})
        )

    mock_client.close.assert_called_once()
def test_tavily_failure_does_not_crash_pipeline(monkeypatch):
    import asyncio
    import discovery_agent.discovery_pipeline as pipeline

    monkeypatch.setattr(
        pipeline,
        "build_search_queries",
        lambda *args: ["query one", "query two"]
    )

    call_count = 0

    def failing_search(*args):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Tavily unavailable")

    monkeypatch.setattr(
        pipeline,
        "search_web",
        failing_search
    )

    result = asyncio.run(
        pipeline.discover_schemes({})
    )

    assert result == []
    assert call_count == 2
def test_multiple_schemes_extracted():
    from discovery_agent.scheme_schema import SchemeRecord

    schemes = [
        SchemeRecord(
            id="scheme-1",
            name="PM Fasal Bima Yojana",
            description="Crop insurance scheme",
            benefits=["Crop insurance"],
            target_groups=["Farmers"]
        ),
        SchemeRecord(
            id="scheme-2",
            name="PM-KISAN",
            description="Income support scheme",
            benefits=["Financial assistance"],
            target_groups=["Farmers"]
        )
    ]

    assert len(schemes) == 2
    assert schemes[0].name == "PM Fasal Bima Yojana"
    assert schemes[1].name == "PM-KISAN"
    assert all(isinstance(scheme, SchemeRecord) for scheme in schemes)
import pytest
from unittest.mock import patch

from discovery_agent.discovery_pipeline import discover_schemes
from discovery_agent.scheme_schema import SchemeRecord


@pytest.mark.parametrize(
    "search_scope",
    ["guided", "all"]
)
@pytest.mark.parametrize(
    "user_context",
    [
        {
            "employment": {"occupation": "farmer"},
            "location": {"district": "Mandya", "state": "Karnataka"},
            "interests": ["crop insurance"]
        },
        {
            "employment": {"occupation": "student"},
            "location": {"district": "Bengaluru", "state": "Karnataka"},
            "interests": ["education", "scholarships"]
        }
    ]
)
@pytest.mark.anyio
async def test_discovery_across_scopes_and_user_contexts(
    search_scope,
    user_context
):
    mock_results = [
        {
            "title": "Government Scheme",
            "url": "https://example.gov.in/scheme",
            "content": "Government scheme information for eligible beneficiaries."
        }
    ]

    mock_scheme = SchemeRecord(
        id="TEST001",
        name="Test Government Scheme",
        description="A test scheme",
        discovery_source="live_search"
    )

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        return_value=mock_results
    ), patch(
        "discovery_agent.discovery_pipeline.extract_schemes",
        return_value=[mock_scheme]
    ):
        results = await discover_schemes(
            user_context,
            search_scope=search_scope
        )

    assert isinstance(results, list)
    assert all(isinstance(s, SchemeRecord) for s in results)
    assert len(results) >= 1

@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("Search request timed out"),
        Exception("429 Too Many Requests")
    ],
    ids=["timeout", "rate_limit"]
)
async def test_discovery_handles_timeout_and_rate_limit(failure):
    user_context = {
        "employment": {"occupation": "farmer"},
        "location": {
            "district": "Mandya",
            "state": "Karnataka"
        },
        "interests": ["crop insurance"]
    }

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        side_effect=failure
    ):
        results = await discover_schemes(
            user_context,
            search_scope="guided"
        )

    assert isinstance(results, list)
    assert results == []

@pytest.mark.anyio
async def test_discovery_handles_malformed_search_results():
    user_context = {
        "employment": {"occupation": "farmer"},
        "location": {
            "district": "Mandya",
            "state": "Karnataka"
        },
        "interests": ["crop insurance"]
    }

    malformed_results = [
        None,
        {},
        {"title": "Missing URL and content"},
        {"url": None, "content": None}
    ]

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        return_value=malformed_results
    ), patch(
        "discovery_agent.discovery_pipeline.extract_schemes",
        return_value=[]
    ):
        results = await discover_schemes(
            user_context,
            search_scope="guided"
        )

    assert isinstance(results, list)


def test_scheme_record_rejects_malformed_gemini_output():
    from pydantic import ValidationError

    malformed_outputs = [
        {},
        {"id": "TEST001"},
        {"name": 123},
    ]

    for output in malformed_outputs:
        try:
            SchemeRecord(**output)
        except ValidationError:
            continue

        raise AssertionError(
            f"Malformed output was accepted: {output}"
        )

@pytest.mark.anyio
async def test_discovery_returns_multiple_schemes_in_one_run():
    user_context = {
        "employment": {"occupation": "farmer"},
        "location": {
            "district": "Mandya",
            "state": "Karnataka"
        },
        "interests": [
            "crop insurance",
            "irrigation assistance"
        ]
    }

    mock_results = [
        {
            "title": "PM Fasal Bima Yojana",
            "url": "https://pmfby.gov.in",
            "content": "Crop insurance scheme for farmers."
        },
        {
            "title": "PM Krishi Sinchai Yojana",
            "url": "https://pmksy.gov.in",
            "content": "Irrigation assistance for farmers."
        }
    ]

    mock_schemes = [
        SchemeRecord(
            id="TEST001",
            name="PM Fasal Bima Yojana",
            description="Crop insurance scheme",
            discovery_source="live_search"
        ),
        SchemeRecord(
            id="TEST002",
            name="PM Krishi Sinchai Yojana",
            description="Irrigation assistance scheme",
            discovery_source="live_search"
        )
    ]

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        return_value=mock_results
    ), patch(
        "discovery_agent.discovery_pipeline.extract_schemes",
        return_value=mock_schemes
    ):
        results = await discover_schemes(
            user_context,
            search_scope="guided"
        )

    assert isinstance(results, list)
    assert len(results) == 2

    scheme_names = {scheme.name for scheme in results}

    assert "PM Fasal Bima Yojana" in scheme_names
    assert "PM Krishi Sinchai Yojana" in scheme_names
