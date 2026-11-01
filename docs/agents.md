# Production-Grade Agent Specifications & Interface Contracts

> **Project:** Unlocked — Karnataka Benefits Discovery & Follow-Through Assistant  
> **Target LLM:** Gemini Flash via `google-genai` SDK  
> **Orchestrator:** Python / FastAPI Deterministic State Machine  
> **Persistence:** SQLite Session Store  

---

## 1. Architectural Philosophy & Execution Model

The four "agents" in Unlocked are **specialized functional modules**, not unconstrained autonomous loops. They execute in a strict, deterministic sequence coordinated by the central orchestrator (`orchestrator.py`).

```text
User Context ──> [1. Discovery Agent] ──> Frozen Candidate Pool
                                                │
                                                ▼
User Answers <── [2. Eligibility Agent] <───────┤
     │          (Consolidated Questions)        │
     ▼                                          ▼
[2. Reassessment Engine] ─────────────────> Assessed Schemes
                                                │
                                                ▼
                                    [3. Document & Planning Agent]
                                       (Deterministic DAG Sort)
                                                │
                                                ▼
                                    [4. Action Agent (P1)]
                                       (User-Reviewed Artifacts)
```

### Core Invariants
1. **Source Grounding**: No requirement, threshold, or document dependency exists in the system without an official source URL (`source_url`) and text excerpt (`evidence`).
2. **Non-Destructive Unknowns**: Skipped questions or missing user data evaluate to `unknown`. `unknown` is **never** coerced to `not_eligible` or `failed`.
3. **Deterministic Structure**: Sorting tasks, question ranking, and graph cycles are executed in deterministic Python. The LLM is used solely for natural language parsing, semantic mapping, and communication synthesis.

---

## 2. Agent 1: Discovery Agent

* **Owner:** Member 1 (Research & Agentic Workflow Engineer)
* **Status / Note:** Base search/scraping is pre-built; Member 1 owns candidate extraction, schema mapping, and fallback data integrity. Candidate outputs must strictly conform to the shared contracts below so Member 2's normalization and planning pipeline can consume them.
* **LLM Engine:** Gemini Flash (`gemini-flash-lite-latest` or `gemini-1.5-flash` via `google-genai`). Note: `gemini-2.5-flash` currently returns 404 on standard free-tier API keys.

### 2.1 Pydantic Data Contracts

```python
from enum import Enum
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, field_validator

class RequirementVerification(str, Enum):
    verified = "verified"
    unverified = "unverified"
    uncertain = "uncertain"

class Operator(str, Enum):
    lte = "lte"
    lt = "lt"
    gte = "gte"
    gt = "gt"
    eq = "eq"
    neq = "neq"
    in_ = "in"
    not_in = "not_in"
    is_true = "is_true"
    is_false = "is_false"

class Requirement(BaseModel):
    id: str = ""  # filled by normalizer if omitted (e.g. scheme_id_req_1)
    attribute: Optional[str] = None  # canonical id from member2/attributes.py (e.g., 'annual_family_income', 'domicile_karnataka')
    criterion: str  # verbatim requirement phrase from official portal
    operator: Optional[Operator] = None
    value: Optional[Any] = None  # threshold value (e.g., 250000, ["SC", "ST"], None for is_true)
    status: RequirementVerification = RequirementVerification.unverified
    source_url: Optional[str] = None  # official .gov.in URL where this rule was stated
    evidence: Optional[str] = None  # verbatim sentence/paragraph containing the rule

class DocumentDependency(BaseModel):
    depends_on: str  # raw document name; normalized in planning
    source_url: Optional[str] = None
    evidence: Optional[str] = None

class DocumentRequirement(BaseModel):
    name: str  # official name of required certificate/document
    mandatory: bool = True  # whether this document is mandatory or optional
    source_url: Optional[str] = None  # official URL confirming this document is required
    evidence: Optional[str] = None  # verbatim excerpt mentioning the document requirement
    dependencies: list[DocumentDependency] = Field(default_factory=list)

class SchemeRecord(BaseModel):
    id: str  # normalized unique scheme slug, e.g., 'karnataka-ssp-post-matric'
    name: str  # official scheme title
    summary: Optional[str] = None  # plain-language 2-sentence summary of the scheme
    government_level: Optional[str] = "state"  # "state" | "central"
    department: Optional[str] = None  # administering department (e.g. Social Welfare Department)
    target_group: list[str] = Field(default_factory=list)
    eligibility_text: Optional[str] = None  # raw text for normalizer LLM extraction pass
    requirements: list[Requirement] = Field(default_factory=list)
    benefit: Any = None  # verified monetary or physical benefit amount
    documents: list[DocumentRequirement] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)
    application_url: Optional[str] = None
    deadline: Optional[str] = None  # ISO date (YYYY-MM-DD), only if verified
    deadline_status: Optional[Literal["upcoming", "expired", "not_published"]] = "not_published"
    deadline_source_url: Optional[str] = None
    official_sources: list[str] = Field(default_factory=list)  # verified official source links (.gov.in / .nic.in)
    verification_status: Literal["verified", "not_verified", "uncertain", "partially_verified", "unverified"] = "not_verified"
    uncertainties: list[str] = Field(default_factory=list)
    source_type: Literal["live_search", "fallback"] = "live_search"
```

> [!IMPORTANT]
> **Contract Rules for Member 1:**
> 1. **Documents must be objects** `{name, source_url, evidence}`, not plain strings. Plain strings have no source, so they will be left out of the action plan by Agent 3 (resulting in an empty checklist).
> 2. **Attribute IDs must match `member2/attributes.py`** (e.g., `domicile_karnataka`, NOT `karnataka_domicile`).
> 3. **Operators** must use `is_true` / `is_false` instead of `"boolean"`. Supported: `eq`, `neq`, `in`, `not_in`, `lt`, `lte`, `gt`, `gte`, `is_true`, `is_false`.
> 4. **Requirement status** on extraction is only `verified | unverified | uncertain`. `needs_clarification` is an assessment result produced by Agent 2, not an extraction status.
> 5. **JSON Contract Verification:** Member 1 can test candidate schemes against the contract using:
>    ```bash
>    python -m member2.check_member1 path/to/schemes.json
>    ```
> 6. **Compliance Adapter:** Member 1 maintains `discovery_agent/adapter.py` (`adapt_m1_to_m2_scheme` / `to_canonical_scheme`), which automatically maps raw extraction outputs into canonical `member2.models.SchemeRecord` instances with sourced documents and canonical attributes.
> 7. **Authority vs Applicability:** Karnataka-resident discovery searches both Central Government pan-India schemes and State schemes. Central queries target national portals (e.g. `myscheme.gov.in`, `agricoop.nic.in`, `scholarships.gov.in`) without district pinning. When deep-fetching Central schemes, other states' portals (e.g., `*.haryana.gov.in`) are excluded so other states' implementation rules are not copied.
> 8. **Geographical Conditions as Values:** State residency conditions must be mapped to `attribute="state", operator=Operator.eq, value="<State>"`, never ad-hoc `unmapped:<state>`. Agent 2 automatically evaluates other-state requirements as `not_satisfied` against the citizen's known domicile and suppresses questions about other states.
> 9. **Verification Vocabulary Safety:** Extractor verification statuses like `"uncertain"` are fully supported across `SchemeRecord`, `SchemeCriterion`, and `SchemeClaim` with safe fallback validators to prevent dropping useful schemes.
> 10. **Error-Tolerant Scheme Salvaging:** When extracted schemes (such as Vidyasiri) have an incomplete or malformed sub-item, the pipeline salvages the record item-by-item rather than discarding the entire scheme.
> 11. **Evidence-Based Source Authority:** Only official Central or Karnataka government portals (`.gov.in`, `.nic.in`) can verify Karnataka eligibility. Private or external state portals cannot independently establish Karnataka eligibility; claims backed only by such sources are marked `"uncertain"`.
> 12. **Application Deadline Calibration:** Deadlines require supporting official sources and are checked against current date (`2026-11-01`). Expired deadlines are marked with `deadline_status="expired"` and rendered prominently in red.
> 13. **Document Mandatory Tracking:** Document requirements retain `mandatory: bool` (default True; False for optional/conditional documents) and carry forward official source URLs and evidence directly into Agent 3's DAG planning.
> 14. **Discovery Diagnostics:** The discovery pipeline tracks and outputs execution metrics: queries generated, search results retrieved, unique results, schemes extracted, validation failures, duplicates removed, claims verified, and final schemes.

### 2.2 System Prompt & Extraction Schema

```text
You are the Discovery & Information Extraction Agent for Unlocked, an official Karnataka government welfare benefit discovery platform.

Your mission is to take raw web search excerpts / official guidelines and parse them into a structured SchemeRecord.

STRICT ACCURACY RULES:
1. NEVER invent eligibility criteria, income thresholds, or document requirements. If a criterion is not explicitly stated in the source text, do NOT assume it.
2. For every requirement, you MUST extract the exact sentence as 'evidence' and provide the 'source_url'.
3. Map requirements to standard canonical attribute names from member2/attributes.py:
   - 'annual_family_income' (INR per year)
   - 'domicile_karnataka' (boolean, is_true)
   - 'social_category' (e.g., 'SC', 'ST', 'OBC', 'General')
   - 'age' (integer)
   - 'education_level' (e.g., 'Class 10', 'Class 12', 'Diploma', 'Undergraduate', 'Postgraduate', 'Not studying')
   - 'course_type' (e.g., 'Engineering', 'Medical', 'Arts/Science/Commerce', 'Other')
   - 'year_of_study' (integer)
   - 'institution_type' (e.g., 'Government', 'Aided', 'Private')
   - 'is_minority' (boolean, is_true)
   - 'has_disability' (boolean, is_true)
   - 'employment_status' (e.g., 'Student', 'Employed', 'Self-employed', 'Unemployed')
   - 'previous_year_marks_percent' (float, percentage)
   - 'residence_area' (e.g., 'Rural', 'Urban')
   - 'household_card_type' (e.g., 'BPL', 'APL', 'Antyodaya', 'None')
4. If a document is required, provide its name, the page source URL, and the verbatim excerpt as evidence.
5. If the source is not an official .gov.in or .nic.in domain, mark verification_status as 'uncertain'.
```

### 2.3 Few-Shot Extraction Example

**Input Text (Snippet from Karnataka State Scholarship Portal guidelines):**
> "State Scholarship Portal (SSP) Post-Matric: Eligible students belonging to Scheduled Caste (SC) and Scheduled Tribe (ST) whose parents' annual income is less than or equal to Rs. 2,50,000/- per annum can apply online through https://ssp.postmatric.karnataka.gov.in. Compulsory documents include Aadhaar Card, Caste & Income Certificate (RD Number), and College Registration Number."

**Output JSON:**
```json
{
  "id": "karnataka-ssp-post-matric-scst",
  "name": "State Scholarship Portal (SSP) Post-Matric Scholarship for SC/ST",
  "summary": "Financial support for SC/ST students in post-matric studies with parental annual income up to Rs. 2.5 Lakhs.",
  "government_level": "state",
  "department": "Social Welfare Department, Government of Karnataka",
  "target_group": ["SC/ST students", "post-matric"],
  "requirements": [
    {
      "id": "karnataka-ssp-post-matric-scst_req_1",
      "attribute": "annual_family_income",
      "criterion": "Parents' annual income must be <= Rs. 2,50,000/- per annum",
      "operator": "lte",
      "value": 250000,
      "status": "verified",
      "source_url": "https://ssp.postmatric.karnataka.gov.in",
      "evidence": "whose parents' annual income is less than or equal to Rs. 2,50,000/- per annum"
    },
    {
      "id": "karnataka-ssp-post-matric-scst_req_2",
      "attribute": "social_category",
      "criterion": "Must belong to Scheduled Caste (SC) or Scheduled Tribe (ST)",
      "operator": "in",
      "value": ["SC", "ST"],
      "status": "verified",
      "source_url": "https://ssp.postmatric.karnataka.gov.in",
      "evidence": "Eligible students belonging to Scheduled Caste (SC) and Scheduled Tribe (ST)"
    }
  ],
  "benefit": "Maintenance allowance and fee reimbursement",
  "documents": [
    {
      "name": "Aadhaar Card",
      "source_url": "https://ssp.postmatric.karnataka.gov.in",
      "evidence": "Compulsory documents include Aadhaar Card"
    },
    {
      "name": "Income Certificate",
      "source_url": "https://ssp.postmatric.karnataka.gov.in",
      "evidence": "Caste & Income Certificate (RD Number)"
    },
    {
      "name": "Admission Proof",
      "source_url": "https://ssp.postmatric.karnataka.gov.in",
      "evidence": "College Registration Number"
    }
  ],
  "application_steps": [
    "Obtain RD number for Caste/Income certificate from Nadakacheri portal",
    "Register e-Attestation on SSP portal",
    "Submit online application before published deadline"
  ],
  "application_url": "https://ssp.postmatric.karnataka.gov.in",
  "official_sources": ["https://ssp.postmatric.karnataka.gov.in"],
  "verification_status": "verified",
  "uncertainties": [],
  "source_type": "live_search"
}
```

---

## 3. Agent 2: Eligibility & Verification Agent

* **Owner:** Member 2 (Eligibility, Verification & Planning Engineer)
* **Priority:** P0 (Core MVP)
* **Key Tasks:** 
  1. Requirement Normalization Matrix
  2. Consolidated Cross-Scheme Question Generation
  3. Reassessment Engine

### 3.1 Pydantic Data Contracts

```python
from enum import Enum
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, model_validator

class Sensitivity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class InputType(str, Enum):
    number = "number"
    range = "range"
    select = "select"
    boolean = "boolean"
    text = "text"

class RangeOption(BaseModel):
    label: str  # UI band label, e.g. "Below ₹1 lakh", "₹1 lakh – ₹2.5 lakh"
    min: Optional[float] = None
    max: Optional[float] = None  # inclusive; None = open-ended

class AnswerState(str, Enum):
    unanswered = "unanswered"
    answered = "answered"
    skipped = "skipped"
    unknown = "unknown"  # user said "not sure"
    prefer_not_to_answer = "prefer_not_to_answer"

class Answer(BaseModel):
    attribute: str
    state: AnswerState
    value: Any = None  # only preserved when state == AnswerState.answered

    @model_validator(mode="after")
    def _drop_value_unless_answered(self) -> "Answer":
        # A skipped answer must not carry a value that could later be compared.
        if self.state != AnswerState.answered:
            self.value = None
        return self

class Question(BaseModel):
    id: str  # "q_" + attribute, e.g. "q_annual_family_income"
    attribute: str  # underlying canonical attribute key
    question: str  # user-friendly civic question text
    input_type: InputType
    options: list[str] = Field(default_factory=list)  # for select, or ["Yes", "No"] for boolean
    ranges: list[RangeOption] = Field(default_factory=list)  # for input_type == range
    required_for_assessment: bool = False
    why_asked: str  # explains why this helps the search + scheme count
    related_scheme_ids: list[str] = Field(default_factory=list)
    sensitivity: Sensitivity
    status: AnswerState = AnswerState.unanswered
    allow_prefer_not_to_answer: bool = True

class RequirementStatus(str, Enum):
    satisfied = "satisfied"
    not_satisfied = "not_satisfied"
    unknown = "unknown"
    needs_clarification = "needs_clarification"
    unverified = "unverified"

class RequirementResult(BaseModel):
    requirement_id: str
    attribute: Optional[str] = None
    status: RequirementStatus
    reason: str
    criterion: str
    source_url: Optional[str] = None

class SchemeStatus(str, Enum):
    potential_match = "potential_match"
    more_information_needed = "more_information_needed"
    not_yet_verified = "not_yet_verified"
    unlikely_to_match = "unlikely_to_match"
    uncertain = "uncertain"

class Assessment(BaseModel):
    scheme_id: str
    status: SchemeStatus
    explanation: str
    requirements: list[RequirementResult] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)
    last_assessed_at: Optional[str] = None  # ISO timestamp (UTC)
```

> [!NOTE]
> **Key Contract Changes (plan.md §5.2 / member2):**
> 1. **Questions & Answers are Decoupled:** `Question` defines the form input; `Answer` represents the user's response or skip state.
> 2. **Income Range Formatting:** Range answers are submitted as `{"min": n|null, "max": n|null}` or a band label string from `Question.ranges`.
> 3. **Non-destructive Skip Representation:** "Not sure", skip, and "prefer not to answer" are stored as explicit `AnswerState` values, ensuring they are never coerced to false or zero.

### 3.2 Question Generation & Reassessment Engine (`member2`)

The eligibility verification and question ranking operate deterministically in Python:

```python
from member2 import (
    normalize_requirements,
    assess_schemes,
    reassess_schemes,
    generate_consolidated_questions,
    generate_scheme_questions,
    apply_answers,
)

# 1. Seed answers from the initial context form (status: answered)
answers, history = apply_answers({}, {}, context_form_answers)

# 2. Score and pick top consolidated questions (defaults to 5)
questions = generate_consolidated_questions(
    schemes=normalized_schemes,
    user_answers=answers,
    question_history=history,
    batch_size=5,
    rephrase_llm=None  # optional: rephrase_llm=default_client()
)

# 3. Apply submitted answers/skips (returns updated copies; never mutates inputs)
answers, history = apply_answers(answers, history, submitted_answers)

# 4. Reassess schemes against updated answers
assessments = reassess_schemes(normalized_schemes, answers)
```

**Question Scoring Formula:**
$$\text{Score} = 10 \times N_{\text{schemes}} + 4 \times N_{\text{reqs}} - \text{Penalty}_{\text{sensitivity}} - \text{Effort}$$
Where sensitivity penalty is 0 (low), 2 (medium), or 5 (high). Attribute questions already answered or previously asked in `history` are excluded from consolidated batches.

### 3.3 Assessment Roll-Up Logic

```text
Deterministic Scheme-Level Status Evaluation:
1. If ANY requirement is 'not_satisfied' -> 'unlikely_to_match'
2. Else if ANY requirement is 'unknown' -> 'more_information_needed'
3. Else if ANY requirement is 'needs_clarification' -> 'uncertain'
4. Else if ANY requirement is 'unverified' or scheme verification is not verified -> 'not_yet_verified'
5. Else (all verified requirements are satisfied) -> 'potential_match'
```

---

## 4. Agent 3: Document & Planning Agent

* **Owner:** Member 2 (Eligibility, Verification & Planning Engineer)
* **Priority:** P0 (Core MVP)
* **Execution Paradigm:** Pure deterministic graph construction & topological sort in Python.

### 4.1 Pydantic Data Contracts

```python
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

class DocStatus(str, Enum):
    have = "have"
    obtained = "obtained"
    needed = "needed"
    unknown = "unknown"

class ChecklistItem(BaseModel):
    id: str  # document id, e.g. "doc_income_certificate", "doc_aadhaar_card"
    name: str  # display title, e.g. "Income Certificate"
    status: DocStatus  # "needed" | "have" | "obtained" | "unknown"
    order: int  # 1-based sequential position in the prioritized action plan
    mandatory: bool = True  # whether this document is mandatory or optional
    required_by_scheme_ids: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)  # prerequisite document ids (plan §5.4)
    source_urls: list[str] = Field(default_factory=list)
    reason: str  # human-readable explanation, e.g. "Get this first: required before SSP e-Attestation."

class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["document", "scheme"]

class GraphEdge(BaseModel):
    source: str
    target: str
    relation: Literal["required_for", "prerequisite_of"] = "required_for"
    source_url: str = Field(min_length=1)  # edges without a source are never created

class ActionPlan(BaseModel):
    checklist: list[ChecklistItem] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    shared_prerequisites: list[str] = Field(default_factory=list)  # doc ids required by 2+ schemes
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    excluded_documents: list[str] = Field(default_factory=list)  # names dropped for lacking a source
```

> [!NOTE]
> **Key Contract Changes (plan.md §5.4 / member2):**
> 1. **Checklist & DAG Graph:** `ActionPlan` provides an ordered `checklist: list[ChecklistItem]` and structured graph `nodes` and `edges` for the frontend. There is no `ordered_tasks` or `prerequisites` list.
> 2. **Shared Prerequisites:** High-leverage documents that unlock 2 or more schemes are captured in `shared_prerequisites`.
> 3. **Document Statuses:** User document possession is tracked via `user_documents: dict[str, "have" | "obtained" | "needed" | "unknown"]`.

### 4.2 Deterministic DAG & Topological Sort (`member2`)

The planning engine executes deterministic topological sorting using NetworkX:

```python
from member2 import build_action_plan

# IMPORTANT: Call with keyword arguments after selected_schemes!
plan = build_action_plan(
    selected_schemes=schemes,
    user_documents={"doc_aadhaar_card": "have"},
    assessments=assessments,
)
```

**Sorting Order Invariant:**
- Documents already marked `have` or `obtained` do not block other tasks; their constraint edges are ignored by the topological sort and they are sequenced last in the checklist.
- The remaining documents are sorted deterministically using Kahn's algorithm with tie-breaking:
  $$\text{Sort Key} = (\text{is\_done},\, -\text{schemes\_reachable},\, \text{earliest\_verified\_deadline},\, \text{doc\_id})$$
- Graph cycles are automatically detected and broken with clear user warnings (`warnings`).

---

## 5. Agent 4: Action & Follow-Through Agent (P1)

* **Package:** `agent4/` (tests in `tests/agent4/`). Built by Member 2; plan.md originally assigned it to Member 1.
* **Priority:** P1 (wire up after the P0 flow works). Member 3's Round 1 plan has no `/api/actions` route yet.
* **Guardrail:** Generates **user-reviewed artifacts only**. Unlocked never sends emails, submits applications or calls application APIs.
* **Independence:** pure Python, no imports from `member2` or `discovery_agent`. The LLM is optional: any object with `complete_json(system, user) -> str`, e.g. `member2.default_client()`. Without one, deterministic templates are used. Failures never raise.
* **Full usage:** `agent4/README.md`; design choices: `agent4/DECISIONS.md`.

### 5.1 Public functions

| Function | Input | Output |
|---|---|---|
| `build_email_draft(request, *, llm=None)` | `EmailRequest {scheme, purpose, question, user_details, facts}` | `ActionArtifact` (`email_draft`) |
| `build_calendar_artifact(request, *, now=None)` | `CalendarRequest {scheme, kind: deadline\|appointment, event_date, date_confirmed_by_user, date_source_url, start_time, end_time, location}` | `ActionArtifact` (`calendar_ics`), or `status: needs_input` with `missing_fields` |
| `update_progress(progress, scheme_id, updates, *, now=None)` | saved `ApplicationProgress` (or `None`) + `[{field, state, simulated}]` | `ProgressResult {progress, follow_ups, warnings, summary}` |
| `analyse_rejection(scheme, notice_text, guidance, *, llm=None, simulated=False)` | user's notice text + official guidance passages `[{text, source_url}]` | `RejectionAnalysis {reason_quote, next_steps, supported, ...}` |
| `facts_from_scheme(scheme, *, attributes=None, limit=5)` | a scheme record | `list[SourcedFact]`: verified rules' exact quotes + links, de-duplicated, for `EmailRequest.facts` |
| `clarification_request(scheme, *, user_details=None)` | a scheme record | `EmailRequest` asking only about what is unclear (uncertain rules, pages that disagree, missing documents/process), quoting the rules; `None` if nothing is unclear. `clarification_points(scheme)` returns the points |
| `email_request_for_step(scheme, step, question, user_details)` | a sourced `NextStep` (or `None`) | `EmailRequest` for a correction / appeal / clarification email |

`scheme` may be a canonical `member2.models.SchemeRecord`, its dict, or any object/dict with `id` and `name`. Agent 4 reads `name`, `department`, `application_url`, `official_sources`, `deadline` + `deadline_source_url`, and optionally `contact_email` / `contact_phone` with their `*_source_url` (not produced by Agent 1 yet).

### 5.2 Pydantic data contract

```python
class ActionType(str, Enum):
    email_draft = "email_draft"
    calendar_ics = "calendar_ics"
    progress_update = "progress_update"
    rejection_assist = "rejection_assist"

class ActionArtifact(BaseModel):
    action_type: ActionType
    status: ArtifactStatus = "ready"            # "ready" | "needs_input"
    title: str
    body_content: str = ""                      # email text, or RFC 5545 calendar
    subject: Optional[str] = None
    target_destination: Optional[str] = None    # only a *sourced* official address
    instructions: str
    user_review_confirmed: bool = False
    filename: Optional[str] = None              # e.g. "<scheme>-deadline-2026-12-15.ics"
    mime_type: Optional[str] = None             # "text/plain" | "text/calendar"
    missing_fields: list[str] = []              # ask the user for these; never guessed
    source_urls: list[str] = []
    warnings: list[str] = []
    generated_by: str = "template"              # "template" | "llm"
```

### 5.3 Guarantees (enforced in Python, not by prompt)

* **Email:** any email address, link or phone number not from a sourced field (or the user's own question) becomes a `[placeholder]`. An LLM draft containing any number not found in the sources (an invented date, amount or reference number) is discarded and the template is used. The user's details are `{{tokens}}` that the LLM never sees.
* **Calendar:** RFC 5545 (CRLF, line folding, escaping, stable UID). Deadlines are all-day events; appointments are timed in Asia/Kolkata with a VTIMEZONE. A date is used only if the user confirmed it or it has a source; otherwise `needs_input`. Replaces the earlier `generate_ics_event` sketch (DTSTAMP equal to the deadline, deadlines at 09:00 UTC, no escaping).
* **Progress:** `submitted`, `decision`, `benefit_received` and `appointment_attended` are independent facts; none is inferred from another. Gaps become follow-up questions; contradictions are kept and flagged.
* **Rejection:** the notice is redacted (ID numbers, phones, emails) before the LLM sees it. A next step is kept only with a verbatim quote from a supplied guidance passage and its URL; otherwise `supported: false` and a clarification email is offered.

---

## 6. Central Orchestrator Interface & Session State Machine

* **Owner:** Member 3 (Technical Lead & Backend)
* **State Machine Diagram:**

```text
[EMPTY_SESSION]
       │
       ▼ POST /api/sessions (save context & scope)
[CONTEXT_INITIALIZED]
       │
       ▼ POST /api/discover
[DISCOVERY_COMPLETE] (Schemes frozen in SQLite)
       │
       ▼ GET /api/questions & POST /api/answers
[ASSESSMENT_UPDATED] (Statuses recalculated, unknowns preserved)
       │
       ▼ GET /api/plan
[PLAN_GENERATED] (Topological DAG computed)
       │
       ▼ POST /api/actions (P1)
[ACTION_ARTIFACT_READY]
```

### 6.1 Database Schema (SQLite)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    state_status TEXT NOT NULL,
    context_json TEXT NOT NULL,
    schemes_json TEXT,
    questions_json TEXT,
    answers_json TEXT,        -- mapping of attribute -> Answer object (preserves skip/unknown state)
    history_json TEXT,        -- mapping of question_id ("q_" + attr) -> AnswerState
    user_documents_json TEXT, -- mapping of doc_id -> "have"|"obtained"|"needed"|"unknown"
    plan_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase 9 Follow-Through, Reminders & Tokens Schema:
CREATE TABLE IF NOT EXISTS notification_preferences (
    session_id TEXT PRIMARY KEY,
    email TEXT,
    email_enabled INTEGER NOT NULL DEFAULT 0,
    categories_json TEXT NOT NULL DEFAULT '{}',
    consent_version TEXT NOT NULL DEFAULT 'v1',
    consent_at TIMESTAMP,
    disabled_at TIMESTAMP,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracked_applications (
    application_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    scheme_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    status_source TEXT NOT NULL DEFAULT 'user_reported',
    reported_submission_at TIMESTAMP,
    recovery_status TEXT,
    recovery_data_json TEXT,
    last_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    application_id TEXT,
    related_task_id TEXT,
    purpose TEXT NOT NULL,
    scheduled_at_utc TIMESTAMP,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    location TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    outcome_summary TEXT,
    outcome_details_json TEXT,
    status_source TEXT NOT NULL DEFAULT 'user_reported',
    follow_up_at_utc TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    application_id TEXT,
    appointment_id TEXT,
    event_type TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT,
    source TEXT NOT NULL DEFAULT 'user_reported',
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    application_id TEXT,
    appointment_id TEXT,
    notification_type TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'email',
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_html TEXT,
    body_text TEXT,
    scheduled_at_utc TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'scheduled',
    provider TEXT NOT NULL DEFAULT 'resend',
    provider_message_id TEXT,
    idempotency_key TEXT UNIQUE,
    sent_at_utc TIMESTAMP,
    delivered_at_utc TIMESTAMP,
    last_error TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS follow_up_tokens (
    token_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    appointment_id TEXT,
    application_id TEXT,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at_utc TIMESTAMP NOT NULL,
    revoked_at_utc TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 Master Orchestration Endpoints (`main.py` / `orchestrator.py`)

```python
from member2 import (
    default_client,
    normalize_requirements,
    assess_schemes,
    reassess_schemes,
    generate_consolidated_questions,
    apply_answers,
    build_action_plan,
)

@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(payload: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    # 1. Seed answers and history from context form (status: answered)
    initial_answers, initial_history = apply_answers({}, {}, payload.context)
    await db.create_session(
        session_id=session_id,
        context=payload.context,
        scope=payload.scope,
        answers=initial_answers,
        history=initial_history,
    )
    return SessionResponse(session_id=session_id, status="initialized")

@app.post("/api/discover")
async def run_discovery(session_id: str):
    session = await db.get_session(session_id)
    # 1. Member 1: Discovery module + compliance adapter
    raw_schemes = await discovery_agent.discover_schemes(session.context, session.scope)
    adapted_schemes = [discovery_agent.adapt_m1_to_m2_scheme(s) for s in raw_schemes]
    
    # 2. Member 2: Normalize once per discovery run with LLM; save normalized schemes!
    # They carry the 'normalized_by' marker that prevents repeat LLM calls.
    normalized_schemes = normalize_requirements(adapted_schemes, llm=default_client())
    await db.save_schemes(session_id, normalized_schemes)
    
    # 3. Assess with current answers and generate consolidated questions
    assessments = assess_schemes(normalized_schemes, session.answers)
    questions = generate_consolidated_questions(normalized_schemes, session.answers, session.history)
    
    await db.save_questions_and_assessments(session_id, questions, assessments)
    return {"status": "discovery_complete", "schemes_count": len(normalized_schemes), "questions": questions}

@app.post("/api/answers")
async def submit_answers(session_id: str, submitted: list[dict[str, Any]]):
    session = await db.get_session(session_id)
    # apply_answers updates states (answered, skipped, unknown) without losing state
    updated_answers, updated_history = apply_answers(session.answers, session.history, submitted)
    assessments = reassess_schemes(session.schemes, updated_answers)
    await db.update_session_answers(session_id, updated_answers, updated_history, assessments)
    return {"status": "reassessed", "assessments": assessments}

@app.get("/api/plan")
async def get_action_plan(session_id: str):
    session = await db.get_session(session_id)
    # Call build_action_plan with keyword arguments after selected_schemes
    plan = build_action_plan(
        session.schemes,
        user_documents=session.user_documents,
        assessments=session.assessments,
    )
    await db.save_plan(session_id, plan)
    return plan
```
