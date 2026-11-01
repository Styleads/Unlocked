// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import App from "./App";
import { installBrowserShims } from "./testkit";
import type { ApiOfficeChat, ApiScheme } from "./api";

beforeAll(installBrowserShims);

type Step = Partial<ApiOfficeChat> & { reply?: string; assistant?: string };

/** A fake backend for the office chat: each "advance" plays the next scripted step, the way api/main.py does. */
function fakeOfficeBackend(steps: Step[], opts: { advanceConflicts?: boolean; email?: string | null; emailFails?: boolean } = {}) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const respond = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const schemes = [{ id: "s1", name: "Fictional Merit Scholarship", summary: "", department: "Dept", government_level: "state", documents: [], application_steps: [], official_sources: [], source_type: "fallback", assessment_status: "potential_match", assessment_explanation: "", requirements: [], missing_attributes: [] }] as unknown as ApiScheme[];
  let chat: ApiOfficeChat = { chat_id: "chat_1", scheme_id: "s1", scenario_id: "x", simulation_mode: true, chat_status: "in_progress", appointment_status: "requested", appointment: null, messages: [{ message_id: "m1", sender: "unlocked", message_text: "Hello, I'd like to ask about document verification slots.", turn_index: 1 }], unresolved_questions: [] };
  let i = 0;
  const email = opts.email === undefined ? "me@example.com" : opts.email;
  const fetchImpl = (async (url: string, init?: RequestInit) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const method = (init?.method ?? "GET").toUpperCase();
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    if (path.endsWith("/schemes")) return respond(200, schemes);
    if (path.endsWith("/questions")) return respond(200, []);
    if (path.endsWith("/office-chats")) return respond(201, chat);
    if (path.endsWith("/advance")) {
      if (opts.advanceConflicts) return respond(409, { detail: "The applicant must approve or decline the offered slot before the chat continues." });
      const step = steps[i++];
      const n = chat.messages.length;
      chat = { ...chat, ...step, messages: [...chat.messages, { message_id: `m${n + 1}`, sender: "simulated_office", message_text: step.reply ?? "", turn_index: n + 1 }, { message_id: `m${n + 2}`, sender: "unlocked", message_text: step.assistant ?? "Noted.", turn_index: n + 2 }] };
      return respond(200, chat);
    }
    if (path.endsWith("/outcome")) return respond(200, { chat_status: chat.chat_status, appointment_status: chat.appointment_status, appointment: chat.appointment, unresolved_questions: chat.unresolved_questions, calendar_ics: chat.appointment?.calendar_ics ?? null, summary: chat.chat_status === "completed" ? "Simulated appointment confirmed for 2026-11-02 at 11:00." : "No appointment slots available in the requested window.", next_steps: ["Bring your original documents."] });
    if (path.endsWith("/notifications")) {
      return respond(200, email ? [
        { notification_id: "n1", notification_type: "simulated_appointment_confirmed", recipient: email, subject: "Confirmed", status: opts.emailFails ? "failed" : "sent", last_error: opts.emailFails ? "Resend rejected the sender address." : null, is_demo: false, created_at: "2026-11-01T02:00:00Z" },
        { notification_id: "n2", notification_type: "appointment_reminders", recipient: email, subject: "Reminder", status: "pending", is_demo: false, created_at: "2026-11-01T02:00:00Z" },
        { notification_id: "n3", notification_type: "appointment_follow_up", recipient: email, subject: "How did it go?", status: "pending", is_demo: false, created_at: "2026-11-01T02:00:00Z" },
      ] : [{ notification_id: "n1", notification_type: "simulated_appointment_confirmed", recipient: "", subject: "", status: "skipped_no_consent", is_demo: false, created_at: "" }].filter(() => false));
    }
    if (path.includes("/mark-sent")) return respond(200, { ...chat.unresolved_questions[0], status: "user_marked_sent" });
    return respond(404, { detail: `no route ${path}` });
  }) as typeof fetch;
  return { fetchImpl, calls };
}

const openChat = () => {
  sessionStorage.setItem("unlocked_live_v1", JSON.stringify({ sessionId: "sess-1", discoveredKey: "k", answers: {}, shown: [], selected: "s1", sourceMode: "fallback", warnings: [] }));
  window.history.pushState({}, "", "/office-chat");
  return render(<StrictMode><App /></StrictMode>); // as main.tsx renders it: effects mount, unmount, mount again
};

let backend: ReturnType<typeof fakeOfficeBackend>;
const use = (steps: Step[], opts?: Parameters<typeof fakeOfficeBackend>[1]) => { backend = fakeOfficeBackend(steps, opts); globalThis.fetch = backend.fetchImpl; };
beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

const CONFIRMED: Step[] = [
  { reply: "We have Monday at 11:00 AM.", assistant: "Could you please confirm?", chat_status: "appointment_offered", appointment_status: "offered", appointment: { date: "2026-11-02", time: "11:00", status: "offered" } },
  { reply: "Monday at 11:00 AM is confirmed.", assistant: "Thank you, confirmed.", chat_status: "completed", appointment_status: "simulated_confirmed", appointment: { date: "2026-11-02", time: "11:00", status: "simulated_confirmed", calendar_ics: "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n" } },
];

const start = async (scenario?: string) => {
  openChat();
  await screen.findByText("Fictional Merit Scholarship", { selector: "option" });
  if (scenario) fireEvent.change(screen.getByLabelText("HOW SHOULD THE OFFICE RESPOND?"), { target: { value: scenario } });
  fireEvent.click(screen.getByRole("button", { name: /Start the chat/ }));
};

describe("office chat (simulated)", () => {
  it("plays the chosen response to the end, confirms, and reports the emails", async () => {
    use(CONFIRMED);
    await start();
    expect(await screen.findByText("Simulated appointment confirmed for 2026-11-02 at 11:00.")).toBeTruthy();
    expect(screen.getByText(/Confirmation emailed to me@example.com\./)).toBeTruthy();
    expect(screen.getByText(/A reminder before the appointment and a follow-up after it are scheduled\./)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Download calendar file/ })).toBeTruthy();
    expect(backend.calls.filter((c) => c.path.endsWith("/advance"))).toHaveLength(2);
    const create = backend.calls.find((c) => c.path.endsWith("/office-chats"))!;
    expect(create.body).toMatchObject({ scheme_id: "s1", scenario_id: "scenario_a_success", preferred_days: [], pre_authorized_confirmation: true });
    expect(screen.queryByRole("button", { name: "Next reply" })).toBeNull(); // nothing to click through
  });

  it("sends the response the user picked", async () => {
    use([{ reply: "No slots this week.", chat_status: "no_availability", appointment_status: "no_availability" }]);
    await start("scenario_b_no_availability");
    expect(await screen.findByText("No appointment slots available in the requested window.")).toBeTruthy();
    expect(backend.calls.find((c) => c.path.endsWith("/office-chats"))!.body).toMatchObject({ scenario_id: "scenario_b_no_availability" });
  });

  it("says when the confirmation couldn't be sent", async () => {
    use(CONFIRMED, { emailFails: true });
    await start();
    expect(await screen.findByText(/couldn't be sent: Resend rejected the sender address\./)).toBeTruthy();
  });

  it("asks for an email when none was given", async () => {
    use(CONFIRMED, { email: null });
    await start();
    expect(await screen.findByText(/Add your email on step 1/)).toBeTruthy();
  });

  it("stops at the WhatsApp handoff with the number the office gave", async () => {
    use([{ reply: "Message us on +91 98765 43210.", chat_status: "awaiting_user_input", unresolved_questions: [{ question_id: "uq1", question_text: "Follow up with the office on WhatsApp: +919876543210", status: "open", receiver_whatsapp_number: "+919876543210", click_to_chat_url: "https://wa.me/919876543210?text=Hi" }] }, { reply: "never reached" }]);
    await start("scenario_c_missing_info");
    const link = (await screen.findByRole("link", { name: /Open WhatsApp \(\+919876543210\)/ })) as HTMLAnchorElement;
    expect(link.href).toBe("https://wa.me/919876543210?text=Hi");
    expect(backend.calls.filter((c) => c.path.endsWith("/advance"))).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "I sent it" }));
    expect(await screen.findByRole("button", { name: "Marked as sent" })).toBeTruthy();
  });

  it("shows no link when no number was given", async () => {
    use([{ reply: "Please bring documents.", chat_status: "awaiting_user_input", unresolved_questions: [{ question_id: "uq1", question_text: "The office asked for: documents", status: "open" }] }]);
    await start("scenario_c_missing_info");
    expect(await screen.findByText("No contact number was given, so there is no link to open.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /WhatsApp/ })).toBeNull();
  });

  it("reports a refused step instead of failing silently", async () => {
    use([], { advanceConflicts: true });
    await start();
    expect((await screen.findByRole("alert")).textContent).toMatch(/must approve or decline/);
  });

  it("asks for a search first when there is no live session", async () => {
    use([]);
    window.history.pushState({}, "", "/office-chat");
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Search for schemes first/)).toBeTruthy());
  });
});
