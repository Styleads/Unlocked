# Member 1 — Research & Agentic Workflow Engineer

* **Assigned Modules:**
  * **Agent 1: Discovery Agent (P0 — Core MVP)**
  * **Agent 4: Action & Follow-Through Agent (P1 — Stretch)**
* **Technical Contact:** Member 1
* **Shared Contract:** [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md)

---

## 1. Responsibilities & Goals

### Agent 1: Discovery Agent (P0)
- [ ] Connect web search API (Tavily, Serper, or SearXNG).
- [ ] Formulate search queries targeted at official Karnataka and central portals (`karnataka.gov.in`, `sevasindhu.karnataka.gov.in`, etc.).
- [ ] Parse extracted scheme data into `SchemeRecord` format.
- [ ] Preserve verbatim source excerpts (`evidence`) and official source URLs (`source_url`).
- [ ] Deduplicate schemes across queries.
- [ ] Create a robust fallback dataset of 4–6 real Karnataka schemes (e.g., SSP Post-Matric Scholarship, Vidyasiri, Yuva Nidhi, Gruha Lakshmi) tagged with `source_type: "fallback"` for demo safety.
- [ ] Deliverable: `async def discover_schemes(user_context, search_scope) -> list[SchemeRecord]`

### Agent 4: Action & Follow-Through Agent (P1)
- [ ] Generate source-grounded email drafts for RTI inquiries or departmental clarifications (strictly reviewable by user, no auto-dispatch).
- [ ] Generate downloadable `.ics` calendar events for application deadlines or interview dates.
- [ ] Deliverable: `def generate_action_artifact(action_type, scheme, user_data) -> ActionArtifact`

---

## 2. Checkpoints Timeline

| Time | Target | Status |
|---|---|---|
| Oct 31, 5:30 PM | 1 working search or verified fallback candidate matching `SchemeRecord` | Pending |
| Oct 31, 7:00 PM | Review Round 1: Discovery returns real or labelled fallback schemes with sources | Pending |
| Oct 31, 12:05 AM | Multi-query discovery, deduplication, error handling completed | Pending |
| Nov 1, 3:00 AM | Action scaffold ready; email or `.ics` generation tested | Pending |

