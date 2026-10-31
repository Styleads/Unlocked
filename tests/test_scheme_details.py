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
    assert len(md) == 1 and "core subjects" in md[0] and "Screen Reader" not in md[0]

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
