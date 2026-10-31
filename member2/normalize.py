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
from .models import InputType, Operator, Requirement, RequirementVerification, RuleCondition, SchemeRecord

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
- If a criterion states several conditions (e.g. income AND course AND college type),
  return one "structured" item per condition, all with the same id. Use attribute
  "unmapped" with a short name in "value" for a condition no attribute fits; never drop it.
- Skip statements that exclude nobody, e.g. "all courses", "students of all categories".
- If a condition applies only to one group (e.g. "65% for General, 60% for SC/ST"),
  return one item per group and add "when": {{"attribute": ..., "operator": ..., "value": ...}}
  naming the group, e.g. {{"attribute": "social_category", "operator": "in", "value": ["SC", "ST"]}}.
- "extracted" lists rules found in "eligibility_text" (empty if none is given).
- Every item with a value also gives "value_quote": the exact words of the evidence that
  state that value, copied verbatim (e.g. the words naming the group, the year or the amount).
  A "when" also gives its own "quote".
- Set "restricts": false on a statement that excludes nobody (it is then dropped).
"""


CONFIRM_SYSTEM = """You check whether a phrase from an official eligibility rule states a value.
For each item: does the phrase, read as written in a government eligibility rule, state exactly
the given value of the given attribute? Answer false if the phrase means something narrower,
broader or different, or if you are not sure.
Return only JSON: {"results": {"<id>": true|false}}"""


def _confirm_meanings(llm: Any, items: list[tuple[str, str, Any]]) -> list[bool]:
    """For (attribute label, phrase, value) items, return True where the meaning
    is REJECTED. One call for all items; any failure rejects every item, so an
    unconfirmed value can never decide eligibility."""
    if not items:
        return []
    if llm is None:
        return [True] * len(items)
    payload = {"items": [{"id": str(i), "attribute": a, "phrase": p, "value": v} for i, (a, p, v) in enumerate(items)]}
    try:
        data = _parse(llm.complete_json(CONFIRM_SYSTEM, json.dumps(payload, ensure_ascii=False, default=str)))
        results = data.get("results")
        if not isinstance(results, dict):
            raise ValueError("no results")
    except Exception as exc:  # noqa: BLE001 - unconfirmed means rejected
        log.warning("meaning check failed: %s", type(exc).__name__)
        return [True] * len(items)
    return [results.get(str(i)) is not True for i in range(len(items))]


class _Structured(BaseModel):
    id: str
    attribute: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    when: Optional[dict] = None  # group the rule applies to, e.g. social_category in [SC, ST]; has "quote"
    value_quote: Optional[str] = None  # exact words in the evidence that state the value
    restricts: Optional[bool] = None  # False: the statement excludes nobody


class _Extracted(BaseModel):
    attribute: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    criterion: str = ""
    evidence: str = ""
    value_quote: Optional[str] = None
    restricts: Optional[bool] = None


# --- helpers ------------------------------------------------------------------

def _slug(text: str) -> str:
    return normalize_text(text).replace(" ", "_")[:40] or "rule"


def _squash(text: str) -> str:
    return " ".join(text.split())


_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|thousand|k\b)?", re.IGNORECASE)
_SCALE = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "crore": 1e7, "crores": 1e7, "thousand": 1e3, "k": 1e3}


def _numbers_in_text(text: str) -> set[float]:
    """Digits with Indian units ("2.5 lakh" -> 2.5 and 250000). Number words
    ("first year") are not parsed here; the model cites them and an independent
    check confirms the meaning (DECISIONS #66)."""
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


def _non_restrictive(attr: str, op: Optional[Operator], value: Any, restricts: Optional[bool]) -> bool:
    """Statements that exclude nobody are not rules; kept, they block a scheme
    for no reason. The model flags them (restricts=false); independently, a
    select "in" covering every option of the attribute excludes nobody."""
    if restricts is False:
        return True
    spec = ATTRIBUTES.get(attr)
    if spec and spec.input_type == InputType.select and op == Operator.in_ and isinstance(value, list):
        return set(spec.options) <= set(value)
    return False


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


def _words(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9.]+", " ", (text or "").casefold()).strip() + " "


def _phrase_in(evidence: Optional[str], phrase: Optional[str]) -> bool:
    """The cited phrase appears in the evidence, ignoring case, spacing and punctuation."""
    p = _words(phrase or "").strip()
    return bool(p) and f" {p} " in _words(evidence or "")


def _literal(option: Any, text: Optional[str]) -> bool:
    """The option's own words appear in the text as whole words."""
    o = _words(str(option)).strip()
    return bool(o) and f" {o} " in _words(text or "")


def _value_check(attr: str, op: Optional[Operator], value: Any, quote: Optional[str],
                 evidence: Optional[str]) -> tuple[bool, list[tuple[str, Any]]]:
    """Is the value stated in the evidence? Returns (ok_so_far, to_confirm):
    to_confirm lists (phrase, value) pairs whose meaning an independent model
    check must confirm, e.g. ("girl students", "Female"), ("first year", 1)."""
    if op is None or op in (Operator.is_true, Operator.is_false) or value is None:
        return True, []
    items = value if isinstance(value, list) else [value]
    numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in items)
    if not quote or not _phrase_in(evidence, quote):
        # No usable pointer: accept only what the evidence states literally.
        if numeric:
            return _numbers_supported(value, evidence), []
        return all(_literal(v, evidence) for v in items), []
    if numeric:
        if _numbers_in_text(quote):
            return _numbers_supported(value, quote), []
        return True, [(quote, v) for v in items]  # number written in words
    pending = [(quote, v) for v in items if not _literal(v, quote)]
    return True, pending


def _unused_thresholds(parts: list[Requirement], evidence: Optional[str]) -> bool:
    """True if the evidence states a number of similar size that none of the
    rules built from it uses, e.g. "Rs 2.5 lakh for Category-I and Rs 1 lakh for
    Category 2A". One comparison can't express such a conditional limit, so the
    rule must not decide anything. Magnitude window 0.25x-4x skips list numbers
    ("4.") and category codes ("2A") next to a threshold like 25 or 250000."""
    # Small values (year of study, number of subjects) can't be told apart from
    # list numbers and counts ("at least 2 subjects"), so only real thresholds count.
    used = [n for p in parts if p.operator is not None for n in _numbers_in_value(p.value) if n >= 10]
    if not used:
        return False
    for n in _numbers_in_text(evidence or ""):
        if any(abs(n - u) < 1e-6 for u in used):
            continue
        if any(0.25 <= n / u <= 4 for u in used if u):
            return True
    return False


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
        if getattr(req, LLM_MARK, None):
            # Conditions split from one criterion share its text; they differ by rule.
            cond = req.condition.model_dump(mode="json") if req.condition else None
            key += "|" + json.dumps([req.attribute, req.operator, req.value, cond], sort_keys=True, default=str)
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
    # One criterion may hold several conditions; each becomes its own rule so
    # none is silently dropped (a dropped condition could yield a false
    # "Potential match"). Unmappable parts stay as yes/no own conditions.
    structured: dict[str, list[Requirement]] = {}
    # (rid, part index, phrase, value) whose meaning a separate check must confirm
    to_confirm: list[tuple[str, int, str, Any]] = []
    all_ids = {r.id for r in scheme.requirements}
    for item in data.get("structured") or []:
        try:
            s = _Structured.model_validate(item)
        except ValidationError:
            continue
        req = by_id.get(s.id)
        if req is None:
            continue
        parts = structured.setdefault(req.id, [])
        unmapped_name = s.value if isinstance(s.value, str) and (s.attribute or "").strip().lower() == "unmapped" else None
        attr, op, value = _canonical_rule(unmapped_name or s.attribute, s.operator, s.value,
                                          f"{_slug(req.criterion)}_{len(parts) + 1}" if parts else _slug(req.criterion))
        if _non_restrictive(attr, op, value, s.restricts):
            continue
        status = req.status
        reason = None  # why a part is uncertain (DECISIONS #65)
        evidence = req.evidence or req.criterion
        pending: list[tuple[str, Any]] = []
        if status == RequirementVerification.verified:
            ok, pending = _value_check(attr, op, value, s.value_quote, evidence)
            if not ok:
                status, reason, pending = RequirementVerification.uncertain, "not_stated", []
        new_id = req.id
        if parts:  # second and later conditions get their own stable id
            k = len(parts) + 1
            while f"{req.id}_{k}" in all_ids:
                k += 1
            new_id = f"{req.id}_{k}"
            all_ids.add(new_id)
        condition = None
        if isinstance(s.when, dict):
            c_attr, c_op, c_value = _canonical_rule(s.when.get("attribute"), s.when.get("operator"), s.when.get("value"), "group")
            c_ok, c_pending = (_value_check(c_attr, c_op, c_value, s.when.get("quote"), evidence)
                               if is_canonical(c_attr) and c_op is not None else (False, []))
            if c_ok:
                condition = RuleCondition(attribute=c_attr, operator=c_op, value=c_value)
                pending += c_pending
            elif status == RequirementVerification.verified:
                # The group is unreadable or unsupported: the rule must not decide anything.
                status, reason, pending = RequirementVerification.uncertain, "not_stated", []
        update = {"id": new_id, "attribute": attr, "operator": op, "value": value,
                  "status": status, "condition": condition, LLM_MARK: "structured"}
        if reason:
            update["uncertain_reason"] = reason
        to_confirm += [(req.id, len(parts), phrase, v) for phrase, v in pending]
        parts.append(req.model_copy(update=update))

    # Meanings the cited words don't state literally ("girl students" = Female,
    # "first year" = 1) are confirmed by an independent call; unconfirmed -> uncertain.
    rejected = _confirm_meanings(llm, [(ATTRIBUTES[p_attr].label if (p_attr := structured[rid][i].attribute) in ATTRIBUTES
                                        else p_attr, phrase, v) for rid, i, phrase, v in to_confirm])
    for (rid, i, _, _), bad in zip(to_confirm, rejected):
        part = structured[rid][i]
        if bad and part.status == RequirementVerification.verified:
            structured[rid][i] = part.model_copy(update={"status": RequirementVerification.uncertain,
                                                         "uncertain_reason": "not_stated"})

    for rid, parts in structured.items():
        if _unused_thresholds(parts, by_id[rid].evidence or by_id[rid].criterion):
            structured[rid] = [
                p.model_copy(update={"status": RequirementVerification.uncertain, "uncertain_reason": "group_limits"})
                if p.status == RequirementVerification.verified and p.operator is not None else p
                for p in parts
            ]
            # One note per scheme; the affected rules are already marked uncertain.
            _add_uncertainty(uncertainties, "Some rules have different limits for different groups and need checking.")

    reqs = [part for r in scheme.requirements for part in structured.get(r.id, [r])]

    if pending_text:
        source = scheme.official_sources[0] if scheme.official_sources else None
        haystack = _squash(scheme.eligibility_text or "")
        seen = {_squash(r.criterion).casefold() for r in reqs}
        used_ids = {r.id for r in reqs}
        n = len(reqs)
        extracted: list[Requirement] = []
        ex_confirm: list[tuple[int, str, Any]] = []
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
            if _non_restrictive(attr, op, value, e.restricts):
                continue
            pending: list[tuple[str, Any]] = []
            if not source:
                status = RequirementVerification.unverified
            else:
                ok, pending = _value_check(attr, op, value, e.value_quote, evidence)
                status = RequirementVerification.verified if ok else RequirementVerification.uncertain
                if not ok:
                    pending = []
            extra = {"uncertain_reason": "not_stated"} if status == RequirementVerification.uncertain else {}
            n += 1
            while f"{scheme.id}_req_{n}" in used_ids:
                n += 1
            used_ids.add(f"{scheme.id}_req_{n}")
            ex_confirm += [(len(extracted), phrase, v) for phrase, v in pending]
            extracted.append(Requirement(
                id=f"{scheme.id}_req_{n}", attribute=attr, criterion=criterion, operator=op, value=value,
                status=status, source_url=source, evidence=evidence, **{LLM_MARK: "extracted"}, **extra,
            ))
        rejected = _confirm_meanings(llm, [(ATTRIBUTES[extracted[i].attribute].label, phrase, v)
                                           for i, phrase, v in ex_confirm])
        for (i, _, _), bad in zip(ex_confirm, rejected):
            if bad and extracted[i].status == RequirementVerification.verified:
                extracted[i] = extracted[i].model_copy(update={"status": RequirementVerification.uncertain,
                                                               "uncertain_reason": "not_stated"})
        reqs += extracted

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
