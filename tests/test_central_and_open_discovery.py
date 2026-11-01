"""
tests/test_central_and_open_discovery.py — Tests for open domain search,
balanced central/state query planning, and central scheme applicability.
"""
from unittest.mock import MagicMock, Mock
import pytest

from discovery_agent.discovery_pipeline import (
    build_search_queries,
    generate_search_queries_with_llm,
)
from discovery_agent.scheme_details import other_state, CENTRAL_JURISDICTIONS
from discovery_agent.search_provider import search_web, is_official_government_url
from discovery_agent.scheme_extractor import extract_schemes, calculate_verification_status


def test_is_official_government_url_classification():
    """Verify that official gov domains are accurately recognized."""
    assert is_official_government_url("https://pmkisan.gov.in/portal") is True
    assert is_official_government_url("https://karnataka.gov.in/schemes") is True
    assert is_official_government_url("https://agricoop.nic.in/guidelines") is True
    assert is_official_government_url("https://myscheme.gov.in/find") is True
    # Non-government domains
    assert is_official_government_url("https://vikaspedia.in/agriculture") is False
    assert is_official_government_url("https://newsportal.com/schemes") is False
    assert is_official_government_url("https://randomblog.org/pmkisan") is False


def test_search_web_open_domain_does_not_restrict(monkeypatch):
    """Verify search_web does not pass restrict filter and retains both gov and non-gov sources."""
    captured_kwargs = {}

    class FakeTavilyClient:
        def search(self, **kwargs):
            captured_kwargs.update(kwargs)
            return {
                "results": [
                    {
                        "title": "Official Portal",
                        "url": "https://agricoop.gov.in/scheme",
                        "content": "Official guidelines text.",
                        "score": 0.95,
                        "raw_content": "Official guidelines text.",
                    },
                    {
                        "title": "Informational Blog",
                        "url": "https://agri-info.org/pmkisan-explained",
                        "content": "Explanation for farmers.",
                        "score": 0.85,
                        "raw_content": "Explanation for farmers.",
                    },
                ]
            }

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr("discovery_agent.search_provider._get_tavily_client", lambda: FakeTavilyClient())

    results = search_web("farmer schemes", max_results=10)

    # Confirm Tavily was NOT called with include_domains restrict mode
    assert "include_domains" not in captured_kwargs
    assert "include_domains_mode" not in captured_kwargs

    # Confirm BOTH results survived
    assert len(results) == 2
    official = next(r for r in results if r["url"] == "https://agricoop.gov.in/scheme")
    assert official["is_official"] is True
    unofficial = next(r for r in results if r["url"] == "https://agri-info.org/pmkisan-explained")
    assert unofficial["is_official"] is False


def test_build_search_queries_expanded_central():
    """Verify expanded query building emits balanced Central and State tracks without district pinning."""
    profile = {
        "employment": {"occupation": "farmer"},
        "location": {"district": "Mandya", "state": "Karnataka"},
        "interests": ["crop insurance", "drip irrigation"],
    }
    queries = build_search_queries(profile, search_scope="guided", expand_central=True)

    assert len(queries) >= 4
    # Central track checks: must mention Central/India, must NOT pin to district
    central_queries = [q for q in queries if "Central" in q]
    assert len(central_queries) >= 2
    assert all("Mandya" not in q for q in central_queries)
    assert any("crop insurance" in q for q in central_queries)

    # State track checks: must mention Karnataka
    state_queries = [q for q in queries if "Karnataka" in q]
    assert len(state_queries) >= 2


def test_llm_query_planner_generates_queries(monkeypatch):
    """Verify generate_search_queries_with_llm parses JSON queries from Gemini."""
    fake_client = Mock()
    fake_client.models = Mock()
    fake_response = Mock()
    fake_response.text = '{"queries": ["Central schemes for farmers India", "Karnataka agriculture subsidies"]}'
    fake_client.models.generate_content.return_value = fake_response

    profile = {"occupation": "farmer", "state": "Karnataka"}
    queries = generate_search_queries_with_llm(fake_client, "model", profile, search_scope="guided")

    assert len(queries) == 2
    assert "Central schemes for farmers India" in queries
    assert "Karnataka agriculture subsidies" in queries


def test_other_state_jurisdiction_preserves_central_schemes():
    """Verify other_state never drops central schemes across all common synonyms."""
    for synonym in CENTRAL_JURISDICTIONS:
        rec = {"jurisdiction": synonym, "government_level": "unknown"}
        assert other_state(rec, "Karnataka") is False, f"Failed for synonym: {synonym}"

    # Also when government_level is explicit central
    assert other_state({"government_level": "central", "jurisdiction": "some_region"}, "Karnataka") is False

    # State scheme matching user state
    assert other_state({"jurisdiction": "Karnataka"}, "Karnataka") is False
    assert other_state({"jurisdiction": "karnataka"}, "Karnataka") is False

    # True other state scheme: MUST be filtered out
    assert other_state({"jurisdiction": "Maharashtra"}, "Karnataka") is True
    assert other_state({"jurisdiction": "Tamil Nadu"}, "Karnataka") is True


def test_calculate_verification_status_handles_uncertain():
    """Verify that claims from non-official sources result in uncertain status."""
    claims = [
        {"claim": "Benefit 1", "verification_status": "uncertain"},
        {"claim": "Benefit 2", "verification_status": "uncertain"},
    ]
    status = calculate_verification_status(claims, [0, 1])
    assert status == "uncertain"

    # Mixed verified and uncertain
    mixed = [
        {"claim": "Benefit 1", "verification_status": "verified"},
        {"claim": "Benefit 2", "verification_status": "uncertain"},
    ]
    status_mixed = calculate_verification_status(mixed, [0, 1])
    assert status_mixed == "partially_verified"


def test_haryana_vs_karnataka_normalization_and_assessment():
    """1. Test that Haryana conditions are mapped to state == 'Haryana' and automatically assessed as not_satisfied for Karnataka resident."""
    from member2.normalize import _canonical_rule
    from member2.assess import assess_requirement, assess_scheme, as_answer_map
    from member2.models import Requirement, RequirementVerification, RequirementStatus, SchemeRecord, SchemeStatus, Operator

    # Normalization should map Haryana to state attribute, not unmapped:haryana
    attr, op, val = _canonical_rule("haryana", None, "resident of Haryana", fallback_slug="haryana")
    assert attr == "state"
    assert op == Operator.eq
    assert val == "Haryana"

    # User profile has Karnataka domicile
    answers = as_answer_map({"domicile_karnataka": {"attribute": "domicile_karnataka", "state": "answered", "value": True}})
    assert answers["state"].value == "Karnataka"

    req = Requirement(
        id="r_haryana",
        attribute="state",
        criterion="Must be a permanent resident of Haryana",
        operator=Operator.eq,
        value="Haryana",
        status=RequirementVerification.verified,
    )
    result = assess_requirement(req, answers)
    assert result.status == RequirementStatus.not_satisfied

    # Scheme with this requirement must be assessed as unlikely_to_match
    scheme = SchemeRecord(
        id="scheme_haryana",
        name="Haryana State Scholarship",
        requirements=[req],
    )
    assessment = assess_scheme(scheme, answers)
    assert assessment.status == SchemeStatus.unlikely_to_match


def test_haryana_question_never_asked_to_karnataka_user():
    """1b. Test that questions regarding Haryana or other states are never generated for Karnataka resident."""
    from member2.questions import generate_consolidated_questions
    from member2.models import SchemeRecord, Requirement, RequirementVerification, Operator

    scheme = SchemeRecord(
        id="scheme_haryana",
        name="Haryana Scholarship",
        requirements=[
            Requirement(
                id="r1",
                attribute="state",
                criterion="Must be a resident of Haryana",
                operator=Operator.eq,
                value="Haryana",
                status=RequirementVerification.verified,
            )
        ],
    )
    answers = {"domicile_karnataka": {"attribute": "domicile_karnataka", "state": "answered", "value": True}}
    qs = generate_consolidated_questions([scheme], answers)
    assert not any("haryana" in q.question.lower() or q.attribute == "state" for q in qs)

    # Even if an unmapped condition mentioning Haryana is present
    scheme_unmapped = SchemeRecord(
        id="scheme_unmapped_haryana",
        name="Some Scheme",
        requirements=[
            Requirement(
                id="r2",
                attribute="unmapped:resident_of_haryana",
                criterion="Must be resident of Haryana",
                operator=Operator.is_true,
                status=RequirementVerification.verified,
            )
        ],
    )
    qs_unmapped = generate_consolidated_questions([scheme_unmapped], answers)
    assert not any("haryana" in q.question.lower() or "haryana" in q.attribute.lower() for q in qs_unmapped)


def test_verification_status_mismatch_tolerance():
    """3. Test that verification status 'uncertain' and variations are accepted safely without dropping records."""
    from discovery_agent.scheme_schema import SchemeRecord as AgentSchemeRecord, SchemeClaim, SchemeCriterion

    claim = SchemeClaim(
        category="eligibility",
        claim="Applicant must be enrolled in college",
        verification_status="uncertain",
    )
    assert claim.verification_status == "uncertain"

    crit = SchemeCriterion(
        description="Enrolled in higher education",
        verification_status="uncertain",
    )
    assert crit.verification_status == "uncertain"

    scheme = AgentSchemeRecord(
        id="test_scheme_uncertain",
        name="Test Welfare Scheme",
        verification_status="uncertain",
        claims=[claim],
        eligibility_criteria=[crit],
    )
    assert scheme.verification_status == "uncertain"


def test_invalid_scheme_record_salvaged():
    """4. Test that malformed sub-items do not cause entire scheme (e.g. Vidyasiri) to be discarded."""
    from discovery_agent.scheme_extractor import sanitize_and_salvage_scheme
    from discovery_agent.scheme_schema import SchemeRecord as AgentSchemeRecord

    # Simulate raw extracted scheme with 1 valid criterion, 1 broken criterion, and 1 broken document
    raw_scheme = {
        "id": "vidyasiri_epass",
        "name": "Vidyasiri Scholarship",
        "eligibility_criteria": [
            {
                "description": "Family income below 2.5 lakhs",
                "kind": "eligibility",
                "verification_status": "verified",
            },
            {
                # Broken criterion: missing description (triggers validation error)
                "kind": "invalid_kind_value",
            },
        ],
        "documents": [
            {"name": "Income Certificate", "mandatory": True},
            {"name": ""},  # Empty document name
        ],
        "benefits": "Rs 1500 per month",  # string instead of list
        "government_level": "state_gov_invalid",
    }

    salvaged = sanitize_and_salvage_scheme(raw_scheme)
    assert salvaged is not None
    assert isinstance(salvaged, AgentSchemeRecord)
    assert salvaged.name == "Vidyasiri Scholarship"
    assert len(salvaged.eligibility_criteria) == 1
    assert salvaged.eligibility_criteria[0].description == "Family income below 2.5 lakhs"
    assert len(salvaged.documents) == 1
    assert salvaged.documents[0].name == "Income Certificate"
    assert salvaged.government_level == "unknown"


def test_can_verify_for_state_source_authority():
    """5. Test that other state domains and non-official domains cannot verify Karnataka eligibility."""
    from discovery_agent.scheme_extractor import can_verify_for_state

    # Karnataka official portals
    assert can_verify_for_state("https://karnataka.gov.in/schemes", is_official=True, target_state="karnataka") is True
    assert can_verify_for_state("https://karepass.cgg.gov.in", is_official=True, target_state="karnataka") is True

    # Central official portals
    assert can_verify_for_state("https://scholarships.gov.in/main", is_official=True, target_state="karnataka") is True
    assert can_verify_for_state("https://pmkisan.gov.in/portal", is_official=True, target_state="karnataka") is True

    # Other state portals CANNOT verify Karnataka
    assert can_verify_for_state("https://haryana.gov.in/schemes", is_official=True, target_state="karnataka") is False
    assert can_verify_for_state("https://punjab.gov.in/scholarship", is_official=True, target_state="karnataka") is False

    # Private portals CANNOT verify
    assert can_verify_for_state("https://buddy4study.com/scholarship", is_official=False, target_state="karnataka") is False


def test_application_deadlines_checked_against_current_date():
    """7. Test that expired deadlines (e.g. 2026-10-31 when today is 2026-11-01) are marked expired."""
    from discovery_agent.scheme_extractor import check_deadline

    official_sources = {
        "https://karnataka.gov.in/portal": {"is_official": True},
        "https://private-blog.com": {"is_official": False},
    }

    # Expired date
    dl, status = check_deadline("2026-10-31", "https://karnataka.gov.in/portal", official_sources)
    assert status == "expired"
    assert dl == "2026-10-31"

    # Future date
    dl_fut, status_fut = check_deadline("2026-12-31", "https://karnataka.gov.in/portal", official_sources)
    assert status_fut == "upcoming"
    assert dl_fut == "2026-12-31"

    # Deadline without official source backing is not published
    dl_unofficial, status_unofficial = check_deadline("2026-12-31", "https://private-blog.com", official_sources)
    assert status_unofficial == "not_published"
    assert dl_unofficial is None


def test_document_requirements_carried_into_action_plan():
    """8. Test that mandatory vs optional flags and document sources are carried forward into Agent 3."""
    from discovery_agent.adapter import to_canonical_scheme
    from member2.planning import build_action_plan

    raw_scheme = {
        "id": "vidyasiri_hostel",
        "name": "Vidyasiri Hostel Scheme",
        "official_sources": ["https://karnataka.gov.in/hostel"],
        "documents": [
            {
                "name": "Caste Certificate",
                "mandatory": True,
                "source_url": "https://karnataka.gov.in/hostel",
                "evidence": "Applicants must submit valid Caste Certificate.",
            },
            {
                "name": "Income Certificate (Optional if BPL card attached)",
                "mandatory": False,
                "source_url": "https://karnataka.gov.in/hostel",
                "evidence": "Income Certificate (Optional if BPL card attached).",
            },
        ],
    }

    canonical = to_canonical_scheme(raw_scheme)
    assert len(canonical.documents) == 2
    assert canonical.documents[0].mandatory is True
    assert canonical.documents[1].mandatory is False

    plan = build_action_plan([canonical])
    assert len(plan.checklist) == 2
    caste_item = next(c for c in plan.checklist if "caste" in c.name.lower())
    assert caste_item.mandatory is True
    income_item = next(c for c in plan.checklist if "income" in c.name.lower())
    assert income_item.mandatory is False

