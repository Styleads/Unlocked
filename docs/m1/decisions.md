# Member 1 — Architecture Decisions & Trade-offs (ADRs)

Document decisions, provider choices, and technical trade-offs here.

---

### Template
```markdown
## [YYYY-MM-DD] ADR-00X: Title
* **Status:** [Proposed | Accepted | Superseded]
* **Context:** What problem were you solving?
* **Decision:** What did you choose and why?
* **Consequences / Trade-offs:** What are the pros and cons?
```

---

## Decisions Log

### [2026-10-31] ADR-001: Live Search Provider Selection
* **Status:** Proposed
* **Context:** Need live web search with high relevance on Indian/Karnataka government domains without complex scraping infrastructure.
* **Decision:** Evaluate Tavily API first for clean markdown/content extraction. If API key latency or quota is a factor, provide local Serper or DuckDuckGo fallback.
* **Consequences:** Tavily provides structured excerpts, reducing scraping boilerplate. Fallback seed records must still be maintained.

### [2026-10-31] ADR-002: Fallback Dataset Design
* **Status:** Accepted
* **Context:** Hackathon venue Wi-Fi or search rate limits could break live demo during judging.
* **Decision:** Pre-compile 5 verified Karnataka schemes (SSP Scholarship, Vidyasiri, Yuva Nidhi, Gruha Jyothi, Dr. B.R. Ambedkar Fellowship) with real official URLs.
* **Consequences:** All records must have `source_type: "fallback"` to maintain transparency and truthfulness in demo.

### [2026-10-31] ADR-003: Pipeline Contract & Attribute Alignment with Member 2
* **Status:** Accepted
* **Context:** Agent 2 and Agent 3 expect structured requirements and sourced document objects. Unaligned attribute keys (e.g. `karnataka_domicile` vs `domicile_karnataka`) or string-only documents break the downstream questionnaire and action plan.
* **Decision:** 
  1. Extract canonical attribute IDs conforming strictly to `member2/attributes.py` (`domicile_karnataka`, `annual_family_income`, `social_category`, etc.).
  2. Structure documents as `{name, source_url, evidence}` objects.
  3. Use operators `is_true` / `is_false` for booleans.
  4. Validate all output with `python -m member2.check_member1`.
* **Consequences:** Zero conversion code needed in backend; full compatibility across Discovery, Verification, and Planning.

### [2026-10-31] ADR-004: Compliance Adapter, Gemini Model Fix, and Orchestration Handoff
* **Status:** Accepted
* **Context:** Review Round 1 identified three critical integration issues:
  1. Fictional model name `"gemini-3.5-flash-lite"` returned HTTP 404.
  2. Schema divergence between M1's `SchemeRecord` and M2's canonical model.
  3. Prototype `api/` developed by M1 conflicted with M3's role as backend and orchestration lead.
* **Decision:**
  1. Replaced fictional model with valid free-tier model `"gemini-flash-lite-latest"`.
  2. Implemented `discovery_agent/adapter.py` providing bidirectional transformation and updated `fallback_schemes.py` to produce canonical `member2.models.SchemeRecord` instances with sourced documents.
  3. Transferred backend/API ownership to Member 3 and removed prototype `api/` and `tests/test_api.py`.
  4. Renamed root interactive script `test_gemini.py` to `demo_gemini_interactive.py` to unblock automated `pytest`.
* **Consequences:** Clean repository layout, full compliance with Member 2 and Member 3, zero test discovery lockups.


