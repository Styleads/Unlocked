from agent4 import EmailPurpose, EmailRequest, SourcedFact, build_email_draft
from agent4.models import PLACEHOLDER_EMAIL, PLACEHOLDER_LINK, PLACEHOLDER_PHONE


def _req(scheme, **kw):
    return EmailRequest(scheme=scheme, question=kw.pop("question", "Is the income limit per family or per student?"), **kw)


def test_template_without_llm(scheme):
    a = build_email_draft(_req(scheme, user_details={"Name": "Asha K"}))
    assert a.generated_by == "template"
    assert a.target_destination == "helpdesk@example.gov.in"
    assert a.body_content.startswith("Dear Sir/Madam,")
    assert "Is the income limit per family or per student?" in a.body_content
    assert a.body_content.rstrip().endswith("Asha K")
    assert a.user_review_confirmed is False
    assert "https://example.gov.in/contact" in a.source_urls


def test_unsourced_contact_email_is_not_used(unsourced_scheme):
    a = build_email_draft(_req(unsourced_scheme))
    assert a.target_destination is None
    assert "someone@example.gov.in" not in a.body_content
    assert any("no official source" in w for w in a.warnings)
    assert any("verified email address" in w for w in a.warnings)


def test_llm_never_sees_detail_values_or_identifiers(scheme, llm_factory):
    llm = llm_factory({"subject": "Query", "body": "Dear Sir/Madam,\n\nPlease advise.\n\n{{Name}}\nApplication ID: {{Application ID}}"})
    req = _req(scheme, question="My Aadhaar 1234 5678 9012 and phone 9876543210, is income per family?",
               user_details={"Name": "Asha K", "Application ID": "APP-00042"})
    a = build_email_draft(req, llm=llm)
    sent = llm.calls[0][1]
    assert "Asha K" not in sent and "APP-00042" not in sent
    assert "1234 5678 9012" not in sent and "9876543210" not in sent
    assert a.generated_by == "llm"
    assert "Asha K" in a.body_content and "APP-00042" in a.body_content


def test_llm_invented_number_falls_back_to_template(scheme, llm_factory):
    llm = llm_factory({"subject": "Query", "body": "Dear Sir/Madam,\n\nThe deadline is 30 November 2026. Please confirm.\n\nThanks"})
    a = build_email_draft(_req(scheme), llm=llm)
    assert a.generated_by == "template"
    assert "30 November" not in a.body_content
    assert any("didn't pass our checks" in w for w in a.warnings)


def test_numbers_from_facts_are_allowed(scheme, llm_factory):
    fact = SourcedFact(text="Annual family income must not exceed Rs 2,50,000.", source_url="https://example.gov.in/guidelines")
    llm = llm_factory({"subject": "Income limit query", "body": "Dear Sir/Madam,\n\nThe guidance says the limit is Rs 2,50,000. Is this per family?\n\nThanks"})
    a = build_email_draft(_req(scheme, facts=[fact]), llm=llm)
    assert a.generated_by == "llm"


def test_invented_contacts_become_placeholders(scheme, llm_factory):
    llm = llm_factory({"subject": "Query", "body": "Dear Sir/Madam,\n\nWrite to fake@gov.in or visit https://evil.example.com or call the helpline. "
                                                   "The portal is https://example.gov.in/apply.\n\nThanks"})
    a = build_email_draft(_req(scheme), llm=llm)
    assert "fake@gov.in" not in a.body_content and PLACEHOLDER_EMAIL in a.body_content
    assert "evil.example.com" not in a.body_content and PLACEHOLDER_LINK in a.body_content
    assert "https://example.gov.in/apply" in a.body_content


def test_users_own_contacts_are_kept_but_invented_ones_are_not(scheme, llm_factory):
    q = "Can I call 080 2222 3333 about this?"
    assert "080 2222 3333" in build_email_draft(_req(scheme, question=q)).body_content
    llm = llm_factory({"subject": "Query", "body": "Dear Sir/Madam,\n\nPlease call me back. Or I will ring 080 4444 5555.\n\nThanks"})
    a = build_email_draft(_req(scheme, question=q), llm=llm)
    assert "080 4444 5555" not in a.body_content


def test_invented_phone_is_placeholdered(scheme, llm_factory):
    # Numbers must also pass the number check, so put the phone in a sourced fact to isolate the contact rule.
    fact = SourcedFact(text="Helpline 080 4444 5555 is open on weekdays.", source_url="https://example.gov.in/guidelines")
    llm = llm_factory({"subject": "Query", "body": "Dear Sir/Madam,\n\nI saw the helpline 080 4444 5555 is open on weekdays.\n\nThanks"})
    a = build_email_draft(_req(scheme, facts=[fact]), llm=llm)
    assert a.generated_by == "llm"
    assert "080 4444 5555" not in a.body_content and PLACEHOLDER_PHONE in a.body_content


def test_llm_failure_never_raises(scheme, llm_factory):
    for bad in (RuntimeError("boom"), "not json", "[1, 2]", {"subject": 3, "body": None}):
        a = build_email_draft(_req(scheme), llm=llm_factory(bad))
        assert a.generated_by == "template"


def test_dropped_detail_tokens_are_restored(scheme, llm_factory):
    llm = llm_factory({"subject": "Query", "body": "Dear Sir/Madam,\n\nPlease advise on the income rule.\n\nRegards"})
    a = build_email_draft(_req(scheme, user_details={"Name": "Asha K"}), llm=llm)
    assert "Name: Asha K" in a.body_content


def test_appeal_without_guidance_warns(scheme):
    a = build_email_draft(_req(scheme, purpose=EmailPurpose.appeal))
    assert any("appeal" in w for w in a.warnings)


def test_accepts_plain_dict(scheme):
    a = build_email_draft({"scheme": scheme.model_dump(), "question": "When are results announced?"})
    assert a.title == "Email draft: Demo Scholarship A"
