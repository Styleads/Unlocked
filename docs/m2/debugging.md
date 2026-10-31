# Member 2 — Debugging & Edge Cases Log

Document edge cases in requirement matching, cyclic dependencies, and assessment quirks here.

---

### Template
```markdown
## [YYYY-MM-DD HH:MM] Bug: Short Description
* **Symptom:** What happened or broke?
* **Cause:** Why did it happen?
* **Fix / Workaround:** How was it solved?
* **Verification:** How do you know it's fixed?
```

---

## Log

## [2026-10-31] Bug: Gemini returns HTTP 404 for `gemini-2.5-flash`
* **Symptom:** Every rule extraction failed; the probe call returned 404.
* **Cause:** The model name is retired for generation, although the model list still shows it.
* **Fix / Workaround:** Default to the alias `gemini-flash-lite-latest`. `live_check` lists usable models on a 404.
* **Verification:** `python -m member2.live_check` extracts all 4 demo rules as verified.

## [2026-10-31] Bug: Gemini returns HTTP 503 / timeouts on `gemini-flash-latest`
* **Symptom:** Probe failed after retries.
* **Cause:** Free-tier overload on the larger Flash model.
* **Fix / Workaround:** Retry 429/5xx up to 4 times with backoff; default to the Flash-Lite alias.
* **Verification:** Probe passes first try on Flash-Lite.

## [2026-10-31] Bug: Rephrasing changed "domicile" to "native"
* **Symptom:** LLM rewrote the domicile question as "Are you a native of Karnataka?", which has a different legal meaning.
* **Cause:** Free rewriting of a legally precise question.
* **Fix / Workaround:** `AttributeSpec.keep_wording`; such questions are never sent to the LLM.
* **Verification:** Unit test plus a live run shows the registry wording.

