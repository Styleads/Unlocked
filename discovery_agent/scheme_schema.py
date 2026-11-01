"""
Pydantic schemas for the Discovery Agent's scheme records.

These models define the structure for government benefit schemes
discovered through live search or loaded from fallback data.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------
# Type aliases for constrained string literals
# --------------------------------------------------

VerificationStatus = Literal[
    "verified",
    "partially_verified",
    "unverified",
    "uncertain",
    "not_verified"
]

ClaimCategory = Literal[
    "description",
    "benefit",
    "eligibility",
    "document",
    "application_process"
]

RelevanceLevel = Literal[
    "direct_match",
    "related",
    "additional"
]

GovernmentLevel = Literal[
    "central",
    "state",
    "local",
    "unknown"
]


# --------------------------------------------------
# Sub-models
# --------------------------------------------------

class SourceEvidence(BaseModel):
    """A single piece of source evidence backing a scheme."""

    title: str
    url: str
    excerpt: str = ""
    is_official: bool | None = None


class SchemeClaim(BaseModel):
    """An individual factual claim extracted from search results."""

    category: ClaimCategory
    claim: str

    source_url: str | None = None
    supporting_excerpt: str = ""

    verification_status: VerificationStatus = "unverified"
    verification_reason: str = ""

    @field_validator("verification_status", mode="before")
    @classmethod
    def normalize_verification_status(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "unverified"
        val = v.strip().lower()
        if val in ("verified", "partially_verified", "unverified", "uncertain", "not_verified"):
            return val
        if "partial" in val:
            return "partially_verified"
        if "uncert" in val:
            return "uncertain"
        if "verif" in val and "unverif" not in val and "not" not in val:
            return "verified"
        return "unverified"


class SchemeCriterion(BaseModel):
    """A single eligibility criterion for a scheme."""

    description: str
    related_attribute: str | None = None
    source_url: str | None = None
    # Exact sentence from source_url, checked verbatim by the extractor.
    evidence: str | None = None
    # "eligibility" (asked as a question) or "obligation" (after the award:
    # attendance, refunds, renewal marks; shown, not asked).
    kind: Literal["eligibility", "obligation"] = "eligibility"
    verification_status: VerificationStatus = "unverified"

    @field_validator("verification_status", mode="before")
    @classmethod
    def normalize_verification_status(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "unverified"
        val = v.strip().lower()
        if val in ("verified", "partially_verified", "unverified", "uncertain", "not_verified"):
            return val
        if "partial" in val:
            return "partially_verified"
        if "uncert" in val:
            return "uncertain"
        if "verif" in val and "unverif" not in val and "not" not in val:
            return "verified"
        return "unverified"


class SchemeDocument(BaseModel):
    """A required document with the sentence that requires it.

    source_url and evidence are set only when the quote was found
    verbatim on that page; otherwise both are None."""

    name: str = Field(min_length=1)
    mandatory: bool = True
    source_url: str | None = None
    evidence: str | None = None


# --------------------------------------------------
# Main scheme record
# --------------------------------------------------

class SchemeRecord(BaseModel):
    """
    A government benefit scheme discovered by the pipeline.

    Every field that cannot be determined from the source
    evidence defaults to an empty or unknown value.
    Information is never invented.
    """

    id: str
    name: str
    description: str = ""

    target_groups: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)

    eligibility_criteria: list[SchemeCriterion] = Field(
        default_factory=list
    )

    required_documents: list[str] = Field(default_factory=list)
    documents: list[SchemeDocument] = Field(default_factory=list)
    application_process: str | None = None
    application_url: str | None = None
    official_url: str | None = None

    # Contact information and deadlines
    deadline: str | None = None
    deadline_status: Literal["upcoming", "expired", "not_published"] = "not_published"
    deadline_source_url: str | None = None
    contact_email: str | None = None
    contact_email_source_url: str | None = None
    contact_phone: str | None = None
    contact_phone_source_url: str | None = None
    office_hours: str | None = None
    office_hours_source_url: str | None = None
    whatsapp_number: str | None = None
    whatsapp_number_source_url: str | None = None
    reception_number: str | None = None
    reception_number_source_url: str | None = None
    contact_source: Literal["website", "receiver_provided", "user_provided"] | None = None

    # Government classification
    government_level: GovernmentLevel = "unknown"
    department: str | None = None

    source_evidence: list[SourceEvidence] = Field(
        default_factory=list
    )

    # Individual claims and their evidence
    claims: list[SchemeClaim] = Field(default_factory=list)

    verification_status: VerificationStatus = "unverified"

    @field_validator("verification_status", mode="before")
    @classmethod
    def normalize_verification_status(cls, v: Any) -> str:
        if not isinstance(v, str):
            return "unverified"
        val = v.strip().lower()
        if val in ("verified", "partially_verified", "unverified", "uncertain", "not_verified"):
            return val
        if "partial" in val:
            return "partially_verified"
        if "uncert" in val:
            return "uncertain"
        if "verif" in val and "unverif" not in val and "not" not in val:
            return "verified"
        return "unverified"

    discovery_source: Literal[
        "live_search", "fallback"
    ] = "live_search"

    relevance: RelevanceLevel = "additional"
    match_reasons: list[str] = Field(default_factory=list)

    missing_information: list[str] = Field(default_factory=list)

    # Timestamp of last verification against source
    last_verified: str | None = None
