import json
from types import SimpleNamespace

import pytest

from member2 import llm as llm_module
from member2.llm import AnthropicClient, LLMError
from member2.models import Operator, Requirement, RequirementVerification as V, SchemeRecord
from member2.normalize import (
    EXTRACTION_FAILED,
    normalize_requirements,
    normalize_scheme,
    requirement_matrix,
)

from fakes import FakeLLM

SRC = "https://example.gov.in/demo/rules"
TEXT = "Family income must not exceed Rs 2.5 lakh per year. Applicants must be 25 years of age or younger."


def scheme(reqs=(), text=None, sources=(SRC,), **kw):
    return SchemeRecord(id="demo_n", name="Demo N", requirements=list(reqs), eligibility_text=text,
                        official_sources=list(sources), verification_status="verified", **kw)


def extracted(**kw):
    item = {"attribute": "annual_family_income", "operator": "lte", "value": 250000,
            "criterion": "Family income must not exceed Rs 2.5 lakh per year.",
            "evidence": "Family income must not exceed Rs 2.5 lakh per year."}
    item.update(kw)
    return {"structured": [], "extracted": [item]}


# --- deterministic pass -------------------------------------------------------

def test_agent1_income_name_resolves():
    s = scheme([Requirement(id="r1", attribute="income", criterion="c", source_url=SRC)])
    assert normalize_scheme(s).requirements[0].attribute == "annual_family_income"


def test_verified_without_evidence_is_downgraded():
    r = Requirement(id="r1", attribute="age", criterion="Age 25 or younger", operator="lte", value=25,
                    status="verified", source_url=SRC, evidence=None)
    assert normalize_scheme(scheme([r])).requirements[0].status == V.unverified


def test_known_attribute_without_operator_is_structured():
    r = Requirement(id="r1", attribute="annual_family_income", criterion=TEXT, status="verified",
                    source_url=SRC, evidence=TEXT)
    llm = FakeLLM({"structured": [{"id": "r1", "attribute": "annual_family_income", "operator": "lte", "value": 250000}],
                   "extracted": []})
    out = normalize_scheme(scheme([r]), llm).requirements[0]
    assert [c["id"] for c in llm.payload()["criteria_to_structure"]] == ["r1"]
    assert out.operator == Operator.lte and out.value == 250000 and out.status == V.verified

def test_alias_mapped_to_canonical():
    s = scheme([Requirement(id="r1", attribute="Family Income", criterion="c", source_url=SRC)])
    assert normalize_scheme(s).requirements[0].attribute == "annual_family_income"


def test_unmapped_attribute_gets_slug():
    s = scheme([Requirement(id="r1", attribute="Hostel resident?", criterion="c", source_url=SRC)])
    assert normalize_scheme(s).requirements[0].attribute == "unmapped:hostel_resident"


def test_missing_source_forces_unverified():
    s = scheme([Requirement(id="r1", attribute="age", criterion="c", status="verified")])
    assert normalize_scheme(s).requirements[0].status == V.unverified


def test_ids_filled_and_text_preserved():
    reqs = [Requirement(attribute="age", criterion="  Exact  text ", source_url=SRC, evidence="ev"),
            Requirement(id="demo_n_req_1", attribute="gender", criterion="other", source_url=SRC)]
    out = normalize_scheme(scheme(reqs)).requirements
    assert [r.id for r in out] == ["demo_n_req_2", "demo_n_req_1"]
    assert (out[0].criterion, out[0].source_url, out[0].evidence) == ("  Exact  text ", SRC, "ev")


def test_duplicate_criteria_removed():
    reqs = [Requirement(id="a", attribute="age", criterion="Age up to 25."),
            Requirement(id="b", attribute="age", criterion="age  up to 25.")]
    assert [r.id for r in normalize_scheme(scheme(reqs)).requirements] == ["a"]


def test_works_without_llm_and_does_not_mutate(schemes):
    d = schemes["demo_unverified_d"]
    before = d.model_dump()
    out = normalize_scheme(d, None)
    assert d.model_dump() == before
    assert out.uncertainties == d.uncertainties
    assert out.requirements[0].status == V.unverified


def test_fixtures_unchanged_by_deterministic_pass(schemes):
    out = normalize_requirements(schemes.values())
    assert [s.model_dump() for s in out] == [s.model_dump() for s in schemes.values()]


# --- extraction from eligibility_text ---------------------------------------

def test_extracted_rule_verified_when_number_in_evidence():
    out = normalize_scheme(scheme(text=TEXT), FakeLLM(extracted()))
    r = out.requirements[0]
    assert (r.attribute, r.operator, r.value, r.status, r.source_url) == ("annual_family_income", Operator.lte, 250000, V.verified, SRC)
    assert r.id == "demo_n_req_1"


def test_misread_number_is_uncertain():
    out = normalize_scheme(scheme(text=TEXT), FakeLLM(extracted(value=300000)))
    assert out.requirements[0].status == V.uncertain


def test_extracted_without_source_is_unverified(schemes):
    llm = FakeLLM({"structured": [], "extracted": [{
        "attribute": "institution_type", "operator": "in", "value": ["government"],
        "criterion": "Students from government institutions are preferred.",
        "evidence": "Students from government institutions are preferred."}]})
    out = normalize_scheme(schemes["demo_unverified_d"], llm)
    new = out.requirements[-1]
    assert new.status == V.unverified and new.value == ["Government"]


def test_hallucinated_evidence_rejected():
    out = normalize_scheme(scheme(text=TEXT), FakeLLM(extracted(evidence="Income below Rs 8 lakh.", criterion="Income below Rs 8 lakh.")))
    assert out.requirements == []
    assert "Could not verify extracted rule: Income below Rs 8 lakh." in out.uncertainties


def test_criterion_not_in_text_replaced_by_evidence():
    out = normalize_scheme(scheme(text=TEXT), FakeLLM(extracted(criterion="Income limit is 2.5L")))
    assert out.requirements[0].criterion == "Family income must not exceed Rs 2.5 lakh per year."


@pytest.mark.parametrize(
    "item,expected_attr,expected_op",
    [
        ({"operator": "approximately"}, "annual_family_income", None),
        ({"operator": "in", "value": ["x"]}, "annual_family_income", None),  # wrong operator for a range
        ({"attribute": "hostel_resident", "operator": "is_true"}, "unmapped:hostel_resident", None),
        ({"attribute": "unmapped", "operator": "is_true"}, "unmapped:family_income_must_not_exceed_rs_2_5_lak", None),
        ({"attribute": "parental income"}, "annual_family_income", Operator.lte),
    ],
)
def test_bad_rules_degrade_to_needs_clarification(item, expected_attr, expected_op):
    r = normalize_scheme(scheme(text=TEXT), FakeLLM(extracted(**item))).requirements[0]
    assert r.attribute == expected_attr and r.operator == expected_op


def test_select_values_must_be_registry_options():
    item = {"attribute": "institution_type", "operator": "in", "value": ["Govt colleges"],
            "criterion": "Applicants must be 25 years of age or younger.", "evidence": "Applicants must be 25 years of age or younger."}
    r = normalize_scheme(scheme(text=TEXT), FakeLLM({"extracted": [item]})).requirements[0]
    assert r.operator is None


# --- structuring Member 1's text-only requirements ---------------------------

def test_text_only_requirement_structured():
    req = Requirement(id="r1", criterion="Applicant age must not exceed 25 years.", status="verified",
                      source_url=SRC, evidence="Applicant age must not exceed 25 years.")
    llm = FakeLLM({"structured": [{"id": "r1", "attribute": "age", "operator": "lte", "value": 25}], "extracted": []})
    r = normalize_scheme(scheme([req]), llm).requirements[0]
    assert (r.attribute, r.operator, r.value, r.status) == ("age", Operator.lte, 25, V.verified)
    assert llm.payload()["criteria_to_structure"][0]["id"] == "r1"


def test_structured_lakh_value_matches_evidence():
    req = Requirement(id="r1", criterion="Income up to 2.5 lakh", status="verified", source_url=SRC, evidence="Income up to 2.5 lakh")
    llm = FakeLLM({"structured": [{"id": "r1", "attribute": "annual_family_income", "operator": "lte", "value": 250000}]})
    assert normalize_scheme(scheme([req]), llm).requirements[0].status == V.verified


def test_structured_with_wrong_number_is_uncertain():
    req = Requirement(id="r1", criterion="Income up to 2.5 lakh", status="verified", source_url=SRC, evidence="Income up to 2.5 lakh")
    llm = FakeLLM({"structured": [{"id": "r1", "attribute": "annual_family_income", "operator": "gte", "value": 25000}]})
    assert normalize_scheme(scheme([req]), llm).requirements[0].status == V.uncertain


def test_structured_ignores_unknown_ids():
    req = Requirement(id="r1", criterion="c", source_url=SRC)
    llm = FakeLLM({"structured": [{"id": "zzz", "attribute": "age", "operator": "lte", "value": 25}]})
    assert normalize_scheme(scheme([req]), llm).requirements[0].attribute is None


# --- failures never raise -----------------------------------------------------

@pytest.mark.parametrize("bad", ["not json at all", "[1, 2, 3]", RuntimeError("provider down"), LLMError("refused")])
def test_failures_add_uncertainty_after_one_retry(bad):
    llm = FakeLLM(bad)
    out = normalize_scheme(scheme(text=TEXT), llm)
    assert len(llm.calls) == 2
    assert out.uncertainties == [EXTRACTION_FAILED] and out.requirements == []


def test_retry_can_succeed():
    llm = FakeLLM("garbage", "```json\n" + json.dumps(extracted()) + "\n```")
    out = normalize_scheme(scheme(text=TEXT), llm)
    assert len(llm.calls) == 2 and len(out.requirements) == 1 and out.uncertainties == []


def test_malformed_items_skipped_not_fatal():
    out = normalize_scheme(scheme(text=TEXT), FakeLLM({"extracted": ["nope", {"criterion": 5}], "structured": "bad"}))
    assert out.requirements == []


# --- idempotency --------------------------------------------------------------

def test_second_run_adds_nothing_and_skips_llm():
    llm = FakeLLM(extracted())
    once = normalize_scheme(scheme(text=TEXT), llm)
    twice = normalize_scheme(once, llm)
    assert len(llm.calls) == 1
    assert twice.model_dump() == once.model_dump()


def test_repeated_failure_does_not_duplicate_uncertainty():
    llm = FakeLLM("garbage")
    out = normalize_scheme(normalize_scheme(scheme(text=TEXT), llm), llm)
    assert out.uncertainties == [EXTRACTION_FAILED]


def test_round_trip_keeps_llm_mark():
    once = normalize_scheme(scheme(text=TEXT), FakeLLM(extracted()))
    reloaded = SchemeRecord.model_validate(json.loads(json.dumps(once.model_dump(mode="json"))))
    llm = FakeLLM(extracted())
    normalize_scheme(reloaded, llm)
    assert llm.calls == []


# --- privacy and matrix -------------------------------------------------------

def test_prompt_contains_only_scheme_text():
    llm = FakeLLM(extracted())
    normalize_scheme(scheme(text=TEXT), llm)
    assert set(llm.payload()) == {"criteria_to_structure", "eligibility_text"}


def test_requirement_matrix(schemes):
    m = requirement_matrix(schemes.values())
    assert m["annual_family_income"] == ["demo_fee_concession_b", "demo_scholarship_a"]
    assert m["age"] == ["demo_unverified_d"]


# --- AnthropicClient (no network) ---------------------------------------------

def _fake_response(stop_reason="end_turn", text='{"ok": true}'):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


def _client(monkeypatch, response, model=None):
    monkeypatch.delenv("UNLOCKED_MODEL", raising=False)
    c = AnthropicClient(model=model, api_key="test-key")
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return response

    monkeypatch.setattr(c._client.beta.messages, "create", create)
    return c, sent


def test_anthropic_module_not_imported_at_load():
    assert "anthropic" not in vars(llm_module)


def test_anthropic_client_request_shape(monkeypatch):
    c, sent = _client(monkeypatch, _fake_response())
    assert c.complete_json("sys", "user") == '{"ok": true}'
    assert sent["model"] == "claude-sonnet-5-5"
    assert sent["fallbacks"] == "default" and sent["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in sent


def test_anthropic_client_env_model_without_fallbacks(monkeypatch):
    c, sent = _client(monkeypatch, _fake_response(), model="claude-haiku-5-5")
    c.complete_json("s", "u")
    assert sent["model"] == "claude-haiku-5-5" and "fallbacks" not in sent


@pytest.mark.parametrize("response", [_fake_response("refusal"), _fake_response("max_tokens"), _fake_response(text="  ")])
def test_anthropic_client_unusable_output_raises(monkeypatch, response):
    c, _ = _client(monkeypatch, response)
    with pytest.raises(LLMError):
        c.complete_json("s", "u")


# --- compound criteria (live NSP example, fictionalised) ----------------------

COMPOUND = ("Total annual family income must not exceed Rs 4.5 lakh. Students must be admitted to "
            "regular degree programmes. Students enrolled in Distance programmes are ineligible.")


def _compound_scheme():
    return scheme([Requirement(id="r1", criterion=COMPOUND, status="verified", source_url=SRC, evidence=COMPOUND)])


def _compound_llm():
    return FakeLLM({"structured": [
        {"id": "r1", "attribute": "annual_family_income", "operator": "lte", "value": 450000},
        {"id": "r1", "attribute": "unmapped", "operator": None, "value": "regular degree programme"},
        {"id": "r1", "attribute": "unmapped", "operator": None, "value": "not distance education"},
    ], "extracted": []})


def test_compound_criterion_keeps_every_condition():
    reqs = normalize_scheme(_compound_scheme(), _compound_llm()).requirements
    assert [r.id for r in reqs] == ["r1", "r1_2", "r1_3"]
    assert reqs[0].attribute == "annual_family_income" and reqs[0].status == V.verified
    assert reqs[1].attribute == "unmapped:regular_degree_programme" and reqs[1].operator is None
    assert reqs[2].attribute == "unmapped:not_distance_education"
    assert all(r.evidence == COMPOUND for r in reqs)


def test_compound_split_is_idempotent_and_blocks_potential_match():
    from member2 import assess_schemes
    once = normalize_scheme(_compound_scheme(), _compound_llm())
    twice = normalize_scheme(once, FakeLLM(RuntimeError("must not be called")))
    assert [r.id for r in twice.requirements] == ["r1", "r1_2", "r1_3"]
    answers = {"annual_family_income": {"attribute": "annual_family_income", "state": "answered",
                                        "value": {"min": 100000, "max": 200000}}}
    status = assess_schemes([twice], answers)[0].status.value
    assert status != "potential_match"  # the two unmapped conditions keep it uncertain


# --- conditional limits (live BCW example, fictionalised) --------------------

CONDITIONAL = "4. Annual income limit is Rs. 2.50 lakh for Category-I students and Rs. 1.00 lakh for Category 2A, 3A and 3B."


def _one_rule(evidence, structured):
    s = scheme([Requirement(id="r1", criterion=evidence, status="verified", source_url=SRC, evidence=evidence)])
    return normalize_scheme(s, FakeLLM({"structured": structured, "extracted": []}))


def test_conditional_limit_is_not_verified():
    out = _one_rule(CONDITIONAL, [{"id": "r1", "attribute": "annual_family_income", "operator": "lte", "value": 250000}])
    assert out.requirements[0].status == V.uncertain
    assert any("different limits" in u for u in out.uncertainties)


def test_range_using_both_numbers_stays_verified():
    text = "Applicants must be between 18 and 25 years of age."
    out = _one_rule(text, [{"id": "r1", "attribute": "age", "operator": "gte", "value": 18},
                           {"id": "r1", "attribute": "age", "operator": "lte", "value": 25}])
    assert [r.status for r in out.requirements] == [V.verified, V.verified]


def test_list_numbers_and_codes_do_not_trigger():
    text = "3. Marks of at least 60 percent in Category 2A courses."
    out = _one_rule(text, [{"id": "r1", "attribute": "previous_year_marks_percent", "operator": "gte", "value": 60}])
    assert out.requirements[0].status == V.verified


def test_unmapped_name_with_digits_keeps_status():
    text = "Students must be listed in the PUC-II merit list and be meritorious."
    out = _one_rule(text, [{"id": "r1", "attribute": "unmapped", "operator": None, "value": "meritorious_puc2_list"}])
    assert out.requirements[0].status == V.verified


# --- select values must be stated -----------------------------------------------

def test_unstated_extra_option_is_uncertain():
    text = "Students belonging to backward classes are eligible."
    out = _one_rule(text, [{"id": "r1", "attribute": "social_category", "operator": "in", "value": ["OBC", "Other"]}])
    assert out.requirements[0].status == V.uncertain


# --- group-specific rules (live Sir C.V. Raman wording, fictionalised) -------

MARKS = "Students passed previous year exam with 65% (General category) and 60% (Scheduled Castes and Scheduled Tribes)."


def _marks_scheme(when_general=None, when_scst=None):
    when_general = when_general or {"attribute": "social_category", "operator": "eq", "value": "General"}
    when_scst = when_scst or {"attribute": "social_category", "operator": "in", "value": ["SC", "ST"]}
    when_general = {**when_general, "quote": when_general.get("quote", "General category")}
    when_scst = {**when_scst, "quote": when_scst.get("quote", "Scheduled Castes and Scheduled Tribes")}
    s = scheme([Requirement(id="r1", criterion=MARKS, status="verified", source_url=SRC, evidence=MARKS)])
    return normalize_scheme(s, FakeLLM({"structured": [
        {"id": "r1", "attribute": "previous_year_marks_percent", "operator": "gte", "value": 65, "when": when_general,
         "value_quote": "65%"},
        {"id": "r1", "attribute": "previous_year_marks_percent", "operator": "gte", "value": 60, "when": when_scst,
         "value_quote": "60%"},
    ], "extracted": []}, {"results": {"0": True, "1": True}}))  # 2nd call: meaning check for SC, ST


def _assess(s, **answers):
    from member2 import assess_schemes
    a = {k: {"attribute": k, "state": "answered", "value": v} for k, v in answers.items()}
    return assess_schemes([s], a)[0]


def test_group_rules_are_verified_and_not_conflicting():
    s = _marks_scheme()
    assert [r.status for r in s.requirements] == [V.verified, V.verified]
    assert s.requirements[1].condition.value == ["SC", "ST"]
    assert not any("different limits" in u for u in s.uncertainties)
    res = _assess(s)
    assert res.status.value == "more_information_needed"
    assert "social_category" in res.missing_attributes


def test_group_rule_applies_only_to_its_group():
    s = _marks_scheme()
    assert _assess(s, social_category="SC", previous_year_marks_percent=62).status.value != "unlikely_to_match"
    assert _assess(s, social_category="General", previous_year_marks_percent=62).status.value == "unlikely_to_match"
    assert _assess(s, social_category="General", previous_year_marks_percent=70).status.value != "unlikely_to_match"


def test_unstated_group_makes_rule_uncertain():
    s = scheme([Requirement(id="r1", criterion=MARKS, status="verified", source_url=SRC, evidence=MARKS)])
    out = normalize_scheme(s, FakeLLM({"structured": [
        {"id": "r1", "attribute": "previous_year_marks_percent", "operator": "gte", "value": 60, "value_quote": "60%",
         "when": {"attribute": "social_category", "operator": "in", "value": ["OBC"],
                  "quote": "Scheduled Castes and Scheduled Tribes"}}], "extracted": []},
        {"results": {"0": False}}))  # the meaning check rejects "Scheduled Castes" = OBC
    assert out.requirements[0].status == V.uncertain

def test_category_question_is_asked_for_group_rules():
    from member2 import generate_consolidated_questions
    attrs = [q.attribute for q in generate_consolidated_questions([_marks_scheme()], {}, {})]
    assert "social_category" in attrs and "previous_year_marks_percent" in attrs


def test_group_rules_survive_renormalization():
    once = _marks_scheme()
    twice = normalize_scheme(once, FakeLLM(RuntimeError("must not be called")))
    assert [r.id for r in twice.requirements] == ["r1", "r1_2"]
    assert twice.requirements[0].condition.value == "General"


def test_small_counts_do_not_trigger_limit_warning():
    text = "First year B.Sc. students who have taken at least 2 subjects of the list Physics, Chemistry, Mathematics."
    out = _one_rule(text, [{"id": "r1", "attribute": "year_of_study", "operator": "eq", "value": 1},
                           {"id": "r1", "attribute": "unmapped", "operator": None, "value": "two core science subjects"}])
    assert not any("different limits" in u for u in out.uncertainties)


# --- number words and non-rules (live findings) -------------------------------




# --- cited values and the independent meaning check (DECISIONS #66) ---------

def _cited(evidence, structured, confirm=None):
    s = scheme([Requirement(id="r1", criterion=evidence, status="verified", source_url=SRC, evidence=evidence)])
    llm = FakeLLM({"structured": structured, "extracted": []}, *( [confirm] if confirm is not None else []))
    return normalize_scheme(s, llm), llm


def test_literal_value_needs_no_meaning_check():
    out, llm = _cited("Only Government and Aided colleges are eligible.",
                      [{"id": "r1", "attribute": "institution_type", "operator": "in", "value": ["Government", "Aided"],
                        "value_quote": "Government and Aided colleges"}])
    assert out.requirements[0].status == V.verified and len(llm.calls) == 1


def test_paraphrased_value_confirmed_by_second_call():
    out, llm = _cited("Meritorious girl students admitted to the first year of degree courses.",
                      [{"id": "r1", "attribute": "gender", "operator": "eq", "value": "Female", "value_quote": "girl students"},
                       {"id": "r1", "attribute": "year_of_study", "operator": "eq", "value": 1, "value_quote": "first year"}],
                      {"results": {"0": True, "1": True}})
    assert [r.status for r in out.requirements] == [V.verified, V.verified]
    checked = json.loads(llm.calls[1][1])["items"]
    assert [(i["phrase"], i["value"]) for i in checked] == [("girl students", "Female"), ("first year", 1)]


def test_rejected_meaning_makes_rule_uncertain():
    out, _ = _cited("Backward classes pursuing post-matric education in Government institutions are eligible.",
                    [{"id": "r1", "attribute": "education_level", "operator": "eq", "value": "Postgraduate",
                      "value_quote": "post-matric education"}],
                    {"results": {"0": False}})
    assert out.requirements[0].status == V.uncertain and out.requirements[0].uncertain_reason == "not_stated"


def test_quote_not_in_evidence_falls_back_to_literal_only():
    out, _ = _cited("Only girl students may apply.",
                    [{"id": "r1", "attribute": "gender", "operator": "eq", "value": "Female", "value_quote": "women only"}])
    assert out.requirements[0].status == V.uncertain  # cited words aren't there; "Female" isn't literal


def test_failed_meaning_check_rejects():
    out, _ = _cited("Only girl students may apply.",
                    [{"id": "r1", "attribute": "gender", "operator": "eq", "value": "Female", "value_quote": "girl students"}],
                    "not json")
    assert out.requirements[0].status == V.uncertain


def test_digits_in_quote_must_match_value():
    out, _ = _cited("Annual family income must not exceed Rs 2.5 lakh.",
                    [{"id": "r1", "attribute": "annual_family_income", "operator": "lte", "value": 300000,
                      "value_quote": "Rs 2.5 lakh"}])
    assert out.requirements[0].status == V.uncertain


def test_model_flagged_non_restriction_is_dropped():
    out, _ = _cited("Girl students of all courses are eligible.",
                    [{"id": "r1", "attribute": "gender", "operator": "eq", "value": "Female", "value_quote": "Girl students"},
                     {"id": "r1", "attribute": "unmapped", "operator": None, "value": "all courses", "restricts": False}],
                    {"results": {"0": True}})
    assert [r.attribute for r in out.requirements] == ["gender"]


def test_select_covering_every_option_is_dropped():
    from member2.attributes import ATTRIBUTES
    every = ATTRIBUTES["social_category"].options
    out, _ = _cited("Students of every category are eligible.",
                    [{"id": "r1", "attribute": "social_category", "operator": "in", "value": every}])
    assert out.requirements == []
