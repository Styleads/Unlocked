# Project Unlocked — Cross-Agent Code Review & Potential Issues Log

> **Master Review Document:** Maintained by Member 3 (Tech Lead & Backend)  
> **Detailed Module Logs:**
> - **Member 3 (Backend, Orchestrator & Cross-Agent Integration):** [`docs/m3/potential_issues.md`](file:///home/kruthik/coding/Unlocked/docs/m3/potential_issues.md)
> - **Member 2 (Agent 2 Eligibility & Agent 3 Document Planning):** [`docs/m2/potential_issues.md`](file:///home/kruthik/coding/Unlocked/docs/m2/potential_issues.md)
> - **Member 1 (Agent 1 Discovery & Kannada Translation):** [`docs/m1/potential_issues.md`](file:///home/kruthik/coding/Unlocked/docs/m1/potential_issues.md)

---

## Executive Summary & Integration Status

All four agents and the central backend have been reviewed and integrated on the `backend` branch. The test suite is passing with **455 tests (100% pass rate)**.

```bash
PYTHONPATH=. .venv/bin/pytest tests/ --ignore=live_api_test.py
# Output: 455 passed in 1.91s
```

---

## Master Issues & Review Matrix

| ID | Component | Severity | Description | Status |
|---|---|---|---|---|
| **1.1** | Cross-Agent | High | Strict provenance rule downgrades verified requirements missing source URL or verbatim quote | **Resolved** in `backend` branch |
| **1.2** | Adapter | Critical | Duplicate `application_process` kwarg caused `SyntaxError` on import | **Resolved** in `backend` branch |
| **1.3** | Translator | High | `application_process` vs `application_steps` schema divergence during Kannada overlay | **Resolved** in `backend` branch |
| **2.1** | Agent 1 | Medium | `MIN_QUOTE_CHARS = 15` in `verbatim_evidence()` drops short official criteria | Logged for Round 2 refinement |
| **2.2** | Agent 1 | Medium | Silent fallback mode on missing Gemini API key | **Surfaced** via `source_mode` in API |
| **3.1** | Agent 2 | High | Empty question batch when candidate rules unverified (`_useful_usage`) | Mitigated via fallback data updates |
| **3.2** | Agent 3 | Medium | Document prerequisites empty without baseline DAG (`KNOWN_PREREQUISITES`) | Logged for Round 2 baseline injection |
| **3.3** | Agent 3 | Medium | Sourceless documents excluded from checklist | Mitigated via adapter URL inheritance |
| **4.1** | Agent 4 | Low | Agent 4 routes not yet wired into REST API (`/api/actions`) | **Resolved** (mounted in session & standalone routes) |
| **4.2** | Agent 4 | Low | Missing appointment time triggers `needs_input` with `missing_fields` | Working as intended (safety guardrail) |
| **4.3** | Agent 4 | Low | Unsupported appeal path without official guidance excerpts | Working as intended (safety guardrail) |
| **5.1** | Backend | Medium | SQLite database lock contention under rapid async write load | **Mitigated** with WAL & 30s busy timeout |
| **5.2** | Backend | Low | Permissive CORS configuration with credentials | **Mitigated** with explicit allowed origins list |

---

*For detailed root causes, reproduction code, and architectural mitigations for each issue, see [`docs/m3/potential_issues.md`](file:///home/kruthik/coding/Unlocked/docs/m3/potential_issues.md).*

