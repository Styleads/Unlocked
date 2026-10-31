"""
api/recovery.py — Source-grounded rejection investigation and recovery engine.

Product principle:
A rejection is an investigation trigger, not an automatic terminal state and not an automatic appeal.
Unlocked must verify whether an official remedy exists before recommending it. If no remedy is
supported by available official information, explain that clearly and discover alternative schemes.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from agent4 import (
    analyse_rejection,
    build_email_draft,
    email_request_for_step,
    facts_from_scheme,
)
from agent4.models import (
    ActionArtifact,
    EmailPurpose,
    EmailRequest,
    NextStep,
    RejectionAnalysis,
    RejectionRoute,
    SchemeContext,
    SourcedFact,
)
from discovery_agent.fallback_schemes import get_fallback_schemes
from member2.models import SchemeRecord

logger = logging.getLogger(__name__)


class RecoveryActionClass(str, Enum):
    correct_document = "correct_document"
    submit_supplementary_documents = "submit_supplementary_documents"
    request_clarification = "request_clarification"
    file_grievance = "file_grievance"
    appeal_or_reconsideration = "appeal_or_reconsideration"
    reapply = "reapply"
    alternative_scheme = "alternative_scheme"
    no_supported_remedy_found = "no_supported_remedy_found"
    needs_more_information = "needs_more_information"
    unknown = "unknown"


class RecoveryStatus(str, Enum):
    not_started = "not_started"
    investigating = "investigating"
    needs_more_information = "needs_more_information"
    action_available = "action_available"
    no_supported_remedy_found = "no_supported_remedy_found"
    user_action_pending = "user_action_pending"
    resolved = "resolved"
    closed = "closed"


def find_alternative_schemes(
    rejected_scheme_id: str,
    target_groups: Optional[list[str]] = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Find alternative welfare schemes when a rejection is non-recoverable,
    excluding the rejected scheme itself.
    """
    alternatives = []
    target_set = set(t.lower() for t in (target_groups or []))

    for raw in get_fallback_schemes():
        s_id = getattr(raw, "id", "")
        if s_id == rejected_scheme_id:
            continue

        raw_targets = set(t.lower() for t in (getattr(raw, "target_group", []) or []))
        overlap = bool(target_set.intersection(raw_targets)) if target_set else True

        if overlap:
            alternatives.append({
                "id": getattr(raw, "id", ""),
                "name": getattr(raw, "name", ""),
                "department": getattr(raw, "department", ""),
                "benefit": getattr(raw, "benefit", None),
                "summary": getattr(raw, "summary", ""),
                "application_url": getattr(raw, "application_url", None),
                "official_sources": getattr(raw, "official_sources", []) or [],
            })
            if len(alternatives) >= limit:
                break

    return alternatives


async def investigate_rejection(
    scheme: Any,
    notice_text: Optional[str] = None,
    reported_reason: Optional[str] = None,
    reason_category: Optional[str] = None,
    llm: Optional[Any] = None,
    simulated: bool = False,
) -> dict[str, Any]:
    """
    Investigate an application rejection with official guidance verification,
    action classification, and grounded user next actions.
    """
    # 1. Prepare scheme context and facts
    s_ctx = scheme if isinstance(scheme, SchemeContext) else SchemeContext.model_validate(scheme)
    facts: list[SourcedFact] = facts_from_scheme(scheme)

    # Combine user reported inputs
    combined_notice = (notice_text or "").strip()
    if not combined_notice and reported_reason:
        combined_notice = reported_reason.strip()

    # Guidance passages for Agent 4
    guidance = list(facts)
    # Add application url if known
    if s_ctx.application_url:
        guidance.append(SourcedFact(
            text=f"Official application portal for {s_ctx.name}: {s_ctx.application_url}",
            source_url=s_ctx.application_url,
        ))

    # 2. Run Agent 4 rejection analyzer
    analysis: RejectionAnalysis = analyse_rejection(
        scheme=s_ctx,
        notice_text=combined_notice,
        guidance=guidance,
        llm=llm,
        simulated=simulated,
    )

    reason_lower = (reported_reason or "").lower() + " " + (notice_text or "").lower() + " " + (reason_category or "").lower()
    next_actions: list[dict[str, Any]] = []
    draft_artifact: Optional[ActionArtifact] = None
    warnings: list[str] = list(analysis.warnings)

    # 3. Determine action classification based on verified facts and reported categories
    if not combined_notice:
        action_class = RecoveryActionClass.needs_more_information
        status = RecoveryStatus.needs_more_information
        explanation = "Please provide the stated rejection reason or notice text so Unlocked can verify official remedies."
    elif any(kw in reason_lower for kw in ("document", "certificate", "income certificate", "caste certificate", "format", "invalid")):
        action_class = RecoveryActionClass.correct_document
        status = RecoveryStatus.action_available
        explanation = "The rejection indicates a missing, invalid, or expired document. You can obtain or re-verify this document through the official issuing authority."
        doc_source = s_ctx.application_url or "https://nadakacheri.karnataka.gov.in"
        next_actions.append({
            "route": "correct_document",
            "description": "Verify and obtain an updated document or certificate before reapplying.",
            "evidence": "Document verification requirement for eligibility determination.",
            "source_url": doc_source,
            "deadline_text": None,
        })
        # Draft a clarification / correction request
        email_req = EmailRequest(
            scheme=s_ctx,
            purpose=EmailPurpose.correction_request,
            question=f"My application was rejected with the following document issue: {reported_reason or 'Document verification issue'}. Could you please guide me on how to submit the corrected document?",
            facts=facts[:2],
        )
        draft_artifact = build_email_draft(email_req, llm=llm)

    elif analysis.supported and analysis.next_steps:
        # Route supported by official guidance
        primary_step = analysis.next_steps[0]
        if primary_step.route == RejectionRoute.appeal:
            action_class = RecoveryActionClass.appeal_or_reconsideration
        elif primary_step.route == RejectionRoute.correction:
            action_class = RecoveryActionClass.correct_document
        elif primary_step.route == RejectionRoute.reapplication:
            action_class = RecoveryActionClass.reapply
        else:
            action_class = RecoveryActionClass.request_clarification

        status = RecoveryStatus.action_available
        explanation = analysis.explanation
        for st in analysis.next_steps:
            next_actions.append({
                "route": st.route.value,
                "description": st.description,
                "evidence": st.evidence,
                "source_url": st.source_url,
                "deadline_text": st.deadline_text,
            })

        # Build email draft for user review
        email_req = email_request_for_step(
            scheme=s_ctx,
            step=primary_step,
            question=f"Regarding my application for {s_ctx.name}: {reported_reason or 'Review request'}",
        )
        draft_artifact = build_email_draft(email_req, llm=llm)

    elif (
        ("income" in reason_lower and any(w in reason_lower for w in ("above", "exceed", "limit", "high", "more than")))
        or any(kw in reason_lower for kw in ("not eligible", "age limit", "criteria not met", "criteria_not_met", "ineligible"))
        or reason_category in ("criteria_not_met", "income_limit_exceeded", "ineligible")
    ):
        action_class = RecoveryActionClass.alternative_scheme
        status = RecoveryStatus.no_supported_remedy_found
        explanation = "Official criteria for this scheme do not appear to be met based on the reported reason. An appeal is not supported by official guidelines. We recommend exploring alternative schemes."
    else:
        action_class = RecoveryActionClass.no_supported_remedy_found
        status = RecoveryStatus.no_supported_remedy_found
        explanation = "No officially supported appeal or correction procedure was found in the verified guidelines. You may request formal clarification from the department."
        # Offer clarification draft
        email_req = EmailRequest(
            scheme=s_ctx,
            purpose=EmailPurpose.clarification,
            question=f"I am writing to respectfully request clarification regarding the rejection of my application: {reported_reason or 'Reason clarification'}.",
            facts=facts[:2],
        )
        draft_artifact = build_email_draft(email_req, llm=llm)

    # 4. Check for alternative schemes if remedy is not found or alternative requested
    alternatives: list[dict[str, Any]] = []
    if action_class in (RecoveryActionClass.alternative_scheme, RecoveryActionClass.no_supported_remedy_found):
        target_group = getattr(scheme, "target_group", []) if hasattr(scheme, "target_group") else scheme.get("target_group", [])
        alternatives = find_alternative_schemes(rejected_scheme_id=s_ctx.id, target_groups=target_group)

    return {
        "scheme_id": s_ctx.id,
        "scheme_name": s_ctx.name,
        "reported_reason": reported_reason or combined_notice,
        "reason_quote": analysis.reason_quote,
        "reason_summary": analysis.reason_summary,
        "recovery_status": status.value,
        "action_classification": action_class.value,
        "explanation": explanation,
        "next_actions": next_actions,
        "email_draft": draft_artifact.model_dump(mode="json") if draft_artifact else None,
        "alternative_schemes": alternatives,
        "warnings": warnings,
        "simulated": simulated,
    }
