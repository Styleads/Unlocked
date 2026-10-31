"""
Scheme extraction and verification pipeline.

Takes search results and uses Gemini to extract structured
government scheme records with evidence-based verification.
"""

from datetime import datetime, timezone
import json
import logging
import re
import time

from pydantic import ValidationError

from discovery_agent.scheme_schema import SchemeRecord

logger = logging.getLogger(__name__)


# ============================================================
# 1. EXTRACTION PROMPT
# ============================================================

EXTRACTION_INSTRUCTIONS = """
You are the scheme extraction component of Unlocked.

Extract government benefit schemes from the supplied search results.

RULES:
1. Use only information present in the supplied search results.
2. Never invent benefits, eligibility criteria, documents or procedures.
3. Never invent URLs.
4. Do not decide verification statuses.
5. Do not claim that the user is eligible.
6. Keep relevant schemes even when information is incomplete.
7. A scheme mention is not proof of its eligibility rules.
8. Use only exact URLs supplied in the search results.
9. Extract ALL distinct schemes mentioned in the results.
10. Do not limit output to a single scheme.
11. For every eligibility criterion and every required document, copy into
    "evidence" the exact sentence from that source_url's content that states it,
    character for character. Do not paraphrase. Use "" if no sentence states it.

Extract important factual claims separately.

Claim categories:
- description
- benefit
- eligibility
- document
- application_process

Each claim must contain:
- category
- claim
- source_url
- supporting_excerpt
- verification_status
- verification_reason

Set every claim's verification_status to "unverified".
Do not mark anything verified during extraction.

Use these relevance labels:
- direct_match
- related
- additional

Use this verification label:
- unverified

Government level labels:
- central (national/central government schemes)
- state (state government schemes)
- local (district/city/panchayat level schemes)
- unknown (when not determinable)

Return JSON only:

{
  "schemes": [
    {
      "id": "unique_identifier",
      "name": "Scheme name",
      "description": "",
      "target_groups": [],
      "benefits": [],
      "eligibility_criteria": [
        {
          "description": "",
          "related_attribute": null,
          "source_url": null,
          "evidence": "",
          "verification_status": "unverified"
        }
      ],
      "required_documents": [],
      "documents": [
        {
          "name": "",
          "source_url": null,
          "evidence": ""
        }
      ],
      "application_process": null,
      "application_url": null,
      "official_url": null,
      "deadline": null,
      "deadline_source_url": null,
      "government_level": "unknown",
      "department": null,
      "source_evidence": [
        {
          "title": "",
          "url": "",
          "excerpt": "",
          "is_official": true
        }
      ],
      "claims": [
        {
          "category": "benefit",
          "claim": "",
          "source_url": null,
          "supporting_excerpt": "",
          "verification_status": "unverified",
          "verification_reason": ""
        }
      ],
      "verification_status": "unverified",
      "discovery_source": "live_search",
      "relevance": "additional",
      "match_reasons": [],
      "missing_information": []
    }
  ]
}

Do not include markdown or explanations outside JSON.
"""


# ============================================================
# 2. VERIFICATION PROMPT
# ============================================================

VERIFICATION_INSTRUCTIONS = """
You are the evidence verification component of Unlocked.

Check whether each factual claim is explicitly supported
by the supplied official source excerpts.

RULES:
1. Use only the supplied source content.
2. A government domain alone is not evidence.
3. An empty excerpt is not evidence.
4. Do not use outside knowledge.
5. Do not invent source URLs or quotations.
6. Be conservative. If uncertain, return supported=false.
7. Return the exact URL of the supporting source.
8. Provide a short, exact quotation copied from that source.
9. The quotation must directly support the claim.
10. Never verify a claim based only on a scheme name.

Return JSON only:

{
  "claim_checks": [
    {
      "claim_index": 0,
      "supported": false,
      "source_url": null,
      "supporting_excerpt": "",
      "reason": "Explanation"
    }
  ]
}
"""


# ============================================================
# 3. GEMINI JSON GENERATION
# ============================================================

def generate_json(
    client,
    model: str,
    prompt: str,
    max_retries: int = 3
) -> dict:
    """
    Ask Gemini to generate a JSON response.

    Retries transient failures *and* bad output: model sampling varies, so
    invalid or empty JSON on one attempt often succeeds on the next.
    Raises ValueError (bad output) or the last transport error once all
    attempts are used.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json"
                }
            )

            data = parse_json_object(response.text)
            return data

        except Exception as error:
            last_error = error
            logger.warning(
                "Gemini attempt %d/%d failed: %s",
                attempt + 1, max_retries, type(error).__name__
            )
            # A daily quota won't clear for hours: fail now instead of waiting.
            if is_daily_quota(error):
                break
            # Per-minute rate limits (HTTP 429 / RESOURCE_EXHAUSTED) clear in
            # seconds; retrying instantly just fails again.
            if attempt < max_retries - 1 and is_rate_limited(error):
                _sleep(RATE_LIMIT_BACKOFF_S * (2 ** attempt))

    raise last_error  # type: ignore[misc]


RATE_LIMIT_BACKOFF_S = 2.0
_sleep = time.sleep  # replaced in tests


def is_daily_quota(error: Exception) -> bool:
    """Gemini's per-day free-tier quota (its quota id names the period)."""
    text = str(error).lower().replace(" ", "")
    return "perday" in text


def is_rate_limited(error: Exception) -> bool:
    text = f"{getattr(error, 'code', '')} {error}".lower()
    return "429" in text or "resource_exhausted" in text or "rate limit" in text or "quota" in text


def parse_json_object(text) -> dict:
    """Parse a JSON object, tolerating ```json fences and stray text around it."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned an empty response.")
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        try:
            data = json.loads(raw[start:end + 1]) if 0 <= start < end else None
        except json.JSONDecodeError:
            data = None
        if data is None:
            raise ValueError("Gemini returned invalid JSON.") from None
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object.")
    return data


# ============================================================
# 4. TEXT NORMALIZATION
# ============================================================

def normalize_quote(value):
    """Normalize text for quotation comparison."""
    if not isinstance(value, str):
        return ""

    val = value.replace("\u201c", '"').replace("\u201d", '"')
    val = val.replace("\u2018", "'").replace("\u2019", "'")
    val = val.replace("\xa0", " ").replace("—", "-").replace("–", "-")
    return " ".join(val.split()).casefold()


def normalize_text(value):
    """Normalize text for keyword matching."""
    if not isinstance(value, str):
        return ""

    return re.sub(
        r"[^a-z0-9\s]",
        " ",
        value.lower()
    ).strip()


# A quote shorter than this ("Yes", "Farmers") proves nothing about a rule.
MIN_QUOTE_CHARS = 15


def _find_official_source(source_url, official_sources):
    """Find source entry handling trailing slashes and case differences."""
    if not isinstance(source_url, str) or not official_sources:
        return None
    if source_url in official_sources:
        return official_sources[source_url]
    s_norm = source_url.rstrip("/").lower()
    for u, data in official_sources.items():
        if isinstance(u, str) and u.rstrip("/").lower() == s_norm:
            return data
    return None


def verbatim_evidence(evidence, source_url, official_sources):
    """Return the model's quote only if it appears word for word in the full
    content of the page it cites; otherwise None. Deterministic: the model
    proposes the quote, Python decides whether it is real."""
    if not isinstance(evidence, str) or len(evidence.strip()) < MIN_QUOTE_CHARS:
        return None
    source = _find_official_source(source_url, official_sources)
    if not source:
        return None
    if normalize_quote(evidence) not in normalize_quote(source.get("content", "")):
        return None
    return " ".join(evidence.split())


# ============================================================
# 5. CLAIM VERIFICATION
# ============================================================

def verify_claims(client, model, claims, evidence):
    """
    Verify claims against supplied official source excerpts.

    A claim is accepted only when:
    1. Gemini says it is supported.
    2. The source URL belongs to accepted evidence.
    3. The supporting quotation exists in that source.

    Returns:
        Dict mapping claim index to verification result.
        Empty dict if verification is unavailable or
        no claims are verified.
    """
    if not claims or not evidence:
        return {}

    evidence_by_url = {
        item["url"]: item
        for item in evidence
        if isinstance(item, dict)
        and isinstance(item.get("url"), str)
        and item.get("url")
    }

    if not evidence_by_url:
        return {}

    verification_data = {
        "claims": [
            {
                "claim_index": index,
                "category": claim.get("category"),
                "claim": claim.get("claim"),
                "proposed_source_url": claim.get("source_url")
            }
            for index, claim in enumerate(claims)
        ],
        "official_sources": [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "excerpt": item.get("excerpt", "")
            }
            for item in evidence_by_url.values()
        ]
    }

    prompt = (
        VERIFICATION_INSTRUCTIONS
        + "\n\nDATA TO VERIFY:\n"
        + json.dumps(
            verification_data,
            ensure_ascii=False
        )
    )

    try:
        result = generate_json(client, model, prompt)
    except Exception as error:
        logger.warning(
            "Claim verification unavailable: %s", error
        )
        return {}

    checks = result.get("claim_checks", [])

    if not isinstance(checks, list):
        return {}

    verified_results = {}

    for check in checks:

        if not isinstance(check, dict):
            continue

        index = check.get("claim_index")

        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < len(claims)
        ):
            continue

        if check.get("supported") is not True:
            continue

        source_url = check.get("source_url")
        quotation = check.get("supporting_excerpt")

        if not isinstance(source_url, str):
            continue

        if not isinstance(quotation, str) or not quotation.strip():
            continue

        source = evidence_by_url.get(source_url)

        if source is None:
            continue

        proposed_url = claims[index].get("source_url")

        if proposed_url and proposed_url != source_url:
            continue

        source_text = source.get("excerpt", "")

        if not isinstance(source_text, str) or not source_text.strip():
            continue

        if normalize_quote(quotation) not in normalize_quote(source_text):
            continue

        verified_results[index] = {
            "source_url": source_url,
            "supporting_excerpt": quotation,
            "reason": str(
                check.get(
                    "reason",
                    "Supported by source evidence."
                )
            )
        }

    return verified_results


# ============================================================
# 6. RELEVANCE CLASSIFICATION
# ============================================================

def classify_relevance(scheme, user_context):
    """
    Estimate scheme relevance using profile interests
    and occupation.

    This is NOT an eligibility decision.

    Returns:
        Tuple of (relevance_level, list_of_reasons).
    """
    employment = user_context.get("employment", {})

    if not isinstance(employment, dict):
        employment = {}

    # The API stores a nested profile; direct callers may pass it flat.
    occupation = normalize_text(
        employment.get("occupation") or user_context.get("occupation") or ""
    )

    interests = user_context.get("interests", [])

    if not isinstance(interests, list):
        interests = []

    benefits = scheme.get("benefits", [])
    target_groups = scheme.get("target_groups", [])

    if not isinstance(benefits, list):
        benefits = []

    if not isinstance(target_groups, list):
        target_groups = []

    scheme_text = normalize_text(
        " ".join([
            str(scheme.get("name", "")),
            str(scheme.get("description", "")),
            " ".join(map(str, benefits)),
            " ".join(map(str, target_groups))
        ])
    )

    # Predefined keyword expansions for common interests.
    # This helps match schemes when interest text doesn't
    # appear verbatim in scheme descriptions.
    interest_keywords = {
        "crop insurance": [
            "crop insurance",
            "fasal bima",
            "crop loss",
            "crop damage",
            "insurance coverage"
        ],
        "irrigation assistance": [
            "irrigation",
            "micro irrigation",
            "drip irrigation",
            "sprinkler irrigation",
            "water use efficiency"
        ],
        "education": [
            "education",
            "scholarship",
            "school",
            "college",
            "university",
            "tuition"
        ],
        "scholarships": [
            "scholarship",
            "fellowship",
            "stipend",
            "merit",
            "education grant"
        ],
        "housing": [
            "housing",
            "awas",
            "home",
            "dwelling",
            "shelter"
        ],
        "health": [
            "health",
            "medical",
            "hospital",
            "treatment",
            "ayushman"
        ],
        "employment": [
            "employment",
            "job",
            "skill",
            "training",
            "rozgar",
            "nrega"
        ],
        "pension": [
            "pension",
            "old age",
            "retirement",
            "social security"
        ],
        "business": [
            "business",
            "entrepreneur",
            "startup",
            "msme",
            "mudra",
            "enterprise"
        ],
    }

    reasons = []
    direct_match = False

    for interest in interests:

        if not isinstance(interest, str):
            continue

        interest_text = normalize_text(interest)

        keywords = interest_keywords.get(
            interest_text,
            [interest_text]
        )

        matched = [
            keyword
            for keyword in keywords
            if keyword and normalize_text(keyword) in scheme_text
        ]

        if matched:
            direct_match = True
            reasons.append(
                f"Matches stated interest '{interest}': "
                f"{', '.join(matched)}"
            )

    normalized_targets = [
        normalize_text(target)
        for target in target_groups
        if isinstance(target, str)
    ]

    occupation_match = (
        bool(occupation)
        and any(
            occupation in target or target in occupation
            for target in normalized_targets
            if target
        )
    )

    if direct_match:
        relevance = "direct_match"

    elif occupation_match:
        relevance = "related"
        reasons.append(
            f"Target group may match occupation: {occupation}"
        )

    else:
        relevance = "additional"

    return relevance, reasons


# ============================================================
# 7. VERIFICATION STATUS
# ============================================================

def calculate_verification_status(claims, verified_claims):
    """
    Calculate overall scheme verification status
    from individual claim results.
    """
    if not claims or not verified_claims:
        return "unverified"

    verified_count = len(verified_claims)

    if verified_count == 0:
        return "unverified"

    if verified_count == len(claims):
        return "verified"

    return "partially_verified"


# ============================================================
# 8. SCHEME DEDUPLICATION
# ============================================================

def deduplicate_schemes(schemes: list[SchemeRecord]) -> list[SchemeRecord]:
    """
    Remove duplicate SchemeRecord entries based on
    normalised name similarity.
    """
    seen_names: set[str] = set()
    unique: list[SchemeRecord] = []

    for scheme in schemes:
        name_key = normalize_text(scheme.name)

        if not name_key or name_key in seen_names:
            continue

        seen_names.add(name_key)
        unique.append(scheme)

    return unique


# ============================================================
# 9. MAIN DISCOVERY EXTRACTION PIPELINE
# ============================================================

def prompt_context(user_context: dict) -> dict:
    """The profile fields extraction needs, and nothing else: the profile may
    hold income, caste or contact details that must not leave the machine."""
    employment = user_context.get("employment") if isinstance(user_context.get("employment"), dict) else {}
    location = user_context.get("location") if isinstance(user_context.get("location"), dict) else {}
    interests = user_context.get("interests") if isinstance(user_context.get("interests"), list) else []
    return {
        "employment": {"occupation": employment.get("occupation")},
        "location": {"district": location.get("district"), "state": location.get("state")},
        "interests": [i for i in interests if isinstance(i, str)],
    }


def extract_schemes(
    client,
    model: str,
    search_results: list[dict],
    user_context: dict | None = None
) -> list[SchemeRecord]:
    """
    Extract government scheme records from search results
    using Gemini for extraction and verification.

    Args:
        client: Gemini API client.
        model: Model name to use.
        search_results: List of search result dicts from
            the search provider.
        user_context: User profile dict for relevance
            classification.

    Returns:
        List of validated SchemeRecord objects.
    """
    if not search_results:
        return []

    user_context = user_context or {}

    # --------------------------------------------------------
    # A. Accept usable official search results
    # --------------------------------------------------------

    official_sources = {}

    for result in search_results:

        if not isinstance(result, dict):
            continue

        url = result.get("url")
        content = result.get("content", "")

        if (
            result.get("is_official") is True
            and isinstance(url, str)
            and url.startswith(("https://", "http://"))
            and isinstance(content, str)
            and content.strip()
        ):
            official_sources[url] = {
                "title": result.get("title", ""),
                "url": url,
                "content": content.strip()
            }

    if not official_sources:
        logger.info("No usable official source content found.")
        return []

    # --------------------------------------------------------
    # B. Ask Gemini to extract schemes
    # --------------------------------------------------------

    prompt = f"""
{EXTRACTION_INSTRUCTIONS}

USER CONTEXT:
{json.dumps(prompt_context(user_context), ensure_ascii=False)}

OFFICIAL SEARCH RESULTS:
{json.dumps(list(official_sources.values()), ensure_ascii=False)}
"""

    try:
        extracted_data = generate_json(
            client,
            model,
            prompt
        )
    except Exception as error:
        logger.error("Scheme extraction failed: %s", error)
        return []

    raw_schemes = extracted_data.get("schemes", [])

    if not isinstance(raw_schemes, list):
        logger.warning("'schemes' field is not a list.")
        return []

    validated_schemes = []

    # --------------------------------------------------------
    # C. Process each extracted scheme
    # --------------------------------------------------------

    for raw_scheme in raw_schemes:

        if not isinstance(raw_scheme, dict):
            continue

        # ----------------------------------------------------
        # C1. Validate source evidence
        # ----------------------------------------------------

        raw_evidence = raw_scheme.get("source_evidence", [])

        if not isinstance(raw_evidence, list):
            raw_evidence = []

        accepted_evidence = []
        seen_urls = set()

        for item in raw_evidence:

            if not isinstance(item, dict):
                continue

            url = item.get("url")

            if (
                url not in official_sources
                or url in seen_urls
            ):
                continue

            source = official_sources[url]
            seen_urls.add(url)

            accepted_evidence.append({
                "title": source["title"],
                "url": url,
                "excerpt": source["content"][:2000],
                "is_official": True
            })

        raw_scheme["source_evidence"] = accepted_evidence

        evidence_urls = {
            item["url"]
            for item in accepted_evidence
        }

        # Do not substitute an unrelated source URL.
        if raw_scheme.get("official_url") not in evidence_urls:
            raw_scheme["official_url"] = None

        if raw_scheme.get("application_url") not in evidence_urls:
            raw_scheme["application_url"] = None

        if raw_scheme.get("deadline_source_url") not in evidence_urls:
            raw_scheme["deadline_source_url"] = None

        # ----------------------------------------------------
        # C2. Clean claims
        # ----------------------------------------------------

        raw_claims = raw_scheme.get("claims", [])

        if not isinstance(raw_claims, list):
            raw_claims = []

        allowed_categories = {
            "description",
            "benefit",
            "eligibility",
            "document",
            "application_process"
        }

        cleaned_claims = []

        for claim in raw_claims:

            if not isinstance(claim, dict):
                continue

            if not isinstance(claim.get("claim"), str):
                continue

            if claim.get("category") not in allowed_categories:
                continue

            if claim.get("source_url") not in evidence_urls:
                claim["source_url"] = None

            claim["supporting_excerpt"] = ""
            claim["verification_status"] = "unverified"
            claim["verification_reason"] = ""

            cleaned_claims.append(claim)

        raw_scheme["claims"] = cleaned_claims

        # ----------------------------------------------------
        # C3. Independently verify claims
        # ----------------------------------------------------

        verified_claims = verify_claims(
            client,
            model,
            cleaned_claims,
            accepted_evidence
        )

        for index, claim in enumerate(cleaned_claims):

            if index not in verified_claims:
                continue

            result = verified_claims[index]

            claim["verification_status"] = "verified"
            claim["source_url"] = result["source_url"]
            claim["supporting_excerpt"] = result["supporting_excerpt"]
            claim["verification_reason"] = result["reason"]

        # ----------------------------------------------------
        # C4. Calculate overall verification status
        # ----------------------------------------------------

        raw_scheme["verification_status"] = (
            calculate_verification_status(
                cleaned_claims,
                verified_claims
            )
        )

        # ----------------------------------------------------
        # C5. Sync eligibility criteria with verified claims
        # ----------------------------------------------------

        raw_criteria = raw_scheme.get(
            "eligibility_criteria",
            []
        )

        if not isinstance(raw_criteria, list):
            raw_criteria = []

        cleaned_criteria = []

        for criterion in raw_criteria:

            if not isinstance(criterion, dict):
                continue

            description = criterion.get("description", "")

            if not isinstance(description, str):
                continue

            criterion["verification_status"] = "unverified"

            if criterion.get("source_url") not in evidence_urls:
                criterion["source_url"] = None

            for claim in cleaned_claims:

                if (
                    claim.get("category") == "eligibility"
                    and normalize_text(claim.get("claim", ""))
                    == normalize_text(description)
                ):
                    criterion["verification_status"] = (
                        claim["verification_status"]
                    )

                    criterion["source_url"] = claim.get("source_url")
                    if claim["verification_status"] == "verified":
                        criterion["evidence"] = claim.get("supporting_excerpt")
                    break

            # A criterion is verified when its own quote is really on the
            # page it cites (checked here, not trusted from the model).
            if criterion["verification_status"] != "verified":
                quote = verbatim_evidence(
                    criterion.get("evidence"),
                    criterion.get("source_url"),
                    official_sources
                )
                criterion["evidence"] = quote
                if quote:
                    criterion["verification_status"] = "verified"

            cleaned_criteria.append(criterion)

        raw_scheme["eligibility_criteria"] = cleaned_criteria

        # ----------------------------------------------------
        # C5b. Documents: keep source and quote only if verbatim
        # ----------------------------------------------------

        cleaned_documents = []
        seen_doc_names = set()

        for doc in raw_scheme.get("documents") or []:

            if not isinstance(doc, dict):
                continue

            name = doc.get("name")

            if not isinstance(name, str) or not name.strip():
                continue

            name = name.strip()

            if name.casefold() in seen_doc_names:
                continue

            seen_doc_names.add(name.casefold())
            source_url = doc.get("source_url") if doc.get("source_url") in evidence_urls else None
            quote = verbatim_evidence(doc.get("evidence"), source_url, official_sources)

            cleaned_documents.append({
                "name": name,
                "source_url": source_url if quote else None,
                "evidence": quote
            })

        names = [
            d for d in raw_scheme.get("required_documents") or []
            if isinstance(d, str) and d.strip()
        ]

        for name in names:
            if name.strip().casefold() not in seen_doc_names:
                seen_doc_names.add(name.strip().casefold())
                cleaned_documents.append({"name": name.strip(), "source_url": None, "evidence": None})

        raw_scheme["documents"] = cleaned_documents
        raw_scheme["required_documents"] = [d["name"] for d in cleaned_documents]

        # ----------------------------------------------------
        # C6. Calculate relevance
        # ----------------------------------------------------

        relevance, reasons = classify_relevance(
            raw_scheme,
            user_context
        )

        raw_scheme["relevance"] = relevance
        raw_scheme["match_reasons"] = reasons

        # ----------------------------------------------------
        # C7. Identify missing information
        # ----------------------------------------------------

        missing = []

        if not cleaned_criteria:
            missing.append("Eligibility criteria")

        documents = raw_scheme.get("required_documents", [])

        if not isinstance(documents, list) or not documents:
            missing.append("Required documents")

        if not raw_scheme.get("application_process"):
            missing.append("Application process")

        if not accepted_evidence:
            missing.append("Official source evidence")

        if not raw_scheme.get("department"):
            missing.append("Responsible department")

        raw_scheme["missing_information"] = missing

        # This pipeline processes live search results.
        raw_scheme["discovery_source"] = "live_search"
        raw_scheme["last_verified"] = datetime.now(timezone.utc).isoformat()

        # Ensure government_level has a valid value
        gov_level = raw_scheme.get("government_level", "unknown")
        if gov_level not in ("central", "state", "local", "unknown"):
            raw_scheme["government_level"] = "unknown"

        # ----------------------------------------------------
        # C8. Validate final SchemeRecord
        # ----------------------------------------------------

        try:
            scheme = SchemeRecord.model_validate(raw_scheme)
            validated_schemes.append(scheme)

        except ValidationError as error:
            logger.warning(
                "Skipped invalid scheme record: %s\n%s",
                raw_scheme.get("name", "Unknown"),
                error
            )

    # Deduplicate extracted schemes
    return deduplicate_schemes(validated_schemes)
