"""Consolidated and scheme-specific questions, and answer tracking.

Python owns ids, dedup, ranking, history and limits. The LLM may only reword a
question's text.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Union

from .assess import AnswersInput, SchemeInput, _as_scheme, as_answer_map, assess_scheme, contradictory_requirement_ids
from .attributes import ATTRIBUTES, AttributeSpec, is_canonical
from .comparators import NOT_SURE_VALUES
from .models import (
    Answer,
    AnswerState,
    InputType,
    Question,
    RequirementVerification,
    SchemeRecord,
    SchemeStatus,
    Sensitivity,
)

log = logging.getLogger(__name__)

HistoryInput = Optional[Mapping[str, Union[AnswerState, str]]]

_SENSITIVITY_PENALTY = {Sensitivity.low: 0, Sensitivity.medium: 2, Sensitivity.high: 5}
_BOOLEAN_OPTIONS = ["Yes", "No"]
_TRUE = {"yes", "true", "y"}
_FALSE = {"no", "false", "n"}

REPHRASE_SYSTEM = (
    "You rewrite form questions for a government-benefits assistant in Karnataka, India. "
    "Make each question short, plain and friendly. Keep its meaning exactly. "
    "Do not add facts, examples, numbers, options or scheme names. Each rewrite must end with '?'. "
    "Return only a JSON object mapping each given id to its rewritten question."
)


def question_id(attribute: str) -> str:
    return "q_" + attribute


def _history(question_history: HistoryInput) -> dict[str, AnswerState]:
    return {k: AnswerState(v) for k, v in (question_history or {}).items()}


@dataclass
class _Usage:
    scheme_ids: set[str] = field(default_factory=set)
    n_requirements: int = 0


def _useful_usage(schemes: Iterable[SchemeRecord], answers: dict[str, Answer], *, skip_unlikely: bool = True) -> dict[str, _Usage]:
    """Attributes whose answer could change an assessment. Unverified, unreadable
    or contradictory rules can't be decided by an answer, and a scheme already
    unlikely to match won't change, so none of those earn a question."""
    usage: dict[str, _Usage] = defaultdict(_Usage)
    for scheme in schemes:
        if skip_unlikely and assess_scheme(scheme, answers).status == SchemeStatus.unlikely_to_match:
            continue
        conflicts = contradictory_requirement_ids(scheme)
        for req in scheme.requirements:
            if (
                req.status == RequirementVerification.verified
                and is_canonical(req.attribute)
                and req.operator is not None
                and req.id not in conflicts
            ):
                usage[req.attribute].scheme_ids.add(scheme.id)
                usage[req.attribute].n_requirements += 1
                # A group-specific rule also needs the attribute that picks the group.
                if req.condition is not None and is_canonical(req.condition.attribute):
                    usage[req.condition.attribute].scheme_ids.add(scheme.id)
                    usage[req.condition.attribute].n_requirements += 1
    return usage


def _score(spec: AttributeSpec, use: _Usage) -> int:
    return 10 * len(use.scheme_ids) + 4 * use.n_requirements - _SENSITIVITY_PENALTY[spec.sensitivity] - spec.effort


def _build(spec: AttributeSpec, use: _Usage, status: AnswerState) -> Question:
    n = len(use.scheme_ids)
    used = "One of the schemes we found uses this." if n == 1 else f"{n} of the schemes we found use this."
    why = f"{spec.why_template} {used}"
    if spec.sensitivity == Sensitivity.high:
        why += " You can skip this."
    options = spec.options or (_BOOLEAN_OPTIONS if spec.input_type == InputType.boolean else [])
    return Question(
        id=question_id(spec.id),
        attribute=spec.id,
        question=spec.question,
        input_type=spec.input_type,
        options=list(options),
        ranges=list(spec.ranges),
        required_for_assessment=use.n_requirements > 0,
        why_asked=why,
        related_scheme_ids=sorted(use.scheme_ids),
        sensitivity=spec.sensitivity,
        status=status,
    )


def _rank(usage: dict[str, _Usage]) -> list[str]:
    return sorted(usage, key=lambda a: (-_score(ATTRIBUTES[a], usage[a]), a))


def _rephrase(questions: list[Question], llm: Any) -> list[Question]:
    # Only question text is sent: no answers, no user data.
    if not questions or llm is None:
        return questions
    # Legal-meaning questions (e.g. domicile) keep their registry wording.
    pending = [q for q in questions if not ATTRIBUTES[q.attribute].keep_wording]
    if not pending:
        return questions
    try:
        raw = llm.complete_json(REPHRASE_SYSTEM, json.dumps({q.id: q.question for q in pending}))
        rewrites = json.loads(raw)
        if not isinstance(rewrites, dict):
            raise ValueError("rephrase output is not an object")
    except Exception:
        log.warning("question rephrasing failed; keeping registry text")
        return questions
    out = []
    sent = {q.id for q in pending}
    for q in questions:
        text = rewrites.get(q.id) if q.id in sent else None
        if isinstance(text, str) and 5 <= len(text.strip()) <= 200 and text.strip().endswith("?"):
            q = q.model_copy(update={"question": text.strip()})
        out.append(q)
    return out


def generate_consolidated_questions(
    schemes: Iterable[SchemeInput],
    user_answers: AnswersInput = None,
    question_history: HistoryInput = None,
    *,
    batch_size: int = 5,
    rephrase_llm: Any = None,
) -> list[Question]:
    answers = as_answer_map(user_answers)
    history = _history(question_history)
    usage = _useful_usage([_as_scheme(s) for s in schemes], answers)

    # Asked once (any state but unanswered) means never re-asked in this flow.
    candidates = {
        a: u
        for a, u in usage.items()
        if answers.get(a, Answer(attribute=a, state=AnswerState.unanswered)).state == AnswerState.unanswered
        and history.get(question_id(a), AnswerState.unanswered) == AnswerState.unanswered
    }
    picked = _rank(candidates)[: max(batch_size, 0)]
    log.debug("consolidated questions: %s", picked)
    return _rephrase([_build(ATTRIBUTES[a], candidates[a], AnswerState.unanswered) for a in picked], rephrase_llm)


def generate_scheme_questions(
    scheme: SchemeInput,
    user_answers: AnswersInput = None,
    question_history: HistoryInput = None,
    *,
    include_skipped: bool = False,
) -> list[Question]:
    answers = as_answer_map(user_answers)
    history = _history(question_history)
    usage = _useful_usage([_as_scheme(scheme)], answers)

    questions = []
    for a in _rank(usage):
        state = answers[a].state if a in answers else AnswerState.unanswered
        if state == AnswerState.unanswered:
            state = history.get(question_id(a), AnswerState.unanswered)
        if state == AnswerState.answered:
            continue
        if state != AnswerState.unanswered and not include_skipped:
            continue
        questions.append(_build(ATTRIBUTES[a], usage[a], state))
    return questions


def _clean_value(spec: AttributeSpec, value: Any) -> tuple[AnswerState, Any]:
    """Coerce a submitted value to the attribute's shape. Anything unusable becomes
    `unknown`: guessing would risk a false 'not satisfied'."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return AnswerState.skipped, None
    if isinstance(value, str) and value.strip().lower() in NOT_SURE_VALUES:
        return AnswerState.unknown, None

    if spec.input_type == InputType.select:
        match = next((o for o in spec.options if o.casefold() == str(value).strip().casefold()), None)
        return (AnswerState.answered, match) if match else (AnswerState.unknown, None)

    if spec.input_type == InputType.boolean:
        if isinstance(value, bool):
            return AnswerState.answered, value
        v = str(value).strip().lower()
        if v in _TRUE or v in _FALSE:
            return AnswerState.answered, v in _TRUE
        return AnswerState.unknown, None

    if spec.input_type == InputType.range:
        if isinstance(value, str):
            band = next((r for r in spec.ranges if r.label.casefold() == value.strip().casefold()), None)
            return (AnswerState.answered, {"min": band.min, "max": band.max}) if band else (AnswerState.unknown, None)
        if isinstance(value, dict) and ("min" in value or "max" in value):
            return AnswerState.answered, {"min": value.get("min"), "max": value.get("max")}
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return AnswerState.answered, {"min": value, "max": value}
        return AnswerState.unknown, None

    if spec.input_type == InputType.number:
        if isinstance(value, bool):
            return AnswerState.unknown, None
        try:
            return AnswerState.answered, float(str(value).replace(",", "").strip())
        except ValueError:
            return AnswerState.unknown, None

    return AnswerState.answered, str(value).strip()


def apply_answers(
    user_answers: AnswersInput,
    question_history: HistoryInput,
    submitted: Iterable[Union[Answer, dict]],
) -> tuple[dict[str, Answer], dict[str, AnswerState]]:
    """Returns new copies; never mutates the inputs."""
    answers = dict(as_answer_map(user_answers))
    history = _history(question_history)
    for item in submitted:
        answer = item if isinstance(item, Answer) else Answer.model_validate(item)
        spec = ATTRIBUTES.get(answer.attribute)
        if spec is None:
            log.warning("ignoring answer for unknown attribute %s", answer.attribute)
            continue
        state, value = answer.state, None
        if state == AnswerState.answered:
            state, value = _clean_value(spec, answer.value)
        answers[spec.id] = Answer(attribute=spec.id, state=state, value=value)
        history[question_id(spec.id)] = state
        log.debug("answer recorded attribute=%s state=%s", spec.id, state.value)
    return answers, history
