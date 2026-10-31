"""
Project Unlocked — Discovery → Eligibility adapter.

Converts Discovery Agent (Member 1) scheme records into canonical
member2.models.SchemeRecord (plan.md §5.1).

Provenance rule: a source URL or evidence quote is only ever copied from the
record itself or from a *verified* claim that states the same thing. Nothing
is defaulted. A requirement without both a source and evidence is marked
unverified; a document without a source stays unsourced, so the planner
leaves it out with a visible warning instead of showing an invented source.
"""
from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from member2.attributes import is_canonical, resolve_attribute
from member2.models import (
    DocumentDependency,
    DocumentRequirement,
    Operator,
    Requirement,
    RequirementVerification,
    SchemeRecord as CanonicalSchemeRecord,
    VerificationStatus,
)

_NON_WORD = re.compile(r"[^a-z0-9_]+")
_SPACE = re.compile(r"\s+")


def _clean_slug(text: str) -> str:
    cleaned = _NON_WORD.sub("_", text.lower().strip()).strip("_")
    return cleaned or "criterion"


def _norm(text: Any) -> str:
    return _SPACE.sub(" ", str(text or "")).strip().casefold()


def _as_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj if isinstance(obj, dict) else {}


def _verified_claims(claims: Sequence[Any], category: str) -> list[dict]:
    """Claims Agent 1 verified against a source excerpt, for one category."""
    out = []
    for c in claims or []:
        d = _as_dict(c)
        if (d.get("category") == category and d.get("verification_status") == "verified"
                and d.get("source_url") and d.get("supporting_excerpt")):
            out.append(d)
    return out


def _map_attribute(raw_attr: Optional[str], criterion_text: str = "") -> Optional[str]:
    """Canonical id, else unmapped:<slug> (member2's normalizer may still map it), else None."""
    if raw_attr:
        if is_canonical(raw_attr):
            return raw_attr
        resolved = resolve_attribute(raw_attr)
        if resolved:
            return resolved
    if criterion_text:
        resolved = resolve_attribute(criterion_text)
        if resolved:
            return resolved
    if not raw_attr:
        return None
    if raw_attr.startswith("unmapped:"):
        return raw_attr
    return f"unmapped:{_clean_slug(raw_attr)}"


_OPERATORS = {
    "lte": Operator.lte, "<=": Operator.lte, "lt": Operator.lt, "<": Operator.lt,
    "gte": Operator.gte, ">=": Operator.gte, "gt": Operator.gt, ">": Operator.gt,
    "eq": Operator.eq, "==": Operator.eq, "equals": Operator.eq,
    "neq": Operator.neq, "!=": Operator.neq, "in": Operator.in_, "not_in": Operator.not_in,
    "is_true": Operator.is_true, "boolean": Operator.is_true, "true": Operator.is_true,
    "is_false": Operator.is_false, "false": Operator.is_false,
}


def _map_operator(op: Any) -> Optional[Operator]:
    # No default from the attribute type: "not receiving another scholarship"
    # is is_false, so guessing is_true would invert the rule. A missing
    # operator is left for member2's normalizer to structure from the text.
    if isinstance(op, Operator):
        return op
    return _OPERATORS.get(str(op).lower().strip()) if op else None


def _map_scheme_status(status: Any) -> VerificationStatus:
    st = str(status.value if hasattr(status, "value") else status or "").lower().strip()
    if st == "verified":
        return VerificationStatus.verified
    if st in ("uncertain", "partially_verified"):
        return VerificationStatus.uncertain
    return VerificationStatus.not_verified


def to_canonical_requirement(
    raw_req: Any,
    index: int = 1,
    scheme_id: str = "scheme",
    claims: Sequence[Any] = (),
) -> Requirement:
    """Convert a criterion (Agent 1 SchemeCriterion, dict, or text) into a Requirement."""
    if isinstance(raw_req, Requirement):
        return raw_req
    data = _as_dict(raw_req) or {"criterion": str(raw_req)}

    criterion = data.get("criterion") or data.get("description") or ""
    source_url = data.get("source_url")
    evidence = data.get("evidence") or data.get("supporting_excerpt")
    status = str(data.get("status") or data.get("verification_status") or "").lower().strip()

    # Agent 1 links a criterion to the eligibility claim with the same text;
    # that claim carries the verbatim excerpt.
    if not evidence:
        for claim in _verified_claims(claims, "eligibility"):
            if _norm(claim.get("claim")) == _norm(criterion):
                source_url = source_url or claim["source_url"]
                evidence = claim["supporting_excerpt"]
                break

    if status == "uncertain":
        verification = RequirementVerification.uncertain
    elif status == "verified" and source_url and evidence:
        verification = RequirementVerification.verified
    else:
        verification = RequirementVerification.unverified

    return Requirement(
        id=data.get("id") or f"{scheme_id}_req_{index}",
        attribute=_map_attribute(data.get("attribute") or data.get("related_attribute"), criterion),
        criterion=criterion,
        operator=_map_operator(data.get("operator")),
        value=data.get("value"),
        status=verification,
        source_url=source_url,
        evidence=evidence,
    )


def to_canonical_document(raw_doc: Any, claims: Sequence[Any] = ()) -> DocumentRequirement:
    """Convert a document (name or dict) into a DocumentRequirement.

    A plain name is sourced only if a verified "document" claim mentions it;
    otherwise it stays unsourced and the planner excludes it with a warning.
    """
    if isinstance(raw_doc, DocumentRequirement):
        return raw_doc
    data = _as_dict(raw_doc) or {"name": str(raw_doc)}
    name = str(data.get("name") or "").strip()
    source_url, evidence = data.get("source_url"), data.get("evidence")

    if name and not (source_url and evidence):
        for claim in _verified_claims(claims, "document"):
            if _norm(name) in _norm(claim.get("claim")) or _norm(name) in _norm(claim.get("supporting_excerpt")):
                source_url, evidence = claim["source_url"], claim["supporting_excerpt"]
                break

    # An edge keeps only its own provenance, never the document's.
    deps = []
    for d in data.get("dependencies") or []:
        dd = {"depends_on": d} if isinstance(d, str) else _as_dict(d)
        if dd.get("depends_on"):
            deps.append(DocumentDependency(depends_on=dd["depends_on"], source_url=dd.get("source_url"),
                                           evidence=dd.get("evidence")))

    return DocumentRequirement(name=name, source_url=source_url, evidence=evidence, dependencies=deps)


def to_canonical_scheme(raw: Any) -> CanonicalSchemeRecord:
    """Convert an Agent 1 SchemeRecord or dict into a canonical member2 SchemeRecord,
    keeping Agent 1's own fields as extras for backwards compatibility."""
    if isinstance(raw, CanonicalSchemeRecord):
        return raw
    data = _as_dict(raw)
    if not data:
        raise ValueError(f"Cannot adapt object of type {type(raw).__name__} to SchemeRecord")

    scheme_id = data.get("id") or "scheme-unknown"
    name = data.get("name") or "Unnamed Scheme"
    summary = data.get("summary") or data.get("description") or ""
    claims = data.get("claims") or []

    official_url = data.get("official_url")
    official_sources = [u for u in (data.get("official_sources") or []) if u]
    for ev in data.get("source_evidence") or []:
        ev = _as_dict(ev)
        if ev.get("url") and ev.get("is_official") is not False and ev["url"] not in official_sources:
            official_sources.append(ev["url"])
    if official_url and official_url not in official_sources:
        official_sources.insert(0, official_url)

    target_group = list(data.get("target_group") or data.get("target_groups") or [])

    benefit = data.get("benefit")
    if benefit is None:
        raw_benefits = data.get("benefits")
        if isinstance(raw_benefits, list) and raw_benefits:
            benefit = "; ".join(str(b) for b in raw_benefits)
        elif raw_benefits:
            benefit = str(raw_benefits)

    documents = [to_canonical_document(d, claims) for d in (data.get("documents") or data.get("required_documents") or [])]
    requirements = [
        to_canonical_requirement(r, index=i + 1, scheme_id=scheme_id, claims=claims)
        for i, r in enumerate(data.get("requirements") or data.get("eligibility_criteria") or [])
    ]

    app_steps = data.get("application_steps")
    process = data.get("application_process")
    if app_steps is None:
        app_steps = ([process] if isinstance(process, str) else list(process)) if process else []

    source_type = data.get("source_type") or data.get("discovery_source") or "live_search"
    if source_type not in ("live_search", "fallback"):
        source_type = "live_search"

    uncertainties = list(data.get("uncertainties") or data.get("missing_information") or [])
    unsourced_docs = [d.name for d in documents if not d.source_url]
    if unsourced_docs:
        note = "Some required documents have no official source yet: " + ", ".join(unsourced_docs) + "."
        if note not in uncertainties:
            uncertainties.append(note)

    return CanonicalSchemeRecord(
        id=scheme_id,
        name=name,
        summary=summary,
        government_level=data.get("government_level"),
        department=data.get("department"),
        target_group=target_group,
        eligibility_text=data.get("eligibility_text"),
        requirements=requirements,
        benefit=benefit,
        documents=documents,
        application_steps=app_steps,
        application_url=data.get("application_url"),
        deadline=data.get("deadline"),
        deadline_source_url=data.get("deadline_source_url"),
        official_sources=official_sources,
        verification_status=_map_scheme_status(data.get("verification_status")),
        uncertainties=uncertainties,
        source_type=source_type,
        # Agent 1 fields kept (extra="allow") so its translator and UI code keep working.
        description=summary,
        target_groups=target_group,
        benefits=data.get("benefits") or ([benefit] if benefit else []),
        required_documents=[d.name for d in documents],
        eligibility_criteria=data.get("eligibility_criteria") or [],
        application_process=process if process is not None else ("\n".join(app_steps) if app_steps else None),
        official_url=official_url,
        discovery_source=source_type,
        missing_information=uncertainties,
        last_verified=data.get("last_verified"),
        claims=claims,
        relevance=data.get("relevance", "additional"),
        match_reasons=data.get("match_reasons") or [],
        source_evidence=data.get("source_evidence") or [],
    )


def to_canonical_schemes(schemes: Sequence[Any]) -> list[CanonicalSchemeRecord]:
    """Convert a sequence of schemes to canonical SchemeRecords."""
    return [to_canonical_scheme(s) for s in schemes]


# Function aliases matching M3 orchestration plan and docs/agents.md terminology
adapt_m1_to_m2_scheme = to_canonical_scheme
adapt_m1_to_m2_schemes = to_canonical_schemes

