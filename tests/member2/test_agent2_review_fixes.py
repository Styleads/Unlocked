"""Regression tests for the code review of the Agent 2 improvements (d0d3c90): each pins a way the new logic could
turn an unknown or a disqualifier into a match, or invent an answer the user never gave."""
from __future__ import annotations

import pytest

from api.schemas import UserProfileInput
from member2.assess import assess_scheme
from member2.comparators import evaluate
from member2.models import (
    Answer,
    AnswerState,
    Operator,
    Requirement,
    RequirementCategory,
    RequirementStatus,
    RequirementVerification,
    SchemeRecord,
    SchemeStatus,
    VerificationStatus,
)
from member2.normalize import _canonical_rule, classify_requirement_category, is_portal_registration
from member2.questions import apply_answers

SRC = "https://example.gov.in/demo"


def req(rid, attribute, criterion, operator, value, category=RequirementCategory.eligibility, evidence="Demo evidence.", status=RequirementVerification.verified):
    return Requirement(id=rid, attribute=attribute, criterion=criterion, operator=operator, value=value, status=status,
                       source_url=SRC, evidence=evidence, category=category)


def scheme(*reqs):
    return SchemeRecord(id="demo", name="Demo Scheme", requirements=list(reqs), verification_status=VerificationStatus.verified)


def ans(**kw):
    return {k: Answer(attribute=k, state=AnswerState.answered, value=v) for k, v in kw.items()}


def ev(op, rule, value):
    """Compare a stored answer with a rule, the way assessment does."""
    return evaluate(op, rule, Answer(attribute="social_category", state=AnswerState.answered, value=value))


# --- comparators: a substring is not a match -------------------------------------------------------------------------

@pytest.mark.parametrize("answer,rule", [("Non-OBC", "OBC"), ("Government-aided", "Government"), ("General Merit", "General"), ("Not Karnataka", "Karnataka")])
def test_a_longer_option_never_equals_a_shorter_one_inside_it(answer, rule):
    assert ev(Operator.eq, rule, answer)[0] == RequirementStatus.not_satisfied
    assert ev(Operator.neq, rule, answer)[0] == RequirementStatus.satisfied


def test_membership_does_not_accept_a_prefix_of_a_listed_option():
    assert ev(Operator.in_, ["Other backward classes", "Scheduled caste"], "Other")[0] == RequirementStatus.not_satisfied


def test_a_compound_option_still_matches_on_any_phrase_it_lists():
    assert ev(Operator.eq, "SC/ST", "SC")[0] == RequirementStatus.satisfied
    assert ev(Operator.in_, ["BPL or APL", "Antyodaya"], "APL")[0] == RequirementStatus.satisfied


# --- classification: the rule decides, never its evidence paragraph ------------------------------------------------------

def test_a_limit_is_not_demoted_to_a_procedure_by_words_in_its_evidence():
    evidence = "Apply online on the portal after e-KYC. Annual family income must not exceed Rs 3 lakh."
    assert classify_requirement_category("Annual family income up to Rs 3 lakh", "annual_family_income", evidence) == RequirementCategory.eligibility


def test_a_failed_income_limit_still_rules_the_scheme_out_whatever_its_evidence_says():
    category = classify_requirement_category("Annual family income up to Rs 3 lakh", "annual_family_income",
                                              "Apply online. Register on the portal. Income up to Rs 3 lakh.")
    s = scheme(req("r1", "annual_family_income", "Annual family income up to Rs 3 lakh", Operator.lte, 300000, category=category))
    assert assess_scheme(s, ans(annual_family_income={"min": 500000, "max": 500000})).status == SchemeStatus.unlikely_to_match


def test_real_procedures_are_still_recognised():
    assert classify_requirement_category("Must be registered on the portal", None) == RequirementCategory.application_prerequisite
    assert classify_requirement_category("Complete basic training", "unmapped:training") == RequirementCategory.post_approval


# --- roll-up -----------------------------------------------------------------------------------------------------------

def test_an_unverified_prerequisite_keeps_the_scheme_at_not_yet_verified():
    s = scheme(
        req("r1", "age", "Age 18 or above", Operator.gte, 18),
        req("r2", "portal_registration", "Must register on the portal", Operator.is_true, None,
            category=RequirementCategory.application_prerequisite, status=RequirementVerification.unverified),
    )
    assert assess_scheme(s, ans(age=20)).status == SchemeStatus.not_yet_verified


def test_a_scheme_with_only_procedural_rules_is_never_a_match():
    s = scheme(req("r1", "portal_registration", "Registered on the portal", Operator.is_true, None, category=RequirementCategory.application_prerequisite))
    assert assess_scheme(s, {}).status != SchemeStatus.potential_match


def test_an_unknown_post_approval_rule_is_unknown_not_satisfied():
    s = scheme(
        req("r1", "age", "Age 18 or above", Operator.gte, 18),
        req("r2", "unmapped:basic_training", "Complete basic training", None, None, category=RequirementCategory.post_approval),
    )
    by_id = {r.requirement_id: r.status for r in assess_scheme(s, ans(age=20)).requirements}
    assert by_id["r2"] == RequirementStatus.unknown


def test_procedural_steps_are_not_listed_as_missing_information():
    s = scheme(
        req("r1", "age", "Age 18 or above", Operator.gte, 18),
        req("r2", "portal_registration", "Register on the portal", Operator.is_true, None, category=RequirementCategory.application_prerequisite),
    )
    assert "portal_registration" not in assess_scheme(s, ans(age=20)).missing_attributes


# --- normalisation keeps what the model extracted ------------------------------------------------------------------------

def test_an_extracted_operator_and_value_are_not_replaced_by_canned_ones():
    attr, op, _ = _canonical_rule("is_micro_enterprise", "is_false", False, "not_micro")
    assert (attr, op) == ("is_micro_enterprise", Operator.is_false)
    assert _canonical_rule("is_micro_enterprise", None, None, "micro")[1] == Operator.is_true  # defaults only fill a gap


@pytest.mark.parametrize("name,expected", [
    ("portal_registration", True), ("unmapped:registration", True), ("registered_on_portal", True),
    ("gst_registration", False), ("birth_registration_certificate", False), ("vishwakarma_trade_list", False),
])
def test_only_a_plain_portal_registration_is_remapped(name, expected):
    assert is_portal_registration(name) is expected


# --- profile seeding invents nothing -----------------------------------------------------------------------------------------

def seeded(**profile):
    return {s["attribute"]: s["value"] for s in UserProfileInput(**profile).extract_seedable_attributes()}


def test_citizenship_is_never_assumed():
    assert "citizenship" not in seeded(state="Karnataka", age=30)


def test_a_trade_does_not_make_someone_a_micro_enterprise():
    got = seeded(state="Karnataka", occupation="tailor")
    assert "is_micro_enterprise" not in got and "business_ownership" not in got
    assert "employment_status" not in got  # a tailor may be employed: that is asked, not guessed
    assert got["occupation"] == "tailor"


def test_living_in_another_state_is_not_domicile_there():
    assert "domicile_state" not in seeded(state="Tamil Nadu")


@pytest.mark.parametrize("category,expected", [("Category 1", "Category 1"), ("1", "Category 1"), ("2A", "Category 2A"), ("OBC 12", None), ("Class 11 student", None)])
def test_karnataka_caste_category_only_matches_a_real_category(category, expected):
    assert seeded(state="Karnataka", caste_category=category).get("karnataka_caste_category") == expected


# --- answers -------------------------------------------------------------------------------------------------------------------

def test_prefer_not_to_say_withdraws_an_earlier_answer_but_not_sure_does_not():
    answers, _ = apply_answers({}, {}, [{"attribute": "age", "state": "answered", "value": 31}])
    kept, _ = apply_answers(answers, {}, [{"attribute": "age", "state": "unknown"}])
    assert kept["age"].state == AnswerState.answered  # "not sure" never destroys a known answer
    withdrawn, _ = apply_answers(answers, {}, [{"attribute": "age", "state": "prefer_not_to_answer"}])
    assert withdrawn["age"].state == AnswerState.prefer_not_to_answer and withdrawn["age"].value is None
