"""Operator evaluation. Pure functions, no I/O.

Rule order matters: answer state is checked before anything else, so a missing
answer can only ever produce `unknown`.
"""
from __future__ import annotations

from typing import Any, Optional
import re

from .models import Answer, AnswerState, Operator, RequirementStatus

Result = tuple[RequirementStatus, str]

_NUMERIC = {Operator.lte, Operator.lt, Operator.gte, Operator.gt}
_VALUELESS = {Operator.is_true, Operator.is_false}

# Free-text "not sure" that slipped through as an answered value is still unknown.
NOT_SURE_VALUES = {"not sure", "dont know", "don't know", "unknown", "unsure", "n/a", "na"}
_TRUE = {"true", "yes", "y"}
_FALSE = {"false", "no", "n"}

_STATE_REASONS = {
    AnswerState.unanswered: "You haven't been asked this yet.",
    AnswerState.skipped: "You skipped this question.",
    AnswerState.unknown: "You said you're not sure.",
    AnswerState.prefer_not_to_answer: "You preferred not to answer.",
}


def evaluate(operator: Optional[Operator], required: Any, answer: Optional[Answer]) -> Result:
    if answer is None or answer.state != AnswerState.answered:
        state = answer.state if answer else AnswerState.unanswered
        return RequirementStatus.unknown, _STATE_REASONS[state]
    value = answer.value
    if value is None or (isinstance(value, str) and value.strip().lower() in NOT_SURE_VALUES):
        return RequirementStatus.unknown, "No usable answer was given."

    if operator is None:
        return RequirementStatus.needs_clarification, "The rule's condition couldn't be read."
    if required is None and operator not in _VALUELESS:
        return RequirementStatus.needs_clarification, "The rule doesn't state a value to compare against."

    if operator in _NUMERIC:
        return _numeric(operator, required, value)
    if operator in (Operator.eq, Operator.neq):
        return _equality(operator, required, value)
    if operator in (Operator.in_, Operator.not_in):
        return _membership(operator, required, value)
    return _boolean(operator, value)


def _to_float(x: Any) -> Optional[float]:
    # bool is an int subclass; True must not compare as 1.
    if isinstance(x, bool) or x is None:
        return None
    try:
        return float(str(x).replace(",", "").strip()) if isinstance(x, str) else float(x)
    except (TypeError, ValueError):
        return None


def _fmt(x: float) -> str:
    """Indian digit grouping for whole numbers (250000 -> 2,50,000)."""
    if x != int(x):
        return str(x)
    digits = str(abs(int(x)))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join([head, *groups, tail])
    return ("-" if x < 0 else "") + digits


def _interval(value: Any) -> Optional[tuple[Optional[float], Optional[float]]]:
    """Answer as (low, high); None on a side means open-ended."""
    if isinstance(value, dict):
        lo_raw, hi_raw = value.get("min"), value.get("max")
        lo, hi = _to_float(lo_raw), _to_float(hi_raw)
        if (lo_raw is not None and lo is None) or (hi_raw is not None and hi is None):
            return None
        if lo is not None and hi is not None and lo > hi:
            return None
        return lo, hi
    n = _to_float(value)
    return None if n is None else (n, n)


def _numeric(op: Operator, required: Any, value: Any) -> Result:
    limit = _to_float(required)
    interval = _interval(value)
    if limit is None or interval is None:
        return RequirementStatus.needs_clarification, "The answer or the rule isn't a usable number."
    lo, hi = interval
    if lo is None and hi is None:
        return RequirementStatus.unknown, "No usable answer was given."

    # Each check only uses the bound that decides it, so an open side
    # is undecidable only when it is the side that matters.
    if op == Operator.lte:
        yes, no = hi is not None and hi <= limit, lo is not None and lo > limit
        rule = f"at most {_fmt(limit)}"
    elif op == Operator.lt:
        yes, no = hi is not None and hi < limit, lo is not None and lo >= limit
        rule = f"below {_fmt(limit)}"
    elif op == Operator.gte:
        yes, no = lo is not None and lo >= limit, hi is not None and hi < limit
        rule = f"at least {_fmt(limit)}"
    else:
        yes, no = lo is not None and lo > limit, hi is not None and hi <= limit
        rule = f"above {_fmt(limit)}"

    if yes:
        return RequirementStatus.satisfied, f"Your answer meets the rule ({rule})."
    if no:
        return RequirementStatus.not_satisfied, f"Your answer does not meet the rule ({rule})."
    return RequirementStatus.unknown, f"Your range overlaps the limit ({rule}); a more exact answer is needed."


def _key(x: Any) -> Any:
    n = _to_float(x)
    if n is not None:
        return n
    if isinstance(x, bool):
        return "true" if x else "false"
    return str(x).strip().casefold()


def _scalar(value: Any) -> bool:
    return not isinstance(value, (dict, list, tuple, set))


def _word_in(needle: str, haystack: str) -> bool:
    if not needle or not haystack or len(needle) < 3:
        return False
    return bool(re.search(rf"\b{re.escape(needle)}\b", haystack, re.IGNORECASE))


def _equality(op: Operator, required: Any, value: Any) -> Result:
    if not _scalar(value) or not _scalar(required):
        return RequirementStatus.needs_clarification, "The answer can't be compared with this rule."
    v_k = _key(value)
    r_k = _key(required)
    equal = v_k == r_k
    if not equal and isinstance(v_k, str) and isinstance(r_k, str):
        equal = _word_in(r_k, v_k) or _word_in(v_k, r_k)
    if (op == Operator.eq) == equal:
        return RequirementStatus.satisfied, "Your answer matches the rule."
    return RequirementStatus.not_satisfied, "Your answer does not match the rule."


def _membership(op: Operator, required: Any, value: Any) -> Result:
    if not isinstance(required, list) or not required:
        return RequirementStatus.needs_clarification, "The rule's list of allowed values couldn't be read."
    if not _scalar(value):
        return RequirementStatus.needs_clarification, "The answer can't be compared with this rule."
    val_key = _key(value)
    req_keys = {_key(r) for r in required}
    member = val_key in req_keys
    if not member and isinstance(val_key, str):
        member = any(isinstance(r, str) and (_word_in(r, val_key) or _word_in(val_key, r)) for r in req_keys)
    allowed = ", ".join(str(r) for r in required)
    if (op == Operator.in_) == member:
        return RequirementStatus.satisfied, f"Your answer is allowed by the rule ({allowed})."
    if op == Operator.in_:
        return RequirementStatus.not_satisfied, f"The rule allows only: {allowed}."
    return RequirementStatus.not_satisfied, f"The rule excludes: {allowed}."


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _TRUE:
            return True
        if v in _FALSE:
            return False
    return None


def _boolean(op: Operator, value: Any) -> Result:
    b = _as_bool(value)
    if b is None:
        return RequirementStatus.needs_clarification, "Expected a yes or no answer."
    if b == (op == Operator.is_true):
        return RequirementStatus.satisfied, "Your answer meets the rule."
    return RequirementStatus.not_satisfied, "Your answer does not meet the rule."
