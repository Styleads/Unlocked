# Unlocked 🔓

> **A Karnataka-focused government benefits discovery and follow-through assistant.**  
> *Built for Personal Productivity & Daily Civic Life.*

Unlocked simplifies the fragmented landscape of government welfare schemes. Instead of returning a static list of links or hallucinating eligibility criteria, Unlocked takes user context, queries live verified official sources, consolidates missing requirement questions across multiple schemes, and generates an ordered document prerequisite plan so citizens can access their rightful benefits.

---

## 📌 Core Architecture: 4 Logical Agents

Unlocked coordinates four logical workflow stages orchestrated deterministically by a central FastAPI backend:

```
                  [ User Context & Discovery Scope ]
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  Agent 1: Discovery Agent (Member 1)                   │
      │  - Live search / official Karnataka portal guidelines   │
      │  - Extracts candidate schemes & verified source URLs   │
      └───────────────────────────┬────────────────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  Agent 2: Eligibility & Verification Agent (Member 2)  │
      │  - Normalizes criteria into structured conditions      │
      │  - Generates consolidated, deduplicated questions      │
      │  - Reassesses match states (Unknown != Ineligible)     │
      └───────────────────────────┬────────────────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  Agent 3: Document & Planning Agent (Member 2)         │
      │  - Aggregates verified required documents              │
      │  - Constructs DAG of document prerequisites            │
      │  - Generates prioritized, topological action plan      │
      └───────────────────────────┬────────────────────────────┘
                                  │
                                  ▼
      ┌────────────────────────────────────────────────────────┐
      │  Agent 4: Action & Follow-Through Agent (Member 1)     │
      │  - Drafts reviewable RTI / inquiry emails              │
      │  - Generates downloadable .ics deadline events         │
      │  - No automated consequential actions                  │
      └────────────────────────────────────────────────────────┘
```

---

## 📂 Repository & Documentation Structure

The repository is modularly structured to allow parallel development across all 4 team members:

```
Unlocked/
├── README.md               # You are here: Root project introduction & quickstart
├── plan.md                 # Master Hackathon Execution Plan (Schedule, Judging, Rules)
└── docs/
    ├── README.md           # Internal documentation guide & ADR conventions
    ├── agents.md           # Production-Grade Agent Specifications, Prompts & Schemas
    ├── m1/                 # Member 1: Discovery & Action Agent
    │   ├── README.md       # Ownership & deliverables
    │   ├── decisions.md    # ADRs (Search APIs, fallback datasets)
    │   └── debugging.md    # Crawler/search edge cases & extraction fixes
    ├── m2/                 # Member 2: Eligibility & Planning Agent
    │   ├── README.md       # Ownership & deliverables
    │   ├── decisions.md    # ADRs (Question ranking algorithms, DAG sorting)
    │   └── debugging.md    # Logic bugs, cycle resolution, skip semantics
    ├── m3/                 # Member 3: Tech Lead, Backend & Orchestration
    │   ├── README.md       # Ownership, API contracts & milestones
    │   ├── decisions.md    # ADRs (SQLite persistence, schema decisions)
    │   └── debugging.md    # State migration, serialization & concurrency
    └── m4/                 # Member 4: Frontend & UX
        ├── README.md       # Ownership, Stitch mock integration & components
        ├── decisions.md    # ADRs (Design system, status badges, accessibility)
        └── debugging.md    # UI/API integration bugs & responsive fixes
```

---

## 👥 Team Workstream Ownership

| Role | Member | Primary Focus | Key Deliverable | Documentation |
|---|---|---|---|---|
| **Research & Agentic Engineer** | **Member 1 (m1)** | Discovery & Action | Agent 1 (Live Search & Extraction) + Agent 4 (Email & .ics Generation) | [`docs/m1/`](file:///home/kruthik/coding/Unlocked/docs/m1/) |
| **Eligibility & Planning Engineer** | **Member 2 (m2)** | Eligibility & Planning | Agent 2 (Question Deduplication & Assessment) + Agent 3 (Prerequisite DAG) | [`docs/m2/`](file:///home/kruthik/coding/Unlocked/docs/m2/) |
| **Tech Lead & Backend** | **Member 3 (m3)** | Orchestration & DB | FastAPI Central Orchestrator, SQLite Session Store, Endpoints | [`docs/m3/`](file:///home/kruthik/coding/Unlocked/docs/m3/) |
| **Frontend & UX** | **Member 4 (m4)** | Interface & UX | Civic-tech Dashboard, Question Flow, Results & Document Visualizer | [`docs/m4/`](file:///home/kruthik/coding/Unlocked/docs/m4/) |

---

## 🚀 Key Technical Specifications

For full Pydantic data contracts, system prompts, few-shot examples, and deterministic algorithm implementations, refer directly to:
👉 **[`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md)**

For hackathon timelines, review rounds, and judging criteria, refer to:
👉 **[`plan.md`](file:///home/kruthik/coding/Unlocked/plan.md)**

