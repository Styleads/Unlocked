# Project Context & Architecture Guidelines

> **Graph logic is generic. All schemes, documents and deadlines come from data files. Adding a new user category means adding data only.**

---

## 1. Core Principle: Zero Hardcoding in Python Logic

The dependency graph, eligibility assessment, checklist ordering, and document procurement planning are completely decoupled from domain-specific data:

- **No Scheme Names in Code:** All scheme definitions, criteria, and deadlines originate from data files (`data/schemes/<category>.json` or YAML) or live discovery APIs.
- **No Document Names in Code:** Document vocabulary, aliases, issuing authorities, and verified prerequisites reside in `data/documents.json`. Any unseen document is dynamically normalized into an ID and title without failing or being mapped into hardcoded assumptions.
- **No Deadlines in Code:** Deadlines and application windows are dynamically extracted from verified scheme requirements and official portal source URLs.
- **Extensible Categories:** Adding support for farmers, students, senior citizens, artisans, women entrepreneurs, or persons with disabilities requires adding a data file only. No Python code is altered.

---

## 2. Data Structure & Organization

```
data/
├── documents.json                 # Canonical document registry, issuing authorities, prerequisites
└── schemes/
    ├── students.json              # Schemes for students (SSP, Vidyasiri, etc.)
    ├── farmers.json               # Schemes for farmers (PM-KISAN, PMFBY, Raitha Siri, etc.)
    └── senior_citizens.json       # Schemes for senior citizens (Sandhya Suraksha, etc.)
```

### Adding a New Category
To add a new category (e.g., `weavers`):
1. Create `data/schemes/weavers.json`.
2. Define schemes with verified requirements, required documents, and official source URLs.
3. If new documents are introduced, optionally add them to `data/documents.json` with their issuing authority.
4. Call `load_schemes_by_category("weavers")` or `load_all_schemes()`—the system discovers and processes them automatically.

---

## 3. Dependency Graph Inputs

The graph requires two inputs:
1. **Verified Schemes:** List of `SchemeRecord` instances (from Agent 2 / Discovery), each containing:
   - Verified required documents (`name`, `source_url`, optional `dependencies`)
   - Optional verified `deadline` with `deadline_source_url`
2. **User Document Status:** Mapping of document ID to one of:
   - `"have"`: User confirmed they already have the document.
   - `"dont_have"`: User confirmed they do not have the document.
   - `"unknown"`: User has not answered yet or status is unconfirmed (treated as missing and flagged until confirmed).

---

## 4. Document Status Flow (Agent 3)

1. **Collection:** Agent 3 scans the shortlisted schemes and aggregates all required documents and prerequisites.
2. **Plain-Language Questionnaire:** Agent 3 presents clear questions to the user:
   - *"Do you have your Income Certificate? (Issued by Revenue Department / Nadakacheri)"*
   - *"Do you have your Land Record (RTC/Pahani)? (Issued by Bhoomi Portal)"*
3. **Status Updates:** When the user replies with `have`, `dont_have`, or `unknown`, the status is recorded.
4. **Dynamic Regeneration:** When answers change, the graph, checklist, and priority ranking immediately regenerate. Documents marked `have` no longer constrain dependent documents.

---

## 5. Output Graph Format

The output is represented as a single universal graph structure:

```json
{
  "nodes": [
    {
      "id": "doc_income_certificate",
      "label": "Income Certificate",
      "type": "document",
      "status": "have"
    },
    {
      "id": "scholarship_a",
      "label": "Scholarship A",
      "type": "scheme",
      "status": null
    }
  ],
  "edges": [
    {
      "source": "doc_income_certificate",
      "target": "scholarship_a",
      "relation": "required_for",
      "type": "scheme requires document",
      "source_url": "https://..."
    },
    {
      "source": "doc_domicile_certificate",
      "target": "doc_caste_certificate",
      "relation": "prerequisite_of",
      "type": "document requires document",
      "source_url": "https://..."
    }
  ],
  "ranking": [
    {
      "priority": 1,
      "doc_id": "doc_caste_certificate",
      "name": "Caste Certificate",
      "status": "dont_have",
      "schemes_helped": ["scholarship_a"],
      "helps_count": 1,
      "summary": "Caste Certificate (helps 1 application)"
    }
  ]
}
```

---

## 6. Multi-Format Renderers

From this single graph data structure, two visualizations are rendered:

### A. Dashboard Mermaid Diagram
- **Color Coding:**
  - `have` -> Green (`#4CAF50`)
  - `dont_have` -> Red (`#F44336`)
  - `unknown` -> Grey (`#9E9E9E`)
  - `scheme` -> Blue (`#1976D2`)
- Edges:
  - Document required for Scheme: `doc --> scheme`
  - Prerequisite document: `prereq -.->|prerequisite| doc`

### B. Obsidian Notes Vault (`scheme-map/`)
- `scheme-map/README.md` & `Overview.md`: Priority checklist of missing documents with wikilinks `[[...]]` and embedded interactive Mermaid graph.
- `scheme-map/schemes/<scheme_name>.md`: Note for each scheme linking to required documents.
- `scheme-map/documents/<doc_name>.md`: Note for each document detailing status, issuing authority, prerequisites, and dependent schemes.
- Regenerates cleanly via `render_obsidian_notes(plan, output_dir="scheme-map")`.
