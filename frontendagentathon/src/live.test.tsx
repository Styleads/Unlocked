// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App";
import { installBrowserShims } from "./testkit";
import type { ApiPlan, ApiQuestion, ApiScheme } from "./api";

beforeAll(installBrowserShims);

/** A fake backend that answers the way api/main.py does (shapes taken from real responses). */
function fakeBackend(opts: { discoverStatus?: number } = {}) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const requirements = (income: "unknown" | "satisfied" | "not_satisfied") => [
    { requirement_id: "s1_req_1", attribute: "education_level", status: "satisfied", reason: "Your answer meets this rule.", criterion: "Must be an undergraduate student.", source_url: "https://example.gov.in/s1" },
    { requirement_id: "s1_req_2", attribute: "annual_family_income", status: income, reason: income === "unknown" ? "You haven't answered this yet." : "ok", criterion: "Family income up to Rs. 2.5 lakh.", source_url: "https://example.gov.in/s1" },
  ];
  const scheme = (income: "unknown" | "satisfied" | "not_satisfied"): ApiScheme[] => [
    {
      id: "s1", name: "Fictional Merit Scholarship", summary: "Scholarship for undergraduates.", department: "Dept of Examples", government_level: "state",
      benefit: "Tuition support", documents: [{ name: "Income certificate", source_url: "https://example.gov.in/s1" }], application_steps: ["Apply on the portal."],
      application_url: "https://example.gov.in/s1/apply", official_sources: ["https://example.gov.in/s1"], source_type: "live_search",
      assessment_status: income === "unknown" ? "more_information_needed" : income === "satisfied" ? "potential_match" : "unlikely_to_match",
      assessment_explanation: income === "unknown" ? "We still need your family income." : "Your answers appear to meet the rules.",
      requirements: requirements(income) as ApiScheme["requirements"], missing_attributes: income === "unknown" ? ["annual_family_income"] : [],
    },
    {
      id: "s2", name: "Fictional Housing Aid", summary: "Rent support.", department: "Dept of Examples", government_level: "state", documents: [], application_steps: [],
      official_sources: ["https://example.gov.in/s2"], source_type: "fallback", assessment_status: "not_yet_verified",
      assessment_explanation: "These rules haven't been confirmed from an official source.",
      requirements: [{ requirement_id: "s2_req_1", attribute: "age", status: "unverified", reason: "Not confirmed.", criterion: "Must be under 30.", source_url: null }], missing_attributes: [],
    },
  ];
  const question: ApiQuestion = {
    id: "q_annual_family_income", attribute: "annual_family_income", question: "What's your family's annual income?", input_type: "range",
    options: [], ranges: [{ label: "Under ₹2.5 lakh", min: 0, max: 250000 }, { label: "Above ₹2.5 lakh", min: 250001, max: null }],
    why_asked: "One scheme sets an income limit.", related_scheme_ids: ["s1"], sensitivity: "high", allow_prefer_not_to_answer: true,
  };
  const plan = (have: boolean): ApiPlan => ({
    checklist: [{ id: "doc_income_certificate", name: "Income Certificate", status: have ? "have" : "needed", order: 1, required_by_scheme_ids: ["s1"], dependencies: [], source_urls: ["https://example.gov.in/s1"], reason: "Needed for 1 scheme: Fictional Merit Scholarship." }],
    nodes: [{ id: "doc_income_certificate", label: "Income Certificate", kind: "document" }, { id: "s1", label: "Fictional Merit Scholarship", kind: "scheme" }],
    edges: [{ source: "doc_income_certificate", target: "s1", relation: "required_for", source_url: "https://example.gov.in/s1" }],
    shared_prerequisites: [], explanation: "1 document covers the scheme you can act on now.", warnings: [], excluded_documents: [],
  });

  let income: "unknown" | "satisfied" | "not_satisfied" = "unknown";
  let have = false;
  const respond = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

  const fetchImpl = (async (url: string, init?: RequestInit) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const method = (init?.method ?? "GET").toUpperCase();
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    if (method === "POST" && path === "/api/sessions") return respond(201, { session_id: "sess-1", status: "initialized" });
    if (path.endsWith("/discover")) {
      if (opts.discoverStatus && opts.discoverStatus !== 200) return respond(opts.discoverStatus, { detail: "Discovery pipeline failed: upstream timeout" });
      return respond(200, { session_id: "sess-1", total_schemes: 2, schemes: scheme(income), questions: [question], source_mode: "live_search", warnings: [] });
    }
    if (path.endsWith("/schemes")) return respond(200, scheme(income));
    if (path.endsWith("/questions")) return respond(200, income === "unknown" ? [question] : []);
    if (path.endsWith("/answers")) {
      const a = body.answers[0];
      income = a.state !== "answered" ? "unknown" : a.value.max !== null && a.value.max <= 250000 ? "satisfied" : "not_satisfied";
      return respond(200, { session_id: "sess-1", next_questions: [] });
    }
    if (path.endsWith("/plan")) return respond(200, plan(have));
    if (path.includes("/checklist/")) { have = body.status === "have"; return respond(200, plan(have)); }
    if (path.endsWith("/progress")) return respond(200, { summary: "You reported that you submitted the application.", warnings: [], follow_ups: [] });
    if (path.endsWith("/actions/email")) return respond(200, { status: "ready", title: "Email", subject: "Query about Fictional Merit Scholarship", body_content: "Dear Sir or Madam,\n\nWhich documents are required?\n\n[Your name]", instructions: "", missing_fields: [], warnings: ["We don't have a verified email address for this department."], generated_by: "template", target_destination: null });
    if (path.endsWith("/actions/calendar")) return respond(200, { status: "ready", title: "Deadline", body_content: "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n", filename: "s1.ics", instructions: "", missing_fields: [], warnings: [], generated_by: "template" });
    if (method === "DELETE") return respond(200, { deleted: true });
    return respond(404, { detail: `no route ${path}` });
  }) as typeof fetch;
  return { fetchImpl, calls };
}

const open = (path: string) => {
  window.history.pushState({}, "", path);
  return render(<App />);
};

let backend: ReturnType<typeof fakeBackend>;
beforeEach(() => {
  sessionStorage.clear();
  backend = fakeBackend();
  globalThis.fetch = backend.fetchImpl;
});
afterEach(cleanup);

const runDiscovery = async () => {
  open("/details");
  fireEvent.click(screen.getByRole("link", { name: /Find schemes/ }));
  await screen.findByText("2 potential schemes identified.");
};

describe("connected to a backend", () => {
  it("creates a session from the Context page and runs discovery once", async () => {
    await runDiscovery();
    const create = backend.calls.find((c) => c.path === "/api/sessions" && c.method === "POST")!;
    expect(create.body).toMatchObject({ scope: "guided", context: { state: "Karnataka" } });
    expect(backend.calls.filter((c) => c.path.endsWith("/discover"))).toHaveLength(1);
    expect(backend.calls.filter((c) => c.path === "/api/sessions")).toHaveLength(1);
  });

  it("shows the backend's schemes on Results, not the demo ones", async () => {
    await runDiscovery();
    fireEvent.click(screen.getAllByRole("link", { name: /Continue/ })[0]);
    fireEvent.click(screen.getByRole("link", { name: /See my results/ }));
    expect(await screen.findByRole("heading", { name: "Fictional Merit Scholarship" })).toBeTruthy();
    expect(screen.queryByText("Demo Scholarship A")).toBeNull();
    expect(screen.getByText(/Answer 1 more question to check 1 scheme/)).toBeTruthy();
  });

  it("renders the backend's question by its input type and sends a structured answer", async () => {
    await runDiscovery();
    fireEvent.click(screen.getAllByRole("link", { name: /Continue/ })[0]);
    expect(await screen.findByText("What's your family's annual income?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Under ₹2.5 lakh" }));
    await waitFor(() => expect(backend.calls.some((c) => c.path.endsWith("/answers"))).toBe(true));
    const sent = backend.calls.find((c) => c.path.endsWith("/answers"))!.body as { answers: unknown[] };
    expect(sent.answers).toEqual([{ attribute: "annual_family_income", state: "answered", value: { min: 0, max: 250000 } }]);
    await screen.findByText("Answered");
    // the question stays on screen after the backend stops asking it
    expect(screen.getByText("What's your family's annual income?")).toBeTruthy();

    fireEvent.click(screen.getByRole("link", { name: /See my results/ }));
    await screen.findByRole("heading", { name: "Fictional Merit Scholarship" });
    expect(screen.queryByText(/Answer \d+ more/)).toBeNull();
    expect(screen.getByText("All available information has been considered.")).toBeTruthy();
  });

  it('sends "Not sure" as unknown, which leaves the scheme needing information', async () => {
    await runDiscovery();
    fireEvent.click(screen.getAllByRole("link", { name: /Continue/ })[0]);
    await screen.findByText("What's your family's annual income?");
    fireEvent.click(screen.getByRole("button", { name: "Not sure" }));
    await screen.findByText("Marked not sure. That's fine.");
    const sent = backend.calls.find((c) => c.path.endsWith("/answers"))!.body as { answers: Record<string, unknown>[] };
    expect(sent.answers[0]).toEqual({ attribute: "annual_family_income", state: "unknown" });
    fireEvent.click(screen.getByRole("link", { name: /See my results/ }));
    await screen.findByRole("heading", { name: "Fictional Merit Scholarship" });
    expect(screen.getAllByText(/family income/).length).toBeGreaterThan(0);
  });

  it("builds the plan from the backend and sends document status changes to it", async () => {
    await runDiscovery();
    window.history.pushState({}, "", "/plan");
    cleanup();
    render(<App />);
    expect(await screen.findByText("1 document covers the scheme you can act on now.")).toBeTruthy();
    const group = await screen.findByRole("group", { name: "Status of Income Certificate" });
    fireEvent.click(within(group).getByRole("button", { name: "I have it" }));
    await waitFor(() => expect(backend.calls.some((c) => c.path.includes("/checklist/doc_income_certificate"))).toBe(true));
    expect(backend.calls.find((c) => c.path.includes("/checklist/"))!.body).toEqual({ status: "have" });
    await screen.findByText("All your documents are ready.", { exact: false });
  });

  it("gets an email draft and a calendar file from the backend, and reports progress", async () => {
    await runDiscovery();
    window.history.pushState({}, "", "/plan");
    cleanup();
    render(<App />);
    await screen.findByText("1 document covers the scheme you can act on now.");
    fireEvent.click(screen.getByRole("button", { name: /Draft email/ }));
    fireEvent.click(screen.getByRole("button", { name: /Write the draft/ }));
    await screen.findByDisplayValue("Query about Fictional Merit Scholarship");
    expect(screen.getByText(/We don't have a verified email address/)).toBeTruthy();
    const mail = screen.getByRole("link", { name: /Open in my email app/ }) as HTMLAnchorElement;
    expect(mail.getAttribute("href")).toMatch(/^mailto:\?subject=/); // no invented address
    const emailCall = backend.calls.find((c) => c.path.endsWith("/actions/email"))!.body as Record<string, unknown>;
    expect(emailCall).toMatchObject({ scheme_id: "s1", purpose: "inquiry" });

    const g = screen.getByRole("group", { name: "Application progress for Fictional Merit Scholarship" });
    fireEvent.click(within(g).getByRole("button", { name: /Submitted/ }));
    await screen.findByText("You reported that you submitted the application.");
    expect(backend.calls.find((c) => c.path.endsWith("/progress"))!.body).toEqual({ scheme_id: "s1", updates: [{ field: "submitted", state: "yes" }] });
  });

  it("shows the real scheme on the details page", async () => {
    await runDiscovery();
    fireEvent.click(screen.getAllByRole("link", { name: /Continue/ })[0]);
    fireEvent.click(screen.getByRole("link", { name: /See my results/ }));
    await screen.findByRole("heading", { name: "Fictional Merit Scholarship" });
    fireEvent.click(screen.getAllByRole("link", { name: "View details" })[0]);
    expect(await screen.findByText("“Family income up to Rs. 2.5 lakh.”")).toBeTruthy();
    expect(screen.getByText("Tuition support")).toBeTruthy();
    expect(screen.queryByText(/Demo Scholarship A/)).toBeNull();
  });

  it("keeps working after a refresh by reloading from the backend", async () => {
    await runDiscovery();
    cleanup();
    open("/results");
    expect(await screen.findByRole("heading", { name: "Fictional Merit Scholarship" })).toBeTruthy();
  });
});

describe("when the backend is unavailable", () => {
  it("falls back to the demo data without an error", async () => {
    globalThis.fetch = (() => Promise.reject(new TypeError("offline"))) as typeof fetch;
    open("/details");
    fireEvent.click(screen.getByRole("link", { name: /Find schemes/ }));
    // the demo sequence runs; its card reads from the built-in schemes
    expect(await screen.findByText("5 potential schemes identified.")).toBeTruthy();
    expect(screen.queryByText(/couldn't reach the official sources/)).toBeNull();
  });

  it("shows the error screen with the backend's message when discovery fails", async () => {
    backend = fakeBackend({ discoverStatus: 500 });
    globalThis.fetch = backend.fetchImpl;
    open("/details");
    fireEvent.click(screen.getByRole("link", { name: /Find schemes/ }));
    expect(await screen.findByRole("heading", { name: /couldn't reach the official sources/ })).toBeTruthy();
    expect(screen.getByText(/upstream timeout/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
