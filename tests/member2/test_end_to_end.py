"""The demo journey from member2.md §11, through the public API only."""
import json

import member2
from member2 import (
    AnswerState,
    SchemeStatus,
    apply_answers,
    assess_schemes,
    build_action_plan,
    generate_consolidated_questions,
    normalize_requirements,
    reassess_schemes,
    run_pipeline,
)

from fakes import load_schemes


def statuses(assessments):
    return {a.scheme_id: a.status for a in assessments}


def test_demo_journey(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # 1. Load and normalize without an LLM.
    schemes = normalize_requirements(load_schemes().values(), llm=None)

    # 2. Nothing answered yet: missing information is never a failure.
    first = statuses(assess_schemes(schemes, {}))
    assert first["demo_scholarship_a"] == SchemeStatus.more_information_needed
    assert first["demo_fee_concession_b"] == SchemeStatus.more_information_needed
    assert first["demo_unverified_d"] == SchemeStatus.not_yet_verified
    assert SchemeStatus.unlikely_to_match not in first.values()

    # 3. The shared income question leads the consolidated batch.
    batch = generate_consolidated_questions(schemes, {}, {})
    assert batch[0].id == "q_annual_family_income"
    assert batch[0].related_scheme_ids == ["demo_fee_concession_b", "demo_scholarship_a"]

    # 4. Answer some, skip one.
    answers, history = apply_answers({}, {}, [
        {"attribute": "annual_family_income", "state": "answered", "value": {"min": 100000, "max": 200000}},
        {"attribute": "domicile_karnataka", "state": "answered", "value": True},
        {"attribute": "education_level", "state": "answered", "value": "Undergraduate"},
        {"attribute": "institution_type", "state": "skipped"},
    ])
    assert answers["institution_type"].value is None
    assert history["q_institution_type"] == AnswerState.skipped

    # 5. Reassess: the skipped answer stays unknown, not failed.
    second = reassess_schemes(schemes, answers)
    after = statuses(second)
    assert after["demo_scholarship_a"] == SchemeStatus.potential_match
    assert after["demo_fee_concession_b"] == SchemeStatus.more_information_needed
    b = next(a for a in second if a.scheme_id == "demo_fee_concession_b")
    assert b.missing_attributes == ["institution_type"]

    # 6. Answered and skipped questions are not asked again.
    nxt = [q.attribute for q in generate_consolidated_questions(schemes, answers, history)]
    assert "annual_family_income" not in nxt and "institution_type" not in nxt

    # 7. The plan leads with the shared prerequisite and respects the sourced dependency.
    by_id = {s.id: s for s in schemes}
    plan = build_action_plan([by_id["demo_scholarship_a"], by_id["demo_fee_concession_b"]], assessments=second)
    ids = [c.id for c in plan.checklist]
    assert ids[0] == "doc_income_certificate"
    assert plan.shared_prerequisites == ["doc_income_certificate"]
    assert plan.checklist[0].required_by_scheme_ids == ["demo_fee_concession_b", "demo_scholarship_a"]
    assert ids.index("doc_domicile_certificate") < ids.index("doc_caste_certificate")

    # 8. Everything is JSON-ready for Member 3.
    for obj in [*schemes, *second, *batch, plan]:
        json.dumps(obj.model_dump(mode="json"))


def test_run_pipeline_is_json_ready():
    out = run_pipeline(load_schemes().values(), {}, {})
    assert set(out) == {"schemes", "assessments", "questions"}
    assert out["questions"][0]["id"] == "q_annual_family_income"
    json.dumps(out)


def test_run_pipeline_accepts_its_own_output_back():
    first = run_pipeline(load_schemes().values())
    again = run_pipeline(first["schemes"])
    assert again["schemes"] == first["schemes"]


def test_public_api_importable():
    for name in member2.__all__:
        assert hasattr(member2, name), name
