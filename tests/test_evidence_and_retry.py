"""Verbatim evidence for criteria/documents, and retry on bad model output."""
import json

import pytest

from discovery_agent.adapter import to_canonical_scheme
from discovery_agent.scheme_extractor import (
    extract_schemes,
    generate_json,
    parse_json_object,
    verbatim_evidence,
)
from member2.models import RequirementVerification as V

URL = "https://example.gov.in/demo-scheme"
PAGE = ("Demo Farmer Scheme. Farmers owning less than 2 hectares of land are eligible to apply. "
        "Applicants must submit a copy of the land record (RTC) along with the form.")
SOURCES = {URL: {"title": "Demo", "url": URL, "content": PAGE}}


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return type("R", (), {"text": item if isinstance(item, str) else json.dumps(item)})()


class FakeClient:
    def __init__(self, *responses):
        self.models = FakeModels(responses)


# --- verbatim_evidence ---------------------------------------------------------

def test_real_quote_is_kept_despite_spacing_and_case():
    q = "farmers owning less than 2 hectares   of land are eligible to apply."
    assert verbatim_evidence(q, URL, SOURCES) == "farmers owning less than 2 hectares of land are eligible to apply."


@pytest.mark.parametrize("quote,url", [
    ("Small farmers with under two hectares can apply.", URL),  # paraphrase
    ("Farmers", URL),                                           # too short to prove a rule
    ("Farmers owning less than 2 hectares of land are eligible to apply.", "https://other.gov.in"),
    (None, URL),
])
def test_unsupported_quotes_are_rejected(quote, url):
    assert verbatim_evidence(quote, url, SOURCES) is None


# --- JSON parsing and retry ----------------------------------------------------

def test_parse_tolerates_fences_and_stray_text():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Here you go: {"a": 1} thanks') == {"a": 1}


@pytest.mark.parametrize("bad", ["", "not json", "[1, 2]", '{"a": '])
def test_parse_rejects_bad_output(bad):
    with pytest.raises(ValueError):
        parse_json_object(bad)


def test_generate_json_retries_invalid_json():
    client = FakeClient('{"schemes": [', {"ok": True})
    assert generate_json(client, "m", "p") == {"ok": True}
    assert client.models.calls == 2


def test_generate_json_gives_up_after_all_attempts():
    client = FakeClient("bad", "bad", "bad")
    with pytest.raises(ValueError):
        generate_json(client, "m", "p")
    assert client.models.calls == 3


def test_generate_json_retries_transport_errors():
    client = FakeClient(TimeoutError("slow"), {"ok": True})
    assert generate_json(client, "m", "p") == {"ok": True}


# --- end to end: extraction keeps only real quotes -----------------------------

def _extraction(criterion_evidence, doc_evidence):
    return {"schemes": [{
        "id": "demo_farmer", "name": "Demo Farmer Scheme", "official_url": URL,
        "source_evidence": [{"title": "Demo", "url": URL, "excerpt": "", "is_official": True}],
        "eligibility_criteria": [{"description": "Landholding below 2 hectares", "related_attribute": "land",
                                  "source_url": URL, "evidence": criterion_evidence}],
        "required_documents": ["Land record (RTC)", "Aadhaar card"],
        "documents": [{"name": "Land record (RTC)", "source_url": URL, "evidence": doc_evidence}],
        "claims": [],
    }]}


def _run(extraction):
    client = FakeClient(extraction, {"claim_checks": []})
    results = [{"title": "Demo", "url": URL, "content": PAGE, "is_official": True}]
    return extract_schemes(client, "m", results, {})


def test_verbatim_quotes_make_criterion_and_document_verified():
    out = _run(_extraction(
        "Farmers owning less than 2 hectares of land are eligible to apply.",
        "Applicants must submit a copy of the land record (RTC) along with the form."))
    scheme = out[0]
    crit = scheme.eligibility_criteria[0]
    assert crit.verification_status == "verified" and crit.evidence.startswith("Farmers owning")
    docs = {d.name: d for d in scheme.documents}
    assert docs["Land record (RTC)"].source_url == URL
    assert docs["Aadhaar card"].source_url is None  # named but never quoted: stays unsourced

    canonical = to_canonical_scheme(scheme)
    assert canonical.requirements[0].status == V.verified
    assert canonical.requirements[0].evidence == crit.evidence
    sourced = [d.name for d in canonical.documents if d.source_url]
    assert sourced == ["Land record (RTC)"]


def test_paraphrased_quotes_are_dropped():
    out = _run(_extraction("Small farmers can apply.", "You need your land papers."))
    scheme = out[0]
    assert scheme.eligibility_criteria[0].verification_status == "unverified"
    assert scheme.eligibility_criteria[0].evidence is None
    assert all(d.source_url is None and d.evidence is None for d in scheme.documents)


# --- search passages -----------------------------------------------------------

def test_relevant_passages_keep_rule_paragraphs_verbatim():
    from discovery_agent.search_provider import relevant_passages
    raw = ("Home | About | Contact\n"
           "Applicants must be permanent residents of Karnataka with family income below Rs 2.5 lakh.\n"
           "Photo gallery of the inauguration ceremony held last year in the city.\n"
           "Documents required: caste certificate, income certificate and marks card.\n")
    out = relevant_passages(raw, "residents family income documents caste certificate")
    assert "permanent residents of Karnataka" in out and "Documents required" in out
    assert "Photo gallery" not in out and "Home | About" not in out
    assert relevant_passages(None) == "" and len(relevant_passages(raw * 200, limit=300)) <= 300
