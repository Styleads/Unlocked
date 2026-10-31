from agent4 import EmailPurpose, RejectionRoute, SourcedFact, analyse_rejection, build_email_draft, email_request_for_step

NOTICE = ("Dear applicant, your application APP-00042 has been rejected. Reason: Income certificate has expired. "
          "Contact 9876543210 for queries.")
GUIDANCE = [
    SourcedFact(text="Applicants whose application is rejected for a document error may submit a correction "
                     "within 15 days of the rejection notice through the portal.",
                source_url="https://example.gov.in/guidelines#corrections"),
]
GOOD = {
    "reason_quote": "Reason: Income certificate has expired.",
    "reason_summary": "Your income certificate was no longer valid.",
    "next_steps": [{"route": "correction", "description": "Upload a valid income certificate as a correction.",
                    "evidence": "may submit a correction within 15 days of the rejection notice",
                    "source_index": 0, "deadline_text": "within 15 days of the rejection notice"}],
}


def test_supported_route_is_kept(scheme, llm_factory):
    llm = llm_factory(GOOD)
    r = analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm)
    assert r.supported and len(r.next_steps) == 1
    step = r.next_steps[0]
    assert step.route is RejectionRoute.correction
    assert step.source_url == "https://example.gov.in/guidelines#corrections"
    assert step.deadline_text == "within 15 days of the rejection notice"
    assert r.reason_quote == "Reason: Income certificate has expired."


def test_notice_is_redacted_before_llm(scheme, llm_factory):
    llm = llm_factory(GOOD)
    analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm)
    assert "9876543210" not in llm.calls[0][1]


def test_unquoted_evidence_is_dropped(scheme, llm_factory):
    bad = dict(GOOD, next_steps=[{"route": "appeal", "description": "File an appeal with the Commissioner.",
                                  "evidence": "Appeals may be filed with the Commissioner", "source_index": 0}])
    r = analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm_factory(bad))
    assert not r.supported and r.next_steps == []
    assert "couldn't find an officially stated next step" in r.explanation
    assert any("couldn't be matched" in w for w in r.warnings)


def test_invented_number_in_description_is_dropped(scheme, llm_factory):
    bad = dict(GOOD, next_steps=[dict(GOOD["next_steps"][0], description="Submit a correction within 30 days.")])
    assert not analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm_factory(bad)).supported


def test_bad_index_and_route_are_dropped(scheme, llm_factory):
    bad = dict(GOOD, next_steps=[dict(GOOD["next_steps"][0], source_index=5), dict(GOOD["next_steps"][0], route="lawsuit")])
    assert analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm_factory(bad)).next_steps == []


def test_unmatched_reason_quote_hides_summary(scheme, llm_factory):
    r = analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm_factory(dict(GOOD, reason_quote="Caste certificate missing.")))
    assert r.reason_quote is None and r.reason_summary is None


def test_no_llm_or_failure_never_raises(scheme, llm_factory):
    assert not analyse_rejection(scheme, NOTICE, GUIDANCE).supported
    assert not analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm_factory(RuntimeError("x"))).supported
    assert not analyse_rejection(scheme, "   ", GUIDANCE, llm=llm_factory(GOOD)).supported


def test_no_guidance_means_no_route(scheme, llm_factory):
    r = analyse_rejection(scheme, NOTICE, [], llm=llm_factory(GOOD))
    assert not r.supported


def test_simulated_is_marked(scheme):
    r = analyse_rejection(scheme, NOTICE, GUIDANCE, simulated=True)
    assert r.simulated and any("simulated" in w for w in r.warnings)


def test_email_for_step_carries_evidence(scheme, llm_factory):
    r = analyse_rejection(scheme, NOTICE, GUIDANCE, llm=llm_factory(GOOD))
    req = email_request_for_step(scheme, r.next_steps[0], "I have a renewed income certificate.", {"Name": "Asha K"})
    assert req.purpose is EmailPurpose.correction_request
    a = build_email_draft(req)
    assert "https://example.gov.in/guidelines#corrections" in a.source_urls
    assert email_request_for_step(scheme, None, "Why was I rejected?").purpose is EmailPurpose.clarification
