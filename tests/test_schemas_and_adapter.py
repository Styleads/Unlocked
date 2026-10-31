"""
tests/test_schemas_and_adapter.py — Tests for api/schemas.py and api/adapter.py.
"""
import pytest
from api.schemas import (
    HealthResponse,
    UserProfileInput,
    CreateSessionRequest,
    SessionResponse,
    FullSessionState,
    DiscoverOptions,
    DiscoveryResult,
    SchemeView,
    SubmitAnswersRequest,
    AnswerInput,
    ReassessmentResult,
    UpdateDocStatusRequest,
    DocStatus,
    AnswerState,
)
from api.adapter import (
    adapt_m1_to_m2_scheme,
    adapt_m1_to_m2_schemes,
    to_canonical_scheme,
    to_canonical_schemes,
)
from member2.models import SchemeRecord, Operator, RequirementVerification


def test_user_profile_flat_to_context():
    profile = UserProfileInput(
        occupation="farmer",
        state="Karnataka",
        district="Mandya",
        annual_income=180000,
        interests=["crop insurance", "irrigation"],
    )
    ctx = profile.to_user_context()
    assert ctx["employment"]["occupation"] == "farmer"
    assert ctx["location"]["state"] == "Karnataka"
    assert ctx["location"]["district"] == "Mandya"
    assert ctx["household"]["annual_income"] == 180000
    assert "crop insurance" in ctx["interests"]


def test_user_profile_seedable_attributes():
    profile = UserProfileInput(
        occupation="student",
        state="Karnataka",
        district="Bengaluru Urban",
        annual_family_income=200000,
        social_category="OBC",
        age=21,
    )
    seeds = profile.extract_seedable_attributes()
    seed_dict = {s["attribute"]: s for s in seeds}

    assert "state" in seed_dict
    assert seed_dict["state"]["value"] == "Karnataka"
    assert "district" in seed_dict
    assert "annual_family_income" in seed_dict
    assert "social_category" in seed_dict
    assert "employment_status" in seed_dict
    assert seed_dict["employment_status"]["value"] == "Student"
    assert "age" in seed_dict


def test_adapter_transforms_raw_dict():
    raw_m1 = {
        "id": "raw-ssp-001",
        "name": "State Scholarship Portal SSP",
        "description": "Post-matric scholarship",
        "target_groups": ["students", "SC/ST"],
        "eligibility_criteria": [
            {
                "description": "Annual income <= 250000",
                "related_attribute": "annual_income",
                "operator": "lte",
                "value": 250000,
                "verification_status": "verified",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
            },
            {
                "description": "Must be Karnataka resident",
                "related_attribute": "domicile_karnataka",
                "operator": "boolean",
                "value": True,
                "verification_status": "verified",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
            },
        ],
        "required_documents": ["Aadhaar Card", "Income Certificate"],
        "application_url": "https://ssp.postmatric.karnataka.gov.in",
        "verification_status": "verified",
    }

    scheme = adapt_m1_to_m2_scheme(raw_m1)
    assert isinstance(scheme, SchemeRecord)
    assert scheme.id == "raw-ssp-001"
    assert len(scheme.requirements) == 2

    # Check requirement attributes and operators
    req1 = scheme.requirements[0]
    assert req1.attribute == "annual_family_income"
    assert req1.operator == Operator.lte
    assert req1.value == 250000
    assert req1.status == RequirementVerification.verified

    req2 = scheme.requirements[1]
    assert req2.attribute == "domicile_karnataka"
    assert req2.operator == Operator.is_true

    # Check documents are structured with source_url and evidence
    assert len(scheme.documents) == 2
    for doc in scheme.documents:
        assert doc.source_url is not None
        assert doc.evidence is not None


def test_health_response_schema():
    health = HealthResponse(
        services={"gemini_configured": True, "tavily_configured": True, "sqlite_connected": True}
    )
    dumped = health.model_dump()
    assert dumped["status"] == "healthy"
    assert dumped["services"]["gemini_configured"] is True


def test_reassessment_result_schema():
    result = ReassessmentResult(
        session_id="sess-1",
        assessments=[],
        next_questions=[],
    )
    assert result.status == "reassessed"

