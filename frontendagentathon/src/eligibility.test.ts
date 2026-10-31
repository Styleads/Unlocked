import { describe, expect, it } from "vitest";
import { evaluateAll, evaluateScheme, improvement, questionsAffecting } from "./eligibility";
import { QUESTIONS, SCHEMES } from "./data";
import type { Session } from "./session";

const session = (answers: Session["answers"] = {}, age = ""): Session => ({
  theme: "dark", scope: "guided",
  categories: { Scholarships: true, "Fee concessions": true, Healthcare: false, Pensions: false, Subsidies: false },
  details: { state: "Karnataka", district: "", age, edu: "", need: "" },
  answers, docStatus: {}, apply: {},
});
const full = { income: "₹1–2.5 lakh", inst: "Government", dom: "Yes", edu: "Undergraduate" };
const byId = (s: Session) => Object.fromEntries(evaluateAll(s).map((e) => [e.scheme.id, e]));

describe("improvement card", () => {
  it("never asks for more answers once all four questions have a response", () => {
    expect(improvement(evaluateAll(session(full)), session(full)).title).not.toMatch(/Answer \d+ more/);
  });
  it("reports the real number of unanswered questions", () => {
    const s = session({ income: "Under ₹1 lakh", edu: "Undergraduate" });
    expect(improvement(evaluateAll(s), s).title).toMatch(/^Answer 2 more questions/);
    const one = session({ ...full, dom: undefined });
    expect(improvement(evaluateAll(one), one).title).toMatch(/^Answer 1 more question\b/);
  });
  it("with no answers asks for all four", () => {
    const s = session();
    expect(improvement(evaluateAll(s), s).title).toMatch(/^Answer 4 more questions/);
  });
  it("case A: all answered but age blank names age and points to the Context page", () => {
    const s = session(full);
    const imp = improvement(evaluateAll(s), s);
    expect(imp.title).toBe("All 4 questions answered.");
    expect(imp.detail).toContain("age");
    expect(imp.to).toBe("/details");
  });
  it("case C: nothing left to ask says so and mentions the unverified scheme", () => {
    const s = session(full, "25");
    const imp = improvement(evaluateAll(s), s);
    expect(imp.title).toBe("All available information has been considered.");
    expect(imp.detail).toMatch(/1 scheme uses rules/);
    expect(imp.to).toBe("/plan");
  });
});

describe('"Not sure" and "Prefer not to say"', () => {
  it("count as a response but leave the criterion unknown, with the reason", () => {
    for (const [skip, note] of [["__unsure", "you marked not sure"], ["__prefer", "you kept this private"]] as const) {
      const s = session({ ...full, income: skip }, "25");
      const a = byId(s).a;
      expect(a.status).toBe("info");
      expect(a.pips).toEqual(["ok", "ok", "unk"]);
      expect(a.missing.join()).toContain(note);
      expect(improvement(evaluateAll(s), s).title).not.toMatch(/Answer \d+ more/);
    }
  });
  it("are never treated as meeting or failing a rule", () => {
    const e = byId(session({ ...full, income: "__unsure" }, "25"));
    expect(e.a.status).not.toBe("ok");
    expect(e.a.status).not.toBe("warn");
  });
});

describe("recalculation", () => {
  it("changing income flips the schemes that use it and leaves the others alone", () => {
    const lo = byId(session({ ...full, income: "Under ₹1 lakh" }, "25"));
    const hi = byId(session({ ...full, income: "Above ₹8 lakh" }, "25"));
    expect(lo.a.status).toBe("ok");
    expect(hi.a.status).toBe("warn");
    expect(hi.b.status).toBe("warn");
    expect([hi.c.status, hi.d.status, hi.e.status]).toEqual([lo.c.status, lo.d.status, lo.e.status]);
  });
  it("counts met criteria from the answers", () => {
    const e = byId(session({ ...full, income: "Under ₹1 lakh" }, "25"));
    expect(e.a.met).toBe(3);
    expect(e.b.met).toBe(3);
  });
  it("uses the age from the Context form for the pension", () => {
    expect(byId(session(full, "70")).e.status).toBe("ok");
    expect(byId(session(full, "25")).e.status).toBe("warn");
    expect(byId(session(full, "")).e.status).toBe("info");
    expect(byId(session(full, "abc")).e.status).toBe("info");
  });
});

describe("safety rules", () => {
  it("never evaluates unverified schemes, whatever the answers", () => {
    for (const a of [{}, full, { dom: "No", edu: "Postgraduate", inst: "Private unaided" }]) {
      const d = byId(session(a)).d;
      expect(d.status).toBe("nv");
      expect(d.pips.every((p) => p === "unv")).toBe(true);
      expect(d.met).toBe(0);
    }
  });
  it("an answer named like an object property is just an unmet value, not a skip marker", () => {
    const e = byId(session({ ...full, dom: "toString" }, "25"));
    expect(e.c.pips[1]).toBe("no");
  });
  it("starts every verified scheme as unknown, not met, before any answer", () => {
    for (const e of evaluateAll(session())) {
      if (!e.scheme.verified) continue;
      expect(e.met).toBe(0);
      expect(e.status).toBe("info");
    }
  });
});

describe("derived text", () => {
  it("explanations match the status", () => {
    const e = byId(session({ ...full, income: "Under ₹1 lakh" }, "25"));
    expect(e.a.expl).toMatch(/meet all 3 criteria/);
    const w = byId(session({ ...full, income: "Above ₹8 lakh" }, "25"));
    expect(w.a.expl).toMatch(/not to meet a stated rule: family income/);
  });
  it("lists affected questions per scheme from its criteria", () => {
    const a = SCHEMES.find((s) => s.id === "a")!;
    expect(questionsAffecting(a)).toBe("Q1 · Q3 · Q4");
    expect(evaluateScheme(a, session()).criteria).toHaveLength(3);
  });
});

describe("data consistency", () => {
  it("every question-based criterion points at a real question and only accepts its real options", () => {
    for (const s of SCHEMES) {
      for (const c of s.criteria) {
        if (c.source.kind !== "question") continue;
        const q = QUESTIONS.find((x) => x.id === (c.source as { id: string }).id);
        expect(q, `${s.id}/${c.id} question`).toBeDefined();
        if ("oneOf" in c.test) for (const v of c.test.oneOf) expect(q!.opts, `${s.id}/${c.id} option "${v}"`).toContain(v);
      }
    }
  });
});
