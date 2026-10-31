"""Requirement normalization.

A deterministic pass always runs. An optional LLM pass then (a) structures
requirements Member 1 delivered as text only and (b) extracts rules from
`eligibility_text`. Every LLM output is validated; failures add an uncertainty
and never raise. Only scheme text is sent to the model, never user answers.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable, Optional

from pydantic import BaseModel, ValidationError

from .assess import SchemeInput, _as_scheme
from .attributes import ATTRIBUTES, AttributeSpec, is_canonical, normalize_text, resolve_attribute
from .llm import LLMClient
from .models import InputType, Operator, Requirement, RequirementVerification, SchemeRecord

log = logging.getLogger(__name__)

LLM_MARK = "normalized_by"  # extra field on requirements the LLM structured or extracted
EXTRACTION_FAILED = "Automatic rule extraction failed."

_ALLOWED_OPS = {
    InputType.number: {Operator.lte, Operator.lt, Operator.gte, Operator.gt, Operator.eq, Operator.neq},
    InputType.range: {Operator.lte, Operator.lt, Operator.gte, Operator.gt},
    InputType.select: {Operator.eq, Operator.neq, Operator.in_, Operator.not_in},
    InputType.text: {Operator.eq, Operator.neq, Operator.in_, Operator.not_in},
    InputType.boolean: {Operator.is_true, Operator.is_false},
}


def _attribute_catalog() -> str:
    lines = []
    for spec in ATTRIBUTES.values():
        extra = f" options={spec.options}" if spec.options else ""
        unit = f" unit={spec.unit}" if spec.unit else ""
        lines.append(f"- {spec.id} ({spec.input_type.value}{unit}){extra}: {spec.label}")
    return "\n".join(lines)


NORMALIZE_SYSTEM = f"""You convert government-scheme eligibility text into structured rules.

Canonical attributes (use these ids exactly, or "unmapped" if none fits):
{_attribute_catalog()}

Operators: lte, lt, gte, gt, eq, neq, in, not_in, is_true, is_false.
- Numbers are plain numbers in base units (rupees, years, percent). "2.5 lakh" is 250000.
- For "in"/"not_in" the value is a list of option strings exactly as listed above.
- For "is_true"/"is_false" the value is null.

Rules:
- Never invent a rule, threshold or value. If a value is not stated, use null.
- "criterion" and "evidence" must be copied verbatim from the input text.
- Output only one JSON object, no prose, in this shape:
{{"structured": [{{"id": "<given id>", "attribute": "...", "operator": "...", "value": ...}}],
  "extracted": [{{"attribute": "...", "operator": "...", "value": ..., "criterion": "...", "evidence": "..."}}]}}
- "structured" answers each item in "criteria_to_structure" by its id.
- "extracted" lists rules found in "eligibility_text" (empty if none is given).
"""


class _Structured(BaseModel):
    id: str
    attribute: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None


class _Extracted(BaseModel):
    attribute: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    criterion: str = ""
    evidence: str = ""


# --- helpers ------------------------------------------------------------------

def _slug(text: str) -> str:
    return normalize_text(text).replace(" ", "_")[:40] or "rule"


def _squash(text: str) -> str:
    return " ".join(text.split())


_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|thousand|k\b)?", re.IGNORECASE)
_SCALE = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "crore": 1e7, "crores": 1e7, "thousand": 1e3, "k": 1e3}


def _numbers_in_text(text: str) -> set[float]:
    found: set[float] = set()
    for raw, unit in _NUM.findall(text or ""):
        try:
            n = float(raw.replace(",", ""))
        except ValueError:
            continue
        found.add(n)
        if unit:
            found.add(n * _SCALE[unit.lower()])
    return found


def _numbers_in_value(value: Any) -> list[float]:
    items = value if isinstance(value, list) else [value]
    out = []
    for v in items:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, str):
            out.extend(_numbers_in_text(v))
    return out


def _numbers_supported(value: Any, evidence: Optional[str]) -> bool:
    """Every number the model produced must be stated in the evidence. Guards
    against a real quote paired with a misread threshold."""
    wanted = _numbers_in_value(value)
    if not wanted:
        return True
    have = _numbers_in_text(evidence or "")
    return all(any(abs(w - h) < 1e-6 for h in have) for w in wanted)


def _canonical_rule(attribute: Optional[str], operator: Optional[str], value: Any, fallback_slug: str) -> tuple[str, Optional[Operator], Any]:
    """Map the model's attribute/operator/value onto the registry. Anything that
    doesn't fit leaves operator None, which assessment treats as needs_clarification."""
    attr = attribute if is_canonical(attribute) else (resolve_attribute(attribute) if attribute else None)
    if not attr:
        named = attribute and attribute.strip().lower() != "unmapped"
        return f"unmapped:{_slug(attribute) if named else fallback_slug}", None, value
    spec: AttributeSpec = ATTRIBUTES[attr]
    try:
        op = Operator(operator) if operator else None
    except ValueError:
        op = None
    if op is None or op not in _ALLOWED_OPS[spec.input_type]:
        return attr, None, value
    if op in (Operator.is_true, Operator.is_false):
        return attr, op, None
    if spec.input_type == InputType.select:
        items = value if isinstance(value, list) else [value]
        matched = [next((o for o in spec.options if o.casefold() == str(v).strip().casefold()), None) for v in items]
        if not items or None in matched:
            return attr, None, value
        if op in (Operator.in_, Operator.not_in):
            return attr, op, matched
        return attr, op, matched[0]
    return attr, op, value


# --- deterministic pass -------------------------------------------------------

def _deterministic(scheme: SchemeRecord) -> SchemeRecord:
    seen: set[str] = set()
    reqs: list[Requirement] = []
    used_ids = {r.id for r in scheme.requirements if r.id}
    n = 0
    for req in scheme.requirements:
        key = _squash(req.criterion).casefold()
        if key in seen:
            continue  # same rule listed twice; keeps normalization idempotent
        seen.add(key)
        update: dict[str, Any] = {}
        if not req.id:
            n += 1
            while f"{scheme.id}_req_{n}" in used_ids:
                n += 1
            update["id"] = f"{scheme.id}_req_{n}"
            used_ids.add(update["id"])
        if req.attribute and not is_canonical(req.attribute) and not req.attribute.startswith("unmapped:"):
            update["attribute"] = resolve_attribute(req.attribute) or f"unmapped:{_slug(req.attribute)}"
        # Verified needs both a source and a quote from it.
        if (not req.source_url or not req.evidence) and req.status == RequirementVerification.verified:
            update["status"] = RequirementVerification.unverified
        reqs.append(req.model_copy(update=update))
    return scheme.model_copy(update={"requirements": reqs})


# --- LLM pass -----------------------------------------------------------------

def _needs_structuring(req: Requirement) -> bool:
    if getattr(req, LLM_MARK, None):
        return False
    # A known attribute with no operator (e.g. Agent 1 sends only the attribute)
    # can't be compared until the text is structured.
    return req.attribute is None or req.attribute.startswith("unmapped:") or req.operator is None


def _text_pending(scheme: SchemeRecord) -> bool:
    return bool(scheme.eligibility_text) and not any(getattr(r, LLM_MARK, None) == "extracted" for r in scheme.requirements)


def _parse(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in model output")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not an object")
    return data


def _call(llm: LLMClient, payload: dict) -> Optional[dict]:
    for attempt in (1, 2):  # one retry, then give up quietly
        try:
            return _parse(llm.complete_json(NORMALIZE_SYSTEM, json.dumps(payload, ensure_ascii=False)))
        except Exception as exc:  # noqa: BLE001 - any provider/parse failure is handled the same way
            log.warning("rule extraction attempt %d failed: %s", attempt, type(exc).__name__)
    return None


def _add_uncertainty(uncertainties: list[str], text: str) -> None:
    if text not in uncertainties:
        uncertainties.append(text)


def _llm_pass(scheme: SchemeRecord, llm: LLMClient) -> SchemeRecord:
    targets = [r for r in scheme.requirements if _needs_structuring(r)]
    pending_text = _text_pending(scheme)
    if not targets and not pending_text:
        return scheme

    payload = {
        "criteria_to_structure": [{"id": r.id, "criterion": r.criterion, "evidence": r.evidence} for r in targets],
        "eligibility_text": scheme.eligibility_text if pending_text else None,
    }
    data = _call(llm, payload)
    uncertainties = list(scheme.uncertainties)
    if data is None:
        _add_uncertainty(uncertainties, EXTRACTION_FAILED)
        return scheme.model_copy(update={"uncertainties": uncertainties})

    by_id = {r.id: r for r in targets}
    structured: dict[str, Requirement] = {}
    for item in data.get("structured") or []:
        try:
            s = _Structured.model_validate(item)
        except ValidationError:
            continue
        req = by_id.get(s.id)
        if req is None:
            continue
        attr, op, value = _canonical_rule(s.attribute, s.operator, s.value, _slug(req.criterion))
        status = req.status
        if status == RequirementVerification.verified and not _numbers_supported(value, req.evidence or req.criterion):
            status = RequirementVerification.uncertain
        structured[req.id] = req.model_copy(update={"attribute": attr, "operator": op, "value": value, "status": status, LLM_MARK: "structured"})

    reqs = [structured.get(r.id, r) for r in scheme.requirements]

    if pending_text:
        source = scheme.official_sources[0] if scheme.official_sources else None
        haystack = _squash(scheme.eligibility_text or "")
        seen = {_squash(r.criterion).casefold() for r in reqs}
        used_ids = {r.id for r in reqs}
        n = len(reqs)
        for item in data.get("extracted") or []:
            try:
                e = _Extracted.model_validate(item)
            except ValidationError:
                continue
            evidence = _squash(e.evidence)
            criterion = _squash(e.criterion) or evidence
            if not evidence or evidence not in haystack:
                _add_uncertainty(uncertainties, f"Could not verify extracted rule: {criterion or '(empty)'}")
                continue
            if criterion not in haystack:
                criterion = evidence  # keep only text that is really in the source
            if criterion.casefold() in seen:
                continue
            seen.add(criterion.casefold())
            attr, op, value = _canonical_rule(e.attribute, e.operator, e.value, _slug(criterion))
            if not source:
                status = RequirementVerification.unverified
            elif _numbers_supported(value, evidence):
                status = RequirementVerification.verified
            else:
                status = RequirementVerification.uncertain
            n += 1
            while f"{scheme.id}_req_{n}" in used_ids:
                n += 1
            used_ids.add(f"{scheme.id}_req_{n}")
            reqs.append(Requirement(
                id=f"{scheme.id}_req_{n}", attribute=attr, criterion=criterion, operator=op, value=value,
                status=status, source_url=source, evidence=evidence, **{LLM_MARK: "extracted"},
            ))

    return scheme.model_copy(update={"requirements": reqs, "uncertainties": uncertainties})


# --- public API ---------------------------------------------------------------

def normalize_scheme(scheme: SchemeInput, llm: Optional[LLMClient] = None) -> SchemeRecord:
    """Returns a new record; the input is not mutated. Safe to call repeatedly."""
    out = _deterministic(_as_scheme(scheme))
    if llm is not None:
        try:
            out = _llm_pass(out, llm)
        except Exception:  # noqa: BLE001 - never raise to the caller
            log.exception("normalization LLM pass failed for scheme=%s", out.id)
            uncertainties = list(out.uncertainties)
            _add_uncertainty(uncertainties, EXTRACTION_FAILED)
            out = out.model_copy(update={"uncertainties": uncertainties})
    return out


def normalize_requirements(schemes: Iterable[SchemeInput], llm: Optional[LLMClient] = None) -> list[SchemeRecord]:
    """plan.md's RequirementMatrix is this list of normalized SchemeRecords."""
    return [normalize_scheme(s, llm) for s in schemes]


def requirement_matrix(schemes: Iterable[SchemeInput]) -> dict[str, list[str]]:
    """Canonical attribute id -> sorted ids of schemes that have a rule on it."""
    matrix: dict[str, set[str]] = {}
    for s in schemes:
        s = _as_scheme(s)
        for r in s.requirements:
            if is_canonical(r.attribute):
                matrix.setdefault(r.attribute, set()).add(s.id)
    return {a: sorted(ids) for a, ids in sorted(matrix.items())}
