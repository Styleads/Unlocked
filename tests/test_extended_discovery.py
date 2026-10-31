"""
Comprehensive test suite for Project Unlocked Discovery Agent.

Covers all 17 mandatory testing requirements:
1. Guided Discovery
2. Discover All
3. Multiple user contexts (farmers, students, job seekers, small business, seniors)
4. Timeout handling
5. Rate-limit handling (HTTP 429)
6. Malformed search results
7. Malformed Gemini output
8. Multiple schemes in one run
9. Deduplication (URLs and scheme names)
10. Official-source classification
11. Evidence and claim verification
12. Empty results
13. Partial results (one query fails, others succeed)
14. Gemini failure
15. Fallback behaviour
16. Invalid profiles
17. Last verified timestamp
"""

import asyncio
from datetime import datetime
from unittest.mock import Mock, patch
import pytest

from discovery_agent.discovery_pipeline import (
    build_search_queries,
    deduplicate_results,
    discover_schemes,
    load_fallback_schemes,
)
from discovery_agent.fallback_schemes import get_fallback_schemes
from discovery_agent.scheme_extractor import (
    classify_relevance,
    deduplicate_schemes,
    extract_schemes,
    verify_claims,
)
from discovery_agent.scheme_schema import (
    SchemeClaim,
    SchemeCriterion,
    SchemeRecord,
    SourceEvidence,
)
from discovery_agent.search_provider import (
    classify_source,
    is_official_government_url,
)


# ============================================================
# 1. GUIDED DISCOVERY
# ============================================================

def test_guided_discovery_queries_focused_on_interests():
    """Guided discovery generates queries specifically matching stated interests."""
    profile = {
        "employment": {"occupation": "weaver"},
        "location": {"district": "Bagalkot", "state": "Karnataka"},
        "interests": ["handloom subsidy", "raw material assistance"]
    }
    queries = build_search_queries(profile, search_scope="guided")

    assert len(queries) == 2
    assert all("weaver" in q for q in queries)
    assert any("handloom subsidy" in q for q in queries)
    assert any("raw material assistance" in q for q in queries)
    assert all("Bagalkot, Karnataka" in q for q in queries)


# ============================================================
# 2. DISCOVER ALL
# ============================================================

def test_discover_all_broadens_queries_beyond_interests():
    """Discover All includes both interests and broad welfare/benefit searches."""
    profile = {
        "employment": {"occupation": "artisan"},
        "location": {"state": "Karnataka"},
        "interests": ["credit assistance"]
    }
    guided = build_search_queries(profile, search_scope="guided")
    broad = build_search_queries(profile, search_scope="all")

    # Broad query count must exceed guided query count
    assert len(broad) > len(guided)
    assert any("credit assistance" in q for q in broad)
    # Broad searches should include central/state welfare and financial support
    assert any("welfare schemes" in q for q in broad)
    assert any("financial assistance" in q for q in broad)


# ============================================================
# 3. MULTIPLE USER CONTEXTS
# ============================================================

@pytest.mark.parametrize(
    "occupation,district,interest",
    [
        ("farmer", "Mandya", "crop insurance"),
        ("student", "Mysuru", "higher education scholarship"),
        ("job seeker", "Bengaluru", "skill development"),
        ("small business owner", "Hubballi", "micro credit loan"),
        ("senior citizen", "Udupi", "old age pension"),
        ("woman entrepreneur", "Dharwad", "self help group loan"),
    ]
)
def test_queries_for_diverse_user_profiles(occupation, district, interest):
    """Pipeline builds appropriate queries for various demographic and occupational groups."""
    profile = {
        "employment": {"occupation": occupation},
        "location": {"district": district, "state": "Karnataka"},
        "interests": [interest]
    }
    queries = build_search_queries(profile, search_scope="guided")
    assert len(queries) >= 1
    assert occupation in queries[0]
    assert district in queries[0]
    assert interest in queries[0]


# ============================================================
# 4. TIMEOUT HANDLING
# ============================================================

@pytest.mark.anyio
async def test_search_timeout_handled_gracefully():
    """Tavily search timeout is caught and logged, returning empty results rather than crashing."""
    profile = {
        "employment": {"occupation": "farmer"},
        "location": {"state": "Karnataka"},
        "interests": ["irrigation"]
    }

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        side_effect=TimeoutError("Request timed out after 10s")
    ):
        results = await discover_schemes(profile, search_scope="guided")

    assert isinstance(results, list)
    assert results == []


# ============================================================
# 5. RATE-LIMIT HANDLING (HTTP 429)
# ============================================================

@pytest.mark.anyio
async def test_search_rate_limit_handled_without_crashing():
    """Tavily 429 Too Many Requests error does not crash the discovery pipeline."""
    profile = {
        "employment": {"occupation": "student"},
        "interests": ["scholarship"]
    }

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        side_effect=Exception("HTTP 429: Too Many Requests")
    ):
        results = await discover_schemes(profile, search_scope="guided")

    assert isinstance(results, list)
    assert results == []


# ============================================================
# 6. MALFORMED SEARCH RESULTS
# ============================================================

def test_deduplicate_results_handles_malformed_inputs():
    """Deduplication safely discards None, non-dict, missing url, and empty urls."""
    malformed_list = [
        None,
        "not a dict",
        {},
        {"title": "No URL here"},
        {"url": None},
        {"url": ""},
        {"url": "   "},
        {"url": "https://agri.karnataka.gov.in/scheme", "title": "Agri Scheme 1"},
        {"url": "https://agri.karnataka.gov.in/scheme/", "title": "Agri Scheme 1 dup"},
        {"url": "https://agri.karnataka.gov.in/scheme?param=1", "title": "Agri Scheme 1 with query"},
        {"url": "https://dept.karnataka.gov.in/other", "title": "Other Scheme"},
    ]
    cleaned = deduplicate_results(malformed_list)
    assert len(cleaned) == 2
    urls = {item["url"] for item in cleaned}
    assert "https://dept.karnataka.gov.in/other" in urls


# ============================================================
# 7. MALFORMED GEMINI OUTPUT
# ============================================================

def test_extract_schemes_handles_invalid_gemini_json():
    """Malformed or invalid JSON from Gemini results in an empty scheme list rather than an unhandled crash."""
    class BrokenClient:
        class Models:
            def generate_content(self, **kwargs):
                class Resp:
                    text = "This is NOT valid JSON {{"
                return Resp()
        models = Models()

    search_results = [{
        "title": "Government Portal",
        "url": "https://karnataka.gov.in/scheme",
        "content": "Official content about the scheme.",
        "is_official": True,
    }]

    schemes = extract_schemes(
        BrokenClient(),
        "fake-model",
        search_results,
        user_context={"employment": {"occupation": "farmer"}}
    )
    assert schemes == []


def test_extract_schemes_handles_non_dict_gemini_response():
    """When Gemini returns a JSON array instead of an object, it is safely handled."""
    class ListReturningClient:
        class Models:
            def generate_content(self, **kwargs):
                class Resp:
                    text = '["not", "a", "dict"]'
                return Resp()
        models = Models()

    search_results = [{
        "title": "Government Portal",
        "url": "https://karnataka.gov.in/scheme",
        "content": "Official content.",
        "is_official": True,
    }]

    schemes = extract_schemes(
        ListReturningClient(),
        "fake-model",
        search_results
    )
    assert schemes == []


# ============================================================
# 8. MULTIPLE SCHEMES IN ONE RUN
# ============================================================

@pytest.mark.anyio
async def test_extracts_and_returns_multiple_schemes_in_single_run():
    """A single discovery run can return multiple distinct SchemeRecord objects."""
    profile = {
        "employment": {"occupation": "farmer"},
        "location": {"district": "Mandya", "state": "Karnataka"},
        "interests": ["crop insurance", "irrigation"]
    }

    mock_schemes = [
        SchemeRecord(
            id="SCHEME-1",
            name="PM Fasal Bima Yojana",
            description="Crop insurance",
            government_level="central",
            discovery_source="live_search"
        ),
        SchemeRecord(
            id="SCHEME-2",
            name="Raitha Siri Scheme",
            description="Karnataka farmer support",
            government_level="state",
            discovery_source="live_search"
        ),
        SchemeRecord(
            id="SCHEME-3",
            name="Pradhan Mantri Krishi Sinchayee Yojana",
            description="Micro irrigation subsidy",
            government_level="central",
            discovery_source="live_search"
        ),
    ]

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        return_value=[{"title": "T", "url": "https://gov.in", "content": "C", "is_official": True}]
    ), patch(
        "discovery_agent.discovery_pipeline.extract_schemes",
        return_value=mock_schemes
    ):
        results = await discover_schemes(profile)

    assert len(results) == 3
    names = [s.name for s in results]
    assert "PM Fasal Bima Yojana" in names
    assert "Raitha Siri Scheme" in names
    assert "Pradhan Mantri Krishi Sinchayee Yojana" in names


# ============================================================
# 9. DEDUPLICATION
# ============================================================

def test_scheme_deduplication_removes_duplicate_names():
    """Duplicate schemes with identical or trivially different names are deduplicated."""
    schemes = [
        SchemeRecord(id="1", name="Pradhan Mantri Fasal Bima Yojana"),
        SchemeRecord(id="2", name="pradhan mantri fasal bima yojana"),
        SchemeRecord(id="3", name="PRADHAN MANTRI FASAL BIMA YOJANA!"),
        SchemeRecord(id="4", name="PM-KISAN Samman Nidhi"),
    ]
    unique = deduplicate_schemes(schemes)
    assert len(unique) == 2
    unique_names = {s.name for s in unique}
    assert "Pradhan Mantri Fasal Bima Yojana" in unique_names
    assert "PM-KISAN Samman Nidhi" in unique_names


# ============================================================
# 10. OFFICIAL-SOURCE CLASSIFICATION
# ============================================================

def test_official_source_classification():
    """Distinguishes official Indian government domains from commercial or blog URLs."""
    # Official domains
    assert is_official_government_url("https://karnataka.gov.in/dept") is True
    assert is_official_government_url("https://sw.kar.nic.in/scholarship") is True
    assert is_official_government_url("https://myscheme.gov.in/schemes/pmfby") is True
    assert is_official_government_url("https://pmkisan.gov.in") is True
    assert classify_source("https://pib.gov.in/release") == "official"

    # Non-official / secondary domains
    assert is_official_government_url("https://karnataka-schemes.blogspot.com") is False
    assert is_official_government_url("https://gov.in.fraud-site.com") is False
    assert is_official_government_url("https://timesofindia.indiatimes.com") is False
    assert is_official_government_url("https://wikipedia.org/wiki/Karnataka") is False
    assert is_official_government_url("") is False
    assert is_official_government_url(None) is False
    assert classify_source("https://newsportal.com/schemes") == "secondary"


# ============================================================
# 11. EVIDENCE AND CLAIM VERIFICATION
# ============================================================

def test_verify_claims_requires_exact_substring_in_source():
    """Claims are only verified when supported quotation is a literal substring of the source excerpt."""
    class VerifierClient:
        class Models:
            def generate_content(self, **kwargs):
                class Resp:
                    text = """
                    {
                        "claim_checks": [
                            {
                                "claim_index": 0,
                                "supported": true,
                                "source_url": "https://pmkisan.gov.in",
                                "supporting_excerpt": "Rs. 6000 per year transferred in three instalments",
                                "reason": "Explicitly stated in source."
                            },
                            {
                                "claim_index": 1,
                                "supported": true,
                                "source_url": "https://pmkisan.gov.in",
                                "supporting_excerpt": "Farmers receive free tractors every year",
                                "reason": "Invented claim"
                            }
                        ]
                    }
                    """
                return Resp()
        models = Models()

    claims = [
        {"category": "benefit", "claim": "Income support of Rs. 6000", "source_url": "https://pmkisan.gov.in"},
        {"category": "benefit", "claim": "Free tractor assistance", "source_url": "https://pmkisan.gov.in"},
    ]
    evidence = [
        {
            "title": "PM Kisan Portal",
            "url": "https://pmkisan.gov.in",
            "excerpt": "Under the scheme, Rs. 6000 per year transferred in three instalments directly to bank accounts."
        }
    ]

    verified = verify_claims(VerifierClient(), "fake-model", claims, evidence)

    # Claim 0 is verified because excerpt matches source
    assert 0 in verified
    assert verified[0]["source_url"] == "https://pmkisan.gov.in"

    # Claim 1 must NOT be verified because quote is not in source excerpt
    assert 1 not in verified


# ============================================================
# 12. EMPTY RESULTS
# ============================================================

@pytest.mark.anyio
async def test_empty_search_results_returns_empty_list():
    """When Tavily search returns 0 results and fallback is off, returns empty list without error."""
    profile = {"employment": {"occupation": "student"}}

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        return_value=[]
    ):
        schemes = await discover_schemes(profile, search_scope="guided", enable_fallback=False)

    assert schemes == []


# ============================================================
# 13. PARTIAL RESULTS
# ============================================================

@pytest.mark.anyio
async def test_partial_search_failure_returns_surviving_results():
    """If one query out of three fails, other queries still succeed and return schemes."""
    profile = {
        "employment": {"occupation": "farmer"},
        "location": {"state": "Karnataka"},
        "interests": ["crop insurance", "irrigation subsidy"]
    }

    call_index = 0

    def mock_search(query, limit=10):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            raise ConnectionError("Temporary network hiccup on query 1")
        return [{
            "title": "Irrigation Scheme",
            "url": "https://pmksy.gov.in",
            "content": "Government provides subsidy for drip irrigation systems.",
            "is_official": True,
        }]

    expected_scheme = SchemeRecord(
        id="PMKSY-001",
        name="PM Krishi Sinchayee Yojana",
        description="Drip irrigation assistance",
        discovery_source="live_search"
    )

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        side_effect=mock_search
    ), patch(
        "discovery_agent.discovery_pipeline.extract_schemes",
        return_value=[expected_scheme]
    ):
        results = await discover_schemes(profile, search_scope="guided")

    assert len(results) == 1
    assert results[0].name == "PM Krishi Sinchayee Yojana"


# ============================================================
# 14. GEMINI FAILURE
# ============================================================

@pytest.mark.anyio
async def test_gemini_extraction_failure_propagates_and_cleans_up():
    """Gemini API failure during extraction raises an exception and cleanly closes the client."""
    profile = {"employment": {"occupation": "farmer"}}

    mock_client = Mock()

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        return_value=[{"title": "T", "url": "https://gov.in", "content": "C", "is_official": True}]
    ), patch(
        "discovery_agent.discovery_pipeline.genai.Client",
        return_value=mock_client
    ), patch(
        "discovery_agent.discovery_pipeline.extract_schemes",
        side_effect=RuntimeError("Gemini quota exceeded or server unavailable")
    ):
        with pytest.raises(RuntimeError, match="Gemini quota exceeded"):
            await discover_schemes(profile)

    # Clean resource cleanup: client.close() MUST have been called
    mock_client.close.assert_called_once()


# ============================================================
# 15. FALLBACK BEHAVIOUR
# ============================================================

def test_fallback_collection_has_valid_attributes():
    """Fallback collection contains reliable, manually verified Karnataka-focused schemes with clear labels."""
    fallbacks = get_fallback_schemes()
    assert len(fallbacks) >= 4

    for s in fallbacks:
        # Must be explicitly labeled as fallback
        assert s.discovery_source == "fallback"
        # Must have verified or explicit source URLs
        assert s.official_url and s.official_url.startswith("https://")
        # Must include missing information warning that data needs rechecking
        assert any("rechecking" in m.lower() for m in s.missing_information)
        # Must have a last_verified date
        assert s.last_verified is not None


@pytest.mark.anyio
async def test_fallback_returned_when_live_search_yields_no_results():
    """When live search produces 0 results and enable_fallback=True, fallback schemes are returned."""
    profile = {
        "employment": {"occupation": "farmer"},
        "location": {"district": "Mandya", "state": "Karnataka"},
        "interests": ["crop insurance"]
    }

    with patch(
        "discovery_agent.discovery_pipeline.search_web",
        return_value=[]
    ):
        results = await discover_schemes(
            profile,
            search_scope="guided",
            enable_fallback=True
        )

    assert len(results) > 0
    assert all(s.discovery_source == "fallback" for s in results)
    names = [s.name for s in results]
    assert any("Fasal Bima" in n for n in names)


@pytest.mark.anyio
async def test_direct_fallback_search_scope():
    """Calling discover_schemes with search_scope='fallback' returns fallback collection directly."""
    profile = {
        "employment": {"occupation": "student"},
        "location": {"state": "Karnataka"},
        "interests": ["scholarship"]
    }
    results = await discover_schemes(profile, search_scope="fallback")
    assert len(results) > 0
    assert all(s.discovery_source == "fallback" for s in results)


# ============================================================
# 16. INVALID PROFILES
# ============================================================

def test_pipeline_handles_invalid_and_corrupt_profiles():
    """Functions gracefully handle empty dicts, missing keys, and invalid types."""
    # Completely empty profile
    queries1 = build_search_queries({}, search_scope="guided")
    assert len(queries1) >= 1
    assert "citizen" in queries1[0]
    assert "India" in queries1[0]

    # Non-dict employment and location
    corrupt_profile = {
        "employment": "not a dict",
        "location": 12345,
        "interests": None,
    }
    queries2 = build_search_queries(corrupt_profile, search_scope="guided")
    assert len(queries2) >= 1

    # Empty interests list
    queries3 = build_search_queries({"interests": []}, search_scope="guided")
    assert len(queries3) >= 1


# ============================================================
# 17. LAST VERIFIED TIMESTAMP
# ============================================================

def test_scheme_record_preserves_last_verified_timestamp():
    """SchemeRecord models serialize and preserve last_verified timestamp."""
    now_iso = datetime.now().isoformat()
    scheme = SchemeRecord(
        id="TEST-001",
        name="Karnataka Gruha Lakshmi Scheme",
        description="Financial assistance for women heads of household",
        government_level="state",
        department="Women and Child Development Department",
        last_verified=now_iso,
    )
    dumped = scheme.model_dump()
    assert dumped["last_verified"] == now_iso
    assert dumped["government_level"] == "state"
    assert dumped["department"] == "Women and Child Development Department"

