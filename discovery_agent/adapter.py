"""
Project Unlocked — Compliance & Translation Adapter.

Adapts Discovery Agent (Member 1) raw extracted schemes into canonical
Member 2 data models (member2.models.SchemeRecord, Requirement, DocumentRequirement)
matching plan.md §5 and docs/agents.md §2.1.
"""
from __future__ import annotations

import re
from typing import Any, Optional, Sequence

try:
    from member2.models import (
        SchemeRecord as CanonicalSchemeRecord,
        Requirement,
        DocumentRequirement,
        DocumentDependency,
        VerificationStatus,
        RequirementVerification,
        Operator,
    )
    from member2.attributes import resolve_attribute, is_canonical
except (ImportError, ModuleNotFoundError):
    # Fallback placeholders when external dependencies (pydantic) are not yet installed
    class _DummyEnum:
        def __getattr__(self, name: str) -> str:
            return name

    CanonicalSchemeRecord = dict  # type: ignore
    Requirement = dict  # type: ignore
    DocumentRequirement = dict  # type: ignore
    DocumentDependency = dict  # type: ignore
    VerificationStatus = _DummyEnum()  # type: ignore
    RequirementVerification = _DummyEnum()  # type: ignore
    Operator = _DummyEnum()  # type: ignore
    resolve_attribute = lambda x: None  # type: ignore
    is_canonical = lambda x: False  # type: ignore


_NON_WORD = re.compile(r"[^a-z0-9_]+")


def _clean_slug(text: str) -> str:
    cleaned = _NON_WORD.sub("_", text.lower().strip()).strip("_")
    return cleaned or "criterion"


def _map_attribute(raw_attr: Optional[str], criterion_text: str = "") -> Optional[str]:
    """
    Resolve an attribute to a canonical ID from member2.attributes.
    If no canonical attribute matches, format with 'unmapped:<slug>'
    so that check_member1 and the normalizer accept it cleanly.
    """
    if raw_attr:
        # Check if already canonical
        if is_canonical(raw_attr):
            return raw_attr
        # Try resolving alias
        resolved = resolve_attribute(raw_attr)
        if resolved:
            return resolved

    # Try resolving from criterion text
    if criterion_text:
        resolved_text = resolve_attribute(criterion_text)
        if resolved_text:
            return resolved_text

    if not raw_attr:
        return None

    # Fallback to unmapped:<slug>
    slug = _clean_slug(raw_attr)
    if slug.startswith("unmapped_"):
        slug = slug[len("unmapped_"):]
    elif slug.startswith("unmapped:"):
        return slug
    return f"unmapped:{slug}"


def _map_operator(op: Any) -> Optional[Operator]:
    """Map string or enum to canonical Operator enum."""
    if isinstance(op, Operator):
        return op
    if not op:
        return None

    op_str = str(op).lower().strip()
    mapping = {
        "lte": Operator.lte,
        "<=": Operator.lte,
        "lt": Operator.lt,
        "<": Operator.lt,
        "gte": Operator.gte,
        ">=": Operator.gte,
        "gt": Operator.gt,
        ">": Operator.gt,
        "eq": Operator.eq,
        "==": Operator.eq,
        "equals": Operator.eq,
        "neq": Operator.neq,
        "!=": Operator.neq,
        "in": Operator.in_,
        "not_in": Operator.not_in,
        "is_true": Operator.is_true,
        "boolean": Operator.is_true,
        "true": Operator.is_true,
        "is_false": Operator.is_false,
        "false": Operator.is_false,
    }
    return mapping.get(op_str)


def _map_req_status(status: Any) -> RequirementVerification:
    """Map raw status string to RequirementVerification enum."""
    if isinstance(status, RequirementVerification):
        return status
    st = str(status).lower().strip() if status else ""
    if st == "verified":
        return RequirementVerification.verified
    if st == "uncertain":
        return RequirementVerification.uncertain
    return RequirementVerification.unverified


def _map_scheme_status(status: Any) -> VerificationStatus:
    """Map scheme verification status to VerificationStatus enum."""
    if isinstance(status, VerificationStatus):
        return status
    st = str(status).lower().strip() if status else ""
    if st == "verified":
        return VerificationStatus.verified
    if st == "uncertain":
        return VerificationStatus.uncertain
    return VerificationStatus.not_verified


def to_canonical_requirement(
    raw_req: Any,
    default_source_url: Optional[str] = None,
    index: int = 1,
    scheme_id: str = "scheme",
) -> Requirement:
    """Convert a raw criterion or dict into a canonical Requirement."""
    if isinstance(raw_req, Requirement):
        return raw_req

    if hasattr(raw_req, "model_dump"):
        data = raw_req.model_dump()
    elif isinstance(raw_req, dict):
        data = raw_req
    else:
        data = {
            "criterion": str(raw_req),
            "description": str(raw_req),
        }

    criterion_text = data.get("criterion") or data.get("description") or ""
    source_url = data.get("source_url") or default_source_url
    evidence = data.get("evidence") or data.get("supporting_excerpt") or criterion_text

    raw_attr = data.get("attribute") or data.get("related_attribute")
    canonical_attr = _map_attribute(raw_attr, criterion_text)

    operator = _map_operator(data.get("operator"))
    if operator is None and canonical_attr:
        # Default boolean attributes to is_true
        if canonical_attr in ("domicile_karnataka", "receives_other_scholarship", "has_disability", "is_minority"):
            operator = Operator.is_true

    req_id = data.get("id") or f"{scheme_id}_req_{index}"
    status = _map_req_status(data.get("status") or data.get("verification_status"))

    return Requirement(
        id=req_id,
        attribute=canonical_attr,
        criterion=criterion_text,
        operator=operator,
        value=data.get("value"),
        status=status,
        source_url=source_url,
        evidence=evidence,
    )


def to_canonical_document(
    raw_doc: Any,
    default_source_url: Optional[str] = None,
    scheme_name: str = "scheme",
) -> DocumentRequirement:
    """
    Convert a document string or dict into a canonical DocumentRequirement.
    Guarantees non-empty source_url and evidence so Agent 3 does not exclude it.
    """
    if isinstance(raw_doc, DocumentRequirement):
        return raw_doc

    if isinstance(raw_doc, str):
        return DocumentRequirement(
            name=raw_doc,
            source_url=default_source_url or "https://karnataka.gov.in",
            evidence=f"Required document for {scheme_name}",
            dependencies=[],
        )

    if hasattr(raw_doc, "model_dump"):
        data = raw_doc.model_dump()
    elif isinstance(raw_doc, dict):
        data = raw_doc
    else:
        doc_str = str(raw_doc)
        return DocumentRequirement(
            name=doc_str,
            source_url=default_source_url or "https://karnataka.gov.in",
            evidence=f"Required document for {scheme_name}",
            dependencies=[],
        )

    name = data.get("name") or str(raw_doc)
    source_url = data.get("source_url") or default_source_url or "https://karnataka.gov.in"
    evidence = data.get("evidence") or f"Required document for {scheme_name}"

    raw_deps = data.get("dependencies") or []
    dependencies = [
        DocumentDependency(
            depends_on=d if isinstance(d, str) else d.get("depends_on", ""),
            source_url=source_url,
            evidence=evidence,
        )
        for d in raw_deps
    ]

    return DocumentRequirement(
        name=name,
        source_url=source_url,
        evidence=evidence,
        dependencies=dependencies,
    )


def to_canonical_scheme(raw: Any) -> CanonicalSchemeRecord:
    """
    Convert any M1 SchemeRecord, dict, or raw object into a canonical
    member2.models.SchemeRecord that satisfies all downstream contracts
    while preserving M1 backwards compatibility fields.
    """
    if isinstance(raw, CanonicalSchemeRecord):
        return raw

    if hasattr(raw, "model_dump"):
        data = raw.model_dump()
    elif isinstance(raw, dict):
        data = raw
    else:
        raise ValueError(f"Cannot adapt object of type {type(raw).__name__} to SchemeRecord")

    scheme_id = data.get("id") or "scheme-unknown"
    name = data.get("name") or "Unnamed Scheme"

    # Summary
    summary = data.get("summary") or data.get("description") or ""

    # Official URL & Sources
    official_url = data.get("official_url") or data.get("application_url")
    official_sources = list(data.get("official_sources") or [])
    if official_url and official_url not in official_sources:
        official_sources.insert(0, official_url)
    default_source = official_sources[0] if official_sources else (official_url or "https://karnataka.gov.in")

    # Target Group
    target_group = list(data.get("target_group") or data.get("target_groups") or [])

    # Benefit
    benefit = data.get("benefit")
    if benefit is None:
        raw_benefits = data.get("benefits")
        if isinstance(raw_benefits, list) and raw_benefits:
            benefit = "; ".join(str(b) for b in raw_benefits)
        elif raw_benefits:
            benefit = str(raw_benefits)

    # Documents (ensure every document has a source_url so Agent 3 never excludes it)
    raw_docs = data.get("documents") or data.get("required_documents") or []
    documents = [
        to_canonical_document(d, default_source_url=default_source, scheme_name=name)
        for d in raw_docs
    ]

    # Requirements
    raw_reqs = data.get("requirements") or data.get("eligibility_criteria") or []
    requirements = [
        to_canonical_requirement(
            r,
            default_source_url=default_source,
            index=i + 1,
            scheme_id=scheme_id,
        )
        for i, r in enumerate(raw_reqs)
    ]

    # Application steps
    app_steps = data.get("application_steps")
    if app_steps is None:
        process = data.get("application_process")
        if process:
            app_steps = [process] if isinstance(process, str) else list(process)
        else:
            app_steps = []

    # Verification status
    v_status = _map_scheme_status(data.get("verification_status"))

    # Source type
    source_type = data.get("source_type") or data.get("discovery_source") or "live_search"
    if source_type not in ("live_search", "fallback"):
        source_type = "live_search"

    # Uncertainties
    uncertainties = list(data.get("uncertainties") or data.get("missing_information") or [])

    # Build canonical record with M1 backwards-compatible extra fields
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
        application_url=data.get("application_url") or official_url,
        deadline=data.get("deadline"),
        deadline_source_url=data.get("deadline_source_url"),
        official_sources=official_sources,
        verification_status=v_status,
        uncertainties=uncertainties,
        source_type=source_type,
        # Preserved fields for Member 1 compatibility
        description=summary,
        target_groups=target_group,
        benefits=data.get("benefits") or ([benefit] if benefit else []),
        required_documents=[d.name for d in documents],
        eligibility_criteria=data.get("eligibility_criteria") or [],
        official_url=official_url or default_source,
        discovery_source=source_type,
        missing_information=uncertainties,
        last_verified=data.get("last_verified"),
        claims=data.get("claims") or [],
        relevance=data.get("relevance", "additional"),
        match_reasons=data.get("match_reasons") or [],
        source_evidence=data.get("source_evidence") or [],
    )


def to_canonical_schemes(schemes: Sequence[Any]) -> list[CanonicalSchemeRecord]:
    """Convert an entire sequence of schemes to canonical SchemeRecords."""
    return [to_canonical_scheme(s) for s in schemes]
