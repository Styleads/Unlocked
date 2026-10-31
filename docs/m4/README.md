# Member 4 — Frontend & User Experience Developer

* **Assigned Modules:**
  * **Stitch Design Direction & Component Hierarchy**
  * **User Context & Discovery Scope UI**
  * **Consolidated Questionnaire Flow (Skip / Unknown UX)**
  * **Scheme Results Dashboard & Details View**
  * **Document Checklist & Dependency Visualization**
  * **Mock-first API Integration**
* **Technical Contact:** Member 4
* **Master Architecture Plan:** [`plan.md`](file:///home/kruthik/coding/Unlocked/plan.md)
* **Shared Contract:** [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md)

---

## 1. Responsibilities & Goals

### Screen Inventory (P0)
1. **Landing & Context Form:**
   - Scope switch: Guided Discovery vs Discover All.
   - Profile inputs: Location/district, age, education status, life goal/category.
2. **Discovery Loading / Stream State:**
   - Transparent progress indicators (searching portals, parsing schemes).
3. **Consolidated Questionnaire View:**
   - 3–5 clean cards.
   - Explicit buttons: Answer, "Not Sure", "Prefer Not to Answer", and "Skip All & View Schemes".
   - Visible reasoning ("Why this is asked").
4. **Scheme Dashboard & Cards:**
   - Status badges: Potential Match, More Information Needed, Unlikely to Match, Uncertain.
   - Verifiable official source links (badge linking directly to `.gov.in` page).
5. **Scheme Details Modal / Drawer:**
   - Full breakdown of criteria, documents, and benefits.
6. **Document Checklist & Action Plan:**
   - Ordered task steps.
   - Shared prerequisite badge (e.g., "Unlocks 2 Schemes").

### Mock-First Development Rule
Do not wait for the backend to run. Build components immediately against mock JSON defined in [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md) and [`plan.md`](file:///home/kruthik/coding/Unlocked/plan.md). Once Member 3 stands up endpoints, swap out mock fixtures.

---

## 2. Checkpoints Timeline

| Time | Target | Status |
|---|---|---|
| Oct 31, 5:30 PM | Stitch design tokens exported; UI shell running with mock data | Pending |
| Oct 31, 7:00 PM | Review Round 1: Context form + Scheme cards running locally | Pending |
| Oct 31, 12:05 AM | Complete question flow (answering/skipping) integrated with real backend API | Pending |
| Nov 1, 3:00 AM | Document checklist and action plan integrated with real API | Pending |
| Nov 1, 6:30 AM | UI polish, zero dead buttons, responsive verification on presentation device | Pending |

