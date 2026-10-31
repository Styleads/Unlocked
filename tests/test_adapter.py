"""The adapter must never invent provenance (plan.md: no unsourced claims or edges)."""
from discovery_agent.adapter import to_canonical_scheme
from member2 import build_action_plan
from member2.models import RequirementVerification as V

URL = "https://example.gov.in/demo"
EXCERPT = "Applicants must submit an Income Certificate issued by the Tahsildar."


def _raw(**kw):
    base = {"id": "demo", "name": "Demo Scheme", "official_url": URL}
    base.update(kw)
    return base


def test_plain_document_stays_unsourced_and_is_excluded_from_plan():
    s = to_canonical_scheme(_raw(required_documents=["Income Certificate"]))
    doc = s.documents[0]
    assert doc.source_url is None and doc.evidence is None
    assert any("no official source" in u for u in s.uncertainties)
    plan = build_action_plan([s])
    assert plan.checklist == [] and plan.excluded_documents


def test_document_sourced_from_verified_claim():
    claim = {"category": "document", "claim": "Income Certificate required", "source_url": URL,
             "supporting_excerpt": EXCERPT, "verification_status": "verified"}
    s = to_canonical_scheme(_raw(required_documents=["Income Certificate"], claims=[claim]))
    assert (s.documents[0].source_url, s.documents[0].evidence) == (URL, EXCERPT)


def test_unverified_claim_is_not_used():
    claim = {"category": "document", "claim": "Income Certificate required", "source_url": URL,
             "supporting_excerpt": EXCERPT, "verification_status": "unverified"}
    s = to_canonical_scheme(_raw(required_documents=["Income Certificate"], claims=[claim]))
    assert s.documents[0].source_url is None


def test_criterion_never_gets_scheme_url_or_self_quote():
    s = to_canonical_scheme(_raw(eligibility_criteria=[
        {"description": "Family income below Rs 2,50,000", "related_attribute": "income", "verification_status": "verified"}]))
    r = s.requirements[0]
    assert r.source_url is None and r.evidence is None
    assert r.status == V.unverified  # "verified" without source and quote is downgraded
    assert r.attribute == "annual_family_income"


def test_criterion_evidence_from_matching_verified_claim():
    text = "Family income below Rs 2,50,000"
    claim = {"category": "eligibility", "claim": text, "source_url": URL,
             "supporting_excerpt": "Annual family income must be below Rs 2,50,000.", "verification_status": "verified"}
    s = to_canonical_scheme(_raw(claims=[claim], eligibility_criteria=[
        {"description": text, "related_attribute": "income", "source_url": URL, "verification_status": "verified"}]))
    r = s.requirements[0]
    assert r.status == V.verified and r.evidence == claim["supporting_excerpt"]


def test_no_operator_is_guessed():
    s = to_canonical_scheme(_raw(eligibility_criteria=[
        {"description": "Must not receive any other scholarship", "related_attribute": "receives_other_scholarship"}]))
    assert s.requirements[0].operator is None


def test_dependency_edge_keeps_only_its_own_source():
    s = to_canonical_scheme(_raw(documents=[{"name": "Caste Certificate", "source_url": URL, "evidence": EXCERPT,
                                             "dependencies": ["Aadhaar"]}]))
    dep = s.documents[0].dependencies[0]
    assert dep.source_url is None and dep.evidence is None


def test_partially_verified_scheme_is_uncertain_and_agent1_fields_kept():
    s = to_canonical_scheme(_raw(verification_status="partially_verified", application_process="Apply online."))
    assert s.verification_status == "uncertain"
    assert s.application_steps == ["Apply online."] and s.application_process == "Apply online."
