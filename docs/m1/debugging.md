# Member 1 — Debugging & Edge Cases Log

Document crawler quirks, malformed HTML issues, search timeouts, and extraction fixes here.

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

### [2026-10-31 20:11] Bug: `application_process` AttributeError in Kannada Translator with Canonical SchemeRecord
* **Symptom:** `tests/test_kannada.py::test_fallback_schemes_translated_with_authentic_overlays` failed with `AttributeError: 'SchemeRecord' object has no attribute 'application_process'`.
* **Cause:** When fallback schemes were migrated to `member2.models.SchemeRecord`, the attribute became `application_steps: list[str]`.
* **Fix / Workaround:** Updated `discovery_agent/adapter.py` to preserve `application_process` during transformation, and made `_apply_kannada_fallback_overlay` inspect both `application_process` and `application_steps[0]`.
* **Verification:** `tests/test_kannada.py` passed (61 passed in discovery test suite).

