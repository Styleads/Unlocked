"""
Discovery pipeline for Project Unlocked.

Orchestrates search, extraction and verification to discover
government benefit schemes relevant to a user's profile.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from google import genai

from discovery_agent.search_provider import search_web
from discovery_agent.scheme_extractor import (
    extract_schemes,
    deduplicate_schemes,
)
from discovery_agent.scheme_schema import SchemeRecord
from discovery_agent.adapter import to_canonical_schemes
from member2.models import SchemeRecord as CanonicalSchemeRecord

logger = logging.getLogger(__name__)


# --------------------------------------------------
# 1. Project configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Real environment variables win over .env (override=False).
load_dotenv(PROJECT_ROOT / ".env", override=False)


def gemini_api_key() -> str | None:
    """GOOGLE_API_KEY (Agent 1's name) or GEMINI_API_KEY (member2's name)."""
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

MODEL = "gemini-flash-lite-latest"


# --------------------------------------------------
# 2. Build search queries from user profile
# --------------------------------------------------

def build_search_queries(
    user_context: dict,
    search_scope: str = "guided"
) -> list[str]:
    """
    Generate search queries based on user profile and scope.

    Args:
        user_context: User profile dict with employment,
            location, and interests.
        search_scope: Either 'guided' (interest-focused),
            'all' (broad discovery), or 'fallback'.

    Returns:
        List of search query strings (max 6).

    Raises:
        ValueError: If search_scope is invalid.
    """
    if search_scope not in ("guided", "all", "fallback"):
        raise ValueError(
            "search_scope must be either 'guided' or 'all'."
        )

    employment = user_context.get("employment", {})
    location = user_context.get("location", {})

    if not isinstance(employment, dict):
        employment = {}

    if not isinstance(location, dict):
        location = {}

    occupation = employment.get("occupation", "citizen")

    # Use only confirmed district/state fields.
    # Do not mistake work_location for a district.
    district = location.get("district")
    state = location.get("state")

    location_parts = [
        str(value).strip()
        for value in (district, state)
        if isinstance(value, str) and value.strip()
    ]

    location_text = (
        ", ".join(location_parts)
        if location_parts
        else "India"
    )

    interests = user_context.get("interests", [])

    if not isinstance(interests, list):
        interests = []

    interests = list(dict.fromkeys(
        interest.strip()
        for interest in interests
        if isinstance(interest, str) and interest.strip()
    ))

    queries = []

    # Guided discovery: focus on the user's interests.
    if search_scope == "guided":

        for interest in interests:
            queries.append(
                f"Government schemes and benefits for "
                f"{occupation} related to {interest} "
                f"in {location_text}"
            )

        if not queries:
            queries.append(
                f"Government welfare and benefit schemes "
                f"for {occupation} in {location_text}"
            )

    # Discover All: interests plus broader benefit searches.
    elif search_scope == "all":

        for interest in interests:
            queries.append(
                f"Government schemes and benefits for "
                f"{occupation} related to {interest} "
                f"in {location_text}"
            )

        # Broader benefit category searches
        broad_categories = [
            "welfare schemes",
            "financial assistance, subsidies and support programmes",
            "health and education schemes",
        ]

        for category in broad_categories:
            queries.append(
                f"Central and state government {category} "
                f"for {occupation} in {location_text}"
            )

    elif search_scope == "fallback":
        return []

    # Remove duplicate queries and limit search volume.
    return list(dict.fromkeys(queries))[:6]


# --------------------------------------------------
# 3. Deduplicate search results
# --------------------------------------------------

def deduplicate_results(results: list[dict]) -> list[dict]:
    """
    Remove duplicate search results by normalised URL.

    Handles None items and missing URLs gracefully.
    """
    unique_results = []
    seen_urls: set[str] = set()

    for result in results:

        # Skip None and non-dict items
        if not isinstance(result, dict):
            continue

        url = result.get("url")

        if not isinstance(url, str) or not url.strip():
            continue

        normalized_url = urlparse(url)._replace(
            query="",
            fragment=""
        ).geturl().rstrip("/").lower()

        if normalized_url in seen_urls:
            continue

        seen_urls.add(normalized_url)
        unique_results.append(result)

    return unique_results


# --------------------------------------------------
# 4. Fallback scheme loading
# --------------------------------------------------

def load_fallback_schemes(
    user_context: dict
) -> list[CanonicalSchemeRecord]:
    """
    Load manually verified fallback schemes when live
    discovery fails or returns no results.

    Returns only schemes that may be relevant to the
    user's profile. Every fallback record is clearly
    labelled as discovery_source='fallback'.
    """
    from discovery_agent.fallback_schemes import (
        get_fallback_schemes,
    )
    from discovery_agent.scheme_extractor import (
        classify_relevance,
    )

    all_fallbacks = get_fallback_schemes()

    # Filter to potentially relevant schemes
    relevant = []
    for scheme in all_fallbacks:
        scheme_dict = scheme.model_dump()
        relevance, reasons = classify_relevance(
            scheme_dict, user_context
        )
        # Include direct matches and related schemes
        updated = scheme.model_copy(update={
            "relevance": relevance,
            "match_reasons": reasons,
        })
        relevant.append(updated)

    return relevant


# --------------------------------------------------
# 4b. Per-scheme detail pass (full eligibility from each scheme's own pages)
# --------------------------------------------------

DETAIL_MAX_SCHEMES = 10     # bounds cost: one search + one model call each
DETAIL_CONCURRENCY = 4
_RELEVANCE_ORDER = {"direct_match": 0, "related": 1, "additional": 2}


async def _enrich_details(client, records: list[dict]) -> None:
    """Deep-fetch the most relevant schemes in place. Best-effort: a failure
    leaves the first-pass record unchanged."""
    from discovery_agent.scheme_details import enrich_scheme

    order = sorted(range(len(records)), key=lambda i: _RELEVANCE_ORDER.get(records[i].get("relevance"), 3))
    gate = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def one(i: int) -> bool:
        async with gate:
            try:
                return await asyncio.to_thread(enrich_scheme, client, MODEL, records[i], search_web)
            except Exception as error:
                logger.warning("Detail pass failed for a scheme: %s", type(error).__name__)
                return False

    done = await asyncio.gather(*(one(i) for i in order[:DETAIL_MAX_SCHEMES]))
    logger.info("Detail pass confirmed rules for %d of %d schemes.", sum(done), len(done))


# --------------------------------------------------
# 5. Main discovery pipeline
# --------------------------------------------------

async def discover_schemes(
    user_context: dict,
    search_scope: str = "guided",
    enable_fallback: bool = False,
    deep_fetch: bool = True,
) -> list[CanonicalSchemeRecord]:
    """
    Discover government benefit schemes for a user.

    Every path returns canonical member2 SchemeRecords (plan.md §5.1),
    converted by discovery_agent.adapter.

    This is the main callable interface for the discovery agent.
    It searches official government sources, extracts scheme
    information, and verifies claims against source evidence.

    Args:
        user_context: User profile dict.
        search_scope: 'guided' for interest-focused discovery,
            'all' for broader search, or 'fallback' for offline data.
        enable_fallback: If True, returns fallback schemes when
            live discovery fails or yields no results.
        deep_fetch: If True, search each scheme's own official pages
            for its full eligibility list and documents.

    Returns:
        List of SchemeRecord objects. May be empty if no
        schemes are found or all searches fail.
    """
    should_fallback = enable_fallback or bool(user_context.get("enable_fallback"))

    if search_scope == "fallback":
        logger.info("Direct fallback scope requested.")
        return load_fallback_schemes(user_context)

    queries = build_search_queries(
        user_context,
        search_scope
    )

    # Queries contain the user's occupation and district: log the count only.
    logger.info("Running %d search queries.", len(queries))

    all_results: list[dict] = []

    # Execute searches concurrently for better performance.
    async def _run_search(query: str) -> list[dict]:
        try:
            results = await asyncio.to_thread(
                search_web,
                query,
                10
            )
            logger.info("Search returned %d results.", len(results))
            return results
        except Exception as error:
            logger.warning("A search query failed: %s", type(error).__name__)
            return []

    search_tasks = [_run_search(q) for q in queries]
    search_results = await asyncio.gather(*search_tasks)

    for results in search_results:
        all_results.extend(results)

    # Deduplicate results.
    unique_results = deduplicate_results(all_results)

    logger.info(
        "Total unique official results: %d",
        len(unique_results)
    )

    if not unique_results:
        if should_fallback:
            logger.info(
                "No official sources found. "
                "Attempting fallback schemes."
            )
            try:
                fallbacks = load_fallback_schemes(user_context)
                if fallbacks:
                    logger.info(
                        "Loaded %d fallback schemes.",
                        len(fallbacks)
                    )
                    return fallbacks
            except Exception as error:
                logger.warning(
                    "Fallback loading failed: %s", error
                )
        else:
            logger.info("No official sources were found.")
        return []

    # Check Gemini API configuration.
    api_key = gemini_api_key()

    if not api_key:
        if should_fallback:
            logger.warning("No Gemini API key set; using fallback schemes.")
            return load_fallback_schemes(user_context)
        raise ValueError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is not set."
        )

    client = genai.Client(api_key=api_key)

    try:
        schemes = await asyncio.to_thread(
            extract_schemes,
            client,
            MODEL,
            unique_results,
            user_context
        )

        logger.info(
            "Extracted %d scheme records.", len(schemes)
        )

        # If live extraction returned nothing and fallback is enabled, try fallback
        if not schemes and should_fallback:
            logger.info(
                "Live extraction returned no schemes. "
                "Trying fallback."
            )
            try:
                fallbacks = load_fallback_schemes(
                    user_context
                )
                if fallbacks:
                    logger.info(
                        "Loaded %d fallback schemes.",
                        len(fallbacks)
                    )
                    return fallbacks
            except Exception as error:
                logger.warning(
                    "Fallback loading failed: %s", error
                )

        records = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in schemes]
        if deep_fetch and records:
            await _enrich_details(client, records)

        # Live records use Agent 1's schema; convert so every path returns
        # the same canonical type (fallbacks are already converted).
        return to_canonical_schemes(records)

    finally:
        client.close()


# --------------------------------------------------
# 6. Direct test
# --------------------------------------------------

if __name__ == "__main__":

    import json

    logging.basicConfig(level=logging.INFO)

    async def main():

        from discovery_agent.profile_manager import load_profile

        profile = load_profile()

        schemes = await discover_schemes(
            profile,
            search_scope="guided"
        )

        print("\nDISCOVERED SCHEMES\n")

        for scheme in schemes:
            print(
                json.dumps(
                    scheme.model_dump(),
                    indent=4,
                    ensure_ascii=False
                )
            )

    asyncio.run(main())
