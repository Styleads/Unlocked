"""
Per-scheme detail extraction ("deep fetch").

The first discovery pass searches by the user's profile, so a scheme's own
page is often missing or crowded out, and only short excerpts are kept.
This pass searches once per scheme, cuts that scheme's own block out of each
official page (markdown sections and table rows alike), and asks Gemini to
list *every* eligibility rule and document in it. Python keeps a rule only if
its quote is found verbatim in the block it cites.

Rules that apply after the award (attendance, refunds, renewal marks) are
kept as kind="obligation" so they are shown, not asked as questions.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional

from discovery_agent.scheme_extractor import generate_json, verbatim_evidence

logger = logging.getLogger(__name__)

MAX_PAGES_PER_SCHEME = 4
SEARCH_RESULTS_PER_SCHEME = 8
MAX_BLOCK_CHARS = 3500       # one scheme block on one page
MAX_SCHEME_CHARS = 12000     # all blocks for one scheme, sent to the model

# Lines that end a scheme block: page furniture common on gov.in sites.
_BOILERPLATE = re.compile(
    r"^(screen reader access|disclaimer|website policies|copyright|last updated|visitors?|"
    r"follow us|related links|important links|quick links|contact us)\b", re.IGNORECASE)
# Markdown headings, whole-line bold ("**PRIZE MONEY SCHOLARSHIP:**") and short
# ALL-CAPS lines ending in ":" all start a new section on these sites.
_HEADING = re.compile(r"^\s*(#{1,6}\s|\*\*[^*]{3,80}\*\*:?\s*$|[A-Z0-9][A-Z0-9 .,&()/'-]{6,80}:\s*$)")
_TABLE_ROW = re.compile(r"^\s*\|")
_SERIAL_CELL = re.compile(r"^\d{1,3}\.?$")

DETAIL_INSTRUCTIONS = """
You read the official text about ONE government scheme and list its rules.

RULES:
1. Use only the supplied blocks. Never add a rule from general knowledge.
2. List EVERY eligibility condition as its own item, even small ones
   (gender, course, year, subjects, marks, category-specific marks, income,
   institution type, residence). Do not merge or summarise conditions.
3. "evidence" is the exact sentence or table cell from the block, copied
   character for character. "source_url" is the url of that block.
4. kind = "eligibility" for conditions to receive the scheme;
   kind = "obligation" for what happens after the award (attendance,
   refunds, renewal conditions, penalties).
5. List every required document the same way.
6. If the blocks disagree with each other, list both versions.

Return JSON only:
{
  "eligibility_criteria": [
    {"description": "", "related_attribute": null, "source_url": "", "evidence": "", "kind": "eligibility"}
  ],
  "documents": [
    {"name": "", "source_url": "", "evidence": ""}
  ]
}
"""


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def name_key(scheme_name: str) -> str:
    """Matching key for a scheme name: punctuation, spacing and any
    parenthesised abbreviation removed, so "Sir C.V. Raman", "Sir CV RAMAN"
    and "Sir C V Raman" all match."""
    return _squash(re.sub(r"\([^)]*\)", " ", scheme_name or ""))


def _clean_lines(raw: str) -> list[tuple[str, bool]]:
    """Page lines as (text, starts_new_row). Table rows become one line per
    non-empty cell; a row whose first cell is a serial number starts a new
    record, which is where one scheme's table block ends."""
    out: list[tuple[str, bool]] = []
    for line in (raw or "").replace("\r", "").split("\n"):
        if _TABLE_ROW.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            filled = [c for c in cells if c and set(c) - set("-: ")]
            if not filled:
                continue
            new_row = bool(cells and _SERIAL_CELL.match(cells[0] or ""))
            for i, cell in enumerate(filled):
                out.append((cell, new_row and i == 0))
        else:
            text = line.strip()
            if text:
                out.append((text, False))
    return out


def scheme_blocks(raw: str, scheme_name: str, max_chars: int = MAX_BLOCK_CHARS) -> list[str]:
    """The parts of a page about this scheme, verbatim (whitespace and table
    pipes aside): from each line naming the scheme until a new heading, a new
    table record, page furniture, or max_chars. At most two blocks."""
    key = name_key(scheme_name)
    if len(key) < 6:
        return []
    lines = _clean_lines(raw)
    blocks: list[str] = []
    i = 0
    while i < len(lines) and len(blocks) < 2:
        if key not in _squash(lines[i][0]):
            i += 1
            continue
        block, size, j = [lines[i][0]], len(lines[i][0]), i + 1
        while j < len(lines):
            text, new_row = lines[j]
            if new_row or _BOILERPLATE.match(text) or (_HEADING.match(text) and key not in _squash(text)):
                break
            if size + len(text) > max_chars:
                break
            block.append(text)
            size += len(text) + 1
            j += 1
        # A heading repeating the name with nothing under it is not a block.
        if len(block) > 1:
            # Drop markdown emphasis so a quote like "This Scholarship is..." matches
            # "**T**his Scholarship is..."; only formatting goes, never words.
            blocks.append(re.sub(r"\*\*|__|`", "", "\n".join(block)))
        i = j
    return blocks


def _merge(scheme: dict, data: dict, pages: dict[str, dict]) -> bool:
    """Replace the scheme's criteria/documents with the verified detail
    results. Returns True if anything verified was found."""
    criteria, documents = [], []
    seen = set()
    for item in data.get("eligibility_criteria") or []:
        if not isinstance(item, dict) or not isinstance(item.get("description"), str):
            continue
        url = item.get("source_url")
        quote = verbatim_evidence(item.get("evidence"), url, pages)
        key = (_squash(item["description"]), url)
        if key in seen:
            continue
        seen.add(key)
        criteria.append({
            "description": item["description"].strip(),
            "related_attribute": item.get("related_attribute") if isinstance(item.get("related_attribute"), str) else None,
            "source_url": url if quote else None,
            "evidence": quote,
            "verification_status": "verified" if quote else "unverified",
            "kind": "obligation" if item.get("kind") == "obligation" else "eligibility",
        })
    for item in data.get("documents") or []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            continue
        url = item.get("source_url")
        quote = verbatim_evidence(item.get("evidence"), url, pages)
        documents.append({"name": item["name"].strip(), "source_url": url if quote else None, "evidence": quote})

    if not any(c["verification_status"] == "verified" for c in criteria):
        return False  # keep what the first pass found; nothing better was confirmed

    scheme["eligibility_criteria"] = criteria
    # The first pass may have noted these as missing; they are not any more.
    notes = scheme.get("missing_information") or []
    found = {"Eligibility criteria"}
    if any(d.get("source_url") for d in documents):
        found.add("Required documents")
    scheme["missing_information"] = [n for n in notes if n not in found]
    if any(d["source_url"] for d in documents):
        names = {d["name"].casefold() for d in documents}
        documents += [d for d in scheme.get("documents") or [] if isinstance(d, dict)
                      and str(d.get("name", "")).casefold() not in names]
        scheme["documents"] = documents
        scheme["required_documents"] = [d["name"] for d in documents]

    used = {c["source_url"] for c in criteria if c["source_url"]}
    evidence = scheme.setdefault("source_evidence", [])
    known = {e.get("url") for e in evidence if isinstance(e, dict)}
    for url in sorted(used - known):
        evidence.append({"title": pages[url]["title"], "url": url, "excerpt": pages[url]["content"][:2000], "is_official": True})
    if scheme.get("official_url") is None and used:
        scheme["official_url"] = sorted(used)[0]

    if len(used) > 1:
        notes = scheme.setdefault("missing_information", [])
        note = "Official pages for this scheme state different rules; all of them are shown."
        per_url = {u: {_squash(c["evidence"] or "") for c in criteria if c["source_url"] == u} for u in used}
        if len({frozenset(v) for v in per_url.values()}) > 1 and note not in notes:
            notes.append(note)
    return True


def enrich_scheme(
    client: Any,
    model: str,
    scheme: dict,
    search: Callable[..., list[dict]],
) -> bool:
    """Deep-fetch one scheme (a dict in Agent 1's schema), in place.
    Never raises; returns True if verified rules were found."""
    name = scheme.get("name")
    if not isinstance(name, str) or not name.strip():
        return False
    try:
        results = search(f"{name} eligibility Karnataka", SEARCH_RESULTS_PER_SCHEME, include_raw=True)
    except Exception as error:  # search is best-effort here; the first pass already ran
        logger.warning("Detail search failed for a scheme: %s", type(error).__name__)
        return False

    pages: dict[str, dict] = {}
    for result in results or []:
        url = result.get("url")
        if not isinstance(url, str) or url in pages or not result.get("is_official"):
            continue
        blocks = scheme_blocks(result.get("raw_content") or "", name)
        if blocks:
            pages[url] = {"title": result.get("title", ""), "url": url, "content": "\n\n".join(blocks)}
    if not pages:
        return False
    # Prefer the pages that say the most about this scheme, not search order:
    # the fullest eligibility list was often the 4th or 5th result.
    ranked = sorted(pages.values(), key=lambda p: len(p["content"]), reverse=True)[:MAX_PAGES_PER_SCHEME]
    pages = {p["url"]: p for p in ranked}

    payload, size = [], 0
    for page in pages.values():
        text = page["content"][: max(0, MAX_SCHEME_CHARS - size)]
        if not text:
            break
        payload.append({"url": page["url"], "text": text})
        size += len(text)

    prompt = (DETAIL_INSTRUCTIONS + "\n\nSCHEME: " + name
              + "\n\nOFFICIAL BLOCKS:\n" + json.dumps(payload, ensure_ascii=False))
    try:
        data = generate_json(client, model, prompt)
    except Exception as error:
        logger.warning("Detail extraction failed for a scheme: %s", type(error).__name__)
        return False
    return _merge(scheme, data, pages)
