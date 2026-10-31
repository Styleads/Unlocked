"""Requirement and scheme assessment. Deterministic; no LLM."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Union

from .attributes import ATTRIBUTES, is_canonical, is_condition
from .comparators import evaluate
from .models import (
    Answer,
    AnswerState,
    Assessment,
    Operator,
    Requirement,
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


def _result(req: Requirement, status: RequirementStatus, reason: str, attribute: Optional[str] = None) -> RequirementResult:
    return RequirementResult(
        requirement_id=req.id,
        attribute=attribute or req.attribute,
        status=status,
        reason=reason,
        criterion=req.criterion,
        source_url=req.source_url,
    )


def assess_requirement(req: Requirement, user_answers: AnswersInput = None) -> RequirementResult:
    answers = as_answer_map(user_answers)
    mapped = is_canonical(req.attribute)
    answer = answers.get(req.attribute, Answer(attribute=req.attribute, state=AnswerState.unanswered)) if mapped else None

    if req.status != RequirementVerification.verified:
        reason = "This rule hasn't been confirmed from an official source."
        # Mention a possible conflict, but an unverified rule can never rule a scheme out.
        if mapped and evaluate(req.operator, req.value, answer)[0] == RequirementStatus.not_satisfied:
            reason += " Your answer may not meet it, once it is confirmed."
        return _result(req, RequirementStatus.unverified, reason)

    if not mapped:
        if is_condition(req.attribute):
            # A scheme's own condition, asked as a yes/no question (DECISIONS #63).
            # If the condition is about Karnataka residency and user is in Karnataka, satisfy it immediately.
            is_kar_user = (
                answers.get("domicile_karnataka", Answer(attribute="", state=AnswerState.unanswered)).value is True
                or str(answers.get("state", Answer(attribute="", state=AnswerState.unanswered)).value or "").lower() == "karnataka"
            )
            if "karnataka" in req.attribute.lower() and is_kar_user:
                return _result(req, RequirementStatus.satisfied, "You are confirmed to be a resident of Karnataka.")

            own = answers.get(req.attribute)
            status, _ = evaluate(Operator.is_true, None, own)
            if status == RequirementStatus.unknown:
                return _result(req, status, "We need to know whether this condition applies to you.")
            if status == RequirementStatus.not_satisfied:
                return _result(req, status, "You said this condition doesn't apply to you.")
            return _result(req, status, "You said this condition applies to you.")
        return _result(req, RequirementStatus.needs_clarification, "We couldn't match this rule to a question we can ask.")

    cond = req.condition
    if cond is not None:
        # "60% for SC/ST": first decide whether the rule applies to this user.
        if not is_canonical(cond.attribute):
            return _result(req, RequirementStatus.needs_clarification, "We couldn't tell which group this rule applies to.")
        applies, _ = evaluate(cond.operator, cond.value, answers.get(cond.attribute))
        if applies == RequirementStatus.unknown:
            label = ATTRIBUTES[cond.attribute].label
            return _result(req, RequirementStatus.unknown,
                           f"This rule depends on your {label[:1].lower() + label[1:]}.", attribute=cond.attribute)
        if applies == RequirementStatus.not_satisfied:
            return _result(req, RequirementStatus.satisfied, "This rule is for a different group, so it doesn't apply to you.")

    status, reason = evaluate(req.operator, req.value, answer)
    return _result(req, status, reason)


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

    if status == SchemeStatus.potential_match:
        text = "Based on what you've shared, you appear to meet the published criteria we checked."
    elif status == SchemeStatus.more_information_needed:
        text = "To assess this scheme we still need: " + ", ".join(_label(a) for a in missing) + "."
    elif status == SchemeStatus.unlikely_to_match:
        failed = having(RequirementStatus.not_satisfied)
        text = " ".join(
            _end(f"Your answer about {_label(r.attribute)} doesn't appear to meet this rule: '{r.criterion}'") for r in failed
        )
    elif status == SchemeStatus.uncertain:
        unclear = having(RequirementStatus.needs_clarification)
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


def _roll_up(scheme: SchemeRecord, statuses: set[RequirementStatus]) -> SchemeStatus:
    # First matching rule wins (member2.md §5).
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

    status = _roll_up(scheme, {r.status for r in results})
    missing = sorted({r.attribute for r in results if r.status == RequirementStatus.unknown and r.attribute})
    log.debug("assessed scheme=%s status=%s missing=%s", scheme.id, status.value, missing)
    return Assessment(
        scheme_id=scheme.id,
        status=status,
        explanation=_explain(status, scheme, results, missing),
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
