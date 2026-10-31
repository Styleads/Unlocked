import json
import re
from datetime import datetime, timezone

import pytest

from member2.assess import assess_requirement, assess_scheme, assess_schemes, reassess_schemes
from member2.attributes import ATTRIBUTES
from member2.models import (
    Answer,
    AnswerState,
    Requirement,
    RequirementStatus as R,
    SchemeRecord,
    SchemeStatus as S,
)

NON_ANSWERED = [s for s in AnswerState if s != AnswerState.answered]
SOURCE = "https://example.gov.in/demo/rules"


def answered(**values):
    return {k: Answer(attribute=k, state=AnswerState.answered, value=v) for k, v in values.items()}


def req(rid, attribute, operator, value, status="verified", source=SOURCE):
    return Requirement(id=rid, attribute=attribute, criterion=f"rule {rid}", operator=operator,
                       value=value, status=status, source_url=source, evidence=f"rule {rid}")


def scheme(*reqs, verification_status="verified"):
    return SchemeRecord(id="demo_x", name="Demo X", requirements=list(reqs), verification_status=verification_status)


# --- the invariant -----------------------------------------------------------

@pytest.mark.parametrize("state", NON_ANSWERED)
def test_invariant_non_answered_never_not_satisfied(schemes, state):
    answers = {a: Answer(attribute=a, state=state) for a in ATTRIBUTES}
    for s in schemes.values():
        a = assess_scheme(s, answers)
        assert a.status != S.unlikely_to_match
        assert all(r.status != R.not_satisfied for r in a.requirements)


def test_empty_answers_on_fixtures(schemes):
    by_id = {a.scheme_id: a for a in assess_schemes(schemes.values(), {})}
    assert by_id["demo_scholarship_a"].status == S.more_information_needed
    assert by_id["demo_fee_concession_b"].status == S.more_information_needed
    assert by_id["demo_merit_c"].status == S.more_information_needed
    assert by_id["demo_unverified_d"].status == S.not_yet_verified
    assert by_id["demo_scholarship_a"].missing_attributes == ["annual_family_income", "domicile_karnataka", "education_level"]


# --- outcomes ----------------------------------------------------------------

def test_conflict_with_verified_rule_is_unlikely(schemes):
    a = assess_scheme(schemes["demo_merit_c"], answered(previous_year_marks_percent=45))
    assert a.status == S.unlikely_to_match
    assert a.explanation.startswith(
        "Your answer about marks in last qualifying exam doesn't appear to meet this rule: "
        "'Minimum 60% marks in the previous qualifying examination.' This is"
    )


def test_all_satisfied_and_verified_is_potential_match(schemes):
    a = assess_scheme(
        schemes["demo_scholarship_a"],
        answered(annual_family_income={"min": 100000, "max": 200000}, domicile_karnataka=True, education_level="Undergraduate"),
    )
    assert a.status == S.potential_match
    assert a.missing_attributes == []


def test_satisfied_but_scheme_not_verified_is_not_yet_verified():
    s = scheme(req("r1", "age", "lte", 25), verification_status="not_verified")
    assert assess_scheme(s, answered(age=20)).status == S.not_yet_verified


def test_unverified_rule_with_conflicting_answer_is_not_yet_verified(schemes):
    a = assess_scheme(schemes["demo_unverified_d"], answered(age=40))
    assert a.status == S.not_yet_verified
    assert a.requirements[0].status == R.unverified
    assert "may not meet" in a.requirements[0].reason


def test_unverified_rule_never_unlikely_even_on_verified_scheme():
    s = scheme(req("r1", "age", "lte", 25, status="unverified"))
    assert assess_scheme(s, answered(age=40)).status == S.not_yet_verified


def test_no_requirements_is_not_yet_verified():
    a = assess_scheme(scheme())
    assert a.status == S.not_yet_verified
    assert "No eligibility rules" in a.explanation


def test_straddling_range_is_more_information_needed(schemes):
    a = assess_scheme(
        schemes["demo_fee_concession_b"],
        answered(annual_family_income={"min": 200000, "max": 300000}, institution_type="Government"),
    )
    assert a.status == S.more_information_needed
    assert a.missing_attributes == ["annual_family_income"]


# --- roll-up precedence ------------------------------------------------------

def test_not_satisfied_beats_unknown():
    s = scheme(req("r1", "age", "lte", 25), req("r2", "gender", "eq", "Female"))
    assert assess_scheme(s, answered(age=40)).status == S.unlikely_to_match


def test_unknown_beats_needs_clarification():
    s = scheme(req("r1", "age", "lte", 25), req("r2", "unmapped:hostel", "is_true", None))
    assert assess_scheme(s, {}).status == S.more_information_needed


def test_needs_clarification_beats_unverified():
    s = scheme(req("r1", "unmapped:hostel", "is_true", None), req("r2", "age", "lte", 25, status="unverified"))
    assert assess_scheme(s, answered(age=20)).status == S.uncertain


# --- requirement-level rules -------------------------------------------------

@pytest.mark.parametrize("attribute", [None, "unmapped:hostel_resident", "made_up_attribute"])
def test_unmapped_attribute_needs_clarification(attribute):
    assert assess_requirement(req("r1", attribute, "eq", "x"), {}).status == R.needs_clarification


def test_missing_operator_on_verified_rule_needs_clarification():
    assert assess_requirement(req("r1", "age", None, None), answered(age=20)).status == R.needs_clarification


def test_contradictory_verified_rules_are_uncertain():
    s = scheme(req("r1", "annual_family_income", "lte", 250000), req("r2", "annual_family_income", "lte", 300000))
    a = assess_scheme(s, answered(annual_family_income={"min": 100000, "max": 200000}))
    assert a.status == S.uncertain
    assert {r.status for r in a.requirements} == {R.needs_clarification}


def test_min_and_max_on_same_attribute_is_not_a_contradiction():
    s = scheme(req("r1", "age", "gte", 18), req("r2", "age", "lte", 25))
    assert assess_scheme(s, answered(age=20)).status == S.potential_match


# --- explanations ------------------------------------------------------------

def test_explanations_never_give_eligible_verdict(schemes):
    cases = [{}, answered(previous_year_marks_percent=45),
             answered(annual_family_income={"min": 0, "max": 99999}, domicile_karnataka=True, education_level="Diploma")]
    for answers in cases:
        for a in assess_schemes(schemes.values(), answers):
            assert not re.search(r"\beligible\b", a.explanation, re.IGNORECASE)
            assert a.explanation.endswith("not an official eligibility decision.")


def test_more_information_names_missing_details(schemes):
    a = assess_scheme(schemes["demo_fee_concession_b"], {})
    assert "annual family income" in a.explanation and "type of institution" in a.explanation


def test_proper_nouns_keep_their_case(schemes):
    a = assess_scheme(schemes["demo_scholarship_a"], {})
    assert "domicile in Karnataka" in a.explanation


def test_no_doubled_punctuation(schemes):
    for answers in ({}, answered(previous_year_marks_percent=45), answered(age=40)):
        for a in assess_schemes(schemes.values(), answers):
            assert ".'." not in a.explanation and ".." not in a.explanation, a.explanation


def test_single_unverified_rule_is_singular(schemes):
    a = assess_scheme(schemes["demo_unverified_d"], {})
    assert a.explanation.startswith(
        "This rule hasn't been confirmed from an official source: 'Applicants must be 25 years of age or younger.' This is"
    )


# --- inputs and outputs ------------------------------------------------------

def test_accepts_dicts_and_answer_lists(schemes):
    raw = schemes["demo_merit_c"].model_dump(mode="json")
    answers = [{"attribute": "previous_year_marks_percent", "state": "answered", "value": 75}]
    assert assess_scheme(raw, answers).status == S.potential_match


def test_does_not_mutate_inputs(schemes):
    s = schemes["demo_scholarship_a"]
    before = s.model_dump()
    answers = answered(age=20)
    assess_scheme(s, answers)
    assert s.model_dump() == before and list(answers) == ["age"]


def test_timestamp_and_json_round_trip(schemes):
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    out = reassess_schemes(schemes.values(), {}, now=now)
    assert all(a.last_assessed_at == "2026-10-31T12:00:00+00:00" for a in out)
    json.dumps([a.model_dump(mode="json") for a in out])


def test_reassess_is_assess():
    assert reassess_schemes is assess_schemes
