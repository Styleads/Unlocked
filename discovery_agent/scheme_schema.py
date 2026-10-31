"""
Pydantic schemas for the Discovery Agent's scheme records.

These models define the structure for government benefit schemes
discovered through live search or loaded from fallback data.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------
# Type aliases for constrained string literals
# --------------------------------------------------

VerificationStatus = Literal[
    "verified",
    "partially_verified",
    "unverified"
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


class SchemeCriterion(BaseModel):
    """A single eligibility criterion for a scheme."""

    description: str
    related_attribute: str | None = None
    source_url: str | None = None
    verification_status: VerificationStatus = "unverified"


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
    application_process: str | None = None
    application_url: str | None = None
    official_url: str | None = None

    # Government classification
    government_level: GovernmentLevel = "unknown"
    department: str | None = None

    source_evidence: list[SourceEvidence] = Field(
        default_factory=list
    )

    # Individual claims and their evidence
    claims: list[SchemeClaim] = Field(default_factory=list)

    verification_status: VerificationStatus = "unverified"

    discovery_source: Literal[
        "live_search", "fallback"
    ] = "live_search"

    relevance: RelevanceLevel = "additional"
    match_reasons: list[str] = Field(default_factory=list)

    missing_information: list[str] = Field(default_factory=list)

    # Timestamp of last verification against source
    last_verified: str | None = None
