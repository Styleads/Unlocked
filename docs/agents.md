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
* **Status / Note:** Base search/scraping is pre-built; Member 2 will update/push the module into the repository. Member 1 owns candidate extraction, schema mapping, and fallback data integrity.
* **LLM Engine:** Gemini Flash (`gemini-2.5-flash` / `gemini-1.5-flash` via `google-genai`) with structured output enforcement.

### 2.1 Pydantic Data Contracts

```python
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

class RequirementSource(BaseModel):
    id: str = Field(description="Unique requirement ID (e.g., req_ssp_01)")
    attribute: str = Field(description="Canonical attribute key, e.g., 'annual_family_income', 'karnataka_domicile', 'caste_category'")
    criterion: str = Field(description="Exact verbatim requirement phrase from official portal")
    operator: Optional[Literal["lte", "gte", "eq", "in", "boolean"]] = Field(
        default=None, description="Comparison operator for deterministic checking"
    )
    value: Optional[Any] = Field(default=None, description="Threshold value (e.g., 250000, 'SC', True)")
    status: Literal["verified", "unverified", "needs_clarification"] = "unverified"
    source_url: str = Field(description="Official .gov.in URL where this rule was stated")
    evidence: Optional[str] = Field(default=None, description="Verbatim sentence/paragraph containing the rule")

class SchemeRecord(BaseModel):
    id: str = Field(description="Normalized unique scheme slug, e.g., 'karnataka-ssp-post-matric'")
    name: str = Field(description="Official scheme title")
    summary: str = Field(description="Plain-language 2-sentence summary of the scheme")
    government_level: Literal["state", "central"] = "state"
    department: Optional[str] = Field(default=None, description="Administering department (e.g. Social Welfare Department)")
    target_group: list[str] = Field(default_factory=list, description="Target demographic (e.g., ['post-matric students', 'OBC', 'rural'])")
    requirements: list[RequirementSource] = Field(default_factory=list)
    benefit: Optional[str] = Field(default=None, description="Verified monetary or physical benefit amount")
    documents: list[str] = Field(default_factory=list, description="List of required certificates/documents")
    application_steps: list[str] = Field(default_factory=list, description="Step-by-step application instructions")
    application_url: Optional[str] = Field(default=None, description="Direct portal application URL")
    official_sources: list[str] = Field(default_factory=list, description="List of all verified official source links")
    verification_status: Literal["verified", "not_verified", "uncertain"] = "not_verified"
    uncertainties: list[str] = Field(default_factory=list, description="Explicit notes on missing or ambiguous guidelines")
    source_type: Literal["live_search", "fallback"] = "live_search"
```

### 2.2 System Prompt & Extraction Schema

```text
You are the Discovery & Information Extraction Agent for Unlocked, an official Karnataka government welfare benefit discovery platform.

Your mission is to take raw web search excerpts / official guidelines and parse them into a structured SchemeRecord.

STRICT ACCURACY RULES:
1. NEVER invent eligibility criteria, income thresholds, or document requirements. If a criterion is not explicitly stated in the source text, do NOT assume it.
2. For every requirement, you MUST extract the exact sentence as 'evidence' and provide the 'source_url'.
3. Map requirements to standard canonical attribute names:
   - 'annual_family_income' (INR per year)
   - 'karnataka_domicile' (boolean)
   - 'caste_category' (e.g., 'SC', 'ST', 'Cat-1', '2A', '2B', '3A', '3B', 'General')
   - 'age' (integer)
   - 'education_level' (e.g., 'post_matric', 'undergraduate', 'diploma')
   - 'marks_percentage' (float)
4. If the page does not clarify whether an income threshold is for Rural or Urban, set status to 'needs_clarification' and record the uncertainty.
5. If the source is not an official .gov.in or .nic.in domain, mark verification_status as 'uncertain'.
```

### 2.3 Few-Shot Extraction Example

**Input Text (Snippet from Karnataka State Scholarship Portal guidelines):**
> "State Scholarship Portal (SSP) Post-Matric: Eligible students belonging to Scheduled Caste (SC) and Scheduled Tribe (ST) whose parents' annual income is less than or equal to Rs. 2,50,000/- per annum can apply online through https://ssp.postmatric.karnataka.gov.in. Compulsory documents include Aadhaar, Caste & Income Certificate (RD Number), and College Registration Number."

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
      "id": "req_ssp_income_01",
      "attribute": "annual_family_income",
      "criterion": "Parents' annual income must be <= Rs. 2,50,000/- per annum",
      "operator": "lte",
      "value": 250000,
      "status": "verified",
      "source_url": "https://ssp.postmatric.karnataka.gov.in",
      "evidence": "whose parents' annual income is less than or equal to Rs. 2,50,000/- per annum"
    },
    {
      "id": "req_ssp_caste_01",
      "attribute": "caste_category",
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
    "Aadhaar Card",
    "Caste and Income Certificate (RD Number)",
    "College Registration Number"
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
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

class QuestionRecord(BaseModel):
    id: str = Field(description="Stable unique ID, e.g., 'q_annual_family_income'")
    attribute: str = Field(description="Underlying normalized attribute key")
    question: str = Field(description="User-friendly civic question text")
    input_type: Literal["number", "select", "radio", "boolean", "range", "text"]
    options: list[str] = Field(default_factory=list, description="Dropdown/radio options if applicable")
    why_asked: str = Field(description="Explains how this answer helps the search (e.g. 'Needed for 3 scholarships')")
    related_scheme_ids: list[str] = Field(description="Schemes whose match status depends on this answer")
    sensitivity: Literal["low", "medium", "high"] = Field(
        default="low", description="Sensitivity of data (e.g., income=medium, religion/caste=high)"
    )
    status: Literal["unanswered", "answered", "skipped", "unknown"] = "unanswered"
    user_answer: Optional[Any] = None

class RequirementAssessment(BaseModel):
    requirement_id: str
    attribute: str
    status: Literal["satisfied", "not_satisfied", "unknown", "needs_clarification", "unverified"]
    reason: str
    source_url: Optional[str] = None

class SchemeAssessment(BaseModel):
    scheme_id: str
    status: Literal["potential_match", "more_information_needed", "unlikely_to_match", "uncertain"]
    explanation: str
    requirements: list[RequirementAssessment]
```

### 3.2 Consolidated Question Ranking Algorithm (Deterministic Python)

The algorithm operates on the candidate pool without calling an LLM:

```python
def rank_and_deduplicate_questions(
    schemes: list[SchemeRecord], 
    known_user_context: dict[str, Any],
    history_asked_ids: set[str],
    batch_limit: int = 4
) -> list[QuestionRecord]:
    """
    1. Collect all missing attributes across all schemes.
    2. Exclude attributes already known or previously asked.
    3. Score by scheme coverage and penalize sensitivity.
    4. Return top batch_limit questions.
    """
    attribute_to_schemes = {}
    for scheme in schemes:
        for req in scheme.requirements:
            attr = req.attribute
            # Skip if user already answered this attribute
            if attr in known_user_context and known_user_context[attr] is not None:
                continue
            if attr not in attribute_to_schemes:
                attribute_to_schemes[attr] = set()
            attribute_to_schemes[attr].add(scheme.id)

    scored_questions = []
    for attr, scheme_ids in attribute_to_schemes.items():
        q_id = f"q_{attr}"
        if q_id in history_asked_ids:
            continue
            
        coverage = len(scheme_ids)
        sensitivity_penalty = 1 if attr in ["caste_category", "disability_status"] else 0
        score = (coverage * 2) - sensitivity_penalty
        
        scored_questions.append((score, attr, list(scheme_ids)))

    # Sort descending by score
    scored_questions.sort(key=lambda x: x[0], reverse=True)
    
    top_candidates = scored_questions[:batch_limit]
    batch = []
    for score, attr, scheme_ids in top_candidates:
        batch.append(build_question_definition(attr, scheme_ids))
    return batch
```

### 3.3 Question Generation & Assessment System Prompt

```text
You are the Eligibility Verification Agent for Unlocked.

YOUR RULES FOR ASSESSING SCHEMES:
1. 'satisfied': The user's answer clearly meets the criteria (e.g. user income is 1.5L and ceiling is 2.5L).
2. 'not_satisfied': The user's answer conflicts directly with the criterion (e.g. user income is 3.5L and ceiling is 2.5L).
3. 'unknown': The user skipped the question, chose 'prefer not to answer', or has not yet provided the information.
   * CRITICAL: An 'unknown' requirement status results in scheme status 'more_information_needed'. It NEVER results in 'unlikely_to_match'.
4. 'uncertain': The official rule itself is ambiguous or lacks verifiable documentation.

Scheme-Level Overall Status Evaluation:
- If ANY requirement is 'not_satisfied' -> 'unlikely_to_match'
- If all evaluated requirements are 'satisfied' and none are 'unknown' -> 'potential_match'
- If any requirement is 'unknown' and none are 'not_satisfied' -> 'more_information_needed'
- If source evidence is missing -> 'uncertain'
```

---

## 4. Agent 3: Document & Planning Agent

* **Owner:** Member 2 (Eligibility, Verification & Planning Engineer)
* **Priority:** P0 (Core MVP)
* **Execution Paradigm:** Pure deterministic graph construction & topological sort in Python.

### 4.1 Pydantic Data Contracts

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

class DocumentTask(BaseModel):
    id: str = Field(description="Canonical document ID (e.g. 'doc_rd_income_cert')")
    name: str = Field(description="Name of document, e.g. 'Income & Caste Certificate (RD Number)'")
    issuing_authority: str = Field(description="Authority, e.g. 'Nadakacheri / Revenue Department'")
    prerequisites: list[str] = Field(default_factory=list, description="IDs of other tasks needed before this one")
    unlocks_schemes: list[str] = Field(default_factory=list, description="Scheme IDs that require this document")
    source_urls: list[str] = Field(default_factory=list)
    status: Literal["needed", "in_progress", "obtained"] = "needed"
    is_shared_prerequisite: bool = False

class ActionPlan(BaseModel):
    session_id: str
    ordered_tasks: list[DocumentTask]
    total_documents_needed: int
    shared_prerequisites_count: int
```

### 4.2 Deterministic DAG & Topological Sort Implementation

```python
from collections import defaultdict, deque

def build_deterministic_action_plan(
    selected_schemes: list[SchemeRecord],
    user_obtained_docs: set[str]
) -> ActionPlan:
    """
    Constructs a prerequisite DAG from verified scheme document lists
    and returns a topologically sorted, prioritized task list.
    """
    # 1. Standard Karnataka Document Prerequisites Knowledge Graph (verified)
    KNOWN_PREREQUISITES = {
        "doc_rd_income_cert": ["doc_aadhaar", "doc_ration_card"],
        "doc_ssp_eattestation": ["doc_rd_income_cert", "doc_college_marks_card", "doc_aadhaar"],
        "doc_domicile_cert": ["doc_aadhaar", "doc_school_study_cert"]
    }
    
    # 2. Collect documents needed across all selected schemes
    doc_to_schemes = defaultdict(set)
    for s in selected_schemes:
        for doc_name in s.documents:
            doc_id = canonicalize_doc_id(doc_name)
            if doc_id not in user_obtained_docs:
                doc_to_schemes[doc_id].add(s.name)
                
    # 3. Build Adjacency List for DAG
    graph = defaultdict(set)
    in_degree = defaultdict(int)
    all_needed_docs = set(doc_to_schemes.keys())
    
    # Expand with prerequisites
    for doc_id in list(all_needed_docs):
        for prereq in KNOWN_PREREQUISITES.get(doc_id, []):
            if prereq not in user_obtained_docs:
                all_needed_docs.add(prereq)
                graph[prereq].add(doc_id)
                in_degree[doc_id] += 1
                
    for doc in all_needed_docs:
        if doc not in in_degree:
            in_degree[doc] = 0

    # 4. Kahn's Algorithm for Topological Sort
    queue = deque([d for d in all_needed_docs if in_degree[d] == 0])
    ordered_doc_ids = []
    
    while queue:
        # Prioritize items that unlock more schemes
        curr = queue.popleft()
        ordered_doc_ids.append(curr)
        
        for neighbor in graph[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                
    # 5. Build structured task list
    tasks = []
    shared_count = 0
    for doc_id in ordered_doc_ids:
        unlocks = list(doc_to_schemes.get(doc_id, []))
        is_shared = len(unlocks) > 1
        if is_shared:
            shared_count += 1
        tasks.append(
            DocumentTask(
                id=doc_id,
                name=get_human_name(doc_id),
                issuing_authority=get_issuing_authority(doc_id),
                prerequisites=KNOWN_PREREQUISITES.get(doc_id, []),
                unlocks_schemes=unlocks,
                is_shared_prerequisite=is_shared,
                status="needed"
            )
        )
        
    return ActionPlan(
        session_id="current",
        ordered_tasks=tasks,
        total_documents_needed=len(tasks),
        shared_prerequisites_count=shared_count
    )
```

---

## 5. Agent 4: Action & Follow-Through Agent (P1)

* **Owner:** Member 1 (Research & Agentic Workflow Engineer)
* **Priority:** P1 (Execute after P0 vertical slice is working)
* **Guardrail:** Generates **user-reviewed artifacts only**. Unlocked never sends emails or calls application APIs automatically.

### 5.1 Pydantic Data Contracts

```python
from enum import Enum
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    EMAIL_DRAFT = "email_draft"
    CALENDAR_ICS = "calendar_ics"
    REJECTION_ASSIST = "rejection_assist"

class ActionArtifact(BaseModel):
    action_type: ActionType
    title: str
    body_content: str  # Markdown email text, or iCalendar RFC 5545 string
    target_destination: Optional[str] = None  # Official email address if verified
    instructions: str
    user_review_confirmed: bool = False
```

### 5.2 System Prompt: Inquiry & RTI Email Generator

```text
You are the Follow-Through Action Agent for Unlocked.
Your job is to draft a formal, polite, source-grounded email inquiry or clarification letter for the citizen to review, copy, and send themselves.

RULES:
1. ONLY include user details that the user has explicitly verified.
2. DO NOT fabricate official department contact emails. If an official email is known in the scheme record, provide it; otherwise, leave a placeholder: "[Insert Department Helpdesk Email]".
3. Frame the tone as constructive, courteous civic correspondence referencing specific Karnataka scheme government orders or portal guidelines.
```

### 5.3 RFC 5545 iCalendar Generator (.ics)

```python
def generate_ics_event(scheme_name: str, deadline_date_iso: str, portal_url: str) -> str:
    """Generates standard iCalendar VEVENT string for deadline reminder."""
    clean_uid = f"{scheme_name.lower().replace(' ', '_')}_{deadline_date_iso}"
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Unlocked//Karnataka Benefits Assistant//EN
BEGIN:VEVENT
UID:{clean_uid}@unlocked.local
DTSTAMP:{deadline_date_iso.replace('-', '')}T090000Z
DTSTART:{deadline_date_iso.replace('-', '')}T090000Z
SUMMARY:Application Deadline: {scheme_name}
DESCRIPTION:Reminder to submit your application on the official portal: {portal_url}. Ensure all prerequisite documents are uploaded.
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""
```

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
    answers_json TEXT,
    plan_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 Master Orchestration Endpoints (`main.py` / `orchestrator.py`)

```python
@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(payload: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    await db.create_session(session_id, payload.context, payload.scope)
    return SessionResponse(session_id=session_id, status="initialized")

@app.post("/api/discover")
async def run_discovery(session_id: str):
    session = await db.get_session(session_id)
    # Member 1 Discovery module
    schemes = await discovery_agent.discover_schemes(session.context, session.scope)
    await db.save_schemes(session_id, schemes)
    
    # Member 2 Initial assessment & question generation
    req_matrix = eligibility_agent.normalize_requirements(schemes)
    questions = eligibility_agent.rank_and_deduplicate_questions(schemes, session.context, set())
    assessments = eligibility_agent.assess_schemes(schemes, session.context)
    
    await db.save_questions_and_assessments(session_id, questions, assessments)
    return {"status": "discovery_complete", "schemes_count": len(schemes), "questions": questions}

@app.post("/api/answers")
async def submit_answers(session_id: str, answers: dict[str, Any]):
    session = await db.get_session(session_id)
    # Save answers (including explicit skips/unknowns)
    updated_context = {**session.context, **answers}
    assessments = eligibility_agent.assess_schemes(session.schemes, updated_context)
    await db.update_session_answers(session_id, updated_context, assessments)
    return {"status": "reassessed", "assessments": assessments}

@app.get("/api/plan")
async def get_action_plan(session_id: str):
    session = await db.get_session(session_id)
    plan = planning_agent.build_deterministic_action_plan(session.schemes, set())
    await db.save_plan(session_id, plan)
    return plan
```
