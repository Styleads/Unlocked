"""Turn a scheme's verified rules into the sourced facts an email may quote.

Duck-typed on purpose: works on a member2 SchemeRecord, its dict, or anything
shaped like them, without importing member2."""
from __future__ import annotations

from typing import Any, Iterable, Optional

from .models import SourcedFact


def _get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _value(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v  # str enums and plain strings alike


def facts_from_scheme(
    scheme: Any,
    *,
    attributes: Optional[Iterable[str]] = None,
    limit: int = 5,
) -> list[SourcedFact]:
    """Verified rules that carry both a verbatim quote and its source, in rule
    order, one per distinct quote (a compound rule's parts share one quote).

    attributes: keep only rules on these attribute ids (e.g. ["annual_family_income"]).
    limit: at most this many facts, so the email stays short.
    """
    wanted = set(attributes) if attributes is not None else None
    facts: list[SourcedFact] = []
    seen: set[str] = set()
    for req in _get(scheme, "requirements") or []:
        # Only verified rules are presented as "the official guidance states".
        if _value(_get(req, "status")) != "verified":
            continue
        evidence, source = _get(req, "evidence"), _get(req, "source_url")
        if not (isinstance(evidence, str) and evidence.strip() and isinstance(source, str) and source.strip()):
            continue
        if wanted is not None and _get(req, "attribute") not in wanted:
            continue
        key = " ".join(evidence.split()).casefold()
        if key in seen:
            continue
        seen.add(key)
        facts.append(SourcedFact(text=evidence.strip(), source_url=source.strip()))
        if len(facts) >= limit:
            break
    return facts
