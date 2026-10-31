# Project Unlocked — DECISIONS.md

**Project:** Unlocked  
**Purpose:** Agentic government benefits and schemes discovery and application-planning platform.  
**Status:** Active Development  
**Last Updated:** 31 October 2026

---

## 1. Project Vision

Unlocked aims to help individuals discover government schemes and benefits relevant to their circumstances.

The platform should:

- Understand individual user profiles.
- Discover relevant government schemes.
- Evaluate potential eligibility.
- Explain why a user may or may not qualify.
- Identify required documents.
- Guide users through the application process.
- Help users track and follow up on their applications.

The system should prioritize accurate information, reliable sources, transparency, and accessibility.

## 2. Agent Architecture

Unlocked is being developed using multiple specialized agents.

Current planned agents:

| Agent               | Responsibility                       | Status                  |
| ------------------- | ------------------------------------ | ----------------------- |
| Agent 1             | Pending confirmation                 | Pending                 |
| Agent 2             | Pending confirmation                 | Built by teammate       |
| Agent 3             | Pending confirmation                 | Built by teammate       |
| Agent 4 — Discovery | Discover relevant government schemes | Approximately 95% built |
| Actions Agent       | Application and action planning      | Next development stage  |
| Follow-up Agent     | Application follow-ups               | Planned                 |

**Important:** The agent numbers and responsibilities must be confirmed against the actual repository and team architecture. Do not assume that the table represents a finalized integration architecture.

## 3. Discovery Agent Decisions

Discovery is currently approximately 95% built.

The current developer is Joshua.

### Confirmed decisions

- Discovery should work with different users and their individual profiles.
- Scheme discovery should not depend exclusively on hardcoded user examples.
- The agent should use AI for scheme analysis and extraction.
- Google Gemini is used for AI processing.
- Tavily is used for live search.
- The agent should return structured output that can be consumed by the backend and other agents.
- The agent should identify missing user information rather than inventing it.

### Environment variables

The current Discovery configuration includes:

- `GOOGLE_API_KEY`
- `TAVILY_API_KEY`
- `HOST`
- `PORT`
- `ALLOWED_ORIGINS`
- `DISCOVERY_TIMEOUT_SECONDS`

Actual credentials must remain in local `.env` files.

### Development policy

Discovery is approaching completion.

Further development should focus on:

- Testing.
- Bug fixes.
- Reliability.
- Output consistency.
- Integration compatibility.

Do not unnecessarily redesign or rebuild the agent.

## 4. Team Development and Integration

The project is being developed collaboratively.

- Joshua is developing Discovery (Agent 4).
- A teammate has developed Agents 2 and 3.
- The teammate has offered to handle integration after the agents are pushed to GitHub.
- Joshua is proceeding to the next agent after completing Discovery.

### Integration decision

The preferred workflow is:

1. Each developer completes their assigned agent.
2. Each developer pushes their code to the shared GitHub repository.
3. The integration owner reviews the agents.
4. Agents are connected through their agreed interfaces.
5. The integrated system is tested end-to-end.

Do not independently modify another teammate's agent without coordination.

## 5. Technology and Development Principles

The project uses AI-powered workflows and a backend/frontend architecture.

Known technologies and services:

- Python
- FastAPI
- Google Gemini API
- Tavily Search API
- Git and GitHub
- n8n exploration and workflow development

The exact production architecture and agent communication mechanism remain subject to repository and team confirmation.

### General principles

- Prefer modular agents with clearly defined responsibilities.
- Avoid unnecessary duplication between agents.
- Avoid hardcoding individual user profiles.
- Keep API credentials outside source code.
- Use structured and predictable interfaces between agents.
- Preserve working implementations.
- Test changes before integration.

## 6. GitHub and Security Decisions

The project must never expose API keys or user credentials.

### Confirmed security rules

- Real credentials remain in `.env`.
- `.env` must not be committed.
- `.env.example` contains placeholder values only.
- `.gitignore` excludes environment files.
- User profile data and personally identifiable information must not be committed.
- Virtual environments, caches, logs, and temporary files should be ignored.

### Current environment template

The `.env.example` file contains placeholders for:

- Google Gemini API key.
- Tavily Search API key.
- FastAPI host and port.
- Allowed frontend origins.
- Discovery timeout.

### Before GitHub push

Verify:

- Actual `.env` files are ignored.
- No real credentials are tracked.
- No secrets are present in tracked source files.
- Previous Git history does not expose credentials.
- `.env.example` remains available to collaborators.

Adding `.gitignore` does not remove previously committed secrets.

If credentials have been exposed, revoke or rotate them.

## 7. Rules for AI Coding Assistants

Antigravity and other AI coding assistants must follow these rules:

1. Inspect before modifying.
2. Do not modify completed agents without explicit permission.
3. Do not rewrite working code merely to improve style.
4. Do not rename files, folders, functions, or variables without approval.
5. Do not change existing agent interfaces without coordination.
6. Do not overwrite `.env` files.
7. Do not expose API keys in terminal output or documentation.
8. Keep documentation synchronized with actual project decisions.
9. Distinguish confirmed decisions from assumptions.
10. Ask before making architecture-changing decisions.

### Discovery protection rule

Discovery is a near-completed component.

Unless explicitly authorized:

- Do not edit Discovery source files.
- Do not change its prompts.
- Do not change its workflow.
- Do not change its API interfaces.
- Do not modify its dependencies.
- Do not refactor its internal logic.

Documentation updates must not change Discovery's implementation.

## 8. Pending Decisions

The following items require confirmation:

- Final responsibility of Agents 1, 2 and 3.
- Final agent-to-agent communication mechanism.
- Final integration contract and output schemas.
- Backend ownership and integration responsibilities.
- Authentication and user-profile storage architecture.
- Deployment platform.
- Final end-to-end testing strategy.
- Actions Agent implementation details.
- Follow-up Agent implementation details.

Do not treat pending decisions as finalized.

## 9. Change Management

Whenever a significant project decision is made:

1. Record the decision in this file.
2. Include the date.
3. Explain why the decision was made.
4. Identify which agents or components are affected.
5. Record whether the decision is confirmed or pending.

Do not silently change previous decisions.

If a decision is superseded, preserve its history and document the replacement.

---

**Core principle: Build modularly, protect working components, document decisions, and integrate only through agreed interfaces.**
