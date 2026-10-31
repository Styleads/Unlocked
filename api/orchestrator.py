"""
api/orchestrator.py — Master Workflow Coordinator for Project Unlocked.

Connects Member 1 Discovery Engine, Member 1 Kannada Translator, the M1<->M2 Adapter,
and Member 2 Eligibility & Document Planning into a single deterministic pipeline,
persisting all citizen state across all workflow stages in SQLite.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Sequence, Union

from api.adapter import adapt_m1_to_m2_schemes
from api.database import (
    DEFAULT_DB_PATH,
    get_session,
    update_answers_and_assessments,
    update_discovery_results,
    update_plan,
    update_scheme_progress,
)
from api.schemas import (
    AnswerInput,
    DiscoveryResult,
    ReassessmentResult,
    SchemeView,
    SessionCalendarActionRequest,
    SessionEmailActionRequest,
    SessionRejectionActionRequest,
)
from discovery_agent.discovery_pipeline import discover_schemes
from discovery_agent.kannada_translator import translate_schemes_to_kannada
from member2 import (
    apply_answers,
    assess_schemes,
    build_action_plan,
    default_client,
    generate_consolidated_questions,
    normalize_requirements,
    reassess_schemes,
)
from member2.models import (
    ActionPlan,
    Answer,
    Assessment,
    DocStatus,
    Question,
    SchemeRecord,
)
from agent4 import (
    analyse_rejection,
    build_calendar_artifact,
    build_email_draft,
    facts_from_scheme,
    update_progress,
)
from agent4.models import (
    ActionArtifact,
    ApplicationProgress,
    CalendarRequest,
    EmailRequest,
    ProgressResult,
    ProgressUpdate,
    RejectionAnalysis,
    SourcedFact,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# View Construction Helper
# ---------------------------------------------------------------------------

def build_scheme_views(
    schemes: Sequence[SchemeRecord],
    assessments: Sequence[Assessment],
) -> list[SchemeView]:
    """
    Unite canonical SchemeRecords with their corresponding Assessment results
    for presentation by Member 4 (Frontend).
    """
    assessments_by_id = {a.scheme_id: a for a in assessments}
    views: list[SchemeView] = []

    for s in schemes:
        ass = assessments_by_id.get(s.id)
        views.append(
            SchemeView(
                id=s.id,
                name=s.name,
                summary=s.summary,
                government_level=s.government_level,
                department=s.department,
                benefit=s.benefit,
                target_group=s.target_group,
                documents=[
                    d.model_dump(mode="json") if hasattr(d, "model_dump") else d
                    for d in s.documents
                ],
                application_steps=s.application_steps,
                application_url=s.application_url,
                official_sources=s.official_sources,
                source_type=s.source_type,
                assessment_status=ass.status.value if ass else None,
                assessment_explanation=ass.explanation if ass else None,
                requirements=[
                    r.model_dump(mode="json") if hasattr(r, "model_dump") else r
                    for r in (ass.requirements if ass and ass.requirements else s.requirements)
                ],
                missing_attributes=ass.missing_attributes if ass else [],
            )
        )

    return views


# ---------------------------------------------------------------------------
# Phase 3: End-to-End Discovery Pipeline
# ---------------------------------------------------------------------------

async def run_discovery(
    session_id: str,
    search_scope: Optional[str] = None,
    preferred_language: Optional[str] = None,
    enable_fallback: bool = True,
    db_path: Optional[str] = None,
) -> DiscoveryResult:
    """
    Execute the full Phase 3 discovery pipeline:
    1. Retrieve session context from SQLite.
    2. Invoke Member 1 live search or verified offline fallbacks.
    3. Translate records to Kannada if requested.
    4. Adapt raw schemes into canonical Member 2 schemas.
    5. Normalize requirements matrix (with normalized_by marker).
    6. Calculate initial assessments using seeded answers.
    7. Generate consolidated cross-scheme questions.
    8. Persist all state in SQLite.
    9. Return structured DiscoveryResult to caller.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found in database.")

    effective_scope = search_scope or session.scope or "guided"
    effective_language = preferred_language or session.preferred_language or "en"
    warnings: list[str] = []

    logger.info(
        "Starting discovery for session=%s, scope=%s, language=%s",
        session_id,
        effective_scope,
        effective_language,
    )

    # 1. Member 1: Discovery execution
    raw_schemes = await discover_schemes(
        session.context,
        search_scope=effective_scope,
        enable_fallback=enable_fallback,
    )

    translation_status = "not_requested"

    # 2. Member 1: Kannada translation if requested
    if effective_language == "kn" and raw_schemes:
        try:
            trans_res = await translate_schemes_to_kannada(raw_schemes)
            raw_schemes = trans_res.schemes
            translation_status = trans_res.translation_status
            warnings.extend(trans_res.warnings)
            logger.info("Kannada translation completed with status=%s", translation_status)
        except Exception as exc:
            logger.warning("Kannada translation failed: %s; falling back to English", exc)
            translation_status = "failed"
            warnings.append(f"Translation to Kannada could not be completed: {exc}")

    # 3. Adapter: Map M1 raw schemas into canonical M2 models
    adapted_schemes = adapt_m1_to_m2_schemes(raw_schemes)

    # 4. Member 2: Normalize requirements once (sets normalized_by marker)
    normalized_schemes = normalize_requirements(adapted_schemes)

    # 5. Member 2: Preliminary assessment using seeded context answers
    assessments = assess_schemes(normalized_schemes, session.answers)

    # 6. Member 2: Generate consolidated cross-scheme questions
    # Seeded attributes in session.history will be excluded from this batch
    questions = generate_consolidated_questions(
        normalized_schemes,
        session.answers,
        session.history,
        batch_size=5,
    )

    # 7. Identify source mode
    if any(s.source_type == "live_search" for s in normalized_schemes):
        source_mode = "live_search"
    else:
        source_mode = "fallback"

    # 8. Persist complete discovery state in SQLite
    await update_discovery_results(
        session_id=session_id,
        raw_schemes=[s.model_dump(mode="json") if hasattr(s, "model_dump") else s for s in raw_schemes],
        normalized_schemes=normalized_schemes,
        questions=questions,
        assessments=assessments,
        db_path=db_path,
    )

    # 9. Return result for presentation
    views = build_scheme_views(normalized_schemes, assessments)
    return DiscoveryResult(
        session_id=session_id,
        status="discovery_complete",
        total_schemes=len(normalized_schemes),
        schemes=views,
        assessments=assessments,
        questions=questions,
        source_mode=source_mode,
        preferred_language=effective_language,
        translation_status=translation_status,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Scheme Retrieval Helpers
# ---------------------------------------------------------------------------

async def get_session_schemes(session_id: str, db_path: Optional[str] = None) -> list[SchemeView]:
    """Retrieve schemes and current assessments for a session."""
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")
    return build_scheme_views(session.normalized_schemes, session.assessments)


async def get_session_scheme(
    session_id: str, scheme_id: str, db_path: Optional[str] = None
) -> Optional[SchemeView]:
    """Retrieve a single scheme and its assessment for a session."""
    schemes = await get_session_schemes(session_id, db_path=db_path)
    return next((s for s in schemes if s.id == scheme_id), None)


async def get_session_questions(session_id: str, db_path: Optional[str] = None) -> list[Question]:
    """Retrieve the currently active consolidated questions for a session."""
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")
    return session.questions


# ---------------------------------------------------------------------------
# Phase 4: Consolidated Question Answering & Reassessment
# ---------------------------------------------------------------------------

async def process_answers(
    session_id: str,
    submitted_answers: Sequence[Union[AnswerInput, dict[str, Any]]],
    batch_size: int = 5,
    db_path: Optional[str] = None,
) -> ReassessmentResult:
    """
    Apply submitted answers, skips, or 'not sure' selections, update question
    history, and trigger deterministic reassessment across all normalized schemes.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    # 1. Clean and normalize submitted answers (handling AnswerInput, Answer, or dict)
    cleaned_submissions = []
    for item in submitted_answers:
        if isinstance(item, Answer):
            cleaned_submissions.append(item)
        elif hasattr(item, "model_dump"):
            d = item.model_dump()
            if not d.get("state"):
                d["state"] = "answered" if d.get("value") is not None else "skipped"
            cleaned_submissions.append(d)
        elif isinstance(item, dict):
            d = dict(item)
            if not d.get("state"):
                d["state"] = "answered" if d.get("value") is not None else "skipped"
            cleaned_submissions.append(d)
        else:
            cleaned_submissions.append(item)

    updated_answers, updated_history = apply_answers(
        session.answers, session.history, cleaned_submissions
    )

    # 2. Reassess schemes against updated answers
    updated_assessments = reassess_schemes(
        session.normalized_schemes, updated_answers
    )

    # 3. Generate the next batch of consolidated questions
    next_questions = generate_consolidated_questions(
        session.normalized_schemes,
        updated_answers,
        updated_history,
        batch_size=batch_size,
    )

    # 4. Persist updated answers, history, assessments, and next questions in SQLite
    await update_answers_and_assessments(
        session_id=session_id,
        answers=updated_answers,
        history=updated_history,
        assessments=updated_assessments,
        questions=next_questions,
        db_path=db_path,
    )

    return ReassessmentResult(
        session_id=session_id,
        status="reassessed",
        assessments=updated_assessments,
        next_questions=next_questions,
    )


# ---------------------------------------------------------------------------
# Phase 5: Document Action Plan DAG & Checklist
# ---------------------------------------------------------------------------

async def generate_action_plan(
    session_id: str, db_path: Optional[str] = None
) -> ActionPlan:
    """
    Generate or recalculate the deterministic document action plan DAG
    using Member 2's topological sorting engine.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    # Always call with keyword arguments after selected_schemes
    plan = build_action_plan(
        session.normalized_schemes,
        user_documents=session.user_documents,
        assessments=session.assessments,
    )

    # Persist the generated plan
    await update_plan(session_id, plan, session.user_documents, db_path=db_path)
    return plan


async def update_checklist_status(
    session_id: str,
    doc_id: str,
    status: Union[DocStatus, str],
    db_path: Optional[str] = None,
) -> ActionPlan:
    """
    Update document procurement status (have/obtained/needed) and immediately
    recompute the DAG checklist to unblock downstream dependent documents.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    user_docs = dict(session.user_documents)
    status_str = status.value if hasattr(status, "value") else str(status)
    user_docs[doc_id] = status_str

    # Recalculate plan with updated document statuses
    plan = build_action_plan(
        session.normalized_schemes,
        user_documents=user_docs,
        assessments=session.assessments,
    )

    # Persist the recalculated plan and updated document states
    await update_plan(session_id, plan, user_docs, db_path=db_path)
    return plan


# ---------------------------------------------------------------------------
# Phase 8: Agent 4 Action & Follow-Through Orchestration
# ---------------------------------------------------------------------------

async def generate_email_action(
    session_id: str,
    request: SessionEmailActionRequest,
    db_path: Optional[str] = None,
) -> ActionArtifact:
    """
    Generate a grounded email draft for department inquiry or clarification.
    Automatically extracts verified facts from the scheme record and applies
    PII tokenization so private citizen details never leak to the LLM.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    scheme = next((s for s in session.normalized_schemes if s.id == request.scheme_id), None)
    if not scheme:
        raise KeyError(f"Scheme '{request.scheme_id}' not found in session '{session_id}'.")

    # Extract verified facts with verbatim evidence and source URLs from scheme
    facts = list(request.facts)
    extracted = facts_from_scheme(scheme, attributes=request.attributes)
    seen_texts = {f.text for f in facts}
    for f in extracted:
        if f.text not in seen_texts:
            facts.append(f)
            seen_texts.add(f.text)

    # Auto-seed user details from session context if not explicitly provided
    user_details = dict(request.user_details)
    if "Name" not in user_details:
        name_val = session.context.get("name") or (session.context.get("personal", {}) or {}).get("name")
        if name_val:
            user_details["Name"] = name_val
    if "District" not in user_details:
        district_val = session.context.get("district") or (session.context.get("location", {}) or {}).get("district")
        if district_val:
            user_details["District"] = district_val

    email_req = EmailRequest(
        scheme=scheme,
        purpose=request.purpose,
        question=request.question,
        user_details=user_details,
        facts=facts,
    )

    llm = default_client()
    return build_email_draft(email_req, llm=llm)


async def generate_calendar_action(
    session_id: str,
    request: SessionCalendarActionRequest,
    db_path: Optional[str] = None,
) -> ActionArtifact:
    """
    Generate an RFC 5545 .ics calendar artifact for an application deadline or appointment.
    Appointments are timed in Asia/Kolkata; deadlines are all-day events.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    scheme = next((s for s in session.normalized_schemes if s.id == request.scheme_id), None)
    if not scheme:
        raise KeyError(f"Scheme '{request.scheme_id}' not found in session '{session_id}'.")

    cal_req = CalendarRequest(
        scheme=scheme,
        kind=request.kind,
        event_date=request.event_date,
        date_confirmed_by_user=request.date_confirmed_by_user,
        date_source_url=request.date_source_url,
        start_time=request.start_time,
        end_time=request.end_time,
        location=request.location,
        notes=request.notes,
        remind_days_before=request.remind_days_before,
    )

    return build_calendar_artifact(cal_req)


async def record_application_progress(
    session_id: str,
    scheme_id: str,
    updates: Sequence[Union[ProgressUpdate, dict[str, Any]]],
    db_path: Optional[str] = None,
) -> ProgressResult:
    """
    Record user-reported application progress in SQLite and evaluate follow-up
    questions and contradiction warnings.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    current = session.progress.get(scheme_id)
    result = update_progress(current, scheme_id, updates)
    await update_scheme_progress(session_id, scheme_id, result.progress, db_path=db_path)
    return result


async def get_application_progress(
    session_id: str,
    scheme_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Union[ProgressResult, dict[str, Any]]:
    """
    Retrieve application progress for a single scheme or all tracked schemes.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    if scheme_id:
        p = session.progress.get(scheme_id)
        return update_progress(p, scheme_id, [])

    return {k: v.model_dump(mode="json") for k, v in session.progress.items()}


async def analyze_scheme_rejection(
    session_id: str,
    request: SessionRejectionActionRequest,
    db_path: Optional[str] = None,
) -> RejectionAnalysis:
    """
    Analyze an official rejection notice, redact PII, extract reasons, and recommend
    only verified next steps supported by official guidelines.
    """
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    scheme = next((s for s in session.normalized_schemes if s.id == request.scheme_id), None)
    if not scheme:
        raise KeyError(f"Scheme '{request.scheme_id}' not found in session '{session_id}'.")

    guidance = list(request.guidance_passages)
    if not guidance:
        guidance = facts_from_scheme(scheme)

    llm = default_client()
    return analyse_rejection(
        scheme,
        request.notice_text,
        guidance=guidance,
        llm=llm,
        simulated=request.simulated,
    )

