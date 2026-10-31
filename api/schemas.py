"""
api/schemas.py — Public Pydantic schemas for Project Unlocked REST API.

Defines all request and response models consumed by Member 4 (Frontend),
adhering strictly to docs/agents.md and M3_Coding_Round_1_Plan.md.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

# Re-export core Member 2 models for full structural typing and serialization
from member2.models import (
    ActionPlan,
    Answer,
    AnswerState,
    Assessment,
    ChecklistItem,
    DocStatus,
    DocumentDependency,
    DocumentRequirement,
    GraphEdge,
    GraphNode,
    InputType,
    Operator,
    Question,
    RangeOption,
    Requirement,
    RequirementResult,
    RequirementStatus,
    RequirementVerification,
    SchemeRecord,
    SchemeStatus,
    Sensitivity,
    VerificationStatus,
)
from member2.attributes import resolve_attribute, ATTRIBUTES


# ---------------------------------------------------------------------------
# 1. Operational & Health Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health and operational readiness status of the backend service."""
    status: str = "healthy"
    application: str = "Project Unlocked — Government Benefits Assistant"
    version: str = "1.0.0"
    operational: bool = True
    services: dict[str, bool] = Field(
        default_factory=lambda: {
            "gemini_configured": False,
            "tavily_configured": False,
            "sqlite_connected": True,
        }
    )


# ---------------------------------------------------------------------------
# 2. User Context & Profile Schemas
# ---------------------------------------------------------------------------

class UserProfileInput(BaseModel):
    """
    Flexible citizen profile input for session creation.
    Supports flat attributes and optional nested sections.
    """
    model_config = ConfigDict(extra="allow")

    # Common flat attributes
    occupation: Optional[str] = None
    state: Optional[str] = "Karnataka"
    district: Optional[str] = None
    annual_income: Optional[Union[float, int, str, dict]] = None
    annual_family_income: Optional[Union[float, int, str, dict]] = None
    age: Optional[Union[int, float]] = None
    gender: Optional[str] = None
    social_category: Optional[str] = None
    caste_category: Optional[str] = None
    education_level: Optional[str] = None
    interests: list[str] = Field(default_factory=list)

    # Optional nested sections (aligned with profile_manager format)
    personal: Optional[dict[str, Any]] = None
    location: Optional[dict[str, Any]] = None
    education: Optional[dict[str, Any]] = None
    employment: Optional[dict[str, Any]] = None
    agriculture: Optional[dict[str, Any]] = None
    household: Optional[dict[str, Any]] = None
    other_details: Optional[dict[str, Any]] = None

    def to_user_context(self) -> dict[str, Any]:
        """Convert input into dictionary expected by Discovery Agent."""
        data = self.model_dump()
        extra_fields = {
            k: v for k, v in data.items()
            if k not in (
                "occupation", "state", "district", "annual_income",
                "annual_family_income", "age", "gender", "social_category",
                "caste_category", "education_level", "interests",
                "personal", "location", "education", "employment",
                "agriculture", "household", "other_details"
            ) and v is not None
        }

        employment = dict(data.get("employment") or {})
        if self.occupation and "occupation" not in employment:
            employment["occupation"] = self.occupation

        location = dict(data.get("location") or {})
        if self.state and "state" not in location:
            location["state"] = self.state
        if self.district and "district" not in location:
            location["district"] = self.district

        household = dict(data.get("household") or {})
        income = self.annual_family_income if self.annual_family_income is not None else self.annual_income
        if income is not None and "annual_income" not in household:
            household["annual_income"] = income

        interests = self.interests
        if isinstance(interests, str):
            interests = [interests]

        context: dict[str, Any] = {
            "employment": employment,
            "location": location,
            "household": household,
            "interests": interests,
            "personal": dict(data.get("personal") or {}),
            "education": dict(data.get("education") or {}),
            "agriculture": dict(data.get("agriculture") or {}),
            "other_details": dict(data.get("other_details") or {}),
            **extra_fields,
        }
        if self.age is not None:
            context["personal"]["age"] = self.age
        if self.gender is not None:
            context["personal"]["gender"] = self.gender
        if self.social_category or self.caste_category:
            context["personal"]["social_category"] = self.social_category or self.caste_category

        return context

    def extract_seedable_attributes(self) -> list[dict[str, Any]]:
        """
        Extract canonical attributes present in the profile so they can be
        seeded as answered in Member 2's answer map and history, preventing
        redundant questions for already known facts.
        """
        seedable: list[dict[str, Any]] = []

        def _add(attr_name: str, val: Any) -> None:
            if val is None or val == "":
                return
            canonical = resolve_attribute(attr_name) or attr_name
            if canonical in ATTRIBUTES:
                seedable.append({
                    "attribute": canonical,
                    "state": AnswerState.answered.value,
                    "value": val,
                })

        # Flat fields
        _add("state", self.state)
        _add("district", self.district)
        _add("annual_family_income", self.annual_family_income or self.annual_income)
        _add("age", self.age)
        _add("gender", self.gender)
        _add("social_category", self.social_category or self.caste_category)
        _add("education_level", self.education_level)

        emp_status = self.model_dump().get("employment_status")
        if not emp_status and self.occupation:
            occ_lower = self.occupation.lower().strip()
            if occ_lower in ("farmer", "agriculturist", "cultivator", "artisan", "business", "self-employed", "self employed"):
                emp_status = "Self-employed"
            elif occ_lower in ("student", "employed", "unemployed", "other"):
                emp_status = self.occupation.capitalize()
            else:
                emp_status = "Other"
        if emp_status:
            _add("employment_status", emp_status)

        # Inspect extra attributes
        for k, v in self.model_dump().items():
            if k not in (
                "personal", "location", "education", "employment",
                "agriculture", "household", "other_details", "interests"
            ):
                _add(k, v)

        # Inspect nested sections
        if self.location:
            _add("state", self.location.get("state"))
            _add("district", self.location.get("district"))
        if self.employment:
            _add("employment_status", self.employment.get("occupation") or self.employment.get("employment_status"))
        if self.household:
            _add("annual_family_income", self.household.get("annual_income") or self.household.get("annual_family_income"))
        if self.personal:
            _add("age", self.personal.get("age"))
            _add("gender", self.personal.get("gender"))
            _add("social_category", self.personal.get("social_category") or self.personal.get("caste_category"))

        # Deduplicate by attribute name
        seen = set()
        unique_seeds = []
        for s in seedable:
            if s["attribute"] not in seen:
                seen.add(s["attribute"])
                unique_seeds.append(s)

        return unique_seeds


# ---------------------------------------------------------------------------
# 3. Session Management Schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    """Payload to initialize a new session with citizen context."""
    context: Union[UserProfileInput, dict[str, Any]] = Field(default_factory=dict)
    scope: Literal["guided", "all", "fallback"] = "guided"
    preferred_language: Literal["en", "kn"] = "en"


class SessionResponse(BaseModel):
    """Initial response returned upon session creation."""
    session_id: str
    status: str = "initialized"
    scope: str = "guided"
    preferred_language: str = "en"
    created_at: str


class FullSessionState(BaseModel):
    """Complete durable session snapshot restored from SQLite."""
    session_id: str
    scope: str
    preferred_language: str
    state_status: str
    context: dict[str, Any]
    raw_schemes: list[dict[str, Any]] = Field(default_factory=list)
    normalized_schemes: list[dict[str, Any]] = Field(default_factory=list)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    answers: dict[str, Any] = Field(default_factory=dict)
    history: dict[str, Any] = Field(default_factory=dict)
    assessments: list[dict[str, Any]] = Field(default_factory=list)
    plan: Optional[dict[str, Any]] = None
    user_documents: dict[str, str] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class DeleteSessionResponse(BaseModel):
    """Response confirming session deletion."""
    deleted: bool = True
    session_id: str


# ---------------------------------------------------------------------------
# 4. Discovery Schemas
# ---------------------------------------------------------------------------

class DiscoverOptions(BaseModel):
    """Optional override parameters for discovery execution."""
    search_scope: Optional[Literal["guided", "all", "fallback"]] = None
    preferred_language: Optional[Literal["en", "kn"]] = None
    enable_fallback: bool = True


class SchemeView(BaseModel):
    """
    Consolidated frontend view of a scheme combining official metadata
    with current assessment results.
    """
    id: str
    name: str
    summary: Optional[str] = None
    government_level: Optional[str] = None
    department: Optional[str] = None
    benefit: Any = None
    target_group: list[str] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)
    application_url: Optional[str] = None
    official_sources: list[str] = Field(default_factory=list)
    source_type: str = "live_search"
    # Assessment overlays
    assessment_status: Optional[str] = None
    assessment_explanation: Optional[str] = None
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    """Response returned upon discovery pipeline completion."""
    session_id: str
    status: str = "discovery_complete"
    total_schemes: int
    schemes: list[SchemeView] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    source_mode: Literal["live_search", "fallback"] = "live_search"
    preferred_language: str = "en"
    translation_status: str = "not_requested"
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 5. Question & Answer Schemas
# ---------------------------------------------------------------------------

class AnswerInput(BaseModel):
    """Individual answer submitted by the citizen."""
    attribute: str
    value: Any = None
    state: Optional[Union[AnswerState, str]] = None


class SubmitAnswersRequest(BaseModel):
    """Batch of citizen answers/skips submitted for reassessment."""
    answers: list[Union[AnswerInput, dict[str, Any]]] = Field(default_factory=list)


class ReassessmentResult(BaseModel):
    """Result returned after answering questions and recalculating eligibility."""
    session_id: str
    status: str = "reassessed"
    assessments: list[Assessment] = Field(default_factory=list)
    next_questions: list[Question] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6. Document & Action Plan Schemas
# ---------------------------------------------------------------------------

class UpdateDocStatusRequest(BaseModel):
    """Request to update procurement status of a document."""
    status: Union[DocStatus, str]


__all__ = [
    # Health
    "HealthResponse",
    # User Profile & Context
    "UserProfileInput",
    # Session
    "CreateSessionRequest",
    "SessionResponse",
    "FullSessionState",
    "DeleteSessionResponse",
    # Discovery
    "DiscoverOptions",
    "SchemeView",
    "DiscoveryResult",
    # Questions & Answers
    "AnswerInput",
    "SubmitAnswersRequest",
    "ReassessmentResult",
    # Document Action Plan
    "UpdateDocStatusRequest",
    # Re-exported Member 2 models
    "ActionPlan",
    "Answer",
    "AnswerState",
    "Assessment",
    "ChecklistItem",
    "DocStatus",
    "DocumentDependency",
    "DocumentRequirement",
    "GraphEdge",
    "GraphNode",
    "InputType",
    "Operator",
    "Question",
    "RangeOption",
    "Requirement",
    "RequirementResult",
    "RequirementStatus",
    "RequirementVerification",
    "SchemeRecord",
    "SchemeStatus",
    "Sensitivity",
    "VerificationStatus",
]
