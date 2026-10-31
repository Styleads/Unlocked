"""Clarification questions come only from real gaps in the scheme data
(cases taken from live runs, fictionalised)."""
import pytest

from agent4 import ClarificationKind as K
from agent4 import build_email_draft, clarification_points, clarification_request

A = "https://example.gov.in/college-a/demo"
B = "https://example.gov.in/portal/demo"
LIMITS = "Annual income limit is Rs. 2.50 lakh for Category-I students and Rs. 1.00 lakh for Category 2A, 3A and 3B."


def _req(attribute, status, evidence, source_url=A):
    return {"attribute": attribute, "status": status, "evidence": evidence, "source_url": source_url, "criterion": evidence}


def _scheme(reqs=(), notes=()):
    return {"id": "demo_c", "name": "Demo Clarify Scholarship", "official_sources": [A],
            "requirements": list(reqs), "uncertainties": list(notes)}


def test_nothing_unclear_means_no_question():
    s = _scheme([_req("gender", "verified", "Only girl students are eligible for this award.")])
    assert clarification_points(s) == []
    assert clarification_request(s) is None


def test_uncertain_rule_becomes_a_quoted_question():
    s = _scheme([_req("annual_family_income", "uncertain", LIMITS), _req("annual_family_income", "uncertain", LIMITS)])
    (p,) = clarification_points(s)  # split parts share one quote: one question
    assert p.kind is K.uncertain_rule
    assert "annual family income" in p.question and p.question.endswith("?")
    assert p.facts[0].text == LIMITS and p.facts[0].source_url == A


def test_disagreeing_pages_cite_one_rule_from_each():
    s = _scheme([_req("gender", "verified", "Bright science girl students are eligible.", A),
                 _req("course_type", "verified", "This scholarship is for all science students.", B)],
                notes=["Official pages for this scheme state different rules; all of them are shown."])
    (p,) = clarification_points(s)
    assert p.kind is K.sources_disagree
    assert {f.source_url for f in p.facts} == {A, B}


@pytest.mark.parametrize("note,kind", [
    ("Required documents", K.missing_documents),
    ("Some required documents have no official source yet: Marks card.", K.missing_documents),
    ("Application process", K.missing_process),
    ("Eligibility criteria", K.missing_criteria),
])
def test_missing_details_become_questions(note, kind):
    assert [p.kind for p in clarification_points(_scheme(notes=[note]))] == [kind]


def test_missing_criteria_not_asked_when_verified_rules_exist():
    s = _scheme([_req("gender", "verified", "Only girl students are eligible for this award.")], notes=["Eligibility criteria"])
    assert clarification_points(s) == []


def test_unverified_rules_are_not_put_in_an_official_letter():
    s = _scheme([_req("age", "unverified", "Applicants must be under 25 years of age.")])
    assert clarification_points(s) == []


def test_ordered_by_usefulness_and_limited():
    s = _scheme([_req("annual_family_income", "uncertain", LIMITS)],
                notes=["Application process", "Required documents"])
    kinds = [p.kind for p in clarification_points(s)]
    assert kinds == [K.uncertain_rule, K.missing_documents, K.missing_process]
    assert len(clarification_points(s, limit=2)) == 2


def test_request_drafts_an_email_citing_the_rule():
    s = _scheme([_req("annual_family_income", "uncertain", LIMITS)], notes=["Required documents"])
    req = clarification_request(s, user_details={"Name": "Demo User"})
    assert req.purpose.value == "clarification"
    assert req.question.startswith("I have the following questions:\n1. ")
    draft = build_email_draft(req)
    assert LIMITS in draft.body_content and A in draft.source_urls
    assert "documents required" in draft.body_content


def test_works_on_member2_records():
    m2 = pytest.importorskip("member2.models")
    rec = m2.SchemeRecord(id="demo_m2", name="Demo M2", official_sources=[A], uncertainties=["Application process"],
                          requirements=[m2.Requirement(id="r1", attribute="annual_family_income", criterion=LIMITS,
                                                       status="uncertain", source_url=A, evidence=LIMITS)])
    assert [p.kind for p in clarification_points(rec)] == [K.uncertain_rule, K.missing_process]
    assert clarification_request(rec).scheme.id == "demo_m2"


# --- only real ambiguity, one question per topic (self-test findings) --------

def test_our_own_mapping_gaps_are_not_asked():
    s = _scheme([
        {**_req("course_type", "uncertain", "Bright science (B.Sc.) girl students in Government colleges."),
         "uncertain_reason": "not_stated", "normalized_by": "structured"},
        {**_req("year_of_study", "uncertain", "Admitted to the first year of B.Sc. programmes."),
         "uncertain_reason": "not_stated", "normalized_by": "structured"},
    ])
    assert clarification_points(s) == []


def test_group_limits_become_one_question_per_topic():
    other = "Income limit is Rs 2.50 lakh for Category-I and Rs 1.00 lakh for Category 2A, 3A and 3B students."
    s = _scheme([
        {**_req("annual_family_income", "uncertain", LIMITS), "uncertain_reason": "group_limits", "normalized_by": "structured"},
        {**_req("annual_family_income", "uncertain", LIMITS), "uncertain_reason": "group_limits", "normalized_by": "structured"},
        {**_req("annual_family_income", "uncertain", other, B), "uncertain_reason": "group_limits", "normalized_by": "structured"},
    ])
    (p,) = clarification_points(s)
    assert "different conditions for different groups" in p.question
    assert [f.text for f in p.facts] == [LIMITS, other]


def test_end_to_end_with_member2_normalizer():
    norm = pytest.importorskip("member2.normalize")
    m2 = pytest.importorskip("member2.models")
    import json

    class FakeLLM:  # local stand-in; agent4 tests don't depend on member2's test helpers
        def __init__(self, data):
            self.data = data

        def complete_json(self, system, user):
            return json.dumps(self.data)

    rec = m2.SchemeRecord(id="demo_e2e", name="Demo E2E", official_sources=[A], verification_status="verified", requirements=[
        m2.Requirement(id="r1", criterion=LIMITS, status="verified", source_url=A, evidence=LIMITS),
        m2.Requirement(id="r2", criterion="Science (B.Sc.) students only.", status="verified", source_url=A,
                       evidence="Science (B.Sc.) students only.")])
    llm = FakeLLM({"structured": [
        {"id": "r1", "attribute": "annual_family_income", "operator": "lte", "value": 250000},
        {"id": "r2", "attribute": "course_type", "operator": "eq", "value": "Arts/Science/Commerce"}], "extracted": []})
    out = norm.normalize_scheme(rec, llm)
    kinds = [(p.kind.value, p.question[:40]) for p in clarification_points(out)]
    assert kinds == [("uncertain_rule", "The official rules on annual family inco")]  # course_type gap not asked
