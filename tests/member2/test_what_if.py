"""What would change a result. Fictional schemes only; every effect comes from assess_scheme."""
from member2.models import (
    Answer, AnswerState, Operator, Requirement, RequirementVerification, SchemeRecord, SchemeStatus, VerificationStatus,
)
from member2.what_if import explore

SRC = "https://example.gov.in/demo"


def rule(rid, attribute, op, value, status=RequirementVerification.verified):
    return Requirement(id=rid, attribute=attribute, criterion=f"{attribute} {op.value} {value}", operator=op, value=value, status=status, source_url=SRC, evidence="Demo.")


def scheme(sid, *reqs):
    return SchemeRecord(id=sid, name=f"Demo Scholarship {sid}", requirements=list(reqs), verification_status=VerificationStatus.verified)


A = scheme("A", rule("a1", "social_category", Operator.in_, ["SC", "ST"]), rule("a2", "annual_family_income", Operator.lte, 250000))
B = scheme("B", rule("b1", "social_category", Operator.in_, ["SC", "ST", "OBC"]), rule("b2", "annual_family_income", Operator.lte, 250000))
C = scheme("C", rule("c1", "social_category", Operator.eq, "OBC"))


def ans(**kw):
    return {k: Answer(attribute=k, state=AnswerState.answered, value=v) for k, v in kw.items()}


OBC_HIGH = ans(social_category="OBC", annual_family_income={"min": 250001, "max": 500000})


def test_names_the_failed_conditions_with_the_users_own_answers():
    w = explore([A, B, C], OBC_HIGH, "A")
    assert w.status == SchemeStatus.unlikely_to_match
    assert {(f.label, f.your_answer) for f in w.failed} == {("Social category", "OBC"), ("Annual family income", "₹2.5 lakh – ₹5 lakh")}


def test_every_change_meets_the_rule_it_is_offered_for():
    w = explore([A, B, C], OBC_HIGH, "A")
    assert {c.proposed for c in w.changes if c.attribute == "social_category"} == {"SC", "ST"}
    incomes = {c.proposed for c in w.changes if c.attribute == "annual_family_income"}
    assert incomes and all("Above" not in i and "₹2.5 lakh – ₹5 lakh" != i for i in incomes)


def test_shows_the_effect_on_other_schemes_including_losses():
    w = explore([A, B, C], OBC_HIGH, "A")
    to_sc = next(c for c in w.changes if c.proposed == "SC")
    effects = {e.scheme_id: (e.before, e.after) for e in to_sc.effects}
    assert effects["C"] == (SchemeStatus.potential_match, SchemeStatus.unlikely_to_match)  # C needs OBC: it would be lost
    lower = next(c for c in w.changes if c.attribute == "annual_family_income")
    assert any(e.scheme_id == "B" and e.after == SchemeStatus.potential_match for e in lower.effects)


def test_both_failed_conditions_together_would_make_it_a_match():
    assert explore([A, B, C], OBC_HIGH, "A").all_fixed_status == SchemeStatus.potential_match


def test_lists_schemes_that_already_fit():
    assert explore([A, B, C], OBC_HIGH, "A").already_matching == [{"scheme_id": "C", "name": "Demo Scholarship C"}]


def test_a_rejection_the_rules_dont_explain_says_so():
    w = explore([A], ans(social_category="SC", annual_family_income={"min": 100000, "max": 250000}), "A")
    assert w.failed == [] and w.changes == [] and "doesn't check" in w.note


def test_an_unverified_rule_is_never_offered_as_the_reason():
    U = scheme("U", rule("u1", "social_category", Operator.eq, "SC", status=RequirementVerification.unverified))
    w = explore([U], ans(social_category="OBC"), "U")
    assert w.failed == [] and w.changes == []


def test_unknown_scheme_is_none_and_nothing_is_saved():
    answers = dict(OBC_HIGH)
    assert explore([A], answers, "missing") is None
    explore([A, B, C], answers, "A")
    assert answers["social_category"].value == "OBC"
