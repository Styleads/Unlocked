"""Document aggregation, dependency graph and ordered checklist. Deterministic; no LLM.

Edges exist only where a source supports them: document -> scheme
(`required_for`) and prerequisite document -> dependent document
(`prerequisite_of`).
"""
from __future__ import annotations

import logging
from typing import Iterable, Mapping, Optional, Union

import networkx as nx

from .assess import SchemeInput, _as_scheme
from .documents import normalize_document_name
from .models import (
    ActionPlan,
    Assessment,
    ChecklistItem,
    DocStatus,
    GraphEdge,
    GraphNode,
    SchemeRecord,
    SchemeStatus,
)

log = logging.getLogger(__name__)

REQUIRED_FOR = "required_for"
PREREQUISITE_OF = "prerequisite_of"
_NO_DEADLINE = "9999-12-31"
_DONE = {DocStatus.have, DocStatus.obtained}


def _names(ids: Iterable[str], schemes: dict[str, SchemeRecord]) -> str:
    return ", ".join(schemes[i].name for i in ids)


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

    def add_doc(doc_id: str, label: str) -> None:
        if doc_id not in g:
            g.add_node(doc_id, kind="document", label=label, sources=set())

    for scheme in schemes:
        g.add_node(scheme.id, kind="scheme", label=scheme.name)
        for doc in scheme.documents:
            if not doc.source_url:
                if doc.name not in excluded:
                    excluded.append(doc.name)
                warnings.append(f"'{doc.name}' for {scheme.name} was left out: no source confirms it is required.")
                continue
            doc_id, label = normalize_document_name(doc.name)
            add_doc(doc_id, label)
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
                add_doc(dep_id, dep_label)
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
    warnings: list[str] = []
    excluded: list[str] = []
    # Sorting makes the plan independent of the order Member 3 passes schemes in.
    schemes = sorted((_as_scheme(s) for s in selected_schemes), key=lambda s: s.id)
    schemes = _drop_unlikely(schemes, assessments, warnings)
    by_id = {s.id: s for s in schemes}
    owned = {k: DocStatus(v) for k, v in (user_documents or {}).items()}

    g = _build_graph(schemes, warnings, excluded)
    _break_cycles(g, warnings)

    doc_ids = [n for n, d in g.nodes(data=True) if d["kind"] == "document"]
    reach = {d: sorted(n for n in nx.descendants(g, d) if g.nodes[n]["kind"] == "scheme") for d in doc_ids}
    required_by = {d: sorted(v for v in g.successors(d) if g.nodes[v]["kind"] == "scheme") for d in doc_ids}

    def deadline(doc_id: str) -> str:
        dates = [by_id[s].deadline for s in reach[doc_id] if by_id[s].deadline and by_id[s].deadline_source_url]
        return min(dates, default=_NO_DEADLINE)

    def status(doc_id: str) -> DocStatus:
        return owned.get(doc_id, DocStatus.needed)

    docs_graph = g.subgraph(doc_ids)
    # A prerequisite the user already has doesn't hold anything back, so its
    # outgoing edges don't constrain the order (they stay in the output).
    sort_graph = nx.DiGraph(docs_graph)
    sort_graph.remove_edges_from([(u, v) for u, v in docs_graph.edges if status(u) in _DONE])
    order = list(nx.lexicographical_topological_sort(
        sort_graph,
        key=lambda d: (status(d) in _DONE, -len(reach[d]), deadline(d), d),
    ))

    checklist = []
    for position, doc_id in enumerate(order, start=1):
        label = g.nodes[doc_id]["label"]
        before = sorted(docs_graph.successors(doc_id))
        parts = []
        if status(doc_id) in _DONE:
            parts.append("You already have this.")
        if before:
            parts.append("Get this first: required before " + ", ".join(g.nodes[b]["label"] for b in before) + ".")
        if required_by[doc_id]:
            n = len(required_by[doc_id])
            parts.append(f"Needed for {n} scheme{'s' if n > 1 else ''}: {_names(required_by[doc_id], by_id)}.")
        if deadline(doc_id) != _NO_DEADLINE:
            parts.append(f"Earliest verified deadline: {deadline(doc_id)}.")
        checklist.append(ChecklistItem(
            id=doc_id,
            name=label,
            status=status(doc_id),
            order=position,
            required_by_scheme_ids=required_by[doc_id],
            dependencies=sorted(docs_graph.predecessors(doc_id)),
            source_urls=sorted(g.nodes[doc_id]["sources"]),
            reason=" ".join(parts),
        ))

    shared = [c.id for c in checklist if len(c.required_by_scheme_ids) >= 2]
    nodes = [GraphNode(id=d, label=g.nodes[d]["label"], kind="document") for d in order]
    nodes += [GraphNode(id=s.id, label=s.name, kind="scheme") for s in schemes]
    edges = [
        GraphEdge(source=u, target=v, relation=d["relation"], source_url=d["source_url"])
        for u, v, d in sorted(g.edges(data=True), key=lambda e: (e[0], e[1]))
    ]

    log.debug("plan built: %d documents, %d edges, %d warnings", len(checklist), len(edges), len(warnings))
    return ActionPlan(
        checklist=checklist,
        nodes=nodes,
        edges=edges,
        shared_prerequisites=shared,
        explanation=_explain(checklist, shared, excluded, by_id),
        warnings=warnings,
        excluded_documents=excluded,
    )


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
