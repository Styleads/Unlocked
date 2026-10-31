import { QUESTIONS, SCHEMES } from "./data";
import type { Criterion, Pip, Scheme } from "./data";
import type { Session } from "./session";

/**
 * Everything the Results (and scheme) pages show is derived here from the saved session, so the
 * scheme cards, breakdown, criteria summary and "improve" card can never disagree.
 *
 * "Not sure" and "Prefer not to say" are recorded responses, but they never satisfy a rule:
 * the criterion stays unknown, with a cause that says why.
 */

export type Cause = "unanswered" | "not_sure" | "private";
export type Evaluated = { criterion: Criterion; pip: Pip; cause?: Cause };
export type SchemeStatus = "ok" | "info" | "nv" | "warn";

export type EvaluatedScheme = {
  scheme: Scheme;
  status: SchemeStatus;
  criteria: Evaluated[];
  pips: Pip[];
  met: number;
  /** Specific information still missing, e.g. "family income (you marked not sure)". */
  missing: string[];
  expl: string;
};

const SKIP: Record<string, Cause> = { __unsure: "not_sure", __prefer: "private" };
const CAUSE_NOTE: Record<Cause, string> = { unanswered: "", not_sure: " (you marked not sure)", private: " (you kept this private)" };

function evaluateCriterion(c: Criterion, session: Session): Evaluated {
  const raw = c.source.kind === "question" ? session.answers[c.source.id] : session.details[c.source.field];
  if (raw === undefined || raw === "") return { criterion: c, pip: "unk", cause: "unanswered" };
  const skipped = Object.prototype.hasOwnProperty.call(SKIP, raw) ? SKIP[raw] : undefined;
  if (skipped) return { criterion: c, pip: "unk", cause: skipped };

  if ("oneOf" in c.test) return { criterion: c, pip: c.test.oneOf.includes(raw) ? "ok" : "no" };
  const n = Number(raw);
  if (!Number.isFinite(n)) return { criterion: c, pip: "unk", cause: "unanswered" };
  return { criterion: c, pip: n >= c.test.min ? "ok" : "no" };
}

export function evaluateScheme(scheme: Scheme, session: Session): EvaluatedScheme {
  // Unverified rules are never evaluated: they can't rule a scheme in or out.
  if (!scheme.verified) {
    const criteria = scheme.criteria.map((criterion): Evaluated => ({ criterion, pip: "unv" }));
    return {
      scheme, status: "nv", criteria, pips: criteria.map(() => "unv"), met: 0, missing: [],
      expl: "We couldn't confirm these rules from an official source yet, so we haven't checked them.",
    };
  }
  const criteria = scheme.criteria.map((c) => evaluateCriterion(c, session));
  const pips = criteria.map((e) => e.pip);
  const met = pips.filter((p) => p === "ok").length;
  const unknown = criteria.filter((e) => e.pip === "unk");
  const unmet = criteria.filter((e) => e.pip === "no");
  const status: SchemeStatus = unmet.length ? "warn" : unknown.length ? "info" : "ok";
  const missing = [...new Set(unknown.map((e) => e.criterion.missing + CAUSE_NOTE[e.cause ?? "unanswered"]))];

  const expl =
    status === "warn" ? `Your answers appear not to meet a stated rule: ${unmet.map((e) => e.criterion.missing).join(", ")}.`
    : status === "info" ? `We still need your ${missing.join(", ")} to check the remaining ${unknown.length === 1 ? "rule" : "rules"}.`
    : `Your answers appear to meet all ${criteria.length} criteria we checked.`;

  return { scheme, status, criteria, pips, met, missing, expl };
}

export function evaluateAll(session: Session): EvaluatedScheme[] {
  return SCHEMES.map((s) => evaluateScheme(s, session));
}

/** "Q1 · Q4"-style list of the questions whose answers can change this scheme's result. */
export function questionsAffecting(scheme: Scheme): string {
  const ids = new Set(scheme.criteria.flatMap((c) => (c.source.kind === "question" ? [c.source.id] : [])));
  return QUESTIONS.flatMap((q, i) => (ids.has(q.id) ? [`Q${i + 1}`] : [])).join(" · ");
}

export type Improve = { title: string; detail?: string; to: "/questions" | "/details" | "/plan"; cta?: string };

/** Which of the three situations the "Improve your results" card is in, from the same evaluation. */
export function improvement(evals: EvaluatedScheme[], session: Session): Improve {
  const checkable = evals.filter((e) => e.scheme.verified);
  const unanswered = QUESTIONS.filter((q) => session.answers[q.id] === undefined);
  const unanswered_ids = new Set(unanswered.map((q) => q.id));

  // B: questions the user hasn't responded to. Count only schemes that one of those answers could still change.
  if (unanswered.length > 0) {
    const n = unanswered.length;
    const affected = checkable.filter(
      (e) => e.status !== "warn" && e.criteria.some((c) => c.pip === "unk" && c.criterion.source.kind === "question" && unanswered_ids.has(c.criterion.source.id)),
    ).length;
    const tail = affected > 0 ? ` to check ${affected} ${affected === 1 ? "scheme" : "schemes"}.` : ".";
    return { title: `Answer ${n} more ${n === 1 ? "question" : "questions"}${tail}`, to: "/questions" };
  }

  // A: every question has a response, but some rules are still unknown.
  const unknown = checkable.flatMap((e) => e.criteria.filter((c) => c.pip === "unk"));
  if (unknown.length > 0) {
    const byLabel = new Map<string, string>();
    unknown.forEach((u) =>
      byLabel.set(
        u.criterion.missing,
        u.criterion.source.kind === "detail" ? `${u.criterion.missing} (add it on the Context page)` : `${u.criterion.missing}${CAUSE_NOTE[u.cause ?? "unanswered"]}`,
      ),
    );
    const parts = [...byLabel.values()];
    const needsDetail = unknown.some((u) => u.criterion.source.kind === "detail");
    return {
      title: `All ${QUESTIONS.length} questions answered.`,
      detail: `Still unknown: ${parts.join("; ")}.`,
      to: needsDetail ? "/details" : "/questions",
      cta: needsDetail ? "Add optional details" : "Revisit those answers (optional)",
    };
  }

  // C: nothing left to ask. Say what still needs outside confirmation.
  const unverified = evals.filter((e) => !e.scheme.verified).length;
  return {
    title: "All available information has been considered.",
    detail: unverified > 0
      ? `${unverified} ${unverified === 1 ? "scheme uses rules" : "schemes use rules"} we couldn't verify from an official source yet. Confirm them on the official page and with the documents.`
      : "The rest needs confirming with the official documents.",
    to: "/plan",
    cta: "Build my document plan",
  };
}
