# Member 3 — Debugging & Edge Cases Log

Document database lock issues, serialization bugs, session state glitches, and integration errors here.

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

### [2026-10-31 20:10] Bug: 5 Member 2 Normalizer Tests Failed with ModuleNotFoundError: No module named 'anthropic'
* **Symptom:** Running `.venv/bin/python -m pytest tests/member2 -q` failed on `tests/member2/test_normalize.py` tests inspecting `AnthropicClient`.
* **Cause:** `anthropic` was listed in `requirements-member2.txt` as optional, but not in unified `requirements.txt`.
* **Fix / Workaround:** Added `anthropic>=0.40.0` to `requirements.txt` and installed it in `.venv`.
* **Verification:** `python -m pytest tests/member2 -q` -> 282 passed (100%).

### [2026-10-31 20:11] Bug: `AttributeError: 'SchemeRecord' object has no attribute 'application_process'` in Kannada Translator
* **Symptom:** `tests/test_kannada.py::test_fallback_schemes_translated_with_authentic_overlays` failed on `scheme.application_process`.
* **Cause:** Member 1's `fallback_schemes.py` returns canonical `member2.models.SchemeRecord` records which use `application_steps: list[str]` rather than `application_process: str`.
* **Fix / Workaround:**
  1. Updated `discovery_agent/adapter.py` `to_canonical_scheme` to preserve `application_process` as an extra field.
  2. Updated `_apply_kannada_fallback_overlay` in `discovery_agent/kannada_translator.py` to use `getattr(scheme, "application_process", ...)` with fallback to `application_steps[0]`.
* **Verification:** `python -m pytest tests/test_discovery.py tests/test_extended_discovery.py tests/test_kannada.py -q` -> 61 passed (100%).

### [2026-10-31 20:20] Bug: `RuntimeError: threads can only be started once` in aiosqlite under Python 3.14
* **Symptom:** `pytest tests/test_database.py` failed with `RuntimeError: threads can only be started once`.
* **Cause:** `get_connection()` awaited `aiosqlite.connect()` (which started the worker thread) and then callers executed `async with conn:`, which invoked `conn.__aenter__()` attempting to start the worker thread a second time.
* **Fix / Workaround:** Implemented `get_connection()` as an `@asynccontextmanager` yielding the active connection inside a single `async with aiosqlite.connect(...)` scope.
* **Verification:** `pytest tests/test_database.py` -> 7 passed (100%).

### [2026-10-31 21:08] Bug: `ValidationError: Input should be a valid dictionary or instance of Answer` in `process_answers`
* **Symptom:** `POST /api/sessions/{session_id}/answers` failed with HTTP 500 when `SubmitAnswersRequest` contained `AnswerInput` models.
* **Cause:** `member2.apply_answers()` expects elements to be either instances of `member2.models.Answer` or `dict`. Pydantic v2 `Answer.model_validate()` rejects other model instances such as `AnswerInput`.
* **Fix / Workaround:** Added normalization in `api/orchestrator.process_answers()` converting `AnswerInput` models into clean dictionaries with default `state="answered"` before delegating to `apply_answers()`.
* **Verification:** `pytest tests/test_api.py` passed (6 passed in test suite).

