"""
Search provider for the Discovery Agent.

Wraps the Tavily API with official government domain filtering,
retry logic with exponential backoff, and robust error handling.
"""

import logging
import os
import random
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env", override=False)


# Official Indian government domain suffixes.
# The is_official_government_url function generalises
# beyond this list, but Tavily include_domains needs
# explicit entries.
OFFICIAL_DOMAINS = [
    "gov.in",
    "nic.in",
    "myscheme.gov.in",
    "pmkisan.gov.in",
    "pmfby.gov.in",
    "pmksy.mowr.gov.in",
    "samrakshane.karnataka.gov.in",
    "pib.gov.in",
    "india.gov.in",
    "karnataka.gov.in",
]

# Search snippets (~1,500 chars) rarely contain the eligibility rules or the
# document list, so the extractor had nothing to quote. We also request the
# page text and keep only the paragraphs that talk about rules and documents.
# They are copied verbatim, so the extractor's quote check still works.
RULE_KEYWORDS = (
    "eligib", "criteria", "criterion", "who can apply", "applicant", "must",
    "should be", "income", "age", "years", "domicile", "resident", "category",
    "document", "certificate", "required", "proof", "marks", "percentage",
    "hectare", "land", "student", "course", "family",
)
MAX_PASSAGE_CHARS = 4000
MIN_PARAGRAPH_CHARS = 30


def relevant_passages(raw_content, limit: int = MAX_PASSAGE_CHARS) -> str:
    """Paragraphs of the page that mention rules or documents, verbatim, in
    page order, up to `limit` characters."""
    if not isinstance(raw_content, str) or not raw_content.strip():
        return ""
    out, size, seen = [], 0, set()
    for para in raw_content.replace("\r", "").split("\n"):
        para = " ".join(para.split())
        key = para.casefold()
        if len(para) < MIN_PARAGRAPH_CHARS or key in seen:
            continue
        if not any(k in key for k in RULE_KEYWORDS):
            continue
        if size + len(para) > limit:
            break
        seen.add(key)
        out.append(para)
        size += len(para) + 1
    return "\n".join(out)


def is_official_government_url(url: str) -> bool:
    """
    Check whether a URL belongs to an Indian government domain.

    Accepts any hostname ending in .gov.in or .nic.in, or
    exactly equal to gov.in or nic.in.
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("https", "http"):
            return False

        hostname = (parsed.hostname or "").lower().rstrip(".")

        return (
            hostname in ("gov.in", "nic.in")
            or hostname.endswith(".gov.in")
            or hostname.endswith(".nic.in")
        )

    except ValueError:
        return False


def _get_tavily_client():
    """
    Create and return a TavilyClient.

    Raises ValueError if TAVILY_API_KEY is not configured.
    Deferred from module level so imports don't fail in tests.
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        raise ImportError(
            "tavily-python is required. "
            "Install it with: pip install tavily-python"
        )

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY missing from .env")

    return TavilyClient(api_key=api_key)


# --------------------------------------------------
# Retry configuration
# --------------------------------------------------

MAX_RETRIES = 3
BASE_DELAY = 1.0    # seconds
MAX_DELAY = 10.0    # seconds


def _is_retryable_error(error: Exception) -> bool:
    """Determine whether an error is worth retrying."""
    error_str = str(error).lower()

    # Rate limits
    if "429" in error_str or "rate limit" in error_str:
        return True

    # Server errors
    if any(code in error_str for code in ("500", "502", "503", "504")):
        return True

    # Timeouts
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    if "timeout" in error_str or "timed out" in error_str:
        return True

    # Connection errors
    if "connection" in error_str:
        return True

    return False


# --------------------------------------------------
# Official-only search with retry
# --------------------------------------------------

def search_web(query: str, max_results: int = 10, include_raw: bool = False) -> list[dict]:
    """
    Search the web for official Indian government sources.

    Args:
        query: The search query string.
        max_results: Maximum number of results to request.

    Returns:
        A list of dicts, each containing title, url, content,
        score, and is_official fields.

    Raises:
        ValueError: If query is empty.
        Exception: If all retries are exhausted.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query cannot be empty.")

    client = _get_tavily_client()

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=max_results,
                include_domains=OFFICIAL_DOMAINS,
                include_domains_mode="restrict",
                include_answer=False,
                include_raw_content=True,
            )

            results = []

            raw_results = response.get("results", [])

            if not isinstance(raw_results, list):
                logger.warning(
                    "Search returned non-list results: %s",
                    type(raw_results).__name__
                )
                return []

            for item in raw_results:
                if not isinstance(item, dict):
                    continue

                url = item.get("url", "")

                if not isinstance(url, str):
                    continue

                # Second layer of protection.
                if not is_official_government_url(url):
                    continue

                title = item.get("title", "")
                content = item.get("content", "")

                # Ensure types are valid
                if not isinstance(title, str):
                    title = ""
                if not isinstance(content, str):
                    content = ""

                passages = relevant_passages(item.get("raw_content"))
                if passages and passages not in content:
                    content = f"{content}\n{passages}".strip()

                result = {
                    "title": title,
                    "url": url,
                    "content": content,
                    "score": item.get("score", 0),
                    "is_official": True,
                }
                if include_raw:
                    # Full page text, for per-scheme extraction (scheme_details.py).
                    raw = item.get("raw_content")
                    result["raw_content"] = raw if isinstance(raw, str) else ""
                results.append(result)

            return results

        except Exception as error:
            last_error = error

            if not _is_retryable_error(error):
                logger.error(
                    "Search failed with non-retryable error: %s",
                    error
                )
                raise

            delay = min(
                BASE_DELAY * (2 ** attempt)
                + random.uniform(0, 0.5),
                MAX_DELAY
            )

            logger.warning(
                "Search attempt %d/%d failed: %s. "
                "Retrying in %.1fs...",
                attempt + 1,
                MAX_RETRIES,
                error,
                delay
            )

            time.sleep(delay)

    # All retries exhausted
    raise last_error  # type: ignore[misc]


# --------------------------------------------------
# Classify source authority
# --------------------------------------------------

def classify_source(url: str) -> str:
    """
    Classify a source URL as official or secondary.

    Returns:
        'official' for government domains,
        'secondary' for everything else.
    """
    if is_official_government_url(url):
        return "official"
    return "secondary"


# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    query = (
        "Government crop insurance schemes "
        "for farmers in Karnataka"
    )

    print("\nUNLOCKED — OFFICIAL SOURCE SEARCH")
    print("=" * 50)

    try:
        results = search_web(query)

        for index, result in enumerate(results, start=1):
            print(f"\nRESULT {index}")
            print("Title:", result["title"])
            print("URL:", result["url"])
            print("Official:", result["is_official"])
            print("Content:", result["content"][:300])

        print("\nTotal accepted results:", len(results))

    except Exception as error:
        print("\nSearch failed:", error)
