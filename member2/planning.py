"""Document aggregation, dependency graph and ordered checklist. Deterministic; no LLM.

Edges exist only where a source supports them: document -> scheme
(`required_for` / "scheme requires document") and prerequisite document -> dependent document
(`prerequisite_of` / "document requires document").

Pure data-driven graph construction: all schemes, requirements, documents and deadlines
originate from input data (e.g. data files or Agent 2 output). Zero hardcoded names in Python.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Union

import networkx as nx

from .assess import SchemeInput, _as_scheme
from .documents import get_issuing_authority, normalize_document_name
from .models import (
    ActionPlan,
    Assessment,
    ChecklistItem,
    DocStatus,
    GraphEdge,
    GraphNode,
    RankedDocument,
    SchemeRecord,
    SchemeStatus,
)

log = logging.getLogger(__name__)

REQUIRED_FOR = "required_for"
PREREQUISITE_OF = "prerequisite_of"
_NO_DEADLINE = "9999-12-31"
_DONE = {DocStatus.have, DocStatus.obtained}


def _names(ids: Iterable[str], schemes: dict[str, SchemeRecord]) -> str:
    return ", ".join(schemes[i].name for i in ids if i in schemes)


def _drop_unlikely(
    schemes: list[SchemeRecord], assessments: Optional[Iterable[Union[Assessment, dict]]], warnings: list[str]
) -> list[SchemeRecord]:
    if not assessments:
        return schemes
    status = {}
    for a in assessments:
        a = a if isinstance(a, Assessment) else Assessment.model_validate(a)
        status[a.scheme_id] = a.status
    kept = []
    for s in schemes:
        if status.get(s.id) == SchemeStatus.unlikely_to_match:
            warnings.append(f"{s.name} was left out of the plan because it appears unlikely to match.")
        else:
            kept.append(s)
    return kept


def _build_graph(schemes: list[SchemeRecord], warnings: list[str], excluded: list[str]) -> nx.DiGraph:
    g = nx.DiGraph()

    def add_doc(doc_id: str, label: str, mandatory: bool = True) -> None:
        if doc_id not in g:
            g.add_node(doc_id, kind="document", label=label, sources=set(), mandatory=mandatory)
        elif mandatory:
            g.nodes[doc_id]["mandatory"] = True

    for scheme in schemes:
        g.add_node(scheme.id, kind="scheme", label=scheme.name)
        for doc in scheme.documents:
            if not doc.source_url:
                if doc.name not in excluded:
                    excluded.append(doc.name)
                warnings.append(f"'{doc.name}' for {scheme.name} was left out: no source confirms it is required.")
                continue
            doc_id, label = normalize_document_name(doc.name)
            doc_mandatory = getattr(doc, "mandatory", True)
            add_doc(doc_id, label, mandatory=doc_mandatory)
            g.nodes[doc_id]["sources"].add(doc.source_url)
            if not g.has_edge(doc_id, scheme.id):
                g.add_edge(doc_id, scheme.id, relation=REQUIRED_FOR, source_url=doc.source_url)

            for dep in doc.dependencies:
                dep_id, dep_label = normalize_document_name(dep.depends_on)
                if not dep.source_url:
                    warnings.append(f"'{dep.depends_on}' before '{doc.name}' was not added: no source confirms that step.")
                    continue
                if dep_id == doc_id:
                    warnings.append(f"'{doc.name}' was listed as its own prerequisite; ignored.")
                    continue
                add_doc(dep_id, dep_label, mandatory=doc_mandatory)
                g.nodes[dep_id]["sources"].add(dep.source_url)
                if not g.has_edge(dep_id, doc_id):
                    g.add_edge(dep_id, doc_id, relation=PREREQUISITE_OF, source_url=dep.source_url)
    return g


def _break_cycles(g: nx.DiGraph, warnings: list[str]) -> None:
    docs = g.subgraph(n for n, d in g.nodes(data=True) if d["kind"] == "document")
    while True:
        try:
            cycle = nx.find_cycle(docs)
        except nx.NetworkXNoCycle:
            return
        labels = " -> ".join(g.nodes[u]["label"] for u, _ in cycle)
        warnings.append(f"The sources describe a circular order ({labels}); those steps are shown without an order.")
        g.remove_edges_from([(u, v) for u, v in cycle])
        docs = g.subgraph(docs.nodes)


def build_action_plan(
    selected_schemes: Iterable[SchemeInput],
    *,
    user_documents: Optional[Mapping[str, Union[DocStatus, str]]] = None,
    assessments: Optional[Iterable[Union[Assessment, dict]]] = None,
) -> ActionPlan:
    """Build the dynamic dependency graph, priority checklist, and ranked missing documents."""
    warnings: list[str] = []
    excluded: list[str] = []
    # Sorting makes the plan independent of the order schemes are passed in.
    schemes = sorted((_as_scheme(s) for s in selected_schemes), key=lambda s: s.id)
    schemes = _drop_unlikely(schemes, assessments, warnings)
    by_id = {s.id: s for s in schemes}

    # Normalize user documents mapping
    owned: dict[str, DocStatus] = {}
    if user_documents is not None:
        for k, v in user_documents.items():
            if isinstance(v, DocStatus):
                owned[k] = v
            else:
                str_val = str(v).strip().lower()
                if str_val == "have":
                    owned[k] = DocStatus.have
                elif str_val == "obtained":
                    owned[k] = DocStatus.obtained
                elif str_val == "dont_have":
                    owned[k] = DocStatus.dont_have
                elif str_val == "needed":
                    owned[k] = DocStatus.needed
                elif str_val == "unknown":
                    owned[k] = DocStatus.unknown
                else:
                    try:
                        owned[k] = DocStatus(str_val)
                    except ValueError:
                        owned[k] = DocStatus.unknown

    g = _build_graph(schemes, warnings, excluded)
    _break_cycles(g, warnings)

    doc_ids = [n for n, d in g.nodes(data=True) if d["kind"] == "document"]
    reach = {d: sorted(n for n in nx.descendants(g, d) if g.nodes[n]["kind"] == "scheme") for d in doc_ids}
    required_by = {d: sorted(v for v in g.successors(d) if g.nodes[v]["kind"] == "scheme") for d in doc_ids}

    def deadline(doc_id: str) -> str:
        dates = [by_id[s].deadline for s in reach[doc_id] if by_id[s].deadline and by_id[s].deadline_source_url]
        return min(dates, default=_NO_DEADLINE)

    def status(doc_id: str) -> DocStatus:
        if user_documents is None:
            return DocStatus.needed
        return owned.get(doc_id, DocStatus.unknown)

    docs_graph = g.subgraph(doc_ids)
    # A prerequisite the user already has doesn't hold anything back, so its
    # outgoing edges don't constrain the order (they stay in the output).
    sort_graph = nx.DiGraph(docs_graph)
    sort_graph.remove_edges_from([(u, v) for u, v in docs_graph.edges if status(u) in _DONE])
    order = list(nx.lexicographical_topological_sort(
        sort_graph,
        key=lambda d: (status(d) in _DONE, status(d) == DocStatus.unknown, -len(reach[d]), deadline(d), d),
    ))

    checklist = []
    for position, doc_id in enumerate(order, start=1):
        label = g.nodes[doc_id]["label"]
        before = sorted(docs_graph.successors(doc_id))
        st = status(doc_id)
        parts = []
        if st in _DONE:
            parts.append("You already have this.")
        if before:
            parts.append("Get this first: required before " + ", ".join(g.nodes[b]["label"] for b in before) + ".")
        if required_by[doc_id]:
            n = len(required_by[doc_id])
            parts.append(f"Needed for {n} scheme{'s' if n > 1 else ''}: {_names(required_by[doc_id], by_id)}.")
        if deadline(doc_id) != _NO_DEADLINE:
            parts.append(f"Earliest verified deadline: {deadline(doc_id)}.")

        authority = get_issuing_authority(doc_id)
        checklist.append(ChecklistItem(
            id=doc_id,
            name=label,
            status=st,
            order=position,
            mandatory=g.nodes[doc_id].get("mandatory", True),
            required_by_scheme_ids=required_by[doc_id],
            dependencies=sorted(docs_graph.predecessors(doc_id)),
            source_urls=sorted(g.nodes[doc_id]["sources"]),
            reason=" ".join(parts),
            issuing_authority=authority,
            is_unknown=(st == DocStatus.unknown),
        ))

    shared = [c.id for c in checklist if len(c.required_by_scheme_ids) >= 2]
    nodes = [
        GraphNode(
            id=d,
            label=g.nodes[d]["label"],
            kind="document",
            type="document",
            status=status(d).value,
        )
        for d in order
    ]
    nodes += [
        GraphNode(
            id=s.id,
            label=s.name,
            kind="scheme",
            type="scheme",
            status=None,
        )
        for s in schemes
    ]

    edges = []
    for u, v, d in sorted(g.edges(data=True), key=lambda e: (e[0], e[1])):
        rel = d["relation"]
        edge_type = "scheme requires document" if rel == REQUIRED_FOR else "document requires document"
        edges.append(GraphEdge(
            source=u,
            target=v,
            relation=rel,
            type=edge_type,
            source_url=d["source_url"],
        ))

    # Priority ranking of missing documents
    missing_docs = [d for d in order if status(d) not in _DONE]
    ranking: list[RankedDocument] = []
    for rank_idx, doc_id in enumerate(missing_docs, start=1):
        st = status(doc_id)
        st_label = "dont_have" if st in (DocStatus.dont_have, DocStatus.needed) else "unknown"
        helps_sids = reach[doc_id]
        helps_names = [_names([sid], by_id) for sid in helps_sids]
        n_helps = len(helps_sids)
        if n_helps == 1:
            desc = f"{g.nodes[doc_id]['label']} (helps 1 application)"
        elif n_helps > 1:
            desc = f"{g.nodes[doc_id]['label']} (helps {n_helps} applications)"
        else:
            desc = g.nodes[doc_id]['label']

        ranking.append(RankedDocument(
            priority=rank_idx,
            doc_id=doc_id,
            name=g.nodes[doc_id]["label"],
            status=st_label,
            schemes_helped=helps_sids,
            scheme_names=helps_names,
            helps_count=n_helps,
            summary=desc,
        ))

    plan = ActionPlan(
        checklist=checklist,
        nodes=nodes,
        edges=edges,
        ranking=ranking,
        shared_prerequisites=shared,
        explanation=_explain(checklist, shared, excluded, by_id),
        warnings=warnings,
        excluded_documents=excluded,
    )
    plan.mermaid = render_mermaid(plan)
    log.debug("plan built: %d documents, %d edges, %d ranked missing", len(checklist), len(edges), len(ranking))
    return plan


def _explain(checklist: list[ChecklistItem], shared: list[str], excluded: list[str], schemes: dict[str, SchemeRecord]) -> str:
    if not checklist:
        text = "No documents with a confirmed source were found for the selected schemes."
    elif shared:
        top = next(c for c in checklist if c.id == shared[0])
        text = (
            f"Start with your {top.name}: it is needed for {len(top.required_by_scheme_ids)} schemes "
            f"({_names(top.required_by_scheme_ids, schemes)}). "
            f"Your plan lists {len(checklist)} documents in the order to get them."
        )
    else:
        text = f"Your plan lists {len(checklist)} documents in the order to get them, starting with your {checklist[0].name}."
    if excluded:
        n = len(excluded)
        text += f" {n} document{'s were' if n > 1 else ' was'} left out because no source confirms {'they are' if n > 1 else 'it is'} required."
    return text


def render_mermaid(plan_or_graph: Union[ActionPlan, dict[str, Any]]) -> str:
    """Render Mermaid text for the dashboard with colours:
    have = green, dont_have = red, unknown = grey
    """
    if isinstance(plan_or_graph, ActionPlan):
        nodes = plan_or_graph.nodes
        edges = plan_or_graph.edges
    elif isinstance(plan_or_graph, dict):
        nodes = [GraphNode.model_validate(n) for n in plan_or_graph.get("nodes", [])]
        edges = [GraphEdge.model_validate(e) for e in plan_or_graph.get("edges", [])]
    else:
        raise TypeError(f"Expected ActionPlan or dict, got {type(plan_or_graph).__name__}")

    lines = [
        "graph TD",
        "    %% Styling definitions for Unlocked Dependency Graph",
        "    classDef have fill:#4CAF50,stroke:#2E7D32,color:#ffffff,stroke-width:2px;",
        "    classDef dont_have fill:#F44336,stroke:#C62828,color:#ffffff,stroke-width:2px;",
        "    classDef unknown fill:#9E9E9E,stroke:#616161,color:#ffffff,stroke-width:2px;",
        "    classDef scheme fill:#1976D2,stroke:#0D47A1,color:#ffffff,stroke-width:2px;",
        "",
        "    %% Document Nodes",
    ]

    doc_nodes = [n for n in nodes if n.kind == "document"]
    scheme_nodes = [n for n in nodes if n.kind == "scheme"]

    for n in doc_nodes:
        clean_label = n.label.replace('"', "'")
        st = (n.status or "unknown").lower()
        if st in ("have", "obtained"):
            cls = "have"
            tag = "(have)"
        elif st in ("dont_have", "needed"):
            cls = "dont_have"
            tag = "(dont_have)"
        else:
            cls = "unknown"
            tag = "(unknown)"
        lines.append(f'    {n.id}["{clean_label} {tag}"]:::{cls}')

    lines.append("")
    lines.append("    %% Scheme Nodes")
    for s in scheme_nodes:
        clean_label = s.label.replace('"', "'")
        lines.append(f'    {s.id}["{clean_label}"]:::scheme')

    lines.append("")
    lines.append("    %% Dependency Edges")
    for e in edges:
        if e.relation == PREREQUISITE_OF or e.type == "document requires document":
            lines.append(f"    {e.source} -.->|prerequisite| {e.target}")
        else:
            lines.append(f"    {e.source} --> {e.target}")

    return "\n".join(lines)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", slug)


def render_obsidian_notes(
    plan_or_graph: Union[ActionPlan, dict[str, Any]],
    output_dir: Union[str, Path] = "scheme-map",
) -> list[Path]:
    """Render Obsidian notes in scheme-map/, regenerated from the same data."""
    out = Path(output_dir)
    schemes_dir = out / "schemes"
    docs_dir = out / "documents"
    schemes_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(plan_or_graph, ActionPlan):
        plan = plan_or_graph
        graph_dict = plan.to_graph_dict()
    else:
        graph_dict = plan_or_graph
        plan = None

    nodes = [GraphNode.model_validate(n) for n in graph_dict.get("nodes", [])]
    edges = [GraphEdge.model_validate(e) for e in graph_dict.get("edges", [])]
    ranking = [RankedDocument.model_validate(r) for r in graph_dict.get("ranking", [])]

    node_by_id = {n.id: n for n in nodes}
    doc_nodes = [n for n in nodes if n.kind == "document"]
    scheme_nodes = [n for n in nodes if n.kind == "scheme"]

    written_files: list[Path] = []

    # 1. Scheme Notes
    for s in scheme_nodes:
        req_edges = [e for e in edges if e.target == s.id and e.source in node_by_id]
        doc_links = []
        for e in req_edges:
            doc_node = node_by_id[e.source]
            st = doc_node.status or "unknown"
            doc_links.append(f"- [[{doc_node.label}]] (Status: `{st}`)")

        scheme_content = [
            f"# {s.label}",
            "",
            "## Overview",
            f"- **Scheme ID:** `{s.id}`",
            "",
            "## Required Documents",
        ]
        if doc_links:
            scheme_content.extend(doc_links)
        else:
            scheme_content.append("- No confirmed document requirements found.")

        scheme_file = schemes_dir / f"{_slugify(s.label)}.md"
        scheme_file.write_text("\n".join(scheme_content), encoding="utf-8")
        written_files.append(scheme_file)

    # 2. Document Notes
    for d in doc_nodes:
        # Dependent schemes
        req_for_edges = [e for e in edges if e.source == d.id and e.target in node_by_id and node_by_id[e.target].kind == "scheme"]
        scheme_links = [f"- [[{node_by_id[e.target].label}]]" for e in req_for_edges]

        # Prerequisites
        prereq_edges = [e for e in edges if e.target == d.id and e.relation == PREREQUISITE_OF and e.source in node_by_id]
        prereq_links = [f"- [[{node_by_id[e.source].label}]]" for e in prereq_edges]

        doc_content = [
            f"# {d.label}",
            "",
            "## Document Details",
            f"- **Document ID:** `{d.id}`",
            f"- **Current Status:** `{d.status or 'unknown'}`",
        ]
        authority = get_issuing_authority(d.id)
        if authority:
            doc_content.append(f"- **Issuing Authority:** {authority}")

        doc_content.append("")
        doc_content.append("## Prerequisites")
        if prereq_links:
            doc_content.extend(prereq_links)
        else:
            doc_content.append("- None (can be obtained directly)")

        doc_content.append("")
        doc_content.append("## Required For Schemes")
        if scheme_links:
            doc_content.extend(scheme_links)
        else:
            doc_content.append("- Not required by current shortlisted schemes directly.")

        doc_file = docs_dir / f"{_slugify(d.label)}.md"
        doc_file.write_text("\n".join(doc_content), encoding="utf-8")
        written_files.append(doc_file)

    # 3. Master Index / Overview Note
    mermaid_text = render_mermaid(plan if plan else graph_dict)
    index_lines = [
        "# Unlocked: Schemes & Documents Dependency Map",
        "",
        "This map is dynamically generated from scheme requirements and user document statuses.",
        "",
        "## Priority Checklist of Missing Documents",
        "",
    ]
    if ranking:
        for r in ranking:
            st_text = "missing" if r.status == "dont_have" else "unconfirmed"
            index_lines.append(f"{r.priority}. **[[{r.name}]]** (`{st_text}`) - {r.summary}")
    else:
        index_lines.append("All required documents are currently marked as **have**! You are ready to apply.")

    index_lines.extend([
        "",
        "## All Shortlisted Schemes",
        "",
    ])
    for s in scheme_nodes:
        index_lines.append(f"- [[{s.label}]]")

    index_lines.extend([
        "",
        "## Interactive Dependency Graph",
        "",
        "```mermaid",
        mermaid_text,
        "```",
        "",
    ])

    index_file = out / "README.md"
    index_file.write_text("\n".join(index_lines), encoding="utf-8")
    written_files.append(index_file)

    overview_file = out / "Overview.md"
    overview_file.write_text("\n".join(index_lines), encoding="utf-8")
    written_files.append(overview_file)

    log.debug("Rendered %d Obsidian notes in %s", len(written_files), out)
    return written_files
