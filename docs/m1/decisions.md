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

### [2026-11-01] ADR-005: Open Web Search Domain Expansion & Balanced Central/State Query Planning
* **Status:** Accepted
* **Context:** The discovery search was artificially restricted to 16 hardcoded domains, suppressing legitimate schemes, and query generation was heavily biased towards Karnataka-specific scheme terminology without discovering Central Government schemes applicable to Karnataka citizens.
* **Decision:**
  1. Removed the 16-domain restriction in `search_provider.py`, allowing open web search while tagging `is_official: False` for non-government domains.
  2. Added Gemini-driven query generation (`generate_search_queries_with_llm`) with balanced 3-4 Central queries (targeting national portals like myscheme, scholarships.gov.in, agricoop without district pinning) and 3-4 State queries (targeting Karnataka departments).
  3. Expanded `other_state()` in `scheme_details.py` to recognize `CENTRAL_JURISDICTIONS` so Central schemes are never dropped as external states.
* **Consequences:** Search results increased dramatically across Central and State departments while maintaining official source provenance.

### [2026-11-01] ADR-006: Geographically-Aware Discovery, Evidence-Based Source Authority, Tolerant Salvaging, and Deadline Checking
* **Status:** Accepted
* **Context:** Post-expansion testing revealed 8 specific issues:
  1. Geographical conditions were becoming `unmapped:<state>` (e.g. `unmapped:haryana`) and asking citizens about other states.
  2. Central schemes copied rules from other states (e.g. Haryana) instead of Karnataka implementations.
  3. Extraction returned `"uncertain"` but schema only accepted `"verified"`, `"partially_verified"`, `"unverified"`.
  4. Schemes like Vidyasiri were discarded entirely when a single sub-item failed validation.
  5. Non-government or other-state portals could erroneously mark eligibility as verified.
  6. Lack of visibility into discovery funnel diagnostics.
  7. Application deadlines were not calibrated against current date (`2026-11-01`).
  8. Document requirements did not carry mandatory vs optional flags into Agent 3.
* **Decision:**
  1. Mapped state conditions to canonical `attribute="state", operator=Operator.eq, value="<State>"`.
  2. Filtered out other states' portals (`*.haryana.gov.in`, etc.) when collecting pages for Central schemes when targeting Karnataka.
  3. Expanded `VerificationStatus` to accept `"uncertain"` and added safe normalization validators.
  4. Implemented `sanitize_and_salvage_scheme()` to repair records item-by-item instead of discarding entire schemes.
  5. Implemented `can_verify_for_state()` ensuring only official Central or Karnataka portals can verify Karnataka eligibility.
  6. Tracked and exposed discovery pipeline diagnostics (queries, results, extracted, validation failed, duplicates removed, claims verified, final schemes).
  7. Implemented `check_deadline()` evaluating dates against `2026-11-01` (`deadline_status="expired"` for past dates) and requiring official source backing.
  8. Propagated `mandatory: bool` on `SchemeDocument` and `DocumentRequirement` through to `ChecklistItem` in Agent 3.
* **Consequences:** Discovery pipeline is robust, geographically aware, tolerant of partial extraction, and fully aligned with downstream agents.


