import json

import pytest
from pydantic import ValidationError

from member2.models import (
    Answer,
    AnswerState,
    GraphEdge,
    Requirement,
    RequirementVerification,
    SchemeRecord,
    VerificationStatus,
)


def test_requirement_accepts_not_verified_as_unverified():
    req = Requirement(id="r1", criterion="x", status="not_verified")
    assert req.status == RequirementVerification.unverified


def test_scheme_accepts_unverified_as_not_verified():
    s = SchemeRecord(id="s", name="Demo", verification_status="unverified")
    assert s.verification_status == VerificationStatus.not_verified


def test_string_documents_become_unsourced_objects():
    s = SchemeRecord(id="s", name="Demo", documents=["Income Certificate", {"name": "Photo", "source_url": "https://example.gov.in/a"}])
    assert s.documents[0].name == "Income Certificate" and s.documents[0].source_url is None
    assert s.documents[1].source_url == "https://example.gov.in/a"


def test_extra_fields_survive_round_trip():
    s = SchemeRecord(id="s", name="Demo", last_verified_at="2026-10-31", requirements=[{"id": "r", "criterion": "c", "member1_note": "n"}])
    dumped = s.model_dump(mode="json")
    assert dumped["last_verified_at"] == "2026-10-31"
    assert dumped["requirements"][0]["member1_note"] == "n"
    json.dumps(dumped)


@pytest.mark.parametrize("state", [s for s in AnswerState if s != AnswerState.answered])
def test_non_answered_states_drop_value(state):
    assert Answer(attribute="age", state=state, value=20).value is None


def test_answered_keeps_value():
    assert Answer(attribute="age", state="answered", value=20).value == 20


def test_graph_edge_requires_source():
    with pytest.raises(ValidationError):
        GraphEdge(source="a", target="b", source_url="")
