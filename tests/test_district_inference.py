"""
tests/test_district_inference.py — Test Karnataka district and domicile resolution.
"""
from member2.attributes import is_karnataka_district, resolve_attribute
from member2.assess import assess_requirement
from member2.models import Answer, AnswerState, Operator, Requirement, RequirementVerification, RequirementStatus
from api.schemas import UserProfileInput


def test_karnataka_district_recognition():
    assert is_karnataka_district("Dharwad") is True
    assert is_karnataka_district("dharwad") is True
    assert is_karnataka_district("Mandya") is True
    assert is_karnataka_district("Bengaluru Urban") is True
    assert is_karnataka_district("Bangalore") is True
    assert is_karnataka_district("Belagavi") is True
    assert is_karnataka_district("Mysuru") is True
    assert is_karnataka_district("Pune") is False
    assert is_karnataka_district("Chennai") is False
    assert is_karnataka_district("") is False
    assert is_karnataka_district(None) is False


def test_resolve_attribute_karnataka_aliases():
    assert resolve_attribute("domicile_karnataka") == "domicile_karnataka"
    assert resolve_attribute("karnataka") == "domicile_karnataka"
    assert resolve_attribute("in karnataka") == "domicile_karnataka"
    assert resolve_attribute("resident in karnataka") == "domicile_karnataka"
    assert resolve_attribute("state") == "state"
    assert resolve_attribute("state of residence") == "state"


def test_user_profile_district_seeds_karnataka_and_domicile():
    profile = UserProfileInput(
        name="Priyanka Naik",
        occupation="student",
        district="Dharwad",
        annual_income=180000,
        social_category="SC",
    )
    ctx = profile.to_user_context()
    assert ctx["location"]["state"] == "Karnataka"
    assert ctx["location"]["district"] == "Dharwad"

    seeds = profile.extract_seedable_attributes()
    seed_map = {s["attribute"]: s["value"] for s in seeds}
    assert seed_map.get("state") == "Karnataka"
    assert seed_map.get("domicile_karnataka") is True
    assert seed_map.get("district") == "Dharwad"
    assert seed_map.get("social_category") == "SC"


def test_user_profile_state_karnataka_seeds_domicile():
    profile = UserProfileInput(
        name="Basavaraj",
        occupation="farmer",
        state="Karnataka",
        district="Mandya",
    )
    seeds = profile.extract_seedable_attributes()
    seed_map = {s["attribute"]: s["value"] for s in seeds}
    assert seed_map.get("state") == "Karnataka"
    assert seed_map.get("domicile_karnataka") is True


def test_unmapped_karnataka_condition_satisfied_for_karnataka_resident():
    req = Requirement(
        id="req_kn_1",
        attribute="unmapped:karnataka",
        criterion="Eligible students in Karnataka",
        operator=None,
        value="Karnataka",
        status=RequirementVerification.verified,
    )
    answers = {
        "domicile_karnataka": Answer(attribute="domicile_karnataka", state=AnswerState.answered, value=True),
        "state": Answer(attribute="state", state=AnswerState.answered, value="Karnataka"),
    }
    res = assess_requirement(req, answers)
    assert res.status == RequirementStatus.satisfied
    assert "resident of Karnataka" in res.reason

