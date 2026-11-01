"""What would change a result: for a scheme the user was turned down for (or that looks unlikely), which of their answers
failed which verified rule, and which other answer to that question would meet it, with the effect on every scheme.

Deterministic: candidate answers come from the attribute registry (its options, ranges or yes/no) or from the rule's
own value, and every effect is computed by assess_scheme, the same code that judged the scheme. Nothing is saved: the
user changes an answer themselves, and only if it is true for them."""
from __future__ import annotations

from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from .assess import as_answer_map, assess_scheme
from .attributes import ATTRIBUTES
from .models import Answer, AnswerState, InputType, Operator, RequirementStatus, SchemeRecord, SchemeStatus

MAX_OPTIONS_PER_QUESTION = 6


class SchemeEffect(BaseModel):
    scheme_id: str
    name: str
    before: SchemeStatus
    after: SchemeStatus


class Change(BaseModel):
    """One different answer to one question, and what it would do."""
    attribute: str
    label: str
    current: Optional[str] = None
    proposed: str
    value: Any  # exactly what the answers endpoint takes, so the frontend can apply it as is
    target_after: SchemeStatus
    effects: list[SchemeEffect] = Field(default_factory=list)  # every scheme whose status would change


class FailedCondition(BaseModel):
    requirement_id: str
    attribute: Optional[str] = None
    label: str
    criterion: str
    your_answer: Optional[str] = None
    source_url: Optional[str] = None


class WhatIf(BaseModel):
    scheme_id: str
    scheme_name: str
    status: SchemeStatus
    failed: list[FailedCondition] = Field(default_factory=list)
    unanswered: list[str] = Field(default_factory=list)  # labels of questions not answered that this scheme asks
    changes: list[Change] = Field(default_factory=list)
    all_fixed_status: Optional[SchemeStatus] = None  # if one fitting answer were given to every failed question
    already_matching: list[dict[str, str]] = Field(default_factory=list)  # [{scheme_id, name}]
    note: str = ""


def _label(attribute: Optional[str]) -> str:
    spec = ATTRIBUTES.get(attribute or "")
    if spec:
        return spec.label
    return (attribute or "Condition").split(":")[-1].replace("_", " ").capitalize()


def _display(attribute: str, value: Any) -> str:
    spec = ATTRIBUTES.get(attribute)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, dict) and spec:
        for r in spec.ranges:
            if r.min == value.get("min") and r.max == value.get("max"):
                return r.label
        lo, hi = value.get("min"), value.get("max")
        unit = "₹" if spec.unit in ("INR", "₹", "rupees") or "income" in attribute else ""
        return f"{unit}{lo:,}–{unit}{hi:,}" if lo is not None and hi is not None else str(value)
    return str(value)


def _candidates(attribute: str, scheme: SchemeRecord) -> list[Any]:
    """Every answer worth trying for this question: the registry's options, else the rule's own values."""
    spec = ATTRIBUTES.get(attribute)
    if spec and spec.input_type == InputType.select and spec.options:
        return list(spec.options)
    if spec and spec.input_type == InputType.range and spec.ranges:
        return [{"min": r.min, "max": r.max} for r in spec.ranges]
    if spec and spec.input_type == InputType.boolean:
        return [True, False]
    out: list[Any] = []
    for req in scheme.requirements:
        if req.attribute != attribute:
            continue
        op, v = req.operator, req.value
        if op in (Operator.is_true, Operator.is_false):
            out += [True, False]
        elif op in (Operator.in_,) and isinstance(v, list):
            out += v
        elif op == Operator.eq:
            out.append(v)
        elif op in (Operator.gte, Operator.lte) and isinstance(v, (int, float)):
            out.append(v)
        elif op == Operator.gt and isinstance(v, (int, float)):
            out.append(v + 1)
        elif op == Operator.lt and isinstance(v, (int, float)):
            out.append(v - 1)
    seen: list[Any] = []
    for c in out:
        if c not in seen:
            seen.append(c)
    return seen


def _with(answers: dict[str, Answer], attribute: str, value: Any) -> dict[str, Answer]:
    changed = dict(answers)
    changed[attribute] = Answer(attribute=attribute, state=AnswerState.answered, value=value)
    return changed


def explore(
    schemes: Iterable[SchemeRecord | dict],
    user_answers: Any,
    scheme_id: str,
) -> Optional[WhatIf]:
    """The what-if for one scheme, or None if the scheme isn't in the list."""
    records = [s if isinstance(s, SchemeRecord) else SchemeRecord.model_validate(s) for s in schemes]
    target = next((s for s in records if s.id == scheme_id), None)
    if target is None:
        return None
    answers = as_answer_map(user_answers)
    base = {s.id: assess_scheme(s, answers).status for s in records}
    names = {s.id: s.name for s in records}
    current = assess_scheme(target, answers)

    failed: list[FailedCondition] = []
    unanswered: list[str] = []
    failed_attrs: list[str] = []
    for r in current.requirements:
        if r.status == RequirementStatus.not_satisfied:
            a = answers.get(r.attribute or "")
            failed.append(FailedCondition(
                requirement_id=r.requirement_id, attribute=r.attribute, label=_label(r.attribute), criterion=r.criterion,
                your_answer=_display(r.attribute, a.value) if a and a.state == AnswerState.answered and r.attribute else None,
                source_url=r.source_url,
            ))
            if r.attribute and r.attribute not in failed_attrs:
                failed_attrs.append(r.attribute)
        elif r.status == RequirementStatus.unknown and r.attribute and _label(r.attribute) not in unanswered:
            unanswered.append(_label(r.attribute))

    changes: list[Change] = []
    first_fit: dict[str, Any] = {}
    for attr in failed_attrs:
        cur = answers.get(attr)
        cur_value = cur.value if cur and cur.state == AnswerState.answered else None
        found = 0
        for value in _candidates(attr, target):
            if value == cur_value:
                continue
            trial = _with(answers, attr, value)
            after = assess_scheme(target, trial)
            fixed = all(x.status != RequirementStatus.not_satisfied for x in after.requirements if x.attribute == attr)
            if not fixed:
                continue
            effects = []
            for s in records:
                now_status = after.status if s.id == target.id else assess_scheme(s, trial).status
                if now_status != base[s.id]:
                    effects.append(SchemeEffect(scheme_id=s.id, name=names[s.id], before=base[s.id], after=now_status))
            changes.append(Change(
                attribute=attr, label=_label(attr), current=_display(attr, cur_value) if cur_value is not None else None,
                proposed=_display(attr, value), value=value, target_after=after.status, effects=effects,
            ))
            first_fit.setdefault(attr, value)
            found += 1
            if found >= MAX_OPTIONS_PER_QUESTION:
                break

    all_fixed = None
    if first_fit:
        trial = dict(answers)
        for attr, value in first_fit.items():
            trial = _with(trial, attr, value)
        all_fixed = assess_scheme(target, trial).status

    if failed:
        note = "These are the conditions your answers didn't meet. Change an answer only if it is true for you: applications are checked against your documents."
    elif current.status == SchemeStatus.potential_match:
        note = ("By the answers you gave, this scheme's verified rules were met, so the reason is likely something Unlocked "
                "doesn't check (a document, a deadline or a quota). Ask the office for the reason in writing.")
    else:
        note = "No verified rule ruled you out; answering the open questions would make this clearer."

    return WhatIf(
        scheme_id=target.id, scheme_name=target.name, status=current.status, failed=failed, unanswered=unanswered,
        changes=changes, all_fixed_status=all_fixed,
        already_matching=[{"scheme_id": s.id, "name": s.name} for s in records if s.id != target.id and base[s.id] == SchemeStatus.potential_match],
        note=note,
    )
