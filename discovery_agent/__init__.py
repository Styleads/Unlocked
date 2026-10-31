"""
Project Unlocked — Discovery Agent Package.

Autonomous discovery engine for Indian and Karnataka government benefits.
"""

from discovery_agent.adapter import (
    to_canonical_scheme,
    to_canonical_schemes,
)
from discovery_agent.discovery_pipeline import (
    build_search_queries,
    deduplicate_results,
    discover_schemes,
    load_fallback_schemes,
)
from discovery_agent.fallback_schemes import get_fallback_schemes
from discovery_agent.kannada_translator import translate_schemes_to_kannada
from discovery_agent.profile_extractor import extract_profile_update
from discovery_agent.profile_manager import (
    load_profile,
    merge_profiles,
    save_profile,
    update_profile,
)
from discovery_agent.scheme_extractor import (
    classify_relevance,
    deduplicate_schemes,
    extract_schemes,
    verify_claims,
)
from discovery_agent.scheme_schema import (
    ClaimCategory,
    GovernmentLevel,
    RelevanceLevel,
    SchemeClaim,
    SchemeCriterion,
    SchemeRecord,
    SourceEvidence,
    VerificationStatus,
)
from discovery_agent.search_provider import (
    classify_source,
    is_official_government_url,
    search_web,
)

__all__ = [
    # Main discovery entrypoint
    "discover_schemes",
    "to_canonical_scheme",
    "to_canonical_schemes",
    "build_search_queries",
    "deduplicate_results",
    "load_fallback_schemes",
    "get_fallback_schemes",
    # Profile management
    "load_profile",
    "save_profile",
    "update_profile",
    "merge_profiles",
    "extract_profile_update",
    # Scheme extraction and verification
    "extract_schemes",
    "verify_claims",
    "classify_relevance",
    "deduplicate_schemes",
    "translate_schemes_to_kannada",
    # Search provider
    "search_web",
    "is_official_government_url",
    "classify_source",
    # Data models
    "SchemeRecord",
    "SchemeCriterion",
    "SchemeClaim",
    "SourceEvidence",
    "VerificationStatus",
    "ClaimCategory",
    "RelevanceLevel",
    "GovernmentLevel",
]

