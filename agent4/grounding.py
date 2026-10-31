"""Deterministic checks that keep generated text tied to its sources, plus the
redaction applied before any user text reaches an LLM."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable, Optional

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\"']+", re.IGNORECASE)
# Indian mobile / landline shapes; loose on purpose, since a false hit only adds a placeholder.
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?(?:\d[\s-]?){9}\d(?!\d)")
AADHAAR_RE = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
NUMBER_RE = re.compile(r"\d+")
TOKEN_RE = re.compile(r"\{\{[^{}]+\}\}|\[[^\[\]]+\]")


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def contains_verbatim(haystack: str, needle: str) -> bool:
    """Whitespace- and case-insensitive substring test, for quotes."""
    n = squash(needle)
    return bool(n) and n in squash(haystack)


def redact(text: str) -> str:
    """Strip identifiers before text leaves the machine. Aadhaar first: its
    12 digits would otherwise be half-matched as a phone number."""
    text = AADHAAR_RE.sub("[ID number removed]", text)
    text = EMAIL_RE.sub("[email removed]", text)
    return PHONE_RE.sub("[phone removed]", text)


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:!?)").lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def replace_unsourced(text: str, *, emails: Iterable[str], urls: Iterable[str], phones: Iterable[str],
                      email_placeholder: str, url_placeholder: str, phone_placeholder: str) -> tuple[str, list[str]]:
    """Replace every email, link or phone number that is not in the allowed
    (sourced) sets with a placeholder the user must fill in."""
    ok_emails = {e.lower() for e in emails if e}
    ok_urls = {_clean_url(u) for u in urls if u}
    ok_phones = {re.sub(r"\D", "", p)[-10:] for p in phones if p}
    warnings: list[str] = []

    def email_sub(m: re.Match) -> str:
        if m.group(0).lower() in ok_emails:
            return m.group(0)
        warnings.append("An email address that isn't in the official sources was replaced with a placeholder.")
        return email_placeholder

    def url_sub(m: re.Match) -> str:
        raw = m.group(0)
        trail = raw[len(raw.rstrip(".,;:!?)")):]
        if _clean_url(raw) in ok_urls:
            return raw
        warnings.append("A link that isn't in the official sources was replaced with a placeholder.")
        return url_placeholder + trail

    def phone_sub(m: re.Match) -> str:
        if re.sub(r"\D", "", m.group(0))[-10:] in ok_phones:
            return m.group(0)
        warnings.append("A phone number that isn't in the official sources was replaced with a placeholder.")
        return phone_placeholder

    text = EMAIL_RE.sub(email_sub, text)
    text = URL_RE.sub(url_sub, text)
    text = PHONE_RE.sub(phone_sub, text)
    return text, sorted(set(warnings))


def unsupported_numbers(text: str, allowed_corpus: Iterable[str]) -> set[str]:
    """Numbers (two digits or more) in `text` that appear in none of the allowed
    texts. Placeholders and {{tokens}} are ignored. Used to catch invented
    dates, amounts and reference numbers."""
    corpus = " ".join(allowed_corpus)
    allowed = {n.lstrip("0") or "0" for n in NUMBER_RE.findall(corpus)}
    allowed |= {n.lstrip("0") or "0" for n in NUMBER_RE.findall(corpus.replace(",", ""))}
    stripped = TOKEN_RE.sub(" ", URL_RE.sub(" ", text))
    found = set()
    for n in NUMBER_RE.findall(stripped) + NUMBER_RE.findall(stripped.replace(",", "")):
        if len(n) >= 2 and (n.lstrip("0") or "0") not in allowed:
            found.add(n)
    return found


def call_llm_json(llm: Any, system: str, user: dict, *, task: str, ref: str) -> Optional[dict]:
    """One LLM call returning a JSON object, or None. Never raises; logs only the
    task and an id, never content."""
    if llm is None:
        return None
    try:
        raw = llm.complete_json(system, json.dumps(user, ensure_ascii=False))
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").removeprefix("json").strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        return data
    except Exception as exc:  # any provider/parse failure falls back to the deterministic path
        log.warning("agent4 %s failed for %s: %s", task, ref, type(exc).__name__)
        return None
