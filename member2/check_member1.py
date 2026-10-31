"""Check a JSON file of scheme records from Member 1 against plan.md section 5.1, then
run it through the offline pipeline. Run from the repo root:
    python -m member2.check_member1 path/to/schemes.json
Reports field names and ids only, never answer values."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import assess_schemes, normalize_requirements
from .attributes import is_canonical as is_canonical_attribute
from pydantic import ValidationError

from .models import SchemeRecord

SCHEME_FIELDS = {
    "id", "name", "summary", "government_level", "department", "target_group", "requirements",
    "benefit", "documents", "application_steps", "application_url", "deadline", "deadline_source_url",
    "official_sources", "verification_status", "uncertainties", "source_type", "eligibility_text",
}
REQ_FIELDS = {"id", "attribute", "criterion", "operator", "value", "status", "source_url", "evidence"}
STATUSES = {"verified", "not_verified", "uncertain"}
REQ_STATUSES = {"verified", "unverified", "not_verified", "uncertain"}


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("schemes", [data])
    if not isinstance(data, list):
        raise ValueError("expected a list of schemes or {\"schemes\": [...]}")
    return data


def contract_problems(raw: dict[str, Any]) -> list[str]:
    out: list[str] = []
    where = raw.get("id") or raw.get("name") or "<no id>"
    for key in ("id", "name"):
        if not raw.get(key):
            out.append(f"{where}: missing '{key}'")
    for key in sorted(set(raw) - SCHEME_FIELDS):
        out.append(f"{where}: unexpected field '{key}' (kept, but check the name against plan.md 5.1)")
    if raw.get("verification_status") not in STATUSES:
        out.append(f"{where}: verification_status {raw.get('verification_status')!r} not in {sorted(STATUSES)}")
    if not raw.get("official_sources") and not raw.get("application_url"):
        out.append(f"{where}: no official_sources or application_url")
    for i, req in enumerate(raw.get("requirements") or []):
        if not isinstance(req, dict):
            out.append(f"{where}: requirements[{i}] is a {type(req).__name__}, expected an object")
            continue
        tag = f"{where}: requirements[{i}]"
        if not req.get("criterion"):
            out.append(f"{tag}: missing 'criterion'")
        if not req.get("source_url"):
            out.append(f"{tag}: no source_url (cannot be verified)")
        if not req.get("evidence"):
            out.append(f"{tag}: no verbatim evidence quote (cannot be verified)")
        if req.get("status", "unverified") not in REQ_STATUSES:
            out.append(f"{tag}: status {req.get('status')!r} not recognised")
        for key in sorted(set(req) - REQ_FIELDS):
            out.append(f"{tag}: unexpected field '{key}'")
        if req.get("attribute") and not is_canonical_attribute(req["attribute"]):
            out.append(f"{tag}: attribute {req['attribute']!r} is not in the registry (will need clarification)")
    for i, doc in enumerate(raw.get("documents") or []):
        if isinstance(doc, str):
            out.append(f"{where}: documents[{i}] is a plain string; needs {{name, source_url, evidence}} or it is left out of the plan")
        elif isinstance(doc, dict) and not doc.get("source_url"):
            out.append(f"{where}: documents[{i}] has no source_url (left out of the plan)")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        raws = load(Path(argv[1]))
    except (OSError, ValueError) as exc:
        print(f"Could not read file: {exc}")
        return 2
    problems = [p for raw in raws for p in contract_problems(raw)]
    print(f"{len(raws)} scheme(s) read.")
    print("\nContract check:" if problems else "\nContract check: no problems.")
    for p in problems:
        print(f"  - {p}")
    try:
        schemes = normalize_requirements([SchemeRecord.model_validate(r) for r in raws])
        results = assess_schemes(schemes, {})
    except ValidationError as exc:
        # One short line per field; pydantic's full message echoes whole records.
        print("\nPIPELINE FAILED: records do not fit SchemeRecord")
        for err in exc.errors():
            print(f"  - {'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        return 1
    except Exception as exc:  # the point of this script is to surface what breaks
        print(f"\nPIPELINE FAILED: {type(exc).__name__}: {exc}")
        return 1
    print("\nOffline pipeline (no answers yet):")
    for s, a in zip(schemes, results):
        mapped = sum(1 for r in s.requirements if is_canonical_attribute(r.attribute))
        print(f"  {s.id}: {a.status.value}; {len(s.requirements)} rule(s), {mapped} mapped to the registry")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
