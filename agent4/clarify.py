"""Clarification questions built from what is actually unclear about a scheme.

A question is only suggested when the scheme data shows a real gap:
  1. a rule found on an official page that can't be applied as written
     (status "uncertain", e.g. limits that differ by category);
  2. official pages that state different rules;
  3. details the search could not find (documents, how to apply, criteria).
Nothing unclear -> no question; the user should apply instead.

Duck-typed (member2 SchemeRecord, its dict, or similar); no member2 import.
The quoted rules travel as SourcedFacts, so the email cites them with links.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .models import EmailPurpose, EmailRequest, SchemeContext, SourcedFact


class ClarificationKind(str, Enum):
    uncertain_rule = "uncertain_rule"
    sources_disagree = "sources_disagree"
    missing_documents = "missing_documents"
    missing_process = "missing_process"
    missing_criteria = "missing_criteria"


class ClarificationPoint(BaseModel):
    kind: ClarificationKind
    question: str  # one sentence, ends with "?"
    facts: list[SourcedFact] = Field(default_factory=list)


# Notes written by Agent 1 / the adapter / member2 into scheme.uncertainties.
_DISAGREE = "official pages for this scheme state different rules"
_MISSING = {
    "required documents": ClarificationKind.missing_documents,
    "some required documents have no official source": ClarificationKind.missing_documents,
    "application process": ClarificationKind.missing_process,
    "eligibility criteria": ClarificationKind.missing_criteria,
}
_MISSING_QUESTION = {
    ClarificationKind.missing_documents: "Could you please share the complete list of documents required to apply?",
    ClarificationKind.missing_process: "Could you please explain how and where to apply, and whether there is a deadline?",
    ClarificationKind.missing_criteria: "Could you please share the eligibility criteria for this scheme?",
}
_ORDER = list(ClarificationKind)  # most useful first


def _get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _value(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _topic(attribute: Optional[str]) -> str:
    """Readable topic for a rule: "annual_family_income" -> "annual family income"."""
    if not attribute or attribute.startswith("unmapped:"):
        return "eligibility"
    return attribute.replace("_", " ")


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def clarification_points(scheme: Any, *, limit: int = 3) -> list[ClarificationPoint]:
    """Up to `limit` questions, most useful first. Empty if nothing is unclear."""
    points: list[ClarificationPoint] = []
    reqs = _get(scheme, "requirements") or []

    # 1. Rules the official text itself leaves open, one question per topic.
    #    Only real ambiguity counts: limits that differ by group ("group_limits"),
    #    or a rule the source marked uncertain. A rule uncertain only because our
    #    checks couldn't confirm a value ("not_stated", e.g. "B.Sc." vs a coarse
    #    course list) is our gap, not the department's, so it is never asked.
    topics: dict[str, list[SourcedFact]] = {}
    grouped: set[str] = set()
    seen: set[str] = set()
    for req in reqs:
        evidence, source = _get(req, "evidence"), _get(req, "source_url")
        if _value(_get(req, "status")) != "uncertain" or not (evidence and source):
            continue
        reason = _get(req, "uncertain_reason")
        if not (reason == "group_limits" or (reason is None and not _get(req, "normalized_by"))):
            continue
        topic = _topic(_get(req, "attribute"))
        if reason == "group_limits":
            grouped.add(topic)
        if _norm(evidence) not in seen:
            seen.add(_norm(evidence))
            topics.setdefault(topic, []).append(SourcedFact(text=evidence.strip(), source_url=source))
    for topic, facts in topics.items():
        if topic in grouped:
            question = (f"The official rules on {topic} (quoted below) set different conditions for different "
                        f"groups. Could you please confirm which one applies to me?")
        else:
            question = f"Could you please clarify how the quoted rule on {topic} applies to me?"
        points.append(ClarificationPoint(kind=ClarificationKind.uncertain_rule, question=question, facts=facts))

    notes = [_norm(n) for n in (_get(scheme, "uncertainties") or []) if isinstance(n, str)]

    # 2. Official pages disagree: cite one verified rule from each page.
    if any(_DISAGREE in n for n in notes):
        by_page: dict[str, SourcedFact] = {}
        for req in reqs:
            evidence, source = _get(req, "evidence"), _get(req, "source_url")
            if _value(_get(req, "status")) == "verified" and evidence and source and source not in by_page:
                by_page[source] = SourcedFact(text=evidence.strip(), source_url=source)
        if len(by_page) > 1:
            points.append(ClarificationPoint(
                kind=ClarificationKind.sources_disagree,
                question="Different official pages describe the eligibility differently (quoted below). "
                         "Could you please confirm which conditions currently apply?",
                facts=list(by_page.values())[:3],
            ))

    # 3. Details the search could not find.
    found: set[ClarificationKind] = set()
    for n in notes:
        for prefix, kind in _MISSING.items():
            if n.startswith(prefix):
                found.add(kind)
    if any(_value(_get(r, "status")) == "verified" for r in reqs):
        found.discard(ClarificationKind.missing_criteria)  # we do have criteria
    for kind in found:
        points.append(ClarificationPoint(kind=kind, question=_MISSING_QUESTION[kind]))

    points.sort(key=lambda p: _ORDER.index(p.kind))
    return points[:limit]


def clarification_request(
    scheme: Any,
    *,
    user_details: Optional[dict[str, str]] = None,
    limit: int = 3,
) -> Optional[EmailRequest]:
    """A ready EmailRequest (purpose clarification) asking about every point,
    or None when nothing is unclear, in which case the user should apply."""
    points = clarification_points(scheme, limit=limit)
    if not points:
        return None
    if len(points) == 1:
        question = points[0].question
    else:
        question = "I have the following questions:\n" + "\n".join(f"{i}. {p.question}" for i, p in enumerate(points, 1))
    facts: list[SourcedFact] = []
    for p in points:
        for f in p.facts:
            if all(_norm(f.text) != _norm(g.text) for g in facts):
                facts.append(f)
    return EmailRequest(
        scheme=SchemeContext.model_validate(scheme),
        purpose=EmailPurpose.clarification,
        question=question,
        user_details=user_details or {},
        facts=facts,
    )
