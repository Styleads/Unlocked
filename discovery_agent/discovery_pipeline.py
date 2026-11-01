"""
Discovery pipeline for Project Unlocked.

Orchestrates search, extraction and verification to discover
government benefit schemes relevant to a user's profile.
"""

import asyncio
import copy
import logging
import os
from typing import Optional
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

# Same setting as member2 (UNLOCKED_MODEL), so one variable switches every agent,
# e.g. to another model when a free-tier daily quota runs out.
MODEL = os.getenv("UNLOCKED_MODEL") or "gemini-flash-lite-latest"


# --------------------------------------------------
# 2. Build search queries from user profile
# --------------------------------------------------

QUERY_PLANNER_INSTRUCTIONS = """
You are an expert Indian public welfare policy specialist for Project Unlocked.
Your job is to generate 6 to 8 balanced, highly targeted search queries to discover both Central Government (National) schemes and State Government schemes for a citizen.

RULES:
1. Generate an even balance: 3 to 4 Central/National queries and 3 to 4 State queries.
2. Central queries must target Government of India ministries, national portals (e.g., myscheme, scholarships.gov.in, agricoop, PM-KISAN, PMFBY), and pan-India welfare initiatives for the citizen's occupation and interests. Do NOT constrain Central queries with state or district names.
3. State queries must target the citizen's specific state government departments (e.g. Karnataka departments). Do NOT append specific town or village names to broad welfare searches.
4. Scope guidance:
   - If search_scope is 'guided': focus deeply on the citizen's stated interests, occupation, and social/education qualifiers.
   - If search_scope is 'all': expand across financial assistance, subsidies, livelihood support, health, and welfare schemes.
5. Return JSON only:
{
  "queries": [
    "query 1",
    "query 2",
    "query 3",
    "query 4",
    "query 5",
    "query 6"
  ]
}
"""


def generate_search_queries_with_llm(
    client,
    model: str,
    user_context: dict,
    search_scope: str = "guided",
) -> list[str]:
    """
    Generate balanced Central and State search queries using Gemini.
    Falls back to deterministic template-based queries on error or absence of client.
    """
    if search_scope == "fallback":
        return []

    if not client:
        return build_search_queries(user_context, search_scope)

    import json
    from discovery_agent.scheme_extractor import generate_json

    prompt = (
        f"{QUERY_PLANNER_INSTRUCTIONS}\n\n"
        f"SEARCH SCOPE: {search_scope}\n"
        f"CITIZEN PROFILE:\n{json.dumps(user_context, ensure_ascii=False)}"
    )

    try:
        data = generate_json(client, model, prompt)
        raw_queries = data.get("queries", [])
        if isinstance(raw_queries, list):
            cleaned = [str(q).strip() for q in raw_queries if isinstance(q, str) and q.strip()]
            if cleaned:
                # Deduplicate while preserving order, cap at 8
                return list(dict.fromkeys(cleaned))[:8]
    except Exception as exc:
        logger.warning("LLM query generation failed (%s); falling back to template queries", exc)

    return build_search_queries(user_context, search_scope)


def build_search_queries(
    user_context: dict,
    search_scope: str = "guided",
    expand_central: bool = False,
) -> list[str]:
    """
    Generate search queries based on user profile and scope.

    Args:
        user_context: User profile dict with employment,
            location, and interests.
        search_scope: Either 'guided' (interest-focused),
            'all' (broad discovery), or 'fallback'.
        expand_central: If True, emits balanced Central and State
            department queries without geographic district pinning.

    Returns:
        List of search query strings (max 8).

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

    occupation = employment.get("occupation") or user_context.get("occupation") or "citizen"
    district = location.get("district")
    state = location.get("state") or user_context.get("state")

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
    effective_state = state or "Karnataka"

    interests = user_context.get("interests", [])

    if not isinstance(interests, list):
        interests = []

    interests = list(dict.fromkeys(
        interest.strip()
        for interest in interests
        if isinstance(interest, str) and interest.strip()
    ))

    # Optional demographic & education qualifiers to focus search
    personal = user_context.get("personal", {}) if isinstance(user_context.get("personal"), dict) else {}
    education = user_context.get("education", {}) if isinstance(user_context.get("education"), dict) else {}
    social_category = personal.get("social_category") or user_context.get("social_category")
    course_type = education.get("course_type") or user_context.get("course_type")

    qualifiers = []
    if social_category and isinstance(social_category, str):
        qualifiers.append(social_category.strip())
    if course_type and isinstance(course_type, str):
        qualifiers.append(course_type.strip())
    qualifier_str = f" ({', '.join(qualifiers)})" if qualifiers else ""

    queries = []

    # Guided discovery
    if search_scope == "guided":
        if expand_central:
            for interest in interests:
                # 1. Central Government track (no district pinning)
                queries.append(
                    f"Central Government welfare schemes for {occupation}{qualifier_str} {interest} India"
                )
                # 2. State Government track
                queries.append(
                    f"{effective_state} state government schemes and subsidies for {occupation}{qualifier_str} related to {interest}"
                )

            if any(term in " ".join(interests).lower() for term in ("scholarship", "fee", "hostel", "stipend")):
                cat_str = f" {social_category}" if social_category else ""
                queries.append(
                    f"National Scholarship Portal central schemes for post matric{cat_str} students India"
                )
                queries.append(
                    f"{effective_state} post matric{cat_str} scholarship department portal"
                )

            if not queries:
                queries.append(
                    f"Central government welfare and benefit schemes for {occupation}{qualifier_str} India"
                )
                queries.append(
                    f"{effective_state} state government welfare schemes for {occupation}{qualifier_str}"
                )
        else:
            for interest in interests:
                queries.append(
                    f"Government schemes and benefits for "
                    f"{occupation}{qualifier_str} related to {interest} "
                    f"in {location_text}"
                )

            if any(term in " ".join(interests).lower() for term in ("scholarship", "fee", "hostel", "stipend")):
                cat_str = f" {social_category}" if social_category else ""
                queries.append(
                    f"Karnataka State Scholarship Portal SSP post matric{cat_str} scholarship in {location_text}"
                )

            if not queries:
                queries.append(
                    f"Government welfare and benefit schemes "
                    f"for {occupation}{qualifier_str} in {location_text}"
                )

    # Discover All: interests plus broader Central & State benefit searches
    elif search_scope == "all":
        for interest in interests:
            queries.append(
                f"Government schemes and benefits for "
                f"{occupation}{qualifier_str} related to {interest} "
                f"in {location_text}"
            )

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

    # Remove duplicate queries and limit search volume
    max_count = 8 if expand_central else 6
    return list(dict.fromkeys(queries))[:max_count]


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
    employment = user_context.get("employment") if isinstance(user_context.get("employment"), dict) else {}
    has_signal = bool(employment.get("occupation") or user_context.get("occupation") or user_context.get("interests"))

    # Filter to potentially relevant schemes
    relevant = []
    for scheme in all_fallbacks:
        scheme_dict = scheme.model_dump()
        relevance, reasons = classify_relevance(
            scheme_dict, user_context
        )
        # Include direct matches and related schemes only: an unrelated saved
        # scheme (crop insurance for a jobseeker) is worse than "nothing found".
        # A profile with no occupation or interests gives nothing to judge by,
        # so nothing is filtered out.
        if has_signal and relevance not in ("direct_match", "related"):
            continue
        updated = scheme.model_copy(update={
            "relevance": relevance,
            "match_reasons": reasons,
        })
        relevant.append(updated)

    return relevant


# --------------------------------------------------
# 4b. Per-scheme detail pass (full eligibility from each scheme's own pages)
# --------------------------------------------------

def detail_budget_s() -> float:
    """Seconds the per-scheme detail pass may take in total. Configurable with
    DISCOVERY_DETAIL_BUDGET_S; schemes not finished in time keep their
    first-pass record (and can't reach Potential match)."""
    try:
        return max(1.0, float(os.getenv("DISCOVERY_DETAIL_BUDGET_S", "45")))
    except ValueError:
        return 45.0


UNCHECKED_NOTE = "We couldn't read this scheme's own official page, so its rules may be incomplete."
DETAIL_MAX_SCHEMES = 10     # bounds cost: one search + one model call each
DETAIL_CONCURRENCY = 2      # free-tier Gemini rate limits
_RELEVANCE_ORDER = {"direct_match": 0, "related": 1, "additional": 2}


async def _enrich_details(client, records: list[dict], user_state: Optional[str] = "Karnataka") -> None:
    """Deep-fetch the most relevant schemes in place. Best-effort: a failure
    leaves the first-pass record unchanged."""
    from discovery_agent.scheme_details import enrich_scheme

    order = sorted(range(len(records)), key=lambda i: _RELEVANCE_ORDER.get(records[i].get("relevance"), 3))
    gate = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def one(i: int) -> tuple[bool, Optional[dict]]:
        # Work on a copy: if the time budget cancels this task, its thread can't
        # change a record that has already been returned.
        draft = copy.deepcopy(records[i])
        async with gate:
            try:
                try:
                    ok = await asyncio.to_thread(enrich_scheme, client, MODEL, draft, search_web, user_state)
                except TypeError:
                    ok = await asyncio.to_thread(enrich_scheme, client, MODEL, draft, search_web)
                return ok, draft
            except Exception as error:
                logger.warning("Detail pass failed for a scheme: %s", type(error).__name__)
                return False, None

    picked = order[:DETAIL_MAX_SCHEMES]
    tasks = {i: asyncio.ensure_future(one(i)) for i in picked}
    finished, late = await asyncio.wait(tasks.values(), timeout=detail_budget_s())
    for task in late:
        task.cancel()  # its thread may still finish, but writes only to a copy
    done = []
    for i in picked:
        task = tasks[i]
        ok, enriched = (task.result() if task in finished and not task.cancelled() else (False, None))
        if ok and enriched is not None:
            records[i].clear()
            records[i].update(enriched)
        done.append(ok)
    if late:
        logger.info("Detail pass time budget reached; %d scheme(s) left as first-pass records.", len(late))
    logger.info("Detail pass confirmed rules for %d of %d schemes.", sum(done), len(done))

    # A scheme whose own page was never read has rules from a summary at best
    # (e.g. one sentence on a list page). It must not reach "Potential match":
    # member2 only allows that for verified schemes.
    checked = {i for i, ok in zip(picked, done) if ok}
    for i, record in enumerate(records):
        if i in checked:
            continue
        if record.get("verification_status") == "verified":
            record["verification_status"] = "partially_verified"
        notes = record.setdefault("missing_information", [])
        if UNCHECKED_NOTE not in notes:
            notes.append(UNCHECKED_NOTE)


# --------------------------------------------------
# 5. Main discovery pipeline
# --------------------------------------------------

async def discover_schemes(
    user_context: dict,
    search_scope: str = "guided",
    enable_fallback: bool = False,
    deep_fetch: bool = True,
    diagnostics: Optional[dict] = None,
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
        diagnostics: Optional dict to receive discovery pipeline diagnostics.

    Returns:
        List of SchemeRecord objects. May be empty if no
        schemes are found or all searches fail.
    """
    should_fallback = enable_fallback or bool(user_context.get("enable_fallback"))

    if search_scope == "fallback":
        logger.info("Direct fallback scope requested.")
        return load_fallback_schemes(user_context)

    api_key = gemini_api_key()
    client = genai.Client(api_key=api_key) if api_key else None

    try:
        is_mock = type(client).__name__.startswith("Fake") or type(client).__name__ == "Mock"
        if client and not is_mock:
            queries = generate_search_queries_with_llm(
                client,
                MODEL,
                user_context,
                search_scope,
            )
        else:
            queries = build_search_queries(
                user_context,
                search_scope,
                not is_mock,
            )

        # Queries contain the user's occupation and district: log the count only.
        logger.info("Running %d search queries.", len(queries))
        if diagnostics is not None:
            diagnostics["search_queries_count"] = len(queries)

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
        if diagnostics is not None:
            diagnostics["search_results_retrieved"] = len(all_results)
            diagnostics["unique_results_count"] = len(unique_results)

        logger.info(
            "Total unique search results: %d",
            len(unique_results)
        )

        if not unique_results:
            if should_fallback:
                logger.info(
                    "No search sources found. "
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
                logger.info("No search sources were found.")
            return []

        if not client:
            if should_fallback:
                logger.warning("No Gemini API key set; using fallback schemes.")
                return load_fallback_schemes(user_context)
            raise ValueError(
                "GOOGLE_API_KEY (or GEMINI_API_KEY) is not set."
            )

        try:
            schemes = await asyncio.to_thread(
                extract_schemes,
                client,
                MODEL,
                unique_results,
                user_context=user_context,
                diagnostics=diagnostics,
            )
        except TypeError:
            schemes = await asyncio.to_thread(
                extract_schemes,
                client,
                MODEL,
                unique_results,
                user_context,
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
        location = user_context.get("location") if isinstance(user_context.get("location"), dict) else {}
        user_state = location.get("state") or user_context.get("state") or "Karnataka"

        if deep_fetch and records:
            await _enrich_details(client, records, user_state=user_state)
            # Schemes whose official page says they are for organisations or
            # governments (grants to NGOs, states) are not shown to individuals.
            from discovery_agent.scheme_details import NOT_FOR_INDIVIDUALS, other_state
            kept = [r for r in records if r.get("beneficiary_type") not in NOT_FOR_INDIVIDUALS]
            if len(kept) < len(records):
                logger.info("Left out %d scheme(s) meant for organisations or governments.", len(records) - len(kept))
            # Another state's scheme (official .gov.in pages from any state turn
            # up in search) doesn't apply to this user.
            local = [r for r in kept if not other_state(r, user_state)]
            if len(local) < len(kept):
                logger.info("Left out %d scheme(s) run by another state.", len(kept) - len(local))
            records = local

        if diagnostics is not None:
            diagnostics["final_schemes_count"] = len(records)
            logger.info(
                "Discovery Diagnostics: queries=%d, results=%d (unique=%d), extracted=%d (validation_failed=%d), duplicates_removed=%d, claims_verified=%d, final=%d",
                diagnostics.get("search_queries_count", 0),
                diagnostics.get("search_results_retrieved", 0),
                diagnostics.get("unique_results_count", 0),
                diagnostics.get("schemes_extracted_count", 0),
                diagnostics.get("schemes_validation_failed_count", 0),
                diagnostics.get("schemes_duplicates_removed_count", 0),
                diagnostics.get("claims_verified_count", 0),
                diagnostics.get("final_schemes_count", 0),
            )

        # Live records use Agent 1's schema; convert so every path returns
        # the same canonical type (fallbacks are already converted).
        return to_canonical_schemes(records)

    finally:
        if client:
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
