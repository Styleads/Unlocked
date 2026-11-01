"""Agent 3: Document & Planning Agent.

Coordinates document requirement collection, user status flow, dynamic dependency
graph generation, priority ranking, and multi-format rendering (Mermaid & Obsidian).
All logic is generic and purely data-driven.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Union

from .assess import SchemeInput, _as_scheme
from .data_loader import load_document_definitions
from .documents import DocumentSpec, normalize_document_name
from .models import (
    ActionPlan,
    Assessment,
    DocStatus,
    RankedDocument,
    SchemeRecord,
)
from .planning import (
    build_action_plan,
    render_mermaid,
    render_obsidian_notes,
)

log = logging.getLogger(__name__)


class Agent3:
    """Document & Planning Agent.

    Dynamically manages:
    1. Gathering document requirements across any shortlisted schemes without hardcoded names.
    2. Generating plain-language questions to ask the user ("Do you have your {doc_name}?").
    3. Recording have / dont_have / unknown status updates.
    4. Regenerating the dependency graph, priority checklist, and ranked missing documents.
    5. Exporting to Mermaid (dashboard) and Obsidian notes in scheme-map/.
    """

    def __init__(self, doc_registry: Optional[dict[str, DocumentSpec]] = None):
        try:
            self.doc_registry = doc_registry or load_document_definitions()
        except Exception as e:
            log.warning("Could not load external document definitions: %s", e)
            self.doc_registry = {}

    def collect_required_documents(self, schemes: Iterable[SchemeInput]) -> list[dict[str, Any]]:
        """Collect the list of all unique documents required across shortlisted schemes."""
        canonical_schemes = [_as_scheme(s) for s in schemes]
        unique_docs: dict[str, dict[str, Any]] = {}

        for scheme in canonical_schemes:
            for doc in scheme.documents:
                if not doc.source_url:
                    continue
                # Main document
                doc_id, display_name = normalize_document_name(doc.name)
                spec = self.doc_registry.get(doc_id)
                authority = spec.issuing_authority if spec else None

                if doc_id not in unique_docs:
                    unique_docs[doc_id] = {
                        "id": doc_id,
                        "name": display_name,
                        "issuing_authority": authority,
                        "required_by_scheme_ids": [scheme.id],
                        "required_by_scheme_names": [scheme.name],
                        "source_urls": [doc.source_url],
                    }
                else:
                    if scheme.id not in unique_docs[doc_id]["required_by_scheme_ids"]:
                        unique_docs[doc_id]["required_by_scheme_ids"].append(scheme.id)
                        unique_docs[doc_id]["required_by_scheme_names"].append(scheme.name)
                    if doc.source_url and doc.source_url not in unique_docs[doc_id]["source_urls"]:
                        unique_docs[doc_id]["source_urls"].append(doc.source_url)

                # Dependencies
                for dep in doc.dependencies:
                    if not dep.source_url:
                        continue
                    dep_id, dep_display = normalize_document_name(dep.depends_on)
                    dep_spec = self.doc_registry.get(dep_id)
                    dep_auth = dep_spec.issuing_authority if dep_spec else None
                    if dep_id not in unique_docs:
                        unique_docs[dep_id] = {
                            "id": dep_id,
                            "name": dep_display,
                            "issuing_authority": dep_auth,
                            "required_by_scheme_ids": [scheme.id],
                            "required_by_scheme_names": [scheme.name],
                            "source_urls": [dep.source_url],
                        }
                    else:
                        if scheme.id not in unique_docs[dep_id]["required_by_scheme_ids"]:
                            unique_docs[dep_id]["required_by_scheme_ids"].append(scheme.id)
                            unique_docs[dep_id]["required_by_scheme_names"].append(scheme.name)
                        if dep.source_url not in unique_docs[dep_id]["source_urls"]:
                            unique_docs[dep_id]["source_urls"].append(dep.source_url)

        return list(unique_docs.values())

    def generate_document_questions(
        self,
        schemes: Iterable[SchemeInput],
        user_documents: Optional[Mapping[str, Union[DocStatus, str]]] = None,
    ) -> list[dict[str, Any]]:
        """Generate plain language questions for documents not yet asked or marked unknown.

        Format: 'Do you have your {document_name}?'
        """
        user_docs = dict(user_documents or {})
        docs = self.collect_required_documents(schemes)
        questions: list[dict[str, Any]] = []

        for d in docs:
            doc_id = d["id"]
            status = user_docs.get(doc_id)
            if status is not None:
                str_status = status.value if isinstance(status, DocStatus) else str(status).lower()
                if str_status in ("have", "obtained", "dont_have"):
                    continue

            # Need to ask user
            q_text = f"Do you have your {d['name']}?"
            questions.append({
                "doc_id": doc_id,
                "name": d["name"],
                "question": q_text,
                "issuing_authority": d.get("issuing_authority"),
                "options": ["have", "dont_have", "unknown"],
                "required_by": d["required_by_scheme_names"],
            })
        return questions

    def record_document_status(
        self,
        user_documents: dict[str, Union[DocStatus, str]],
        doc_id_or_name: str,
        status: Union[DocStatus, str],
    ) -> dict[str, str]:
        """Record or update user's document status (have / dont_have / unknown)."""
        doc_id, _ = normalize_document_name(doc_id_or_name)
        if isinstance(status, DocStatus):
            val = status.value
        else:
            val = str(status).strip().lower()
            if val not in ("have", "dont_have", "unknown", "obtained", "needed"):
                raise ValueError(f"Invalid status '{status}'. Expected 'have', 'dont_have', or 'unknown'.")
        user_documents[doc_id] = val
        return {k: str(v.value if isinstance(v, DocStatus) else v) for k, v in user_documents.items()}

    def build_plan(
        self,
        schemes: Iterable[SchemeInput],
        user_documents: Optional[Mapping[str, Union[DocStatus, str]]] = None,
        assessments: Optional[Iterable[Union[Assessment, dict]]] = None,
    ) -> ActionPlan:
        """Construct the action plan, DAG graph, checklist, and ranked missing documents."""
        return build_action_plan(schemes, user_documents=user_documents, assessments=assessments)

    def to_graph_structure(self, plan: ActionPlan) -> dict[str, Any]:
        """Return the standard graph structure (nodes, edges, ranking)."""
        return plan.to_graph_dict()

    def render_mermaid(self, plan_or_graph: Union[ActionPlan, dict[str, Any]]) -> str:
        """Render Mermaid text with color classes (have=green, dont_have=red, unknown=grey)."""
        return render_mermaid(plan_or_graph)

    def render_obsidian_notes(
        self,
        plan_or_graph: Union[ActionPlan, dict[str, Any]],
        output_dir: Union[str, Path] = "scheme-map",
    ) -> list[Path]:
        """Render Obsidian notes in scheme-map/, regenerated from the plan data."""
        return render_obsidian_notes(plan_or_graph, output_dir=output_dir)
