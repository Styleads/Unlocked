import { describe, expect, it } from "vitest";
import { buildIcs } from "./ics";
import { PLAN_DOCS, PLAN_SCHEME_NODES, SCHEMES } from "./data";

const ics = (isoDate: string, extra: Partial<Parameters<typeof buildIcs>[0]> = {}) =>
  buildIcs({ title: "Apply: Demo Scholarship A", isoDate, description: "Docs", ...extra });
const line = (text: string, key: string) => text.split("\r\n").find((l) => l.startsWith(key));

describe("buildIcs", () => {
  it("is a well-formed all-day event with CRLF endings", () => {
    const t = ics("2026-12-30");
    expect(t.startsWith("BEGIN:VCALENDAR\r\n")).toBe(true);
    expect(t.endsWith("END:VCALENDAR\r\n")).toBe(true);
    expect(t).not.toMatch(/[^\r]\n/);
    expect(line(t, "DTSTART")).toBe("DTSTART;VALUE=DATE:20261230");
    expect(line(t, "DTEND")).toBe("DTEND;VALUE=DATE:20261231");
  });
  it("ends the event the next day across month, year and leap-day boundaries", () => {
    expect(line(ics("2026-12-31"), "DTEND")).toBe("DTEND;VALUE=DATE:20270101");
    expect(line(ics("2026-01-31"), "DTEND")).toBe("DTEND;VALUE=DATE:20260201");
    expect(line(ics("2028-02-28"), "DTEND")).toBe("DTEND;VALUE=DATE:20280229");
    expect(line(ics("2027-02-28"), "DTEND")).toBe("DTEND;VALUE=DATE:20270301");
  });
  it("escapes commas, semicolons, backslashes and newlines in text fields", () => {
    const t = ics("2026-12-30", { title: "a, b; c", description: "x\\y\nz" });
    expect(line(t, "SUMMARY")).toBe("SUMMARY:a\\, b\\; c");
    expect(line(t, "DESCRIPTION")).toBe("DESCRIPTION:x\\\\y\\nz");
  });
  it("includes the link only when given, and gives each event its own id", () => {
    expect(line(ics("2026-12-30"), "URL")).toBeUndefined();
    expect(line(ics("2026-12-30", { url: "https://example.gov.in/a" }), "URL")).toBe("URL:https://example.gov.in/a");
    expect(line(ics("2026-12-30"), "UID")).not.toBe(line(ics("2026-12-30"), "UID"));
  });
});

describe("plan data", () => {
  it("every document is needed for a scheme that exists, and 'after' names a real document", () => {
    const names = new Set(SCHEMES.map((s) => s.name));
    for (const d of PLAN_DOCS) {
      for (const f of d.for) expect(names.has(f), `${d.id} for ${f}`).toBe(true);
      if (d.after) expect(PLAN_DOCS.some((p) => p.name === d.after), `${d.id} after`).toBe(true);
    }
  });
  it("graph scheme nodes match real scheme names", () => {
    for (const n of PLAN_SCHEME_NODES) expect(SCHEMES.find((s) => s.id === n.id)?.name).toBe(n.label);
  });
});
