# Unlocked — Project Documentation Directory

Welcome to the internal engineering documentation for **Unlocked**.  
This repository is configured to allow all four team members to work asynchronously and in parallel without blocking each other or causing git conflicts.

---

## 1. Directory Structure

```
docs/
├── README.md              # You are here: Team documentation index & guidelines
├── agents.md              # Complete specification of the 4 Logical Agents
├── m1/                    # Member 1: Discovery & Action Agent
│   ├── README.md          # Ownership, tasks & deliverables
│   ├── decisions.md       # ADRs: Search provider, seed fallback, formatting
│   └── debugging.md       # Scraping errors, rate limits, edge cases
├── m2/                    # Member 2: Eligibility, Verification & Planning Agent
│   ├── README.md          # Ownership, tasks & deliverables
│   ├── decisions.md       # Normalization rules, DAG structure, question ranking
│   └── debugging.md       # Cyclic dependencies, skip semantics, assessment bugs
├── m3/                    # Member 3: Lead, Backend, SQLite & Orchestration
│   ├── README.md          # Architecture, contracts & integration milestones
│   ├── decisions.md       # DB schema, session lifecycle, API endpoints
│   └── debugging.md       # Migration issues, serialization, race conditions
└── m4/                    # Member 4: Frontend & UX
    ├── README.md          # Stitch designs, screen hierarchy & mock setup
    ├── decisions.md       # UX decisions, state management, form validations
    └── debugging.md       # Integration mismatches, responsive UI bugs
```

---

## 2. Team Member Workstream Map

| Member | Workstream | Primary Responsibilities | Direct Docs Folder |
|---|---|---|---|
| **Member 1 (m1)** | Research & Agentic Workflow | Agent 1 (Discovery) & Agent 4 (Action / Follow-Through) | [`docs/m1/`](file:///home/kruthik/coding/Unlocked/docs/m1/) |
| **Member 2 (m2)** | Eligibility & Planning | Agent 2 (Eligibility & Verification) & Agent 3 (Doc Planning) | [`docs/m2/`](file:///home/kruthik/coding/Unlocked/docs/m2/) |
| **Member 3 (m3)** | Tech Lead & Backend | SQLite, FastAPI, Central Orchestrator, Shared Contracts | [`docs/m3/`](file:///home/kruthik/coding/Unlocked/docs/m3/) |
| **Member 4 (m4)** | Frontend & UX | Stitch designs, React/Vite UI, mock data integration | [`docs/m4/`](file:///home/kruthik/coding/Unlocked/docs/m4/) |

---

## 3. How to Use Your Workspace Folder (`m1/`, `m2/`, `m3/`, `m4/`)

Every member has their own subfolder in `docs/`:
1. **`decisions.md`**: Whenever you make a technical choice (e.g., choosing a search API, deciding on a question deduplication threshold, picking a date parsing library, or UI component state strategy), record a short entry with the date, context, decision, and consequences.
2. **`debugging.md`**: When you hit a gnarly bug, parser crash, API rate limit, or schema mismatch, document the symptom, root cause, and fix. This preserves institutional memory during rapid hackathon iteration.
3. **`README.md`**: Keep your personal task checklist, current blocker status, and milestone readiness updated.

---

## 4. Key References

* **Master Plan:** [`plan.md`](file:///home/kruthik/coding/Unlocked/plan.md) (1223-line hackathon strategy, timeline, judging criteria)
* **Agent Specifications:** [`docs/agents.md`](file:///home/kruthik/coding/Unlocked/docs/agents.md) (Schemas, contracts, deterministic rules)

