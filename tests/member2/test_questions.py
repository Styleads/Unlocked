import json
import random

import pytest

from member2.models import Answer, AnswerState, InputType, Requirement, SchemeRecord
from member2.questions import apply_answers, generate_consolidated_questions, generate_scheme_questions

from fakes import FakeLLM

SOURCE = "https://example.gov.in/demo/rules"


def req(rid, attribute, operator="eq", value="x", status="verified"):
    return Requirement(id=rid, attribute=attribute, criterion=f"rule {rid}", operator=operator,
                       value=value, status=status, source_url=SOURCE, evidence=f"rule {rid}")


def scheme(sid, *reqs):
    return SchemeRecord(id=sid, name=sid, requirements=list(reqs), verification_status="verified")


def ids(questions):
    return [q.attribute for q in questions]


def answered(**values):
    return {k: Answer(attribute=k, state="answered", value=v) for k, v in values.items()}


# --- ranking -----------------------------------------------------------------

def test_shared_attribute_ranks_above_single_use():
    schemes = [
        scheme("s1", req("a", "gender"), req("b", "course_type")),
        scheme("s2", req("c", "gender")),
        scheme("s3", req("d", "gender")),
    ]
    qs = generate_consolidated_questions(schemes, {}, {})
    assert ids(qs) == ["gender", "course_type"]
    assert qs[0].related_scheme_ids == ["s1", "s2", "s3"]


def test_fixture_batch_puts_shared_income_first(schemes):
    qs = generate_consolidated_questions(schemes.values(), {}, {})
    assert ids(qs) == ["annual_family_income", "education_level", "institution_type", "domicile_karnataka", "previous_year_marks_percent"]
    income = qs[0]
    assert income.id == "q_annual_family_income"
    assert income.related_scheme_ids == ["demo_fee_concession_b", "demo_scholarship_a"]
    assert income.input_type == InputType.range and income.ranges
    assert "2 of the schemes we found use this." in income.why_asked and "You can skip this." in income.why_asked
    assert "One of the schemes we found uses this." in qs[1].why_asked


def test_order_is_deterministic(schemes):
    first = generate_consolidated_questions(schemes.values(), {}, {})
    shuffled = list(schemes.values())
    random.Random(7).shuffle(shuffled)
    assert first == generate_consolidated_questions(shuffled, {}, {})


# --- exclusions --------------------------------------------------------------

def test_answered_never_asked(schemes):
    qs = generate_consolidated_questions(schemes.values(), answered(education_level="Diploma"), {})
    assert "education_level" not in ids(qs)


@pytest.mark.parametrize("state", ["skipped", "unknown", "prefer_not_to_answer", "answered"])
def test_history_blocks_reasking(schemes, state):
    qs = generate_consolidated_questions(schemes.values(), {}, {"q_annual_family_income": state})
    assert "annual_family_income" not in ids(qs)


def test_skipped_answer_state_blocks_reasking(schemes):
    answers = {"institution_type": Answer(attribute="institution_type", state="skipped")}
    assert "institution_type" not in ids(generate_consolidated_questions(schemes.values(), answers, {}))


def test_unverified_only_attribute_not_asked(schemes):
    # Demo D's age rule is unverified, so an answer could not change anything.
    assert "age" not in ids(generate_consolidated_questions(schemes.values(), {}, {}, batch_size=50))


def test_unlikely_scheme_attributes_not_asked():
    s = scheme("s1", req("a", "age", "lte", 25), req("b", "gender", "eq", "Female"))
    qs = generate_consolidated_questions([s], answered(age=40), {})
    assert qs == []


def test_unmapped_and_contradictory_not_asked():
    s = scheme(
        "s1",
        req("a", "unmapped:hostel"),
        req("b", "annual_family_income", "lte", 250000),
        req("c", "annual_family_income", "lte", 300000),
    )
    assert generate_consolidated_questions([s], {}, {}) == []


# --- batch size --------------------------------------------------------------

def test_batch_size_respected(schemes):
    assert len(generate_consolidated_questions(schemes.values(), {}, {}, batch_size=3)) == 3


def test_fewer_candidates_than_batch_is_fine():
    assert ids(generate_consolidated_questions([scheme("s1", req("a", "gender"))], {}, {}, batch_size=5)) == ["gender"]


def test_zero_candidates_returns_empty():
    assert generate_consolidated_questions([], {}, {}) == []


# --- scheme-specific ---------------------------------------------------------

def test_scheme_questions_have_no_batch_limit_and_skip_answered(schemes):
    a = schemes["demo_scholarship_a"]
    # Within one scheme every attribute has the same reach, so sensitivity decides: income last.
    assert ids(generate_scheme_questions(a, {}, {})) == ["education_level", "domicile_karnataka", "annual_family_income"]
    assert ids(generate_scheme_questions(a, answered(education_level="Diploma"), {})) == ["domicile_karnataka", "annual_family_income"]


def test_scheme_questions_skipped_only_when_requested(schemes):
    b = schemes["demo_fee_concession_b"]
    history = {"q_institution_type": "skipped"}
    assert "institution_type" not in ids(generate_scheme_questions(b, {}, history))
    qs = generate_scheme_questions(b, {}, history, include_skipped=True)
    assert [q.status for q in qs if q.attribute == "institution_type"] == [AnswerState.skipped]


# --- apply_answers -----------------------------------------------------------

def test_apply_answers_does_not_mutate_inputs():
    answers = answered(age=20)
    history = {"q_age": AnswerState.answered}
    new_answers, new_history = apply_answers(answers, history, [{"attribute": "gender", "state": "answered", "value": "female"}])
    assert list(answers) == ["age"] and history == {"q_age": AnswerState.answered}
    assert new_answers["gender"].value == "Female"
    assert new_history["q_gender"] == AnswerState.answered


@pytest.mark.parametrize("state", ["skipped", "unknown", "prefer_not_to_answer"])
def test_skip_stores_no_value(state):
    answers, history = apply_answers({}, {}, [{"attribute": "age", "state": state, "value": 20}])
    assert answers["age"].state == AnswerState(state) and answers["age"].value is None
    assert history["q_age"] == AnswerState(state)


@pytest.mark.parametrize(
    "attribute,value,state,stored",
    [
        ("institution_type", "Not sure", "unknown", None),
        ("institution_type", "Govt-ish", "unknown", None),
        ("institution_type", "aided", "answered", "Aided"),
        ("annual_family_income", "₹1 lakh – ₹2.5 lakh", "answered", {"min": 100000, "max": 250000}),
        ("annual_family_income", {"min": 100000, "max": 200000}, "answered", {"min": 100000, "max": 200000}),
        ("annual_family_income", "lots", "unknown", None),
        ("domicile_karnataka", "Yes", "answered", True),
        ("domicile_karnataka", "maybe", "unknown", None),
        ("previous_year_marks_percent", "72.5", "answered", 72.5),
        ("previous_year_marks_percent", "", "skipped", None),
        ("district", "  Mysuru ", "answered", "Mysuru"),
    ],
)
def test_apply_answers_cleans_values(attribute, value, state, stored):
    answers, _ = apply_answers({}, {}, [{"attribute": attribute, "state": "answered", "value": value}])
    assert answers[attribute].state == AnswerState(state)
    assert answers[attribute].value == stored


def test_unknown_attribute_ignored():
    answers, history = apply_answers({}, {}, [{"attribute": "aadhaar_number", "state": "answered", "value": "x"}])
    assert answers == {} and history == {}


# --- rephrasing --------------------------------------------------------------

def test_rephrase_changes_text_only(schemes):
    llm = FakeLLM(json.dumps({"q_annual_family_income": "Roughly how much does your family earn in a year?"}))
    plain = generate_consolidated_questions(schemes.values(), {}, {})
    qs = generate_consolidated_questions(schemes.values(), {}, {}, rephrase_llm=llm)
    assert qs[0].question == "Roughly how much does your family earn in a year?"
    assert [q.model_dump(exclude={"question"}) for q in qs] == [q.model_dump(exclude={"question"}) for q in plain]
    assert qs[1:] == plain[1:]


def test_legal_meaning_questions_are_never_rephrased(schemes):
    llm = FakeLLM(json.dumps({"q_domicile_karnataka": "Are you a native of Karnataka?"}))
    plain = {q.id: q.question for q in generate_consolidated_questions(schemes.values(), {}, {})}
    qs = {q.id: q.question for q in generate_consolidated_questions(schemes.values(), {}, {}, rephrase_llm=llm)}
    assert "q_domicile_karnataka" in plain
    assert qs["q_domicile_karnataka"] == plain["q_domicile_karnataka"]
    assert "q_domicile_karnataka" not in llm.payload()


def test_rephrase_sends_no_answers(schemes):
    llm = FakeLLM("{}")
    generate_consolidated_questions(schemes.values(), answered(district="Mysuru"), {}, rephrase_llm=llm)
    assert "Mysuru" not in llm.calls[0][1]


@pytest.mark.parametrize(
    "llm",
    [
        FakeLLM(RuntimeError("down")),
        FakeLLM("not json"),
        FakeLLM("[1, 2]"),
        FakeLLM(json.dumps({"q_annual_family_income": "No question mark"})),
        FakeLLM(json.dumps({"q_annual_family_income": 42})),
    ],
)
def test_rephrase_failure_keeps_registry_text(schemes, llm):
    plain = generate_consolidated_questions(schemes.values(), {}, {})
    assert generate_consolidated_questions(schemes.values(), {}, {}, rephrase_llm=llm) == plain


# --- the demo journey's question step ----------------------------------------

def test_next_batch_after_answers(schemes):
    answers, history = apply_answers({}, {}, [
        {"attribute": "annual_family_income", "state": "answered", "value": {"min": 100000, "max": 200000}},
        {"attribute": "domicile_karnataka", "state": "answered", "value": True},
        {"attribute": "education_level", "state": "answered", "value": "Undergraduate"},
        {"attribute": "institution_type", "state": "skipped"},
    ])
    nxt = ids(generate_consolidated_questions(schemes.values(), answers, history))
    assert "annual_family_income" not in nxt and "institution_type" not in nxt
    assert nxt == ["previous_year_marks_percent"]
