"""Requirement and scheme assessment. Deterministic; no LLM."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Union

from .attributes import ATTRIBUTES, detect_state_in_text, is_canonical, is_condition
from .comparators import evaluate
from .models import (
    Answer,
    AnswerState,
    Assessment,
    Operator,
    Requirement,
    RequirementCategory,
    RequirementResult,
    RequirementStatus,
    RequirementVerification,
    SchemeRecord,
    SchemeStatus,
    VerificationStatus,
)

log = logging.getLogger(__name__)

# Member 3 may hand us dicts straight from SQLite/JSON, or a list instead of a map.
AnswersInput = Union[Mapping[str, Union[Answer, dict]], Iterable[Union[Answer, dict]], None]
SchemeInput = Union[SchemeRecord, dict]

DISCLAIMER = "This is Unlocked's assessment, not an official eligibility decision."


def as_answer_map(user_answers: AnswersInput) -> dict[str, Answer]:
    if not user_answers:
        return {}
    items = user_answers.values() if isinstance(user_answers, Mapping) else user_answers
    out: dict[str, Answer] = {}
    for a in items:
        answer = a if isinstance(a, Answer) else Answer.model_validate(a)
        out[answer.attribute] = answer
    # Bi-directional inference between state, domicile_state and domicile_karnataka
    if "state" in out and out["state"].state == AnswerState.answered:
        st_val = str(out["state"].value or "").strip().lower()
        if st_val == "karnataka":
            if "domicile_karnataka" not in out:
                out["domicile_karnataka"] = Answer(attribute="domicile_karnataka", state=AnswerState.answered, value=True)
            if "domicile_state" not in out:
                out["domicile_state"] = Answer(attribute="domicile_state", state=AnswerState.answered, value="Karnataka")
        elif "domicile_state" not in out:
            out["domicile_state"] = Answer(attribute="domicile_state", state=AnswerState.answered, value=out["state"].value)
    elif "domicile_state" in out and out["domicile_state"].state == AnswerState.answered:
        st_val = str(out["domicile_state"].value or "").strip().lower()
        if st_val == "karnataka":
            if "domicile_karnataka" not in out:
                out["domicile_karnataka"] = Answer(attribute="domicile_karnataka", state=AnswerState.answered, value=True)
            if "state" not in out:
                out["state"] = Answer(attribute="state", state=AnswerState.answered, value="Karnataka")
        elif "state" not in out:
            out["state"] = Answer(attribute="state", state=AnswerState.answered, value=out["domicile_state"].value)
    elif "domicile_karnataka" in out and out["domicile_karnataka"].state == AnswerState.answered:
        if out["domicile_karnataka"].value is True:
            if "state" not in out:
                out["state"] = Answer(attribute="state", state=AnswerState.answered, value="Karnataka")
            if "domicile_state" not in out:
                out["domicile_state"] = Answer(attribute="domicile_state", state=AnswerState.answered, value="Karnataka")
    return out


def _as_scheme(scheme: SchemeInput) -> SchemeRecord:
    return scheme if isinstance(scheme, SchemeRecord) else SchemeRecord.model_validate(scheme)


def _label(attribute: Optional[str]) -> str:
    # Lowercase only the first letter so proper nouns ("Karnataka") keep their case.
    spec = ATTRIBUTES.get(attribute or "")
    if spec is None:
        return "one of the scheme's own conditions" if is_condition(attribute) else "this detail"
    return spec.label[0].lower() + spec.label[1:]


def _end(text: str) -> str:
    """Add a full stop unless the text already ends with one (inside a quote too)."""
    return text if text.rstrip("'\"").endswith((".", "?", "!")) else text + "."


def _result(req: Requirement, status: RequirementStatus, reason: str, attribute: Optional[str] = None, category: Optional[RequirementCategory] = None) -> RequirementResult:
    return RequirementResult(
        requirement_id=req.id,
        attribute=attribute or req.attribute,
        status=status,
        reason=reason,
        criterion=req.criterion,
        source_url=req.source_url,
        category=category or getattr(req, "category", RequirementCategory.eligibility),
    )


def assess_requirement(req: Requirement, user_answers: AnswersInput = None) -> RequirementResult:
    answers = as_answer_map(user_answers)
    mapped = is_canonical(req.attribute)
    category = getattr(req, "category", RequirementCategory.eligibility)
    answer = answers.get(req.attribute, Answer(attribute=req.attribute, state=AnswerState.unanswered)) if mapped else None

    if req.status != RequirementVerification.verified:
        reason = "This rule hasn't been confirmed from an official source."
        # Mention a possible conflict, but an unverified rule can never rule a scheme out.
        if mapped and evaluate(req.operator, req.value, answer)[0] == RequirementStatus.not_satisfied:
            reason += " Your answer may not meet it, once it is confirmed."
        return _result(req, RequirementStatus.unverified, reason, category=category)

    if not mapped:
        if is_condition(req.attribute):
            # A scheme's own condition, asked as a yes/no question (DECISIONS #63).
            # If the condition is about Karnataka residency and user is in Karnataka, satisfy it immediately.
            is_kar_user = (
                answers.get("domicile_karnataka", Answer(attribute="", state=AnswerState.unanswered)).value is True
                or str(answers.get("state", Answer(attribute="", state=AnswerState.unanswered)).value or "").lower() == "karnataka"
                or str(answers.get("domicile_state", Answer(attribute="", state=AnswerState.unanswered)).value or "").lower() == "karnataka"
            )
            detected_state = detect_state_in_text(f"{req.attribute} {req.criterion or ''}")
            if detected_state:
                if detected_state.lower() == "karnataka":
                    if is_kar_user:
                        return _result(req, RequirementStatus.satisfied, "You are confirmed to be a resident of Karnataka.", category=category)
                elif is_kar_user:
                    return _result(req, RequirementStatus.not_satisfied, f"This condition requires residency in {detected_state}, but your profile indicates Karnataka.", category=category)
            elif "karnataka" in req.attribute.lower() and is_kar_user:
                return _result(req, RequirementStatus.satisfied, "You are confirmed to be a resident of Karnataka.", category=category)

            own = answers.get(req.attribute)
            status, _ = evaluate(Operator.is_true, None, own)
            if status == RequirementStatus.unknown:
                return _result(req, status, "We need to know whether this condition applies to you.", category=category)
            if status == RequirementStatus.not_satisfied:
                if category == RequirementCategory.application_prerequisite:
                    return _result(req, status, "You have not completed this registration/procedure yet; it will be completed during the application process.", category=category)
                elif category == RequirementCategory.post_approval:
                    return _result(req, status, "This is a post-approval condition (required before loan disbursement) rather than an upfront eligibility exclusion.", category=category)
                return _result(req, status, "You said this condition doesn't apply to you.", category=category)
            return _result(req, status, "You said this condition applies to you.", category=category)
        if category == RequirementCategory.application_prerequisite:
            return _result(req, RequirementStatus.unknown, "This registration/procedure is part of the application process rather than an eligibility disqualification.", category=category)
        if category == RequirementCategory.post_approval:
            return _result(req, RequirementStatus.satisfied, "This is a post-approval condition (required before loan disbursement) rather than an upfront eligibility exclusion.", category=category)
        return _result(req, RequirementStatus.needs_clarification, "We couldn't match this rule to a question we can ask.", category=category)

    cond = req.condition
    if cond is not None:
        # "60% for SC/ST": first decide whether the rule applies to this user.
        if not is_canonical(cond.attribute):
            return _result(req, RequirementStatus.needs_clarification, "We couldn't tell which group this rule applies to.", category=category)
        applies, _ = evaluate(cond.operator, cond.value, answers.get(cond.attribute))
        if applies == RequirementStatus.unknown:
            label = ATTRIBUTES[cond.attribute].label
            return _result(req, RequirementStatus.unknown,
                           f"This rule depends on your {label[:1].lower() + label[1:]}.", attribute=cond.attribute, category=category)
        if applies == RequirementStatus.not_satisfied:
            return _result(req, RequirementStatus.satisfied, "This rule is for a different group, so it doesn't apply to you.", category=category)

    status, reason = evaluate(req.operator, req.value, answer)
    if status == RequirementStatus.not_satisfied and category != RequirementCategory.eligibility:
        if category == RequirementCategory.application_prerequisite:
            reason = "You have not completed this registration/procedure yet; it is part of the application process rather than a disqualifying criterion."
        elif category == RequirementCategory.post_approval:
            reason = "This is a post-approval requirement rather than an upfront eligibility exclusion."
    return _result(req, status, reason, category=category)


def contradictory_requirement_ids(scheme: SchemeRecord) -> set[str]:
    """Verified requirements that state different values for the same attribute
    and operator (e.g. two different income limits). Different operators on one
    attribute, such as a min and a max age, are a normal range, not a conflict."""
    groups: dict[tuple[str, Any, str], list[Requirement]] = defaultdict(list)
    for req in scheme.requirements:
        if req.status == RequirementVerification.verified and is_canonical(req.attribute) and req.operator:
            # Rules for different groups (condition) are not in conflict.
            cond = json.dumps(req.condition.model_dump(mode="json"), sort_keys=True) if req.condition else ""
            groups[(req.attribute, req.operator, cond)].append(req)
    ids: set[str] = set()
    for reqs in groups.values():
        if len({json.dumps(r.value, sort_keys=True, default=str) for r in reqs}) > 1:
            ids.update(r.id for r in reqs)
    return ids


def _quote(results: list[RequirementResult]) -> str:
    return "; ".join(f"'{r.criterion}'" for r in results)


def _explain(status: SchemeStatus, scheme: SchemeRecord, results: list[RequirementResult], missing: list[str]) -> str:
    def having(s: RequirementStatus) -> list[RequirementResult]:
        return [r for r in results if r.status == s]

    eligibility_results = [
        r for r in results
        if getattr(r, "category", RequirementCategory.eligibility) == RequirementCategory.eligibility
    ]
    failed_eligibility = [r for r in eligibility_results if r.status == RequirementStatus.not_satisfied]

    pending_prereqs = [
        r for r in results
        if getattr(r, "category", RequirementCategory.eligibility) in (
            RequirementCategory.application_prerequisite,
            RequirementCategory.post_approval,
        )
        and r.status in (RequirementStatus.not_satisfied, RequirementStatus.unknown)
    ]

    if status == SchemeStatus.potential_match:
        text = "Based on what you've shared, you appear to meet the published criteria we checked."
        if pending_prereqs:
            text += " (Note: Portal registration, eKYC, or subsequent training steps will be completed as part of the official application procedure.)"
    elif status == SchemeStatus.more_information_needed:
        text = "To assess this scheme we still need: " + ", ".join(_label(a) for a in missing) + "."
    elif status == SchemeStatus.unlikely_to_match:
        failed = failed_eligibility or having(RequirementStatus.not_satisfied)
        text = " ".join(
            _end(f"Your answer about {_label(r.attribute)} doesn't appear to meet this rule: '{r.criterion}'") for r in failed
        )
    elif status == SchemeStatus.uncertain:
        unclear = [r for r in eligibility_results if r.status == RequirementStatus.needs_clarification] or having(RequirementStatus.needs_clarification)
        rule = "this rule" if len(unclear) == 1 else "these rules"
        text = _end(f"We couldn't confidently interpret {rule}: " + _quote(unclear))
    elif not results:
        text = "No eligibility rules for this scheme have been confirmed yet."
    elif having(RequirementStatus.unverified):
        unverified = having(RequirementStatus.unverified)
        rule = "This rule hasn't" if len(unverified) == 1 else "These rules haven't"
        text = _end(f"{rule} been confirmed from an official source: " + _quote(unverified))
    else:
        text = "This scheme's details haven't been confirmed from an official source yet."
    return f"{text} {DISCLAIMER}"


def _roll_up(scheme: SchemeRecord, items: Union[list[RequirementResult], set[RequirementStatus]]) -> SchemeStatus:
    # Separate core eligibility from application prerequisites and post-approvals
    if items and isinstance(next(iter(items)), RequirementResult):
        results = list(items)
        eligibility_results = [
            r for r in results
            if getattr(r, "category", RequirementCategory.eligibility) == RequirementCategory.eligibility
        ]
        statuses = {r.status for r in eligibility_results}
    else:
        statuses = set(items)

    # First matching rule wins for core eligibility (member2.md §5).
    if RequirementStatus.not_satisfied in statuses:
        return SchemeStatus.unlikely_to_match
    if RequirementStatus.unknown in statuses:
        return SchemeStatus.more_information_needed
    if RequirementStatus.needs_clarification in statuses:
        return SchemeStatus.uncertain
    if (
        RequirementStatus.unverified in statuses
        or not scheme.requirements
        or scheme.verification_status != VerificationStatus.verified
    ):
        return SchemeStatus.not_yet_verified
    return SchemeStatus.potential_match


def assess_scheme(scheme: SchemeInput, user_answers: AnswersInput = None, *, now: Optional[datetime] = None) -> Assessment:
    scheme = _as_scheme(scheme)
    answers = as_answer_map(user_answers)
    conflicts = contradictory_requirement_ids(scheme)

    results = []
    for req in scheme.requirements:
        if req.id in conflicts:
            results.append(_result(req, RequirementStatus.needs_clarification, "The sources state different values for this rule."))
        else:
            results.append(assess_requirement(req, answers))

    status = _roll_up(scheme, results)
    missing = sorted({r.attribute for r in results if r.status == RequirementStatus.unknown and r.attribute})
    log.debug("assessed scheme=%s status=%s missing=%s", scheme.id, status.value, missing)

    explanation = _explain(status, scheme, results, missing)

    # Scheme interactions (e.g. Vishwakarma 5-year loan restriction and family restriction)
    prev_loan = answers.get("previous_government_loan")
    fam_ben = answers.get("family_member_beneficiary")
    if scheme.id in ("pm_vishwakarma", "fallback_pm_vishwakarma"):
        if prev_loan and prev_loan.value is True:
            explanation = explanation.replace(
                DISCLAIMER,
                "Interaction Notice: PM Vishwakarma credit assistance cannot be availed if you have an active loan under PMEGP, PM SVANidhi, or MUDRA in the past 5 years. " + DISCLAIMER
            )
        if fam_ben and fam_ben.value is True:
            explanation = explanation.replace(
                DISCLAIMER,
                "Interaction Notice: PM Vishwakarma scheme benefits are restricted to one member per family. " + DISCLAIMER
            )

    return Assessment(
        scheme_id=scheme.id,
        status=status,
        explanation=explanation,
        requirements=results,
        missing_attributes=missing,
        last_assessed_at=(now or datetime.now(timezone.utc)).isoformat(),
    )


def assess_schemes(schemes: Iterable[SchemeInput], user_answers: AnswersInput = None, *, now: Optional[datetime] = None) -> list[Assessment]:
    answers = as_answer_map(user_answers)
    stamp = now or datetime.now(timezone.utc)
    return [assess_scheme(s, answers, now=stamp) for s in schemes]


# plan.md lists "reassessment" as a deliverable: it is the same call with updated answers.
reassess_schemes = assess_schemes
