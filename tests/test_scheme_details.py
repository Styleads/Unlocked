"""Per-scheme detail pass: cut each scheme's block from real page shapes,
keep only verbatim rules, separate obligations. Pages are fictionalised
copies of the live gov.in layouts (markdown section, bold section, table)."""
import json

from discovery_agent.adapter import to_canonical_scheme
from discovery_agent.scheme_details import enrich_scheme, name_key, scheme_blocks

NAME = "Demo C.V. Science Scholarship"
URL_A = "https://example.gov.in/college-a/demo-cv-scholarship"
URL_B = "https://example.gov.in/youth-portal/college-education"

PAGE_MARKDOWN = """\
* [Home](https://example.gov.in/)
### **Demo CV SCIENCE SCHOLARSHIP**
To encourage basic science, scholarships are awarded to meritorious students.
**Eligibility:** Student should be pursuing degree with any of these as core subjects Chemistry, Physics, Mathematics.
#### Screen Reader Access
The website complies with WCAG 2.0.
"""

PAGE_BOLD = """\
**DEMO C.V.SCIENCE SCHOLARSHIP:**
**T**his Scholarship is for all Science Students of all categories.
**DEMO PRIZE MONEY SCHOLARSHIP:**
Students who completed graduation in a single attempt are eligible.
"""

PAGE_TABLE = """\
| 3 | Department of Demo Education | Demo C V Science scholarship | Benefits | Whom |
|  |  |  | Annually Rs. 5000/- is paid to each student | Offline |
|  |  |  |  | Eligibility |
|  |  |  |  | Bright science (B.Sc.) girl students studying in Government and Aided colleges |
|  |  |  |  | Students passed previous year exam with 65% (General category) and 60% (Scheduled Castes and Scheduled Tribes) |
|  |  |  |  | If a student discontinues or has low attendance, the scholarship is taken back at the time of the transfer certificate. |
| 4 |  | Demo Other Puraskara scholarship | Benefits |  |
|  |  |  |  | Girl students below poverty line |
"""


def test_name_key_ignores_spacing_and_dots():
    assert name_key("Demo C.V. Science Scholarship") == name_key("Demo CV SCIENCE SCHOLARSHIP") == name_key("Demo C V Science scholarship")


def test_blocks_from_three_page_shapes():
    md = scheme_blocks(PAGE_MARKDOWN, NAME)
    assert len(md) == 1 and "core subjects" in md[0] and "Screen Reader" not in md[0]  # heading ends it

    bold = scheme_blocks(PAGE_BOLD, NAME)
    assert len(bold) == 1 and "This Scholarship is for all Science" in bold[0]  # ** stripped
    assert "PRIZE MONEY" not in bold[0]

    table = scheme_blocks(PAGE_TABLE, NAME)
    assert len(table) == 1
    assert "girl students" in table[0] and "65% (General category)" in table[0]
    assert "Puraskara" not in table[0] and "below poverty line" not in table[0]  # next table record


def test_no_block_without_the_scheme_name():
    assert scheme_blocks(PAGE_TABLE, "Completely Different Yojana") == []


class _Client:
    def __init__(self, response):
        self.response = response
        self.prompts = []
        self.models = self

    def generate_content(self, **kwargs):
        self.prompts.append(kwargs["contents"])
        return type("R", (), {"text": json.dumps(self.response)})()


def _search(pages):
    def search(query, max_results, include_raw=False):
        assert include_raw
        return [{"url": u, "title": "Demo", "raw_content": raw, "content": "", "is_official": True} for u, raw in pages]
    return search


def _model_output():
    return {
        "eligibility_criteria": [
            {"description": "Girl B.Sc. students in Government or Aided colleges", "related_attribute": "gender",
             "source_url": URL_B, "kind": "eligibility",
             "evidence": "Bright science (B.Sc.) girl students studying in Government and Aided colleges"},
            {"description": "Marks 65% General, 60% SC/ST", "related_attribute": "previous_year_marks_percent",
             "source_url": URL_B, "kind": "eligibility",
             "evidence": "Students passed previous year exam with 65% (General category) and 60% (Scheduled Castes and Scheduled Tribes)"},
            {"description": "Refund on discontinuing", "source_url": URL_B, "kind": "obligation",
             "evidence": "If a student discontinues or has low attendance, the scholarship is taken back at the time of the transfer certificate."},
            {"description": "Core subjects", "source_url": URL_A, "kind": "eligibility",
             "evidence": "Student should be pursuing degree with any of these as core subjects Chemistry, Physics, Mathematics."},
            {"description": "Invented rule", "source_url": URL_A, "kind": "eligibility",
             "evidence": "Students must be under 21 years of age."},
        ],
        "documents": [{"name": "Previous marks card", "source_url": URL_B, "evidence": "Not on the page at all."}],
    }


def test_enrich_keeps_verbatim_rules_and_marks_obligations():
    scheme = {"id": "demo_cv", "name": NAME, "eligibility_criteria": [{"description": "meritorious students"}],
              "documents": [], "source_evidence": [], "missing_information": []}
    client = _Client(_model_output())
    ok = enrich_scheme(client, "m", scheme, _search([(URL_A, PAGE_MARKDOWN), (URL_B, PAGE_TABLE)]))
    assert ok
    crit = {c["description"]: c for c in scheme["eligibility_criteria"]}
    assert crit["Girl B.Sc. students in Government or Aided colleges"]["verification_status"] == "verified"
    assert crit["Core subjects"]["source_url"] == URL_A
    assert crit["Invented rule"]["verification_status"] == "unverified" and crit["Invented rule"]["evidence"] is None
    assert crit["Refund on discontinuing"]["kind"] == "obligation"
    assert scheme["documents"] == []  # the document quote wasn't on the page, so nothing replaced
    assert {e["url"] for e in scheme["source_evidence"]} == {URL_A, URL_B}
    assert any("different rules" in n for n in scheme["missing_information"])

    canonical = to_canonical_scheme(scheme)
    assert all("Refund" not in r.criterion for r in canonical.requirements)
    assert canonical.obligations[0]["text"] == "Refund on discontinuing"
    assert sum(r.status.value == "verified" for r in canonical.requirements) == 3


def test_enrich_is_best_effort():
    scheme = {"id": "demo_cv", "name": NAME, "eligibility_criteria": [{"description": "kept"}]}
    def failing(*a, **k):
        raise TimeoutError("slow")
    assert not enrich_scheme(_Client({}), "m", scheme, failing)
    assert not enrich_scheme(_Client({}), "m", scheme, _search([(URL_A, "No scheme here.")]))
    # nothing verified -> first-pass criteria kept
    assert not enrich_scheme(_Client({"eligibility_criteria": [{"description": "x", "evidence": "nope", "source_url": URL_A}]}),
                             "m", scheme, _search([(URL_A, PAGE_MARKDOWN)]))
    assert scheme["eligibility_criteria"] == [{"description": "kept"}]


def test_scheme_without_detail_check_cannot_be_potential_match(monkeypatch):
    """A scheme verified only from a summary sentence is downgraded when its own
    page couldn't be read, so member2 can't call it a Potential match."""
    import asyncio
    from discovery_agent import discovery_pipeline as pipeline
    from member2 import assess_schemes

    records = [{"id": "demo_sum", "name": "Demo Summary Scheme", "verification_status": "verified",
                "eligibility_criteria": [{"description": "SC students", "related_attribute": "social_category",
                                          "source_url": URL_A, "evidence": "Open to SC students.", "verification_status": "verified"}],
                "missing_information": []}]
    monkeypatch.setattr(pipeline, "search_web", lambda *a, **k: [])  # own page not found
    asyncio.run(pipeline._enrich_details(object(), records))
    assert records[0]["verification_status"] == "partially_verified"
    assert pipeline.UNCHECKED_NOTE in records[0]["missing_information"]

    canonical = to_canonical_scheme(records[0])
    canonical.requirements[0].operator, canonical.requirements[0].value = "in", ["SC"]
    status = assess_schemes([canonical], {"social_category": {"attribute": "social_category", "state": "answered", "value": "SC"}})[0].status
    assert status.value == "not_yet_verified"


def test_rate_limit_waits_before_retrying(monkeypatch):
    from discovery_agent import scheme_extractor as ex

    waits = []
    monkeypatch.setattr(ex, "_sleep", waits.append)

    class RateLimited(Exception):
        code = 429

    class Models:
        calls = 0

        def generate_content(self, **kwargs):
            Models.calls += 1
            if Models.calls < 3:
                raise RateLimited("RESOURCE_EXHAUSTED")
            return type("R", (), {"text": '{"ok": true}'})()

    client = type("C", (), {"models": Models()})()
    assert ex.generate_json(client, "m", "p") == {"ok": True}
    assert waits == [2.0, 4.0]


# --- #5 documents: own page keeps its sections; follow-up documents search ---

OWN_URL = "https://example.gov.in/59/demo-cv-science-scholarship/en"
OWN_PAGE = """\
# Demo C.V. Science Scholarship
### Eligibility
Girl students studying B.Sc. in Government colleges are eligible.
### Documents Required
Caste certificate, income certificate and previous year marks card must be uploaded.
#### Screen Reader Access
The website complies with WCAG 2.0.
"""
DOCS_URL = "https://example.gov.in/portal/demo-guide"
DOCS_PAGE = """\
**Demo C.V. Science Scholarship - documents:**
1. Aadhaar-seeded bank account passbook copy.
2. Study certificate from the college principal.
"""


def test_own_page_keeps_eligibility_and_documents_sections():
    (block,) = scheme_blocks(OWN_PAGE, NAME, whole_page=True)
    # Ends by structure or size only (no fixed footer list); footer text is never quoted.
    assert "Girl students" in block and "previous year marks card" in block
    # Without whole_page the "### Eligibility" heading right under the name ends the
    # block at once, so a scheme's own page yielded nothing: why whole_page exists.
    assert scheme_blocks(OWN_PAGE, NAME) == []


class _Seq:
    def __init__(self, *responses):
        self.responses, self.models = list(responses), self

    def generate_content(self, **kwargs):
        return type("R", (), {"text": json.dumps(self.responses.pop(0))})()


def test_documents_search_adds_only_quoted_documents():
    detail = {"eligibility_criteria": [{"description": "Girls in B.Sc.", "source_url": OWN_URL, "kind": "eligibility",
                                        "evidence": "Girl students studying B.Sc. in Government colleges are eligible."}],
              "documents": []}
    docs = {"documents": [
        {"name": "Bank passbook copy", "source_url": DOCS_URL, "evidence": "1. Aadhaar-seeded bank account passbook copy."},
        {"name": "Study certificate", "source_url": DOCS_URL, "evidence": "2. Study certificate from the college principal."},
        {"name": "Ration card", "source_url": DOCS_URL, "evidence": "Ration card copy."},  # not on the page
    ]}
    calls = []

    def search(query, n, include_raw=False):
        calls.append(query)
        if "documents required" in query:
            return [{"url": DOCS_URL, "title": "Guide", "raw_content": DOCS_PAGE, "is_official": True}]
        return [{"url": OWN_URL, "title": "Demo", "raw_content": OWN_PAGE.replace("Caste certificate", "Nothing"), "is_official": True}]

    scheme = {"id": "demo_cv", "name": NAME, "missing_information": ["Required documents"]}
    assert enrich_scheme(_Seq(detail, docs), "m", scheme, search)
    assert calls == [f"{NAME} eligibility Karnataka", f"{NAME} documents required"]
    assert [(d["name"], d["source_url"]) for d in scheme["documents"]] == [
        ("Bank passbook copy", DOCS_URL), ("Study certificate", DOCS_URL)]
    assert "Required documents" not in scheme["missing_information"]
    assert DOCS_URL in {e["url"] for e in scheme["source_evidence"]}


def test_no_documents_search_when_documents_already_sourced():
    detail = {"eligibility_criteria": [{"description": "Girls in B.Sc.", "source_url": OWN_URL, "kind": "eligibility",
                                        "evidence": "Girl students studying B.Sc. in Government colleges are eligible."}],
              "documents": [{"name": "Marks card", "source_url": OWN_URL,
                             "evidence": "Caste certificate, income certificate and previous year marks card must be uploaded."}]}
    calls = []

    def search(query, n, include_raw=False):
        calls.append(query)
        return [{"url": OWN_URL, "title": "Demo", "raw_content": OWN_PAGE, "is_official": True}]

    scheme = {"id": "demo_cv", "name": NAME}
    assert enrich_scheme(_Seq(detail), "m", scheme, search)
    assert len(calls) == 1 and scheme["documents"][0]["source_url"] == OWN_URL


def test_announcement_link_text_can_be_quoted():
    page = ("[4 3 weeks ago 3. Demo C.V. Science Scholarship - Applications are invited from eligible minority students "
            "[Last Date to Apply: 31.10.2026].](https://example.gov.in/299/online-applications)\n"
            "[5 3 weeks ago Other scheme notice](https://example.gov.in/300/other)")
    (block,) = scheme_blocks(page, NAME)
    assert "https://" not in block
    from discovery_agent.scheme_extractor import verbatim_evidence
    quote = "3. Demo C.V. Science Scholarship - Applications are invited from eligible minority students"
    assert verbatim_evidence(quote, URL_A, {URL_A: {"content": block}})


def test_fallback_is_filtered_by_profile():
    from discovery_agent.discovery_pipeline import load_fallback_schemes
    farmer = load_fallback_schemes({"employment": {"occupation": "farmer"}, "interests": ["crop insurance"]})
    assert farmer and all(s.relevance in ("direct_match", "related") for s in farmer)
    jobseeker = load_fallback_schemes({"employment": {"occupation": "unemployed"},
                                       "interests": ["disability pension and assistance"]})
    assert jobseeker == []  # unrelated saved schemes are not shown
    assert len(load_fallback_schemes({"state": "Karnataka"})) == len(load_fallback_schemes({}))  # no signal: no filter


GRANT_PAGE = """\
**Demo Elder Care Grant:**
Grants are released to registered NGOs and voluntary organisations for running day-care centres.
Organisations must be registered for at least three years.
"""


def test_beneficiary_type_recorded_only_with_a_real_quote():
    url = "https://example.gov.in/grant"
    data = {"eligibility_criteria": [{"description": "Registered 3 years", "source_url": url, "kind": "eligibility",
                                      "evidence": "Organisations must be registered for at least three years."}],
            "documents": [],
            "beneficiary": {"type": "organisation", "source_url": url,
                            "evidence": "Grants are released to registered NGOs and voluntary organisations for running day-care centres."}}
    scheme = {"id": "demo_grant", "name": "Demo Elder Care Grant", "documents": []}
    assert enrich_scheme(_Seq(data, {"documents": []}), "m", scheme, _search([(url, GRANT_PAGE)]))
    assert scheme["beneficiary_type"] == "organisation"

    invented = dict(data, beneficiary={"type": "organisation", "source_url": url, "evidence": "Only for companies."})
    scheme2 = {"id": "demo_grant", "name": "Demo Elder Care Grant", "documents": []}
    enrich_scheme(_Seq(invented, {"documents": []}), "m", scheme2, _search([(url, GRANT_PAGE)]))
    assert "beneficiary_type" not in scheme2


def test_organisation_schemes_left_out_and_budget_respected(monkeypatch):
    import asyncio, time
    from discovery_agent import discovery_pipeline as pipeline
    import discovery_agent.scheme_details as sd

    def fake_enrich(client, model, record, search):
        if record["id"] == "slow":
            time.sleep(2)
            record["eligibility_criteria"] = ["should never appear"]
            return True
        record["beneficiary_type"] = "organisation" if record["id"] == "ngo" else "individual"
        return True

    monkeypatch.setattr(sd, "enrich_scheme", fake_enrich)
    monkeypatch.setenv("DISCOVERY_DETAIL_BUDGET_S", "1")
    records = [{"id": i, "name": i, "eligibility_criteria": [], "missing_information": []} for i in ("ngo", "person", "slow")]
    asyncio.run(pipeline._enrich_details(object(), records))
    by_id = {r["id"]: r for r in records}
    assert by_id["slow"]["eligibility_criteria"] == []  # late result never applied
    assert pipeline.UNCHECKED_NOTE in by_id["slow"]["missing_information"]
    assert by_id["ngo"]["beneficiary_type"] == "organisation" and by_id["person"]["beneficiary_type"] == "individual"
