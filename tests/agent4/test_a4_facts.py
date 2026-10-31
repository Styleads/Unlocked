from enum import Enum

import pytest
from pydantic import BaseModel

from agent4 import EmailRequest, build_email_draft, facts_from_scheme

SRC = "https://example.gov.in/demo/rules"
INCOME = "Total annual family income must not exceed Rs 4.5 lakh."
COMPOUND = "Students must be admitted to regular degree programmes and listed in the merit list."


def _req(attribute, status="verified", evidence=INCOME, source_url=SRC, **kw):
    return {"attribute": attribute, "status": status, "evidence": evidence, "source_url": source_url, **kw}


def _scheme(*reqs):
    return {"id": "demo_f", "name": "Demo Facts Scheme", "official_sources": [SRC], "requirements": list(reqs)}


def test_only_verified_rules_with_quote_and_source():
    s = _scheme(
        _req("annual_family_income"),
        _req("age", status="unverified", evidence="Age below 25 years."),
        _req("gender", status="uncertain", evidence="Girl students only."),
        _req("state", evidence=None),
        _req("district", source_url=None, evidence="Applicants from Demo district."),
    )
    facts = facts_from_scheme(s)
    assert [(f.text, f.source_url) for f in facts] == [(INCOME, SRC)]


def test_compound_parts_sharing_a_quote_appear_once():
    s = _scheme(_req("unmapped:regular_degree", evidence=COMPOUND),
                _req("unmapped:merit_list", evidence="  Students must be admitted to regular degree programmes and "
                                                     "listed in the merit list. "))
    assert len(facts_from_scheme(s)) == 1


def test_filter_by_attribute_and_limit():
    s = _scheme(_req("annual_family_income"), *[_req(f"unmapped:c{i}", evidence=f"Condition number {i} applies here.")
                                                for i in range(10)])
    assert [f.text for f in facts_from_scheme(s, attributes=["annual_family_income"])] == [INCOME]
    assert len(facts_from_scheme(s)) == 5 and len(facts_from_scheme(s, limit=2)) == 2
    assert facts_from_scheme(s, attributes=[]) == []


def test_works_on_model_objects_with_enum_status():
    class Status(str, Enum):
        verified = "verified"

    class Req(BaseModel):
        attribute: str
        status: Status
        evidence: str
        source_url: str

    class Rec(BaseModel):
        id: str = "demo_obj"
        name: str = "Demo"
        requirements: list[Req]

    rec = Rec(requirements=[Req(attribute="annual_family_income", status="verified", evidence=INCOME, source_url=SRC)])
    assert facts_from_scheme(rec)[0].text == INCOME


def test_member2_record_end_to_end():
    m2 = pytest.importorskip("member2.models")
    rec = m2.SchemeRecord(id="demo_m2", name="Demo M2", official_sources=[SRC], requirements=[
        m2.Requirement(id="r1", attribute="annual_family_income", criterion=INCOME, operator="lte", value=450000,
                       status="verified", source_url=SRC, evidence=INCOME)])
    draft = build_email_draft(EmailRequest(scheme=rec, purpose="clarification", question="Is this per family?",
                                           facts=facts_from_scheme(rec)))
    assert INCOME in draft.body_content and SRC in draft.source_urls


def test_no_requirements_gives_no_facts():
    assert facts_from_scheme({"id": "x", "name": "X"}) == []
