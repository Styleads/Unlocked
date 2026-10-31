"""
Pydantic schemas for the Project Unlocked FastAPI application.

Defines the request and response models for public API endpoints.
"""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from discovery_agent.scheme_schema import SchemeRecord


# --------------------------------------------------
# Request Models
# --------------------------------------------------

class UserProfileInput(BaseModel):
    """
    User demographic and circumstantial profile.

    Supports both flat fields (e.g. occupation, state, district)
    and nested sections (e.g. employment, location, agriculture)
    to flexibly accommodate diverse caller structures.
    """
    model_config = ConfigDict(extra="allow")

    # Common flat attributes
    occupation: str | None = None
    state: str | None = "Karnataka"
    district: str | None = None
    annual_income: float | int | None = None
    interests: list[str] = Field(default_factory=list)

    # Optional nested sections (aligned with profile_manager format)
    personal: dict[str, Any] | None = None
    location: dict[str, Any] | None = None
    education: dict[str, Any] | None = None
    employment: dict[str, Any] | None = None
    agriculture: dict[str, Any] | None = None
    business: dict[str, Any] | None = None
    household: dict[str, Any] | None = None
    other_details: dict[str, Any] | None = None

    def to_user_context(self) -> dict[str, Any]:
        """
        Normalize input into the user_context dictionary structure
        expected by discover_schemes().
        """
        data = self.model_dump()
        extra_fields = {
            k: v for k, v in data.items()
            if k not in (
                "occupation", "state", "district", "annual_income",
                "interests", "personal", "location", "education",
                "employment", "agriculture", "business", "household",
                "other_details"
            )
        }

        # Initialize nested sections if not present
        employment = data.get("employment") or {}
        if not isinstance(employment, dict):
            employment = {}
        if self.occupation and not employment.get("occupation"):
            employment["occupation"] = self.occupation

        location = data.get("location") or {}
        if not isinstance(location, dict):
            location = {}
        if self.state and not location.get("state"):
            location["state"] = self.state
        if self.district and not location.get("district"):
            location["district"] = self.district

        household = data.get("household") or {}
        if not isinstance(household, dict):
            household = {}
        if self.annual_income is not None and not household.get("annual_income"):
            household["annual_income"] = self.annual_income

        interests = self.interests
        if isinstance(interests, str):
            interests = [interests]

        context: dict[str, Any] = {
            "employment": employment,
            "location": location,
            "household": household,
            "interests": interests,
            "personal": data.get("personal") or {},
            "education": data.get("education") or {},
            "agriculture": data.get("agriculture") or {},
            "business": data.get("business") or {},
            "other_details": data.get("other_details") or {},
            **extra_fields,
        }

        return context


class DiscoverRequest(BaseModel):
    """Request payload for scheme discovery."""
    user_profile: UserProfileInput = Field(default_factory=UserProfileInput)
    search_scope: Literal["guided", "all", "fallback"] = "guided"
    preferred_language: Literal["en", "kn"] = "en"


# --------------------------------------------------
# Response Models
# --------------------------------------------------

class DiscoverResponse(BaseModel):
    """Structured response returned by the discovery endpoint."""
    success: bool
    preferred_language: str
    actual_response_language: Literal["kn", "en"] = "en"
    translation_status: Literal["not_requested", "complete", "partial", "failed"] = "not_requested"
    total_schemes: int
    schemes: list[SchemeRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health and operational status of the service."""
    status: str
    application: str
    version: str
    operational: bool
    services: dict[str, bool] = Field(default_factory=dict)

