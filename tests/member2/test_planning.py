import json
import random

import pytest

from member2.assess import assess_schemes
from member2.models import Answer, DocStatus, SchemeRecord, SchemeStatus
from member2.planning import build_action_plan

SRC = "https://example.gov.in/demo/docs"


def order(plan):
    return [c.id for c in plan.checklist]


def scheme(sid, docs, **kw):
    return SchemeRecord(id=sid, name=sid.upper(), documents=docs, verification_status="verified", **kw)


def doc(name, *deps, source=SRC):
    return {"name": name, "source_url": source,
            "dependencies": [{"depends_on": d, "source_url": SRC} if isinstance(d, str) else d for d in deps]}


# --- the fixture journey -----------------------------------------------------

def test_shared_income_certificate_once_and_first(schemes):
    plan = build_action_plan([schemes["demo_scholarship_a"], schemes["demo_fee_concession_b"]])
    ids = order(plan)
    assert ids.count("doc_income_certificate") == 1
    assert ids[0] == "doc_income_certificate"
    assert plan.shared_prerequisites == ["doc_income_certificate"]
    first = plan.checklist[0]
    assert first.required_by_scheme_ids == ["demo_fee_concession_b", "demo_scholarship_a"]
    assert first.reason == "Needed for 2 schemes: Demo Fee Concession B, Demo Scholarship A."
    assert "Start with your Income Certificate" in plan.explanation


def test_fixture_order_respects_sourced_dependency(schemes):
    plan = build_action_plan([schemes["demo_scholarship_a"], schemes["demo_fee_concession_b"]])
    assert order(plan) == [
        "doc_income_certificate", "doc_admission_proof", "doc_bank_passbook",
        "doc_domicile_certificate", "doc_caste_certificate", "doc_fee_receipt",
    ]
    domicile = next(c for c in plan.checklist if c.id == "doc_domicile_certificate")
    assert domicile.required_by_scheme_ids == []
    assert domicile.reason == "Get this first: required before Caste Certificate."
    caste = next(c for c in plan.checklist if c.id == "doc_caste_certificate")
    assert caste.dependencies == ["doc_domicile_certificate"]


def test_every_edge_has_a_source(schemes):
    plan = build_action_plan(schemes.values())
    assert plan.edges and all(e.source_url for e in plan.edges)
    assert {e.relation for e in plan.edges} == {"required_for", "prerequisite_of"}


def test_unsourced_document_excluded_with_warning(schemes):
    plan = build_action_plan([schemes["demo_merit_c"]])
    assert plan.excluded_documents == ["Recommendation Letter"]
    assert "doc_recommendation_letter" not in order(plan)
    assert any("Recommendation Letter" in w for w in plan.warnings)
    assert "1 document was left out" in plan.explanation


# --- dependencies and cycles -------------------------------------------------

def test_unsourced_dependency_not_added():
    s = scheme("s1", [doc("Caste Certificate", {"depends_on": "Domicile Certificate"})])
    plan = build_action_plan([s])
    assert order(plan) == ["doc_caste_certificate"]
    assert all(e.relation == "required_for" for e in plan.edges)
    assert any("Domicile Certificate" in w for w in plan.warnings)


def test_cycle_is_broken_without_exception():
    s = scheme("s1", [doc("Caste Certificate", "Domicile Certificate"), doc("Domicile Certificate", "Caste Certificate")])
    plan = build_action_plan([s])
    assert sorted(order(plan)) == ["doc_caste_certificate", "doc_domicile_certificate"]
    assert all(e.relation == "required_for" for e in plan.edges)
    assert any("circular" in w for w in plan.warnings)


def test_self_dependency_ignored():
    plan = build_action_plan([scheme("s1", [doc("Income Certificate", "income cert.")])])
    assert order(plan) == ["doc_income_certificate"]
    assert any("own prerequisite" in w for w in plan.warnings)


def test_aliases_merge_and_sources_union():
    plan = build_action_plan([
        scheme("s1", [doc("Income Certificate", source="https://example.gov.in/1")]),
        scheme("s2", [doc("income cert.", source="https://example.gov.in/2")]),
    ])
    assert order(plan) == ["doc_income_certificate"]
    assert plan.checklist[0].source_urls == ["https://example.gov.in/1", "https://example.gov.in/2"]


# --- ordering ----------------------------------------------------------------

def test_order_is_deterministic(schemes):
    first = build_action_plan(schemes.values())
    shuffled = list(schemes.values())
    random.Random(3).shuffle(shuffled)
    assert build_action_plan(shuffled).model_dump() == first.model_dump()


def test_have_documents_come_after_needed(schemes):
    plan = build_action_plan(
        [schemes["demo_scholarship_a"], schemes["demo_fee_concession_b"]],
        user_documents={"doc_income_certificate": "have", "doc_domicile_certificate": DocStatus.obtained},
    )
    ids = order(plan)
    # Documents in hand go last; one already obtained no longer holds back what depends on it.
    assert ids[-2:] == ["doc_income_certificate", "doc_domicile_certificate"]
    assert ids.index("doc_caste_certificate") < ids.index("doc_domicile_certificate")
    assert [c.status for c in plan.checklist[-2:]] == [DocStatus.have, DocStatus.obtained]
    assert plan.checklist[-2].reason.startswith("You already have this.")
    caste = next(c for c in plan.checklist if c.id == "doc_caste_certificate")
    assert caste.dependencies == ["doc_domicile_certificate"]  # still shown


def test_needed_prerequisite_still_comes_first(schemes):
    plan = build_action_plan(
        [schemes["demo_fee_concession_b"]], user_documents={"doc_caste_certificate": "have"},
    )
    ids = order(plan)
    assert ids.index("doc_domicile_certificate") < ids.index("doc_caste_certificate")


def test_verified_deadline_breaks_ties():
    plan = build_action_plan([
        scheme("s1", [doc("Fee Receipt")], deadline="2026-12-01", deadline_source_url=SRC),
        scheme("s2", [doc("Bank Passbook")], deadline="2026-11-15", deadline_source_url=SRC),
        scheme("s3", [doc("Admission Letter")], deadline="2026-01-01"),  # no source: ignored
    ])
    assert order(plan) == ["doc_bank_passbook", "doc_fee_receipt", "doc_admission_proof"]
    assert "Earliest verified deadline: 2026-11-15." in plan.checklist[0].reason
    assert "deadline" not in plan.checklist[2].reason


# --- assessments, inputs and outputs ------------------------------------------

def test_unlikely_scheme_dropped_with_warning(schemes):
    answers = {"previous_year_marks_percent": Answer(attribute="previous_year_marks_percent", state="answered", value=40)}
    selected = [schemes["demo_scholarship_a"], schemes["demo_merit_c"]]
    assessments = assess_schemes(selected, answers)
    assert assessments[1].status == SchemeStatus.unlikely_to_match
    plan = build_action_plan(selected, assessments=assessments)
    assert "doc_previous_marksheet" not in order(plan)
    assert "demo_merit_c" not in {n.id for n in plan.nodes}
    assert any("Demo Merit Award C" in w for w in plan.warnings)


def test_accepts_dicts_and_round_trips(schemes):
    raw = [s.model_dump(mode="json") for s in schemes.values()]
    assessments = [a.model_dump(mode="json") for a in assess_schemes(schemes.values(), {})]
    plan = build_action_plan(raw, assessments=assessments)
    json.dumps(plan.model_dump(mode="json"))
    assert plan.checklist[0].id == "doc_income_certificate"


def test_empty_selection():
    plan = build_action_plan([])
    assert plan.checklist == [] and plan.edges == []
    assert plan.explanation.startswith("No documents")


def test_positional_misuse_fails_loudly(schemes):
    # plan.md sketched (selected_schemes, verified_requirements, user_documents); extra
    # positional arguments must not be silently misread.
    with pytest.raises(TypeError):
        build_action_plan(list(schemes.values()), [], {})
