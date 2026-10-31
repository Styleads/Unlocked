# Unlocked — Hackathon Implementation Plan

> **Project:** Unlocked — a Karnataka-focused government benefits discovery and follow-through assistant  
> **Track:** Personal Productivity (Daily Life)  
> **Team size:** 4  
> **Hackathon window:** October 31, 2026 – November 1, 2026  
> **Primary objective:** Deliver one reliable, source-backed, end-to-end user journey—not a collection of disconnected features.

---

## 1. Executive direction

Unlocked helps people discover government benefits they may qualify for, understand the requirements, prepare documents, and work out what to do next. It should reduce the effort of navigating fragmented scheme information and application processes.

The product must go beyond returning a list of schemes. Its strongest demonstration is:

**User context → live scheme discovery → cross-scheme questions → updated eligibility assessment → document dependency plan → concrete next action.**

The team should build four **logical workflow stages (agents)**, but does not need four separate models or autonomous services. Start with ordinary Python modules coordinated by one backend workflow. Use an LLM where interpretation and language generation help; use deterministic Python for state, comparisons, deduplication, validation, and graph ordering.

### The most important choices

1. **Build the P0 journey first.** Live discovery, traceable official sources, uncertainty-aware eligibility assessment, consolidated questions, and a usable document plan are the core.
2. **Use one shared workflow and one shared data contract.** Do not let each member invent their own schema or build isolated components until the end.
3. **Split the four agents between the two members doing the agent/intelligence work.** The member who has already done research owns Discovery and Action/Follow-through. The other owns Eligibility/Verification and Document/Planning.
4. **The team lead owns backend orchestration, SQLite, interfaces, and integration.** This role connects the modules; it should not reimplement every module.
5. **The newer member owns the frontend.** Stitch can accelerate design and Antigravity can help implement it, but the deliverable is a working UI connected to the backend, not just generated screens.
6. **Do not start with voice.** Voice input is optional and should only be considered after the complete P0 journey is working and tested. It is entirely acceptable—and probably wiser—to omit it in this 24-hour build.
7. **No automatic consequential actions.** Unlocked may prepare an email or calendar file, but the user reviews and carries out the action.

---

## 2. Product boundaries and agreed user journey

### 2.1 Start and basic context

The user chooses one of two discovery scopes:

- **Guided Discovery:** the user chooses supported benefit categories, such as scholarships, healthcare, pensions, or subsidies.
- **Discover All:** the system searches across all supported categories using the information the user provides.

These are different search scopes, not different user skill levels. Text and voice (if ever implemented) are interaction modes, not discovery modes.

Collect only information useful for finding and assessing schemes. Depending on the categories supported, this may include:

- State and district/location.
- Age or age range.
- Education or employment status.
- Relevant life situation or goal.
- Approximate income range, where relevant.
- Selected benefit categories, for Guided Discovery.
- Preferred language, if the implemented experience supports it.

Do not collect information merely because it might be useful someday. Explain why sensitive information is requested and make optional questions skippable.

### 2.2 Live scheme discovery

The Discovery stage searches for candidate schemes and converts useful findings into a common structured representation.

For each candidate, preserve where available:

- Scheme name and summary.
- Government level, department, or administering body.
- Target group.
- Eligibility requirements.
- Benefits and benefit amounts, only when supported by a source.
- Required documents.
- Application process and route.
- Official source URLs and application URLs.
- Evidence or excerpt supporting important claims.
- Verification status, uncertainty, and missing information.
- Last-verified information, where the implementation can reliably record it.

Prefer official government portals, department pages, and official scheme guidelines. Third-party pages may be discovery leads, but should not silently be treated as official verification.

The system must not invent scheme names, thresholds, amounts, documents, deadlines, dependencies, or application links. Deduplicate candidates and remove obvious mismatches, but do not discard a potentially relevant scheme simply because information is incomplete.

### 2.3 Consolidated questions across schemes

This is a central differentiator and must be part of the MVP.

After the initial candidate batch is collected and requirements are extracted:

1. Collect the missing user attributes across the whole candidate set.
2. Exclude attributes already answered by the user.
3. Deduplicate questions that ask for the same information in different words.
4. Rank questions by usefulness across relevant schemes, impact on assessment, ease of answering, and sensitivity.
5. Present a small initial batch—roughly 3–5 questions is a starting target, not a hard limit.
6. Let the user answer, choose “not sure” / “prefer not to answer” where appropriate, or skip.
7. Let the user browse the initial results without completing the questions.
8. Reassess the original candidate collection after answers are submitted.

Skipped and unknown answers remain **unknown**. They must never be converted into “no”, “not eligible”, or a failed requirement.

Python should enforce question deduplication, tracking, answer state, and limits. The LLM can help map differently worded requirements to the same underlying attribute and phrase user-friendly questions.

For the hackathon MVP, freeze the original candidate collection after the consolidated questionnaire. A new search can be a separate user-initiated discovery run. This avoids complicating the state model while a questionnaire is in progress.

### 2.4 Results and scheme details

Show relevant candidates, not just those predicted to be eligible. Suggested user-facing labels:

- **Potential match** — known information appears consistent with the published criteria.
- **More information needed** — an important answer is missing.
- **Not yet verified** — the relevant rule or source has not been adequately checked.
- **Unlikely to match** — known information appears to conflict with a stated criterion.
- **Uncertain** — the source or rule cannot be confidently interpreted.

These labels describe Unlocked's assessment, not an official eligibility decision.

A scheme details view should show its summary, source links, criteria, assessment explanation, benefits (only when verified), documents, application steps, and uncertainty. An optional **Check my eligibility** action can ask only the extra questions required for that scheme. Reuse existing answers; allow skipping or stopping.

Internally, distinguish requirement states such as satisfied, not satisfied, unknown, needs clarification, and unverified. Missing information is not a failed criterion.

### 2.5 Document checklist and dependency-aware plan

Use verified document requirements and only source-supported dependencies.

The system should:

- Combine document requirements across relevant schemes.
- Identify shared prerequisites.
- Mark what the user already has and what is still needed, when the user has supplied that information.
- Build a graph of document and scheme/task dependencies.
- Prioritize prerequisite tasks so that a shared document can unlock preparation for more than one application.
- Return an understandable checklist and ordered action plan.

Graph construction, traversal, and task ordering belong in deterministic Python—not in an LLM prompt. The LLM may extract a requirement from official text, but the system should only create an edge when the source supports that dependency.

### 2.6 Action and follow-through

The longer-term product can help users continue after discovery:

- Draft an email or clarification request for the user to review and send.
- Generate a downloadable `.ics` calendar event for a deadline or appointment.
- Record user-reported application status and progress.
- Ask whether an appointment was attended or an application decision was received.
- Interpret a user-provided rejection notice and check official guidance for an allowed next step.
- Prepare a correction request, clarification email, reapplication checklist, or appeal draft only when official guidance supports that route.

For the hackathon, treat this as P1 after the P0 journey is stable. Do not automatically submit applications, send communications, make payments, or file appeals. Do not promise that every rejection can be appealed or every application can be reopened.

Keep four distinct claim states separate:

1. Potential eligibility assessed by Unlocked.
2. Application submitted by the user.
3. Application approved by the authority.
4. Benefit actually received.

Approval and receipt are recorded only when confirmed by the user or a reliable source. Simulated outcomes in the demo must be labelled as simulated.

---

## 3. Architecture and workflow

### 3.1 Four logical agents

The four stages are:

1. **Discovery Agent** — finds potentially relevant schemes and returns structured candidates with source evidence.
2. **Eligibility & Verification Agent** — normalizes requirements, checks them against user information and sources, assesses potential matches, and identifies missing attributes/questions.
3. **Document & Planning Agent** — combines verified document requirements, constructs the dependency graph, and produces the checklist/action plan.
4. **Action & Follow-through Agent** — prepares user-approved next-step artifacts, tracks user-reported progress, and supports source-grounded recovery after a setback.

They do not have to be four separate LLMs, microservices, or autonomous agents. Implement them initially as separate Python modules with clear input/output contracts. One model/provider may be used for multiple stages with different instructions. Python controls the sequence and state transitions.

### 3.2 Recommended workflow

```text
USER
  |
  v
Create / restore session
  |
  v
Collect basic context + discovery scope
  |
  v
1. DISCOVERY AGENT
  |  live search, extraction, deduplication, source evidence
  v
Candidate scheme collection (frozen for this discovery run)
  |
  v
2. ELIGIBILITY & VERIFICATION AGENT
  |  normalize requirements, compare known answers, identify unknowns
  v
Consolidated cross-scheme questions
  |
  v
User answers / skips / browses initial results
  |
  v
Reassess all candidates
  |
  v
Browse results and open a scheme
  |
  +---- optional scheme-specific questions and reassessment
  |
  v
3. DOCUMENT & PLANNING AGENT
  |  verified documents, dependency graph, ordered checklist
  v
Action plan
  |
  v
4. ACTION & FOLLOW-THROUGH AGENT (P1 / stretch)
  |  draft email, .ics, progress/outcome, verified recovery guidance
  v
USER REVIEWS AND TAKES ACTION
  |
  v
User-reported outcome / next step; return to planning or verification if needed
```

A central workflow coordinates the stages and passes structured records. If a rejection reveals a missing document, the Action stage may send the case back to Planning. If new information changes eligibility, the Verification stage reassesses it.

### 3.3 Implementation pattern

Recommended starting point:

- Frontend: use the team's existing stack; use React if starting from scratch and the team can support it.
- Backend: Python + FastAPI.
- Model: begin with one provider/model, subject to API access, latency, and budget.
- Search: integrate an actual web-search tool/API. A prompt alone is not live search.
- Workflow: plain Python modules and orchestration first. LangChain/LangGraph are optional, not mandatory.
- Persistence: SQLite.
- Dependency graph: deterministic Python logic.
- Calendar: generate a downloadable `.ics` file; do not spend time on calendar OAuth.
- Voice: optional stretch feature only; see Section 10.

Keep model-provider and search-provider calls behind small service/adapter functions if practical. Validate model outputs against schemas and evidence; structured JSON is not automatically accurate.

---

## 4. Team of four — ownership and detailed responsibilities

The team has four people. Two members will split ownership of the four logical agents. The person who has already done research gets the more externally oriented/agentic stages: Discovery and Action/Follow-through. The other technical member owns Eligibility/Verification and Document/Planning. The team lead owns the shared backend and integration. The newer member owns the frontend.

This is a split by coherent workstream, not a claim that all four agents have equal effort. In particular, Action/Follow-through is deliberately scoped as P1 so the Discovery work does not prevent the core MVP from being completed.

### Member 1 — Research & Agentic Workflow Engineer

**Owns:** Agent 1 — Discovery; Agent 4 — Action & Follow-through.  
**Primary strength:** Existing research and ability to work with external information/tools.

#### A. Discovery Agent — P0

- Review and consolidate the research already completed; separate confirmed official sources from secondary leads.
- Select and integrate an actual web-search provider/API with Member 3's help on credentials/configuration if needed.
- Build reusable search functions for the supported search scope.
- Support Guided Discovery and Discover All.
- Search official government portals, department pages, scheme guidelines, and application portals first.
- Extract candidates into the shared scheme schema.
- Preserve source URLs and evidence for important requirements.
- Normalize scheme names, target groups, criteria, benefits, documents, application route, and uncertainty.
- Deduplicate records and remove obvious mismatches.
- Keep potentially relevant schemes where information is incomplete, with uncertainty clearly marked.
- Handle timeouts, rate limits, malformed pages, empty results, and partial results.
- Prepare a small manually verified Karnataka-relevant fallback set for demo reliability. Fallback records must be clearly labelled as fallback/demo data and must not silently masquerade as live-search results.
- Test at least two distinct user contexts/search scopes.

**Deliverable:** A callable discovery module that accepts user context and search scope and returns normalized candidate records with source evidence and verification status.

Suggested interface (adapt to the final contract):

```python
async def discover_schemes(user_context, search_scope) -> list[SchemeRecord]:
    ...
```

#### B. Action & Follow-through Agent — P1 after core flow

Build a small, reliable action module rather than attempting every long-term follow-through capability.

First implementation options, in priority order:

1. Generate a source-grounded email draft that the user can copy, review, and send.
2. Generate a downloadable `.ics` event from a user-confirmed appointment/deadline.
3. Record user-reported progress/outcomes through the shared session state.
4. If time remains, parse a user-provided rejection reason and prepare a source-grounded next-step explanation/draft only when the official procedure supports it.

Tasks:

- Define action inputs using the selected scheme, source references, user's chosen action, and confirmed dates/details.
- Ensure generated emails contain no invented office contacts, facts, deadlines, or claims.
- Ensure the `.ics` output contains only supplied or verified date/time details; ask for missing essential event information through the UI rather than inventing it.
- Keep action generation separate from sending/submission. The user must review and carry out every consequential action.
- Record application submission, approval, and actual receipt as separate states; never infer one from another.
- Clearly mark simulated rejection/outcome scenarios in the demo.

**Deliverable:** At least one working user-reviewed action artifact if P0 is already stable; otherwise a clean module/interface and a documented stretch implementation. Do not sacrifice live discovery or source reliability to finish this section.

#### C. Tests and evidence

- Test search failure and empty result states.
- Verify that each important extracted criterion has a source reference or is explicitly marked unverified.
- Check that fallback data is distinguishable from live results.
- Test generated email/calendar output for invented fields and unsafe assumptions.

---

### Member 2 — Eligibility, Verification & Planning Engineer

**Owns:** Agent 2 — Eligibility & Verification; Agent 3 — Document & Planning.  
**Primary strength:** Structured reasoning, assessment logic, and deterministic planning.

#### A. Requirement normalization — P0

- Consume scheme records from Member 1.
- Convert unstructured eligibility text into a normalized requirement matrix.
- Represent each requirement separately, with its value/condition, source evidence, and verification/uncertainty state.
- Identify which user attributes each requirement depends on.
- Distinguish simple deterministic rules (for example, a clearly stated age threshold) from conditions requiring interpretation.
- Flag missing, contradictory, ambiguous, or outdated information.
- Preserve the exact criterion and supporting source used in an assessment.

#### B. Eligibility & Verification Agent — P0

- Compare known user attributes against normalized criteria.
- Use deterministic checks for simple and unambiguous rules.
- Use the LLM to interpret unstructured or differently worded requirements where useful.
- Produce per-requirement statuses such as satisfied, not satisfied, unknown, needs clarification, and unverified.
- Produce a scheme-level status and a plain-language explanation.
- Ensure that a missing answer does not become a negative answer.
- Ensure that a potentially relevant scheme remains browseable even when information is incomplete.
- Keep assessment labels distinct from official eligibility decisions.
- Reassess candidates after consolidated answers arrive.

#### C. Consolidated cross-scheme question generation — P0

- Collect missing attributes across the entire initial candidate set, not one scheme at a time.
- Map equivalent requirements to a shared attribute/question.
- Remove attributes already present in the user context or saved answers.
- Rank questions by usefulness across relevant schemes, impact on assessment, ease of answering, and sensitivity.
- Generate a small initial batch (roughly 3–5 questions as a starting target).
- Support answer, skip, not sure, and prefer-not-to-answer states.
- Maintain asked/answered/skipped state so the same question is not repeatedly asked.
- Return a short explanation of why the question matters, when helpful.
- Allow the user to skip the entire question step and browse initial results.

Python should own deduplication, ranking constraints, question IDs, state, and answer tracking. The LLM can help map free-text requirements to attributes and phrase questions clearly.

#### D. Scheme-specific assessment — P0 if time allows after consolidated flow

- When a user chooses “Check my eligibility” for a scheme, request only additional information needed for that scheme.
- Reuse all existing session answers.
- Permit skip/stop.
- Return criterion-level results and a clear explanation.
- Do not repeat questions that are already answered or treat unknown as failure.

#### E. Document & Planning Agent — P0 basic version

- Collect document requirements that have been extracted and verified against sources.
- Normalize document names so equivalent items can be combined.
- Identify shared prerequisites across schemes.
- Build a directed dependency graph with documents/tasks and scheme/application nodes.
- Add an edge only when a source supports the dependency; never infer dependencies from a scheme name.
- Use deterministic Python for graph construction, traversal, cycle checks where relevant, and task ordering.
- Generate a checklist with required/known/obtained/not-yet-obtained/unknown states as appropriate.
- Prioritize shared prerequisites and verified deadlines where available.
- Return both a human-readable explanation and structured graph/checklist data for the UI.

Example: if an income certificate is verified as required for two schemes, represent it as one shared prerequisite that helps prepare both applications. Do not claim that it unlocks a scheme unless its requirements support that relationship.

**Deliverable:** Callable requirement-normalization, assessment, consolidated-question, reassessment, and planning modules with tests.

Suggested interfaces (adapt to shared contracts):

```python
def normalize_requirements(schemes) -> RequirementMatrix:
    ...

def assess_schemes(requirements, user_answers) -> list[Assessment]:
    ...

def generate_consolidated_questions(requirements, user_answers, question_history):
    ...

def build_action_plan(selected_schemes, verified_requirements, user_documents):
    ...
```

#### F. Tests and evidence

- Known scenario tests with expected assessment results.
- Complete, partial, skipped, and contradictory answer tests.
- Tests proving that unknown values are not treated as false.
- Tests for question deduplication and repeat-question prevention.
- Tests proving that graph edges are source-supported and ordering is deterministic.

---

### Member 3 — Technical Lead, Backend, SQLite & Integration

**Owns:** Shared backend, state, contracts, orchestration, integration and end-to-end reliability.  
**Primary objective:** Make the four logical stages work as one product. This role should coordinate interfaces and integration rather than independently implement the other members' intelligence modules.

#### A. Repository and backend foundation — P0

- Confirm the team's existing frontend stack; avoid changing it without a strong reason.
- Set up Python/FastAPI backend.
- Establish repository conventions, environment configuration, and a runnable development setup.
- Add a health-check endpoint.
- Configure API keys through environment variables; commit only an `.env.example`, never real secrets.
- Define shared models/schemas for sessions, user context, schemes, evidence, requirements, questions, answers, assessments, documents, dependencies, and action artifacts.
- Agree the API contract with all members before parallel implementation expands.

#### B. SQLite and session persistence — P0

Implement the minimum persistence needed for the journey:

- Random session IDs; no mandatory login/account system for the hackathon.
- Store initial user context and discovery scope.
- Store the current candidate collection and source data.
- Store questions and their status (asked, answered, skipped, unknown, etc.).
- Store user answers without converting skipped/unknown to negative values.
- Store assessment results and their source/evidence references.
- Store checklist items and user progress.
- Store user-reported application status/outcomes only where implemented.
- Support retrieving a session and resetting/deleting it.
- Define appropriate cleanup/retention behavior and make the actual persistence behavior clear in the UI.

SQLite persistence does not require user accounts. Use only data needed for the workflow. Avoid storing Aadhaar numbers, identity-document scans, passwords, OTPs, or unnecessary personal data. Do not log sensitive answers unnecessarily.

#### C. Workflow orchestration — P0

Implement the central workflow that calls the owned modules in the right order:

1. Create or restore a session.
2. Store user context and search scope.
3. Call Discovery and persist the candidate collection.
4. Call Eligibility/Verification to normalize requirements and assess known information.
5. Generate the consolidated question batch.
6. Persist answers and skip/unknown states.
7. Reassess the frozen candidate collection after answers.
8. Return results and detailed scheme information to the frontend.
9. Call Document/Planning when a plan is requested or a scheme is selected.
10. Call Action/Follow-through only when the user selects an implemented action.

The workflow—not the LLM—must decide which step executes next. Handle retries and failures without duplicating questions or losing session state.

#### D. API contract and frontend integration — P0

Proposed minimum endpoints (final names may be adjusted once, then shared):

| Endpoint | Purpose |
|---|---|
| `POST /api/sessions` | Create a session and save initial context/scope |
| `GET /api/sessions/{session_id}` | Restore session and progress |
| `POST /api/discover` | Start discovery for a session |
| `GET /api/schemes` | Return current candidate schemes/results |
| `GET /api/schemes/{scheme_id}` | Return scheme details and evidence |
| `GET /api/questions` | Retrieve consolidated questions |
| `POST /api/answers` | Save answers/skip/unknown states and trigger reassessment |
| `POST /api/schemes/{scheme_id}/assess` | Optional scheme-specific assessment |
| `GET /api/plan` | Return checklist and dependency/action plan |
| `POST /api/checklist/{item_id}` | Update a checklist item's user-reported progress |
| `POST /api/actions` | Generate an enabled draft or calendar artifact (P1) |

Do not overbuild endpoints. Some operations can be combined into one workflow call; what matters is a stable contract and predictable response shape.

#### E. Integration and reliability — P0

- Integrate the modules as they become callable; do not wait until they are “finished”.
- Provide mock fixtures/contracts to the frontend early.
- Add validation for model outputs and API inputs.
- Preserve source URLs and evidence throughout every stage.
- Handle timeouts, empty search results, malformed structured output, API failures, and partial results.
- Distinguish live-search results from fallback records.
- Run the end-to-end demo journey repeatedly.
- Ensure persistent state survives navigation and reload/re-entry to the session.
- Freeze a known-good version before the final review.

**Deliverable:** A working FastAPI + SQLite application that orchestrates the modules and supports the complete frontend journey.

---

### Member 4 — Frontend & User Experience Developer (newer member)

**Owns:** Stitch design direction, frontend implementation, user interaction, dashboard and API presentation.  
**Scope:** Give this member clear ownership of the UI, with mock data and a stable API contract. Stitch and Antigravity accelerate work but do not remove the need to test the generated code.

#### A. Design system and screens — P0

Use Stitch to establish a consistent visual system and generate/iterate key screens:

1. Landing / product introduction.
2. Discovery-mode selection (Guided Discovery / Discover All).
3. Initial user-context form.
4. Discovery loading/progress state.
5. Consolidated-question flow, with answer, unknown, prefer-not-to-answer, and visible skip actions.
6. Scheme results dashboard/cards.
7. Scheme details and source/evidence view.
8. Optional scheme-specific eligibility view.
9. Document checklist and ordered action-plan view.
10. Empty, partial-result, error, and session-restoration states.

Aim for a trustworthy civic-tech interface: clear information hierarchy, readable text, accessible form controls, visible sources, understandable status labels, and concrete next actions. Avoid making the whole app a generic chatbot. Conversation can collect context, but results and plans should be structured dashboard content.

#### B. Frontend implementation — P0

- Use the team's existing stack; if starting new, use the stack agreed with Member 3.
- Convert the Stitch design into reusable components.
- Implement navigation and form state.
- Build the context form and discovery-mode selection.
- Build the consolidated questionnaire, including skip/unknown states.
- Render scheme cards with status, explanation, and official source links.
- Render scheme details and requirements.
- Render document requirements, shared prerequisites, graph or simplified dependency visualization, and ordered checklist.
- Show progress/loading states and handle empty/error/partial results.
- Make the main flow usable at the presentation screen size and reasonably responsive.

#### C. Mock-first development — start immediately

Do not wait for the backend. Build against mock data matching the shared API schema:

- A collection of several candidate schemes.
- Different status labels, including potential match and more information needed.
- Source links and verification indicators.
- A consolidated question batch with answered/skipped examples.
- One shared document prerequisite across two schemes.
- An action plan with ordered tasks.

Once the API is ready, replace mocks with actual responses without redesigning the data model.

#### D. API integration — P0

- Connect context submission and session creation.
- Trigger discovery and show progress.
- Load candidate results and scheme details.
- Submit answers and skipped/unknown states.
- Display updated assessments.
- Load the document plan.
- Persist progress through the session API.
- Handle failed requests and allow a sensible retry or return path.

#### E. Accessibility, clarity, and final polish

- Use plain language; explain why information is requested.
- Make optional questions visibly optional and skipping easy.
- Do not use color alone to communicate eligibility status.
- Keep official sources easy to open.
- Never label the user “eligible” as though an authority has confirmed it.
- Ensure buttons work and no core demo path contains dead controls.
- Remove placeholder content from the demo path.
- Check long names, long source URLs, small screens, and loading states.

**Deliverable:** A polished frontend that works with mock data early and with real backend responses before the final review.

#### F. What not to assign to this member

Do not make this member responsible for database design, search-provider setup, agent architecture, the eligibility engine, dependency-graph algorithms, or overall integration. If the UI is ready early, ask them to help test the demo, improve accessibility, or implement a contained optional UI feature.

---

## 5. Shared data contracts

The team must agree on these structures before building independently. The examples below are illustrative; field names can be changed during the initial contract meeting, but should not drift afterward.

### 5.1 Scheme record

```json
{
  "id": "scheme_001",
  "name": "Example Scholarship",
  "summary": "Financial assistance for eligible students.",
  "government_level": "state",
  "department": null,
  "target_group": ["students"],
  "requirements": [
    {
      "id": "req_001",
      "attribute": "annual_family_income",
      "criterion": "Published income limit from official guideline",
      "operator": "lte",
      "value": null,
      "status": "unverified",
      "source_url": "https://example.gov.in/guideline",
      "evidence": null
    }
  ],
  "benefit": null,
  "documents": [],
  "application_steps": [],
  "application_url": null,
  "official_sources": [],
  "verification_status": "not_verified",
  "uncertainties": [],
  "source_type": "live_search"
}
```

Do not leave illustrative placeholder values in actual records. Unknown fields should be explicitly `null`, empty with a documented meaning, or marked unverified—not guessed.

### 5.2 Question record

```json
{
  "id": "q_annual_income",
  "attribute": "annual_family_income",
  "question": "What is your approximate annual family income?",
  "input_type": "range",
  "options": [],
  "required_for_assessment": false,
  "why_asked": "This information is used by several schemes found in this search.",
  "related_scheme_ids": ["scheme_001", "scheme_002"],
  "sensitivity": "high",
  "status": "unanswered"
}
```

A question should have a stable ID so the system can avoid repeating it. Support `answered`, `skipped`, `unknown`, and `prefer_not_to_answer` states (or an equivalent explicit representation).

### 5.3 Assessment record

```json
{
  "scheme_id": "scheme_001",
  "status": "more_information_needed",
  "explanation": "The income criterion cannot be assessed because the answer is missing.",
  "requirements": [
    {
      "requirement_id": "req_001",
      "status": "unknown",
      "reason": "No income information was provided.",
      "source_url": "https://example.gov.in/guideline"
    }
  ],
  "last_assessed_at": null
}
```

### 5.4 Document and dependency records

Use stable IDs for documents/tasks and explicit dependency edges. Each edge should retain the source supporting it.

```json
{
  "id": "doc_income_certificate",
  "name": "Income certificate",
  "status": "needed",
  "required_by_scheme_ids": ["scheme_001", "scheme_002"],
  "dependencies": [],
  "source_urls": ["https://example.gov.in/guideline"]
}
```

### 5.5 Session and persistence rules

- Use a random session ID; no mandatory login for the MVP.
- Store only information needed for discovery, assessment, and user-requested progress.
- Persist user answers and skipped states distinctly.
- Freeze the candidate list for the current discovery run after consolidated questions are generated.
- Preserve evidence/source links at criterion level where possible.
- Provide a clear reset/delete-session action.
- Communicate that SQLite persistence means data is retained according to the application's actual cleanup policy. Do not claim data is temporary if it is stored.

---

## 6. MVP scope and feature prioritization

### P0 — Must work for the final review

- Guided Discovery and Discover All (within supported categories).
- Real live search integration.
- A limited but useful set of relevant schemes.
- Normalized scheme information with official source links/evidence.
- Verification/uncertainty states.
- Eligibility assessment and explanations.
- Cross-scheme consolidated questions.
- Skip/unknown handling.
- Reassessment after answers.
- Scheme browsing/details.
- Verified document checklist.
- Basic deterministic dependency graph / ordered action plan.
- SQLite session and workflow persistence.
- Working frontend and backend integration.
- Basic error states and a full end-to-end demo.

### P1 — Add only after the P0 flow works

- Email draft generation.
- Downloadable `.ics` calendar event.
- User-reported progress and outcome tracking.
- Optional scheme-specific eligibility interview, if not already included in P0.
- Rejection analysis and verified recovery draft.
- More polished dependency visualization.
- One supported additional language, if it can be tested reliably.
- Voice input (see Section 10; not an assumed P1 deliverable).

### P2 — Do not target during the 24-hour build unless everything else is stable

- Real WhatsApp/SMS reminders.
- Extensive additional scheme categories.
- Long-term saved profiles/accounts.
- Additional official API/data integrations.
- Automated portal operation or application submission.
- Automatic payment verification.
- Automatic appeal filing.
- Collection/storage of large quantities of identity documents.

### Cut order if behind

Cut in this order:

1. Voice input and voice output.
2. Extra languages that are not already working reliably.
3. Automated notifications and messaging integrations.
4. Complex rejection recovery.
5. Advanced graph visualization (retain the graph logic or a clear ordered list).
6. Separate LLM instances/autonomous-agent infrastructure.

Do **not** cut live search, source links, uncertainty handling, consolidated questions, or the complete core journey. A limited verified fallback may be used for demo reliability, but it must be identified as fallback data.

---

## 7. Hackathon execution timeline and milestones

The event schedule is the constraint. The first review arrives quickly, so the first target is a thin vertical slice, not a complete product. The final review starts at 8:30 AM on November 1.

### October 31 — 3:00–4:00 PM: Registration & Welcome

- Check in and collect badges.
- Confirm team location, internet access, power, and device setup.
- Ensure every member can access the repository and required accounts.

### October 31 — 4:00–4:15 PM: Opening & Kickoff

- Confirm rules, deliverables, judging format, and any submission constraints.
- Confirm which API/model/search services are available and permitted.
- Do not spend this time changing the product direction.

### October 31 — 4:15–5:30 PM: Coding Session 1

**Goal: shared contract and independent foundations.**

| Member | Work during this block | Checkpoint by 5:30 PM |
|---|---|---|
| Member 1 — Discovery/Action | Review existing research; select search approach; implement one real search/extraction path; list verified fallback candidates. | At least one real candidate can be returned in the shared scheme shape, or an identified provider blocker plus useful fallback records. |
| Member 2 — Eligibility/Planning | Define requirement and assessment structures; implement a first simple criterion assessment; outline consolidated question mapping. | A sample scheme can be assessed with known/unknown answers. |
| Member 3 — Lead/backend | FastAPI app, SQLite initialization, session creation, shared schema/API contract, repository setup. | Backend runs; session can be created; contract is agreed. |
| Member 4 — Frontend | Stitch visual direction and essential screen designs; create frontend shell using mock data. | Landing/context/results shells run locally. |

**Team checkpoint:** All members must exchange schemas/interfaces before building further. Identify blockers early.

### October 31 — 5:30–6:00 PM: Evening Snacks

- Take the break.
- Briefly identify blockers and confirm the first-review demo flow.
- Do not expand scope.

### October 31 — 6:00–7:00 PM: Coding Session 1 continued

**Goal: prepare the first review vertical slice.**

| Member | Target |
|---|---|
| Member 1 | Discovery can return real or clearly labelled fallback scheme records with source links. |
| Member 2 | First assessment result and missing-information explanation are available. |
| Member 3 | Backend can accept user context and call discovery; initial result can be returned. |
| Member 4 | Frontend can submit context and display scheme cards/source links using mock or real API data. |

#### October 31 — 7:00–8:15 PM: Review Round 1

Show, honestly:

1. The user context and discovery scope.
2. A live search result or clearly labelled fallback result.
3. Scheme information and source links.
4. The intended consolidated-question flow, preferably a working first version.
5. The architecture and the remaining build milestones.

Do not claim that unimplemented features are working. Ask judges for feedback on product direction and the most important missing functionality.

### October 31 — 8:15–9:15 PM: Dinner Break

Rest and make one scope adjustment based on review feedback. Do not restart the architecture unless a critical issue requires it.

### October 31 — 9:15 PM–12:05 AM: Coding Session 2

**Goal: complete discovery → consolidated questions → reassessed results.**

| Member | Work |
|---|---|
| Member 1 | Improve search/extraction, source evidence, deduplication, and fallback behavior. Keep Action Agent optional. |
| Member 2 | Finish requirement normalization, consolidated question deduplication, skip/unknown states, and reassessment. Begin basic document requirement aggregation. |
| Member 3 | Persist scheme collection/questions/answers; implement orchestration and connect the two agent modules. |
| Member 4 | Finish question flow, answer/skip interactions, results cards, scheme detail view, and real API integration. |

**Midnight target:** A user can enter context, receive scheme candidates, answer or skip a consolidated question batch, and see updated assessment statuses without losing state.

### November 1 — 12:05–1:30 AM: Midnight Snacks and Games

- Take the break.
- Before leaving the code, commit a known-good state and ensure no one has uncommitted critical work.

### November 1 — 1:30–7:30 AM: Coding Session 3

**Goal: finish the plan, integrate, test, and stabilize.**

#### 1:30–3:00 AM — Document planning and action-plan UI

| Member | Work |
|---|---|
| Member 1 | Verify extracted requirements/source evidence; implement an Action Agent scaffold and, only if ready, one email or `.ics` output. |
| Member 2 | Implement shared document aggregation, deterministic dependency graph, and ordered checklist. |
| Member 3 | Integrate planning output, persist checklist progress, complete session restoration, and handle errors. |
| Member 4 | Build checklist/action-plan UI and show shared prerequisites clearly. |

#### 3:00–4:30 AM — Full end-to-end integration

Run the actual frontend and backend together. Verify:

- Session creation and restoration.
- Live discovery and source links.
- Fallback labeling if fallback is used.
- Consolidated question generation.
- Answering, skipping, not sure, and prefer-not-to-answer.
- Updated eligibility assessments.
- Scheme details and official source links.
- Document checklist and dependency ordering.
- Persistence after navigation/reload.

Fix integration defects before adding optional functionality.

#### 4:30–5:30 AM — Reliability and optional-feature gate

Test:

1. Search returns no results.
2. Search provider times out or fails.
3. A source omits a required detail.
4. The user skips an important question.
5. A model returns malformed or incomplete structured output.
6. A scheme has contradictory or unverified criteria.
7. A document dependency lacks evidence.
8. A session is restored after the user leaves the page.

At the end of this block, make a go/no-go decision on voice using Section 10. Do not start voice if any P0 journey is broken.

#### 5:30–6:30 AM — Polish and final fixes

- Fix the highest-impact usability issues.
- Improve status explanations and source visibility.
- Improve the graph or present a clear ordered checklist if visualization is unstable.
- Add one P1 action feature only if the core journey is stable.
- Do not add large new dependencies or refactor working architecture.

#### 6:30–7:30 AM — Freeze and rehearsal

- Stop major feature development.
- Create a known-good commit/tag or branch for the demo.
- Run the exact presentation scenario end-to-end.
- Confirm demo data and source links.
- Prepare a permitted backup recording/screenshots if helpful.
- Ensure every member can explain the whole system and their own contribution.

### November 1 — 7:30–8:30 AM: Breakfast

Rest, then have one designated person run the demo from a clean starting state. Avoid risky last-minute changes.

### November 1 — 8:30–10:00 AM: Review Round 2 (Final Review)

Demonstrate the complete discovery-to-action-plan experience. Prioritize working behavior, source-grounded claims, and clear explanations over architecture slides.

### November 1 — 10:00–11:30 AM: Announcement of Top 8

If selected, use the available time for presentation preparation and high-impact fixes only. Keep the stable demo version intact.

### November 1 — 11:30 AM–12:30 PM: Lunch and Finalist Presentation Preparation

- Finalize the pitch narrative.
- Assign speaking portions.
- Test the demo environment again.

### November 1 — 12:30–2:15 PM: Final Presentation

Present the problem, differentiators, working journey, impact, limitations, and responsible design. Every feature claim must match what is actually implemented.

### November 1 — 2:15–2:45 PM: Judges' Deliberation

Keep the demo environment available and team members ready for questions.

### November 1 — 2:45–3:00 PM: Closing Ceremony and Winner Announcement

---

## 8. Demo scenario and presentation narrative

### Recommended scenario

Use one realistic Karnataka-focused student seeking financial assistance. This scenario can naturally demonstrate scholarships and fee concessions, missing income/education details, shared documents, and a prioritized action plan.

Do not invent an actual scheme or eligibility threshold for the scenario. Use real official source information for schemes shown in the demo. If you simulate later events such as rejection or approval, label them explicitly as simulated.

### Core demo sequence

1. **Start:** User chooses Guided Discovery or Discover All.
2. **Context:** User gives location, education/life situation, and relevant basic information.
3. **Discovery:** Unlocked searches and displays relevant schemes with official sources.
4. **Consolidated questions:** Unlocked explains that it found candidate schemes and asks a small deduplicated batch of missing questions.
5. **Skip behavior:** User answers some questions and skips one. The skipped answer remains unknown.
6. **Reassessment:** Scheme statuses and explanations update without treating unknown as a negative.
7. **Scheme details:** User opens one scheme and sees the criteria, sources, benefits/documents if verified, and uncertainty.
8. **Planning:** Unlocked combines verified document requirements and highlights a shared prerequisite/dependency.
9. **Next action:** User sees an ordered checklist. If implemented, show an email draft or `.ics` download.
10. **Responsible boundary:** Explain that the user reviews and submits; Unlocked does not guarantee approval or payment.

### What makes the demo convincing

- Show the system's reasoning in terms the user understands.
- Make at least one source link easy for judges to inspect.
- Show the difference between a missing answer and a negative answer.
- Show the consolidated-question mechanism actually reducing repetition.
- Show the dependency graph/list producing an actionable order.
- Keep the demo focused on one scenario rather than rapidly browsing many unrelated schemes.

---

## 9. Evaluation strategy — 50 points total

Each criterion is worth 10 points. The team should deliberately demonstrate evidence for all five.

### 9.1 Innovation & Creativity — 10 points

Show that Unlocked is not a generic chatbot or a static scheme directory.

Evidence to demonstrate:

- Cross-scheme consolidated questions.
- Adaptive reassessment after user responses.
- Shared document prerequisites and dependency-aware planning.
- Follow-through artifacts or recovery when implemented.

**Owners:** Members 1 and 2 build the logic; Member 4 makes it visible; Member 3 integrates the flow.

### 9.2 Technical Implementation — 10 points

Show actual working integration:

- Live search, not a prompt pretending to search.
- Structured scheme extraction with source evidence.
- Validated eligibility assessment.
- Deterministic question tracking and graph ordering.
- SQLite-backed state.
- Working API/frontend integration.
- Graceful failure handling.

**Owners:** Members 1, 2, and 3; Member 4 for frontend integration.

### 9.3 Design & User Experience — 10 points

Make it easy to understand:

- What schemes were found?
- Why might each be relevant?
- What information is missing?
- What documents are needed?
- What should the user do first?
- Where can the user verify the information?

Use structured dashboard components rather than presenting every result as chat text. Show status explanations and sources clearly. Do not rely on color alone.

**Owner:** Member 4, supported by the quality of structured data from the other members.

### 9.4 Impact & Practicality — 10 points

Show a plausible user problem and how the workflow reduces the work needed to pursue a benefit. Explain how consolidated questions and shared prerequisites reduce repetitive effort. Be honest about eligibility uncertainty and the boundary between assessment, application, approval, and receipt.

**Owners:** All members.

### 9.5 Presentation & Demo — 10 points

Rehearse a short, predictable journey. Have one primary presenter/navigator, but let technical owners explain their parts when asked. Use actual working functionality and clearly identify any simulated event or fallback data.

**Owners:** All members.

---

## 10. Voice input — when to build it, and whether to build it at all

### Recommendation: do not make voice input part of the initial build

The handoff explicitly marks voice as optional and says it must not block the core flow. It also states that interaction mode (text/voice) is separate from discovery scope (Guided Discovery/Discover All).

For this 24-hour hackathon, voice input is **not P0**. The team should assume it will not be implemented unless the entire P0 journey is already stable.

### Why voice is lower priority

Voice can improve accessibility, especially for users who are more comfortable speaking than typing. However, it adds extra work that is not necessary to prove Unlocked's core innovation:

- Microphone permissions and browser/device compatibility.
- Speech recognition and transcription errors, including local names and scheme terminology.
- Language/accent handling.
- Editing and confirming misunderstood answers.
- Extra UI states for recording, listening, errors, and retry.
- Potential privacy/consent explanations for audio processing.
- More integration and demo failure points.

A voice interface that transcribes a user's answer incorrectly can undermine trust in a benefits assistant. The text journey is easier to test and makes it clearer what information has actually been provided.

### Decision gate and timing

**Do not work on voice during Coding Session 1 or the early part of Session 2.**

At approximately **4:30–5:30 AM on November 1**, evaluate the following checklist:

- [ ] A new user can complete the text-based discovery flow.
- [ ] Live search returns results, or a clearly labelled fallback works when search fails.
- [ ] Official sources remain attached to schemes and requirements.
- [ ] Consolidated questions work across multiple schemes.
- [ ] Answer, skip, and unknown states behave correctly.
- [ ] Assessments update without treating missing data as negative.
- [ ] The document checklist/action plan works.
- [ ] SQLite preserves the session and progress.
- [ ] The frontend and backend are integrated.
- [ ] The complete flow has been run successfully at least once after the latest changes.

**If even one of the core items is unstable: skip voice entirely.** Use the remaining time for reliability, source verification, UX, and rehearsal.

**Only if every item is stable:** consider a minimal voice-to-text input as a stretch feature during the polish window, and only if the team can test it on the actual demo browser/device. Do not build a separate voice agent, continuous listening, voice output, or a multilingual voice stack.

### What a minimal voice feature should look like

If the gate passes, implement only:

- A microphone button beside a text input.
- User-initiated recording/listening, with a clear recording indicator.
- Speech converted to editable text.
- The user reviews/corrects the transcription before submitting.
- A graceful fallback to typing if permission or recognition fails.
- No automatic submission of transcribed answers.

Voice should be an alternate way to fill the same text fields. It should not create a separate discovery flow or change the agent architecture. Do not claim support for languages or browsers that have not been tested.

### How to describe voice to judges

If not implemented: say it is a planned accessibility extension, deliberately deferred so the team could prioritize source-backed discovery, uncertainty-aware assessment, and reliable planning.

If implemented: demonstrate one short input, show the editable transcription, and continue through the same text-based workflow. Do not let voice dominate the presentation.

---

## 11. Privacy, consent, and responsible behavior

Unlocked may handle income, education, caste/category, and other personal circumstances. Treat privacy as a product requirement.

- Collect only information needed for the requested discovery/assessment.
- Explain why a sensitive question is being asked.
- Let the user skip optional questions; explain that this may limit assessment accuracy.
- Do not request Aadhaar numbers, passwords, OTPs, or unnecessary identity-document scans.
- Avoid storing document scans or large quantities of identity data.
- Use random session IDs; do not require permanent accounts for the MVP.
- Store only data needed for the workflow and user-requested progress.
- Provide a clear reset/delete-session option.
- Set an appropriate retention/cleanup policy and describe actual behavior accurately.
- Minimize personal information sent to model providers.
- Avoid logging personal answers unnecessarily.
- Check provider/hosting data-handling assumptions before making privacy claims.
- Keep email drafts and other consequential outputs under user review.
- Clearly distinguish live verified facts, unverified information, fallback data, user-reported outcomes, and simulated demo events.

Do not claim that no data is stored anywhere unless the complete system—including provider calls, server logs, and persistence—has been checked.

---

## 12. Quality assurance and test plan

Create a small set of known scenarios rather than relying only on ad hoc clicking.

### Scenario A — enough information for some requirements

- User provides the relevant attributes.
- Several schemes are returned.
- Deterministic criteria are assessed.
- Missing requirements are still shown as unknown.

### Scenario B — partial information and skipped question

- User skips an important consolidated question.
- The answer remains unknown.
- Relevant schemes remain visible.
- The assessment says more information is needed, not ineligible.

### Scenario C — shared document

- Two verified schemes require the same document.
- The document appears once in the shared checklist.
- The graph/list shows the schemes it supports.
- The dependency is backed by source references.

### Scenario D — search failure

- Live search times out or returns no usable results.
- The UI explains the limited-results/failure state.
- If fallback data is used, it is clearly identified.
- The system never fabricates live results.

### Scenario E — uncertain or contradictory source

- The relevant field is marked uncertain/unverified.
- The system avoids a definitive eligibility claim.
- The source is visible to the user.

### Scenario F — persistence

- User enters context and answers questions.
- The browser navigates away/reloads.
- The session can be restored with progress intact.
- Reset/delete works as intended.

### Scenario G — action artifact (if implemented)

- Email content uses only supplied/verified details.
- Calendar event uses a confirmed date/time and timezone.
- The output is reviewed by the user; nothing is sent automatically.
- Simulated outcomes are labelled.

---

## 13. Collaboration, Git, and integration rules

1. **One shared contract:** Member 3 publishes the schema/API notes. Changes must be communicated before implementation changes propagate.
2. **Parallel modules:** Members 1 and 2 implement separate agent modules; Member 4 uses mocks matching the contract.
3. **Small branches:** Use one branch per feature/workstream and merge small, working changes frequently.
4. **Integration owner:** Member 3 reviews cross-module changes and keeps the demo branch runnable.
5. **No late rewrites:** Do not replace the framework, database, search provider, or workflow architecture late in the hackathon without a critical reason.
6. **Commit known-good states:** Make a working commit at each major checkpoint, particularly before breaks and the final freeze.
7. **Definition of done:** A feature is not complete merely because a function exists. It must be integrated, return the agreed schema, handle expected failure states, and be reachable through the actual demo flow when it is part of P0.
8. **Communicate blockers early:** If an API key, provider, or library is unavailable, report it immediately and activate the smallest fallback. Do not discover the blocker at integration time.

---

## 14. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Search provider/API unavailable or slow | Discovery blocked | Test access early; prepare clearly labelled verified fallback data. |
| Official pages are hard to parse | Poor extraction | Limit initial categories/schemes; preserve source URLs; mark uncertain fields rather than guessing. |
| LLM invents criteria or URLs | Harmful/inaccurate advice | Require evidence; validate output; keep source and uncertainty fields; do not trust structured output by itself. |
| Different members use different schemas | Integration failure | Freeze shared contract in the first coding block. |
| Frontend waits for backend | Lost parallel development time | Use mock data from the start. |
| Question engine repeats questions | Poor UX | Stable attribute/question IDs and deterministic question history. |
| Skipped answer becomes “no” | False ineligibility | Explicit answer-state model and tests. |
| Graph includes invented dependency | Misleading plan | Create edges only from verified source requirements. |
| Lead becomes integration bottleneck | Components remain disconnected | Members own callable modules; frontend integrates its own API calls; merge early. |
| Too much scope | Core flow unfinished | P0/P1/P2 priorities and strict cut order. |
| Voice consumes debugging time | Demo risk | Defer until P0 gate passes; use editable transcription only. |
| Demo relies on a live external service | Unpredictable presentation | Test beforehand and prepare labelled fallback; never misrepresent fallback as live. |
| Personal data is over-collected or retained unclearly | Trust/privacy issue | Data minimization, session reset, honest retention statement, no unnecessary ID scans. |

---

## 15. Final completion checklist

### Product
- [ ] User can choose Guided Discovery or Discover All.
- [ ] User can enter basic context.
- [ ] System performs real search or clearly identifies a fallback.
- [ ] Schemes show official source links and verification/uncertainty state.
- [ ] Requirements are represented in a consistent structure.
- [ ] System creates consolidated cross-scheme questions.
- [ ] User can answer, skip, or mark unknown/prefer not to answer.
- [ ] Skipped/unknown information remains unknown.
- [ ] All candidates are reassessed after answers.
- [ ] Relevant schemes remain browseable even when eligibility is unclear.
- [ ] Scheme details show requirements, evidence, documents, and application information where verified.
- [ ] Document checklist uses source-supported requirements.
- [ ] Shared prerequisites and task ordering are visible.
- [ ] At least one complete demo journey works.

### Engineering
- [ ] FastAPI backend runs.
- [ ] SQLite persists sessions and user progress.
- [ ] Shared contracts are consistent.
- [ ] Four logical stages are implemented as modules or clearly defined workflow functions.
- [ ] Workflow controls stage order.
- [ ] LLM outputs are validated.
- [ ] Errors and empty states are handled.
- [ ] Source evidence survives across the workflow.
- [ ] A known-good demo commit exists.

### UX and presentation
- [ ] Essential screens are implemented.
- [ ] Frontend uses actual backend responses for the demo.
- [ ] Loading, empty, partial, and failure states are understandable.
- [ ] No dead buttons on the demo path.
- [ ] Eligibility wording does not imply official approval.
- [ ] The demo clearly distinguishes fallback/simulated content.
- [ ] Every member can explain the product and their contribution.

### Optional features
- [ ] Email draft and/or `.ics` export only if P0 is stable.
- [ ] Voice only if the Section 10 gate passed and the implementation was tested; otherwise explicitly defer it.

---

## 16. Decisions that remain open

These were not finalized in the source documents and must be decided by the team during the initial setup block:

- Exact model provider/model and API budget.
- Exact live web-search provider/tool.
- Whether the frontend already has a stack that should be retained.
- Exact SQLite schema and cleanup/retention period.
- Which Karnataka-focused scheme categories and fallback examples are practical for the demo.
- Whether email draft, `.ics`, or both can be completed after P0.
- Whether one additional language can be reliably supported.
- Whether voice passes the explicit go/no-go gate; it is not assumed for the MVP.

Do not let these open decisions delay the first vertical slice. Choose the simplest workable option, document it, and proceed.

---

## 17. Final team principle

**Unlocked should be judged by the quality of the journey it completes, not the number of agents, models, or features it claims to have.**

A trustworthy scheme result with an official source, an honest explanation of what is unknown, a non-repetitive question flow, and a useful document plan is more valuable than a large collection of unverified schemes or an impressive voice demo that fails during the presentation.

Build the core journey first. Make the reasoning visible. Preserve evidence. Let the user remain in control. Add optional capabilities only when they strengthen—not threaten—the working product.
