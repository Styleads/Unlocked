"""Canonical document registry and name normalization.

Collapses "Income Certificate" / "income cert." into one checklist item. Vocabulary
only: it never states that a scheme requires a document or that one document
depends on another.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .attributes import normalize_text


class DocumentSpec(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


_SPECS = [
    DocumentSpec(
        id="doc_income_certificate",
        name="Income Certificate",
        aliases=["income cert", "family income certificate", "annual income certificate", "income proof"],
    ),
    DocumentSpec(
        id="doc_caste_certificate",
        name="Caste Certificate",
        aliases=["caste cert", "category certificate", "caste and income certificate", "community certificate", "sc st certificate"],
    ),
    DocumentSpec(
        id="doc_domicile_certificate",
        name="Domicile Certificate",
        aliases=["residence certificate", "residence proof", "proof of residence", "nativity certificate", "domicile cert"],
    ),
    DocumentSpec(
        id="doc_aadhaar_card",
        name="Aadhaar Card",
        aliases=["aadhaar", "aadhar", "aadhar card", "aadhaar copy"],
    ),
    DocumentSpec(
        id="doc_admission_proof",
        name="Admission Proof",
        aliases=["admission letter", "proof of admission", "admission order", "allotment letter"],
    ),
    DocumentSpec(
        id="doc_fee_receipt",
        name="Fee Receipt",
        aliases=["fee structure", "fee payment receipt", "fees receipt", "tuition fee receipt"],
    ),
    DocumentSpec(
        id="doc_previous_marksheet",
        name="Previous Marksheet",
        aliases=["marksheet", "marks card", "marks sheet", "previous year marksheet", "mark list", "previous marks card"],
    ),
    DocumentSpec(
        id="doc_bank_passbook",
        name="Bank Passbook",
        aliases=["bank account details", "bank passbook copy", "passbook", "bank account proof"],
    ),
    DocumentSpec(
        id="doc_passport_photo",
        name="Passport Photo",
        aliases=["passport size photo", "photograph", "photo", "recent photograph"],
    ),
    DocumentSpec(
        id="doc_disability_certificate",
        name="Disability Certificate",
        aliases=["pwd certificate", "udid card", "disability proof"],
    ),
    DocumentSpec(
        id="doc_bonafide_certificate",
        name="Bonafide Certificate",
        aliases=["study certificate", "bonafide", "student certificate"],
    ),
    DocumentSpec(
        id="doc_ration_card",
        name="Ration Card",
        aliases=["bpl card", "bpl ration card", "ration card copy"],
    ),
    DocumentSpec(
        id="doc_transfer_certificate",
        name="Transfer Certificate",
        aliases=["tc", "school leaving certificate", "leaving certificate"],
    ),
]

DOCUMENTS: dict[str, DocumentSpec] = {d.id: d for d in _SPECS}


def _build_alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for spec in _SPECS:
        for key in (spec.name, *spec.aliases):
            norm = normalize_text(key)
            if index.setdefault(norm, spec.id) != spec.id:
                raise ValueError(f"alias {key!r} maps to more than one document")
    return index


_ALIAS_INDEX = _build_alias_index()


def resolve_document(name: str) -> Optional[str]:
    return _ALIAS_INDEX.get(normalize_text(name))


def normalize_document_name(name: str) -> tuple[str, str]:
    """(doc_id, display_name). Unknown names get their own id rather than being
    guessed into an existing document."""
    doc_id = resolve_document(name)
    if doc_id:
        return doc_id, DOCUMENTS[doc_id].name
    norm = normalize_text(name)
    return "doc_" + norm.replace(" ", "_"), norm.title()
