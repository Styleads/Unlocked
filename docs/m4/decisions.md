# Member 4 — Architecture Decisions & Trade-offs (ADRs)

Document UI framework decisions, state management, design tokens, and mock strategies here.

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

### [2026-10-31] ADR-001: UI Component Framework & Styling
* **Status:** Accepted
* **Context:** Need clean civic-tech UI fast without spending hours writing custom CSS.
* **Decision:** Use Tailwind CSS + Lucide icons (or agreed component library like shadcn/ui).
* **Consequences:** Quick prototyping; accessible colors and layout grids.

### [2026-10-31] ADR-002: Status Badge Color & Text Design
* **Status:** Accepted
* **Context:** Accessibility guidelines in plan.md forbid relying solely on color (green/red) to indicate eligibility.
* **Decision:** Always pair distinct color tokens with clear descriptive text:
  - Potential match (Blue/Emerald badge + check icon)
  - More information needed (Amber badge + help icon)
  - Uncertain / Unverified (Purple/Gray badge + info icon)
  - Unlikely to match (Neutral gray badge + slash icon)
* **Consequences:** Fully accessible, prevents misunderstanding of official eligibility.

### [2026-10-31] ADR-003: Contract Synchronization with Member 2 Models
* **Status:** Accepted
* **Context:** M2 finalized the Question, Answer, and ActionPlan models following `plan.md §5`. The frontend must match the backend JSON payload structures.
* **Decision:**
  1. Questionnaire renders inputs using `Question.input_type` (`range`, `select`, `number`, `boolean`, `text`).
  2. For `range` questions (income), show selectable chips/buttons using `Question.ranges` labels, or min/max numeric fields.
  3. Send skips and "not sure" as `{attribute, state: "skipped" | "unknown"}`.
  4. Render the Action Plan using `ActionPlan.checklist` (`ChecklistItem.order`, `status`, `reason`) and highlight `shared_prerequisites`.
* **Consequences:** Eliminates schema mismatch bugs between frontend form submission and backend evaluation.

### [2026-10-31] ADR-004: Review Round 1 Endpoint Specifications & Session Restore
* **Status:** Accepted
* **Context:** Member 3 published the revised `M3_Coding_Round_1_Plan.md` outlining the consolidated REST API routes for sessions, discovery, questions, answers, and action planning.
* **Decision:**
  1. Frontend uses session-scoped endpoints (`/api/sessions/{session_id}/...`) rather than legacy flat endpoints.
  2. The initial context landing form feeds `POST /api/sessions`, automatically seeding answered demographic attributes.
  3. Swapping mock fixtures for live backend calls occurs seamlessly against the frozen schemas.
* **Consequences:** Frontend development remains completely unblocked while aligning perfectly with Member 3's backend implementation.


