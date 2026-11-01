import type { ApiPlan, ApiQuestion, ApiRequirement, ApiScheme } from "./api";
import type { DocStatus, Pip, SourceType, Status } from "./data";
import { PLAN_DOCS, PLAN_SCHEME_NODES } from "./data";
import type { EvaluatedScheme, Improve } from "./eligibility";
import { CONTEXT_ATTRIBUTES } from "./live";

/**
 * View models the pages render. They are built either from the backend's responses or from the
 * built-in demo data, so a page never needs to know which one it is showing.
 */

export type SchemeVM = {
  id: string;
  name: string;
  dept: string;
  summary: string;
  status: Status;
  expl: string;
  pips: Pip[];
  met: number;
  missing: string[];
  /** Backend attribute ids behind `missing`, so the page can tell which ones the Context form could supply. */
  missingAttrs: string[];
  url: string;
  sourceType: SourceType;
  lastVerified: string;
  verified: boolean;
};

const STATUS: Record<NonNullable<ApiScheme["assessment_status"]>, Status> = {
  potential_match: "ok",
  more_information_needed: "info",
  not_yet_verified: "nv",
  uncertain: "unclear",
  unlikely_to_match: "warn",
};

const PIP: Record<ApiRequirement["status"], Pip> = {
  satisfied: "ok",
  not_satisfied: "no",
  unknown: "unk",
  needs_clarification: "unk",
  unverified: "unv",
};

/** "annual_family_income" -> "annual family income" */
export const humanize = (attr: string) => attr.replace(/^unmapped:/, "").replace(/[_-]+/g, " ").trim();

/** Only eligibility rules count towards "criteria met"; registration, document and post-approval steps do not. */
export const isEligibilityRule = (r: ApiRequirement) => (r.category ?? "eligibility") === "eligibility";

export function fromApiScheme(s: ApiScheme): SchemeVM {
  const pips = s.requirements.filter(isEligibilityRule).map((r) => PIP[r.status] ?? "unk");
  const fallback = s.source_type === "fallback";
  return {
    id: s.id,
    name: s.name,
    dept: [s.government_level, s.department].filter(Boolean).join(" · ").toUpperCase(),
    summary: s.summary ?? "",
    status: s.assessment_status ? STATUS[s.assessment_status] : "nv",
    expl: s.assessment_explanation ?? "",
    pips,
    met: pips.filter((p) => p === "ok").length,
    missing: s.missing_attributes.map(humanize),
    missingAttrs: s.missing_attributes,
    url: s.application_url ?? s.official_sources[0] ?? "",
    sourceType: fallback ? "fallback" : "verified",
    lastVerified: fallback ? "Offline fallback data" : "",
    verified: s.assessment_status !== "not_yet_verified" && s.assessment_status != null,
  };
}

export function fromEvaluated(e: EvaluatedScheme): SchemeVM {
  const s = e.scheme;
  return {
    id: s.id, name: s.name, dept: s.dept, summary: s.summary, status: e.status, expl: e.expl, pips: e.pips, met: e.met,
    missing: e.missing, missingAttrs: [], url: s.url, sourceType: s.sourceType, lastVerified: s.lastVerified, verified: s.verified,
  };
}

/** The same three situations as the demo's improvement card, worked out from what the backend says is still open. */
export function improveFromApi(schemes: SchemeVM[], questions: ApiQuestion[], skippedAny: boolean): Improve {
  if (questions.length > 0) {
    const n = questions.length;
    const open = new Set(schemes.filter((s) => s.status === "info" || s.status === "unclear").map((s) => s.id));
    const affected = new Set(questions.flatMap((q) => q.related_scheme_ids).filter((id) => open.has(id))).size;
    const tail = affected > 0 ? ` to check ${affected} ${affected === 1 ? "scheme" : "schemes"}.` : ".";
    return { title: `Answer ${n} more ${n === 1 ? "question" : "questions"}${tail}`, to: "/questions" };
  }
  const open = schemes.filter((s) => s.status !== "nv");
  const unknown = [...new Set(open.flatMap((s) => s.missing))];
  if (unknown.length > 0) {
    // Only offer the Context page when it has a field that could fill a gap; otherwise it is a dead end.
    const fillable = open.some((s) => s.missingAttrs.some((a) => CONTEXT_ATTRIBUTES.has(a)));
    if (skippedAny || fillable) {
      return {
        title: "No more questions to answer.",
        detail: `Still unknown: ${unknown.join("; ")}.${skippedAny ? " You can revisit answers you skipped." : ""}`,
        to: skippedAny ? "/questions" : "/details",
        cta: skippedAny ? "Revisit those answers (optional)" : "Add optional details",
      };
    }
    return {
      title: "We have no more questions we can ask.",
      detail: `Still unknown: ${unknown.join("; ")}. Check these on the official page; the document plan lists what to bring.`,
      to: "/plan",
      cta: "Build my document plan",
    };
  }
  const unverified = schemes.filter((s) => s.status === "nv").length;
  return {
    title: "All available information has been considered.",
    detail: unverified > 0
      ? `${unverified} ${unverified === 1 ? "scheme uses rules" : "schemes use rules"} we couldn't verify from an official source yet. Confirm them on the official page and with the documents.`
      : "The rest needs confirming with the official documents.",
    to: "/plan",
    cta: "Build my document plan",
  };
}

// ---- Document plan ----

export type PlanDocVM = {
  id: string;
  name: string;
  reason: string;
  forIds: string[];
  forNames: string[];
  shared: boolean;
  /** Names of documents that have to come first. */
  after: string[];
  url: string;
  status: DocStatus;
};
export type PlanVM = {
  docs: PlanDocVM[];
  schemes: { id: string; name: string }[];
  /** doc -> scheme ("needed for"), and pre -> doc ("get after"). */
  edges: { doc: string; scheme: string }[];
  deps: { pre: string; doc: string }[];
  explanation: string;
  warnings: string[];
};

const docStatus = (s: string): DocStatus => (s === "have" || s === "obtained" ? s : "needed");

export function planFromApi(p: ApiPlan): PlanVM {
  const schemeNodes = p.nodes.filter((n) => n.kind === "scheme");
  const nameOf = new Map(p.nodes.map((n) => [n.id, n.label]));
  const docs = [...p.checklist].sort((a, b) => a.order - b.order).map((c): PlanDocVM => ({
    id: c.id,
    name: c.name,
    // the backend's default reason only repeats the "for" tags shown beside it, so don't show it twice
    reason: c.reason.replace(/\s*Needed for \d+ schemes?:.*$/, "").trim(),
    forIds: c.required_by_scheme_ids,
    forNames: c.required_by_scheme_ids.map((id) => nameOf.get(id) ?? id),
    shared: c.required_by_scheme_ids.length > 1 || p.shared_prerequisites.includes(c.id),
    after: c.dependencies.map((d) => nameOf.get(d) ?? d),
    url: c.source_urls[0] ?? "",
    status: docStatus(c.status),
  }));
  const ids = new Set(docs.map((d) => d.id));
  const schemeIds = new Set(schemeNodes.map((n) => n.id));
  return {
    docs,
    schemes: schemeNodes.map((n) => ({ id: n.id, name: n.label })),
    edges: p.edges.filter((e) => ids.has(e.source) && schemeIds.has(e.target)).map((e) => ({ doc: e.source, scheme: e.target })),
    deps: p.edges.filter((e) => e.relation === "prerequisite_of" && ids.has(e.source) && ids.has(e.target)).map((e) => ({ pre: e.source, doc: e.target })),
    explanation: p.explanation,
    warnings: p.warnings,
  };
}

export function planFromDemo(status: Record<string, DocStatus>): PlanVM {
  const nodes = PLAN_SCHEME_NODES.map((n) => ({ id: n.id, name: n.label }));
  const docs = PLAN_DOCS.map((d): PlanDocVM => ({
    id: d.id, name: d.name, reason: d.reason,
    forIds: d.for.flatMap((n) => nodes.filter((s) => s.name === n).map((s) => s.id)),
    forNames: d.for, shared: !!d.shared, after: d.after ? [d.after] : [], url: d.url, status: status[d.id] ?? "needed",
  }));
  return {
    docs,
    schemes: nodes,
    edges: docs.flatMap((d) => d.forIds.map((scheme) => ({ doc: d.id, scheme }))),
    deps: docs.flatMap((d) => d.after.flatMap((n) => docs.filter((p) => p.name === n).map((p) => ({ pre: p.id, doc: d.id })))),
    explanation: "",
    warnings: [],
  };
}
