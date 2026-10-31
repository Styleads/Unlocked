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

> [!IMPORTANT]
> **Data Contracts & Answer Submission Formats for Frontend (Member 4):**
> 1. **Questions (`Question` model):**
>    - `id`: Stable ID, e.g. `"q_annual_family_income"`.
>    - `input_type`: `"number" | "range" | "select" | "boolean" | "text"`.
>    - `options`: Dropdown/radio options (for `select`, or `["Yes", "No"]` for `boolean`).
>    - `ranges`: Pre-defined bands for `input_type == range` (e.g. `[{"label": "Below ₹1 lakh", "min": 0, "max": 99999}, ...]`).
>    - `why_asked`: Transparent civic explanation of why this question matters and how many schemes require it.
> 2. **Submitting Answers (`POST /api/answers`):**
>    Submit a list of answer objects:
>    - **Range (Income):** Submit a band label from `Question.ranges` (e.g. `"Below ₹1 lakh"`) OR a dictionary `{"min": 100000, "max": 250000}`.
>    - **Select:** Submit one of `Question.options` (case-insensitive, e.g. `"Aided"`).
>    - **Boolean:** Submit `true` / `false` or `"Yes"` / `"No"`.
>    - **Number:** Submit a number or clean string (e.g. `72.5`).
>    - **Skips & Unknowns:** Send as explicit state objects:
>      ```json
>      {"attribute": "annual_family_income", "state": "skipped"}
>      {"attribute": "domicile_karnataka", "state": "unknown"}
>      {"attribute": "social_category", "state": "prefer_not_to_answer"}
>      ```
> 3. **Action Plan (`ActionPlan` model):**
>    - `checklist`: Ordered list of `ChecklistItem` (each with `id`, `name`, `status`, `order`, `required_by_scheme_ids`, `dependencies`, `source_urls`, `reason`).
>    - `shared_prerequisites`: List of document IDs required by 2+ schemes (badge in UI).
>    - `nodes` & `edges`: Directed graph data for dependency visualization (`kind: "document" | "scheme"`).

### Mock-First Development Rule
Do not wait for the backend to run. Build components immediately against mock JSON defined in [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md) and [`plan.md`](file:///home/kruthik/coding/Unlocked/plan.md). Once Member 3 stands up endpoints, swap out mock fixtures.

---

## 2. Checkpoints Timeline

| Time | Target | Status |
|---|---|---|
| Oct 31, 5:30 PM | Stitch design tokens exported; UI shell running with mock data | Done |
| Oct 31, 7:00 PM | Review Round 1: Context form + Scheme cards running locally against frozen contracts | Done |
| Oct 31, 12:05 AM | Complete question flow (answering/skipping) integrated with real backend API | Pending |
| Nov 1, 3:00 AM | Document checklist and action plan integrated with real API | Pending |
| Nov 1, 6:30 AM | UI polish, zero dead buttons, responsive verification on presentation device | Pending |

