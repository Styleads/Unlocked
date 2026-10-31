"""Email drafts the user reviews, copies and sends themselves. Unlocked never sends.

The LLM, if given, only words the letter. It never sees the user's detail values
(they are {{tokens}} until after validation), and its output is rejected for any
number that isn't in the sources, so it can't invent dates, amounts or ids.
Any email, link or phone number not from a sourced field becomes a placeholder."""
from __future__ import annotations

from typing import Any, Optional

from .grounding import EMAIL_RE, PHONE_RE, URL_RE, call_llm_json, redact, replace_unsourced, unsupported_numbers
from .models import (
    PLACEHOLDER_EMAIL,
    PLACEHOLDER_LINK,
    PLACEHOLDER_PHONE,
    ActionArtifact,
    ActionType,
    ArtifactStatus,
    EmailPurpose,
    EmailRequest,
)

PURPOSE_SUBJECT = {
    EmailPurpose.inquiry: "Query regarding",
    EmailPurpose.clarification: "Request for clarification on",
    EmailPurpose.document_query: "Query about required documents for",
    EmailPurpose.status_query: "Application status enquiry for",
    EmailPurpose.correction_request: "Request to correct my application for",
    EmailPurpose.appeal: "Request for review of decision on",
}

PURPOSE_OPENING = {
    EmailPurpose.inquiry: "I would like some information about this scheme.",
    EmailPurpose.clarification: "I would like to clarify one of the published requirements.",
    EmailPurpose.document_query: "I would like to confirm the documents needed for my application.",
    EmailPurpose.status_query: "I would like to know the current status of my application.",
    EmailPurpose.correction_request: "I would like to request a correction to my application.",
    EmailPurpose.appeal: "I would like to request a review of the decision on my application, as provided for in the official guidance.",
}

SYSTEM = (
    "You draft a short, formal, polite email from a citizen in Karnataka, India to a government "
    "department about a welfare scheme. The citizen will review and send it themselves. "
    "Use only the facts given. Do not add any date, amount, deadline, reference number, email address, "
    "phone number or link that is not in the input. Keep every {{token}} exactly as written; they are "
    "filled in later. Quote official facts only as given. "
    'Return only JSON: {"subject": "...", "body": "..."}. The body starts with "Dear Sir/Madam," '
    "and ends with a sign-off using the {{Name}} token if present."
)

INSTRUCTIONS = (
    "This is a draft for you to review. Check every line, fill in any [bracketed] placeholders, "
    "and send it yourself from your own email. Unlocked does not send emails."
)


def _token(key: str) -> str:
    return "{{" + key + "}}"


def _template(req: EmailRequest) -> tuple[str, str]:
    s = req.scheme
    subject = f"{PURPOSE_SUBJECT[req.purpose]} {s.name}"
    dept = f" administered by {s.department}" if s.department else ""
    lines = ["Dear Sir/Madam,", "", f"I am writing regarding {s.name}{dept}. {PURPOSE_OPENING[req.purpose]}", "", req.question.strip()]
    if req.facts:
        lines += ["", "For reference, the official guidance states:"]
        lines += [f'- "{f.text.strip()}" ({f.source_url})' for f in req.facts]
    if req.user_details:
        lines += ["", "My details:"]
        lines += [f"- {k}: {_token(k)}" for k in req.user_details]
    sign = _token("Name") if "Name" in req.user_details else "[Your Name]"
    lines += ["", "I would be grateful for your guidance.", "", "Yours faithfully,", sign]
    return subject, "\n".join(lines)


def _fill(text: str, details: dict[str, str]) -> str:
    for k, v in details.items():
        text = text.replace(_token(k), v)
    return text


def build_email_draft(request: EmailRequest | dict, *, llm: Optional[Any] = None) -> ActionArtifact:
    req = request if isinstance(request, EmailRequest) else EmailRequest.model_validate(request)
    s = req.scheme
    warnings: list[str] = []

    sourced_email = s.contact_email if s.contact_email and s.contact_email_source_url else None
    sourced_phone = s.contact_phone if s.contact_phone and s.contact_phone_source_url else None
    allowed_urls = [u for u in [s.application_url, *s.official_sources, *(f.source_url for f in req.facts)] if u]
    if s.contact_email and not sourced_email:
        warnings.append("The department email on file has no official source, so it was not used.")

    subject, body = _template(req)
    generated_by = "template"

    if llm is not None:
        payload = {
            "scheme_name": s.name,
            "department": s.department,
            "purpose": req.purpose.value,
            "citizen_question": redact(req.question),
            "official_facts": [{"text": f.text, "source_url": f.source_url} for f in req.facts],
            "detail_tokens": [_token(k) for k in req.user_details],
        }
        data = call_llm_json(llm, SYSTEM, payload, task="email_draft", ref=s.id)
        if data is not None:
            subj, text = data.get("subject"), data.get("body")
            ok = isinstance(subj, str) and isinstance(text, str) and 5 <= len(subj) <= 200 and 40 <= len(text) <= 5000
            corpus = [s.name, s.department or "", req.question, s.deadline or "", *(f.text for f in req.facts), *allowed_urls]
            if ok and not unsupported_numbers(subj + "\n" + text, corpus):
                missing = [k for k in req.user_details if _token(k) not in text]
                if missing:  # the model dropped some confirmed details; keep them
                    text += "\n\nMy details:\n" + "\n".join(f"- {k}: {_token(k)}" for k in missing)
                subject, body, generated_by = subj.strip(), text.strip(), "llm"
            else:
                warnings.append("The AI draft didn't pass our checks, so a standard template was used.")

    # Contacts the user typed in their own question are theirs; anything else must be sourced.
    own = req.question
    body, found = replace_unsourced(
        body, emails=[*([sourced_email] if sourced_email else []), *EMAIL_RE.findall(own)],
        urls=[*allowed_urls, *URL_RE.findall(own)],
        phones=[*([sourced_phone] if sourced_phone else []), *PHONE_RE.findall(own)],
        email_placeholder=PLACEHOLDER_EMAIL, url_placeholder=PLACEHOLDER_LINK, phone_placeholder=PLACEHOLDER_PHONE,
    )
    warnings += found
    # User values go in last, after the checks, so they are never altered or flagged.
    body, subject = _fill(body, req.user_details), _fill(subject, req.user_details)

    if sourced_email is None:
        warnings.append("We don't have a verified email address for this department. Find it on the official website before sending.")
    if req.purpose is EmailPurpose.appeal and not req.facts:
        warnings.append("No official guidance was attached that provides for a review or appeal. Check the official procedure before sending.")

    return ActionArtifact(
        action_type=ActionType.email_draft,
        status=ArtifactStatus.ready,
        title=f"Email draft: {s.name}",
        subject=subject,
        body_content=body,
        target_destination=sourced_email,
        instructions=INSTRUCTIONS,
        mime_type="text/plain",
        source_urls=sorted({u for u in ([s.contact_email_source_url] if sourced_email else []) + [f.source_url for f in req.facts]}),
        warnings=warnings,
        generated_by=generated_by,
    )
