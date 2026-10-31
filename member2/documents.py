"""Canonical document registry and name normalization.

Collapses "Income Certificate" / "income cert." into one checklist item. Vocabulary
only: it never states that a scheme requires a document or that one document
depends on another. All definitions live in data files (e.g. data/documents.json).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field

from .attributes import normalize_text

log = logging.getLogger(__name__)


class DocumentSpec(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    issuing_authority: Optional[str] = None
    prerequisites: list[Union[dict, str]] = Field(default_factory=list)
    description: Optional[str] = None


def _find_default_data_file() -> Optional[Path]:
    candidates = [
        Path("data/documents.json"),
        Path(__file__).resolve().parent.parent / "data" / "documents.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_document_registry(path: Optional[Union[str, Path]] = None) -> list[DocumentSpec]:
    target = Path(path) if path else _find_default_data_file()
    if target and target.is_file():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            docs_list = raw.get("documents", raw) if isinstance(raw, dict) else raw
            specs = [DocumentSpec.model_validate(item) for item in docs_list]
            log.debug("Loaded %d document definitions from %s", len(specs), target)
            return specs
        except Exception as e:
            log.warning("Failed loading documents from %s: %s; falling back to built-ins", target, e)

    # Minimal fallback specs in case data file is missing
    return [
        DocumentSpec(
            id="doc_income_certificate",
            name="Income Certificate",
            aliases=["income cert", "family income certificate", "annual income certificate", "income proof"],
            issuing_authority="Revenue Department (Tahsildar / Nadakacheri)",
        ),
        DocumentSpec(
            id="doc_caste_certificate",
            name="Caste Certificate",
            aliases=["caste cert", "category certificate", "caste and income certificate", "community certificate", "sc st certificate"],
            issuing_authority="Revenue Department (Tahsildar)",
        ),
        DocumentSpec(
            id="doc_domicile_certificate",
            name="Domicile Certificate",
            aliases=["residence certificate", "residence proof", "proof of residence", "nativity certificate", "domicile cert"],
            issuing_authority="Revenue Department (Tahsildar)",
        ),
        DocumentSpec(
            id="doc_aadhaar_card",
            name="Aadhaar Card",
            aliases=["aadhaar", "aadhar", "aadhar card", "aadhaar copy"],
            issuing_authority="UIDAI",
        ),
        DocumentSpec(
            id="doc_admission_proof",
            name="Admission Proof",
            aliases=["admission letter", "proof of admission", "admission order", "allotment letter"],
            issuing_authority="Educational Institution",
        ),
        DocumentSpec(
            id="doc_fee_receipt",
            name="Fee Receipt",
            aliases=["fee structure", "fee payment receipt", "fees receipt", "tuition fee receipt"],
            issuing_authority="Educational Institution",
        ),
        DocumentSpec(
            id="doc_previous_marksheet",
            name="Previous Marksheet",
            aliases=["marksheet", "marks card", "marks sheet", "previous year marksheet", "mark list", "previous marks card"],
            issuing_authority="Examination Board / University",
        ),
        DocumentSpec(
            id="doc_bank_passbook",
            name="Bank Passbook",
            aliases=["bank account details", "bank passbook copy", "passbook", "bank account proof"],
            issuing_authority="Commercial / Scheduled Bank",
        ),
        DocumentSpec(
            id="doc_passport_photo",
            name="Passport Photo",
            aliases=["passport size photo", "photograph", "photo", "recent photograph"],
            issuing_authority="Applicant",
        ),
        DocumentSpec(
            id="doc_disability_certificate",
            name="Disability Certificate",
            aliases=["pwd certificate", "udid card", "disability proof"],
            issuing_authority="District Medical Board / UDID Portal",
        ),
        DocumentSpec(
            id="doc_bonafide_certificate",
            name="Bonafide Certificate",
            aliases=["study certificate", "bonafide", "student certificate"],
            issuing_authority="Educational Institution",
        ),
        DocumentSpec(
            id="doc_ration_card",
            name="Ration Card",
            aliases=["bpl card", "bpl ration card", "ration card copy"],
            issuing_authority="Food and Civil Supplies Department",
        ),
        DocumentSpec(
            id="doc_transfer_certificate",
            name="Transfer Certificate",
            aliases=["tc", "school leaving certificate", "leaving certificate"],
            issuing_authority="Previous School / College",
        ),
    ]


_SPECS: list[DocumentSpec] = load_document_registry()
DOCUMENTS: dict[str, DocumentSpec] = {d.id: d for d in _SPECS}


def _build_alias_index(specs: Optional[list[DocumentSpec]] = None) -> dict[str, str]:
    target_specs = specs if specs is not None else _SPECS
    index: dict[str, str] = {}
    for spec in target_specs:
        for key in (spec.id, spec.name, *spec.aliases):
            norm = normalize_text(key)
            if index.setdefault(norm, spec.id) != spec.id:
                log.debug("Alias %r maps to more than one document id; keeping %s", key, index[norm])
    return index


_ALIAS_INDEX: dict[str, str] = _build_alias_index()


def reload_document_registry(path: Optional[Union[str, Path]] = None) -> None:
    """Dynamically reloads document definitions from a data file without code changes."""
    global _SPECS, DOCUMENTS, _ALIAS_INDEX
    _SPECS = load_document_registry(path)
    DOCUMENTS = {d.id: d for d in _SPECS}
    _ALIAS_INDEX = _build_alias_index(_SPECS)


def resolve_document(name: str) -> Optional[str]:
    if name in DOCUMENTS:
        return name
    return _ALIAS_INDEX.get(normalize_text(name))


def normalize_document_name(name: str) -> tuple[str, str]:
    """(doc_id, display_name). Unknown names get their own id rather than being
    guessed into an existing document."""
    if name in DOCUMENTS:
        return name, DOCUMENTS[name].name
    doc_id = resolve_document(name)
    if doc_id and doc_id in DOCUMENTS:
        return doc_id, DOCUMENTS[doc_id].name
    norm = normalize_text(name)
    return "doc_" + norm.replace(" ", "_"), norm.title()


def get_issuing_authority(doc_id_or_name: str) -> Optional[str]:
    doc_id = resolve_document(doc_id_or_name) or doc_id_or_name
    spec = DOCUMENTS.get(doc_id)
    return spec.issuing_authority if spec else None
