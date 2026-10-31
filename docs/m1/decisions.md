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

