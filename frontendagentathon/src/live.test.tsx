// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App";
import { installBrowserShims } from "./testkit";
import type { ApiPlan, ApiQuestion, ApiScheme } from "./api";

beforeAll(installBrowserShims);

/** A fake backend that answers the way api/main.py does (shapes taken from real responses). */
function fakeBackend(opts: { discoverStatus?: number; extraQuestion?: boolean; fallbackFirst?: boolean; sendFails?: boolean } = {}) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const requirements = (income: "unknown" | "satisfied" | "not_satisfied") => [
    { requirement_id: "s1_req_1", attribute: "education_level", status: "satisfied", reason: "Your answer meets this rule.", criterion: "Must be an undergraduate student.", source_url: "https://example.gov.in/s1" },
    { requirement_id: "s1_req_2", attribute: "annual_family_income", status: income, reason: income === "unknown" ? "You haven't answered this yet." : "ok", criterion: "Family income up to Rs. 2.5 lakh.", source_url: "https://example.gov.in/s1" },
    // a step in applying, not a condition on the person: it must not count as a criterion
    { requirement_id: "s1_req_3", attribute: "portal_registration", status: "unknown", category: "application_prerequisite", reason: "Part of the application process.", criterion: "Applicants register on the scholarship portal.", source_url: "https://example.gov.in/s1" },
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
  const second: ApiQuestion = {
    id: "q_employment_status", attribute: "employment_status", question: "Which best describes your work situation?", input_type: "select",
    options: ["Student", "Employed"], ranges: [], why_asked: "One scheme asks about work.", related_scheme_ids: ["s1"], sensitivity: "low", allow_prefer_not_to_answer: false,
  };
  const asked = () => [question, ...(opts.extraQuestion ? [second] : [])];
  const plan = (have: boolean): ApiPlan => ({
    checklist: [{ id: "doc_income_certificate", name: "Income Certificate", status: have ? "have" : "needed", order: 1, required_by_scheme_ids: ["s1"], dependencies: [], source_urls: ["https://example.gov.in/s1"], reason: "Needed for 1 scheme: Fictional Merit Scholarship." }],
    nodes: [{ id: "doc_income_certificate", label: "Income Certificate", kind: "document" }, { id: "s1", label: "Fictional Merit Scholarship", kind: "scheme" }],
    edges: [{ source: "doc_income_certificate", target: "s1", relation: "required_for", source_url: "https://example.gov.in/s1" }],
    shared_prerequisites: [], explanation: "1 document covers the scheme you can act on now.", warnings: [], excluded_documents: [],
  });

  let discoverRuns = 0;
  let prefs: Record<string, unknown> = { session_id: "sess-1", email: null, email_enabled: false, categories: {}, timezone: "Asia/Kolkata" };
  const notifs: Record<string, unknown>[] = [];
  const appts: Record<string, unknown>[] = [];
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
      return respond(200, { session_id: "sess-1", total_schemes: 2, schemes: scheme(income), questions: asked(), source_mode: opts.fallbackFirst && discoverRuns++ === 0 ? "fallback" : "live_search", warnings: [] });
    }
    if (path.endsWith("/schemes")) return respond(200, scheme(income));
    if (path.endsWith("/questions")) return respond(200, income === "unknown" ? asked() : []);
    if (path.endsWith("/answers")) {
      const a = body.answers[0];
      income = a.state !== "answered" ? "unknown" : a.value.max !== null && a.value.max <= 250000 ? "satisfied" : "not_satisfied";
      return respond(200, { session_id: "sess-1", next_questions: [] });
    }
    if (path.endsWith("/plan")) return respond(200, plan(have));
    if (path.includes("/checklist/")) { have = body.status === "have"; return respond(200, plan(have)); }
    if (path.endsWith("/notifications/preferences")) {
      if (method === "POST") prefs = { ...prefs, ...body, session_id: "sess-1", consent_at: "2026-11-01T02:00:00Z" };
      return respond(200, prefs);
    }
    if (path.endsWith("/notifications/action-plan/preview")) return respond(200, { to_email: String(prefs.email), subject: "Your Unlocked Action Plan", body_text: "Hello,\n\nHere is your plan.", body_html: "<p>Hello</p>", schemes_included: ["Fictional Merit Scholarship"], checklist_tasks: ["Income Certificate"], follow_up_url: "http://localhost:5173/follow-up/abc" });
    if (path.endsWith("/notifications/action-plan/send")) {
      if (!prefs.email_enabled) return respond(400, { detail: "Cannot send: user has not opted in to email notifications." });
      notifs.push({ notification_id: "n1", notification_type: "action_plan_summary", recipient: prefs.email, subject: "Your Unlocked Action Plan", status: opts.sendFails ? "failed" : "sent", last_error: opts.sendFails ? "Resend rejected the sender address." : null, sent_at_utc: "2026-11-01T02:05:00Z", is_demo: false, created_at: "2026-11-01T02:05:00Z" });
      return respond(200, { notification_id: "n1", status: opts.sendFails ? "failed" : "sent", provider: "resend", recipient: prefs.email });
    }
    if (path.endsWith("/notifications/disable")) { prefs = { ...prefs, email_enabled: false }; return respond(200, { disabled: true }); }
    if (path.includes("/notifications/") && path.endsWith("/cancel")) return respond(200, { cancelled: true });
    if (path.endsWith("/notifications")) return respond(200, notifs);
    if (path.endsWith("/appointments") && method === "POST") { appts.push({ appointment_id: "a1", purpose: body.purpose, scheduled_at_utc: body.scheduled_at_utc ?? null, location: body.location ?? null, status: "scheduled", timezone: "Asia/Kolkata" }); return respond(200, appts[appts.length - 1]); }
    if (path.endsWith("/appointments")) return respond(200, appts);
    if (path.includes("/appointments/") && method === "PATCH") { appts[0] = { ...appts[0], status: body.status }; return respond(200, appts[0]); }
    if (path.startsWith("/api/follow-up/")) {
      if (path.includes("expired")) return respond(410, { detail: "This follow-up link has expired." });
      if (path.endsWith("/outcome")) return respond(200, { updated: true });
      return respond(200, { scope_type: "appointment", scheme_name: null, appointment: { appointment_id: "a1", purpose: "Document verification", scheduled_at_utc: "2026-11-10T05:00:00Z", location: "Taluk office", status: "scheduled", timezone: "Asia/Kolkata" }, expires_at: "2026-11-15T00:00:00Z" });
    }
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

describe("questions the backend stops asking", () => {
  it("explains why the other questions disappear after an answer settles them", async () => {
    backend = fakeBackend({ extraQuestion: true });
    globalThis.fetch = backend.fetchImpl;
    await runDiscovery();
    fireEvent.click(screen.getAllByRole("link", { name: /Continue/ })[0]);
    expect(await screen.findByText("Which best describes your work situation?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Under ₹2.5 lakh" }));
    // the fake backend (like the real one) now reports nothing left to ask
    expect(await screen.findByText(/1 other question isn't needed any more/)).toBeTruthy();
    expect(screen.queryByText("Which best describes your work situation?")).toBeNull();
    expect(screen.getByText("What's your family's annual income?")).toBeTruthy(); // the answered one stays
  });
});

describe("rules that are steps, not conditions", () => {
  it("counts only eligibility rules as criteria and lists the steps in applying separately", async () => {
    await runDiscovery();
    fireEvent.click(screen.getAllByRole("link", { name: /Continue/ })[0]);
    fireEvent.click(screen.getByRole("link", { name: /See my results/ }));
    await screen.findByRole("heading", { name: "Fictional Merit Scholarship" });
    expect(screen.getByText("1 of 2 criteria met")).toBeTruthy(); // not "1 of 3": the portal step is not a criterion
    fireEvent.click(screen.getAllByRole("link", { name: "View details" })[0]);
    expect(await screen.findByRole("heading", { name: "Steps in applying" })).toBeTruthy();
    expect(screen.getByText("“Applicants register on the scholarship portal.”")).toBeTruthy();
    expect(screen.queryByText("“Applicants register on the scholarship portal.”", { selector: ".crit .row-between span" })).toBeNull();
  });
});

describe("offline results from a search that failed", () => {
  it("shows a notice with a Search again button that re-runs discovery and clears the notice", async () => {
    backend = fakeBackend({ fallbackFirst: true });
    globalThis.fetch = backend.fetchImpl;
    await runDiscovery();
    fireEvent.click(screen.getAllByRole("link", { name: /Continue/ })[0]);
    fireEvent.click(screen.getByRole("link", { name: /See my results/ }));
    expect(await screen.findByText(/Live search had trouble/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Search again" }));
    await waitFor(() => expect(screen.queryByText(/Live search had trouble/)).toBeNull());
    expect(backend.calls.filter((c) => c.path.endsWith("/discover"))).toHaveLength(2);
    expect(backend.calls.filter((c) => c.path === "/api/sessions" && c.method === "POST")).toHaveLength(1); // same session, searched again
  });

  it("searches again by itself when the Search page is opened with offline results", async () => {
    backend = fakeBackend({ fallbackFirst: true });
    globalThis.fetch = backend.fetchImpl;
    await runDiscovery();
    cleanup();
    open("/discovering");
    await screen.findByRole("link", { name: /Continue/ });
    await waitFor(() => expect(backend.calls.filter((c) => c.path.endsWith("/discover"))).toHaveLength(2));
  });
});


const openPlan = async () => {
  await runDiscovery();
  window.history.pushState({}, "", "/plan");
  cleanup();
  render(<App />);
  await screen.findByText("Email me my plan and reminders.");
};
const optIn = async (address = "me@example.com") => {
  fireEvent.change(screen.getByLabelText("YOUR EMAIL ADDRESS"), { target: { value: address } });
  fireEvent.click(screen.getByRole("button", { name: "Turn on emails" }));
  await screen.findByText("Emails on");
};
const prefPosts = () => backend.calls.filter((c) => c.path.endsWith("/notifications/preferences") && c.method === "POST");

describe("demo fallback switch", () => {
  it("searches the offline fallback schemes when the site is opened with ?fallback=1", async () => {
    open("/details?fallback=1");
    fireEvent.click(screen.getByRole("link", { name: /Find schemes/ }));
    await screen.findByText("2 potential schemes identified.");
    expect(backend.calls.find((c) => c.path === "/api/sessions")!.body).toMatchObject({ scope: "fallback" });
  });
});

describe("email follow-through", () => {
  it("is off until an address is given, and a bad address is rejected", async () => {
    await openPlan();
    expect(screen.getByText("Emails off")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Send it to me now/ })).toBeNull();
    expect(screen.queryByRole("checkbox", { name: /Yes, email me my plan/ })).toBeNull(); // no consent box
    fireEvent.change(screen.getByLabelText("YOUR EMAIL ADDRESS"), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: "Turn on emails" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Enter a valid email address.");
    expect(prefPosts()).toHaveLength(0);
  });

  it("turns emails on from the address given on step 1", async () => {
    open("/start");
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "step1@example.com" } });
    fireEvent.click(screen.getByRole("link", { name: /Continue with/ }));
    fireEvent.click(await screen.findByRole("link", { name: /Find schemes/ }));
    await screen.findByText("2 potential schemes identified.");
    await waitFor(() => expect(prefPosts()).toHaveLength(1));
    expect(prefPosts()[0].body).toMatchObject({ email: "step1@example.com", email_enabled: true, consent_version: "step1" });
  });

  it("won't continue from step 1 with an invalid address", () => {
    open("/start");
    fireEvent.change(screen.getByPlaceholderText("you@example.com"), { target: { value: "nope" } });
    expect(screen.queryByRole("link", { name: /Continue with/ })).toBeNull();
    expect(screen.getByText("Check your email address to continue.")).toBeTruthy();
  });

  it("saves the address and the reminder choice", async () => {
    await openPlan();
    await optIn();
    const saved = prefPosts()[0].body as Record<string, unknown>;
    expect(saved).toMatchObject({ email: "me@example.com", email_enabled: true, consent_version: "step1" });
    expect(saved.categories).toEqual({ action_plan_summary: true, appointment_reminders: true, appointment_follow_up: true });
    expect(screen.getByText("me@example.com")).toBeTruthy();
  });

  it("previews the email without sending anything", async () => {
    await openPlan();
    await optIn();
    fireEvent.click(screen.getByRole("button", { name: /Preview the email/ }));
    expect(await screen.findByText("PREVIEW · NOT SENT")).toBeTruthy();
    expect(screen.getByText("Your Unlocked Action Plan")).toBeTruthy();
    expect(backend.calls.some((c) => c.path.endsWith("/action-plan/send"))).toBe(false);
  });

  it("sends the plan once, on request, and lists it in the history", async () => {
    await openPlan();
    await optIn();
    fireEvent.click(screen.getByRole("button", { name: /Send it to me now/ }));
    expect(await screen.findByText(/Sent to me@example.com/)).toBeTruthy();
    expect(backend.calls.filter((c) => c.path.endsWith("/action-plan/send"))).toHaveLength(1);
    expect((await screen.findAllByText("Your plan")).length).toBeGreaterThan(0); // history row
  });

  it("shows why a send failed instead of claiming success", async () => {
    backend = fakeBackend({ sendFails: true });
    globalThis.fetch = backend.fetchImpl;
    await openPlan();
    await optIn();
    fireEvent.click(screen.getByRole("button", { name: /Send it to me now/ }));
    await waitFor(() => expect(screen.getAllByRole("alert").some((a) => a.textContent === "Resend rejected the sender address.")).toBe(true));
    expect(screen.queryByText(/Sent to me@example.com/)).toBeNull();
  });

  it("turns everything off with one button", async () => {
    await openPlan();
    await optIn();
    fireEvent.click(screen.getByRole("button", { name: /Turn off all emails/ }));
    expect(await screen.findByText("Emails off")).toBeTruthy();
    expect(backend.calls.some((c) => c.path.endsWith("/notifications/disable"))).toBe(true);
  });

  it("adds an appointment, asking for a reminder only once emails are on", async () => {
    await openPlan();
    expect((screen.getByRole("checkbox", { name: /Turn on emails to get a reminder/ }) as HTMLInputElement).disabled).toBe(true);
    await optIn();
    fireEvent.change(screen.getByLabelText("WHAT IS IT FOR?"), { target: { value: "Document verification" } });
    fireEvent.change(screen.getByLabelText("When"), { target: { value: "2026-12-01T10:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Add appointment" }));
    expect(await screen.findByText("Document verification")).toBeTruthy();
    const sent = backend.calls.find((c) => c.path.endsWith("/appointments") && c.method === "POST")!.body as Record<string, unknown>;
    expect(sent).toMatchObject({ purpose: "Document verification", remind_email: true });
    expect(new Date(String(sent.scheduled_at_utc)).toISOString()).toBe(sent.scheduled_at_utc); // a real ISO instant
  });

  it("is not shown without a backend", async () => {
    globalThis.fetch = (() => Promise.reject(new TypeError("offline"))) as typeof fetch;
    open("/plan");
    await screen.findByRole("heading", { name: "Your document plan." });
    expect(screen.queryByText("Email me my plan and reminders.")).toBeNull();
  });
});

describe("follow-up link from an email", () => {
  it("opens the page for that link, with no session, and records the update", async () => {
    sessionStorage.clear();
    open("/follow-up/abc123");
    expect(await screen.findByRole("heading", { name: "How did your appointment go?" })).toBeTruthy();
    expect(screen.getByText("Document verification")).toBeTruthy();
    expect(backend.calls.some((c) => c.path === "/api/follow-up/abc123")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "I missed it" }));
    fireEvent.click(screen.getByRole("button", { name: "Save my update" }));
    expect(await screen.findByText(/that's saved/i)).toBeTruthy();
    const out = backend.calls.find((c) => c.path === "/api/follow-up/abc123/outcome")!.body as Record<string, unknown>;
    expect(out).toEqual({ attended: "missed" });
  });

  it("explains an expired link", async () => {
    open("/follow-up/expired-token");
    expect(await screen.findByText(/This link has expired/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save my update" })).toBeNull();
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
