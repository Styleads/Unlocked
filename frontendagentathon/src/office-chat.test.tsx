// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { installBrowserShims } from "./testkit";
import type { ApiOfficeChat, ApiScheme } from "./api";

beforeAll(installBrowserShims);

type Step = Partial<ApiOfficeChat> & { reply?: string; assistant?: string };

/** A fake backend for the office chat: each "advance" plays the next scripted step, the way api/main.py does. */
function fakeOfficeBackend(steps: Step[], opts: { advanceConflicts?: boolean } = {}) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const respond = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const schemes = [{ id: "s1", name: "Fictional Merit Scholarship", summary: "", department: "Dept", government_level: "state", documents: [], application_steps: [], official_sources: [], source_type: "live_search", assessment_status: "potential_match", assessment_explanation: "", requirements: [], missing_attributes: [] }] as unknown as ApiScheme[];
  let chat: ApiOfficeChat = { chat_id: "chat_1", scheme_id: "s1", scenario_id: "x", simulation_mode: true, chat_status: "in_progress", appointment_status: "requested", appointment: null, messages: [{ message_id: "m1", sender: "unlocked", message_text: "Hello, I'd like to ask about document verification slots.", turn_index: 1 }], unresolved_questions: [] };
  let i = 0;
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
    if (path.endsWith("/user-input")) {
      chat = body.user_approved_slot
        ? { ...chat, chat_status: "completed", appointment_status: "simulated_confirmed", appointment: { ...chat.appointment!, status: "simulated_confirmed", calendar_ics: "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n" } }
        : { ...chat, chat_status: "cancelled", appointment_status: "cancelled" };
      return respond(200, chat);
    }
    if (path.endsWith("/finish")) { chat = { ...chat, chat_status: "cancelled" }; return respond(200, chat); }
    if (path.endsWith("/outcome")) return respond(200, { chat_status: chat.chat_status, appointment_status: chat.appointment_status, appointment: chat.appointment, unresolved_questions: chat.unresolved_questions, calendar_ics: chat.appointment?.calendar_ics ?? null, summary: chat.chat_status === "completed" ? "Simulated appointment confirmed for 2026-11-02 at 11:00." : "The chat ended without an appointment.", next_steps: ["Bring your original documents."] });
    if (path.includes("/mark-sent")) return respond(200, { ...chat.unresolved_questions[0], status: "user_marked_sent" });
    return respond(404, { detail: `no route ${path}` });
  }) as typeof fetch;
  return { fetchImpl, calls };
}

const openChat = () => {
  sessionStorage.setItem("unlocked_live_v1", JSON.stringify({ sessionId: "sess-1", discoveredKey: "k", answers: {}, shown: [], selected: "s1", sourceMode: "live_search", warnings: [] }));
  window.history.pushState({}, "", "/office-chat");
  return render(<App />);
};

let backend: ReturnType<typeof fakeOfficeBackend>;
const use = (steps: Step[], opts?: Parameters<typeof fakeOfficeBackend>[1]) => { backend = fakeOfficeBackend(steps, opts); globalThis.fetch = backend.fetchImpl; };
beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

const start = async () => {
  openChat();
  await screen.findByText("Fictional Merit Scholarship", { selector: "option" });
  fireEvent.click(screen.getByRole("button", { name: "Start the chat" }));
  await screen.findByText(/I'd like to ask about document verification/);
};

describe("office chat (simulated)", () => {
  it("says plainly that it is a simulation and sends only what the applicant chose", async () => {
    use([]);
    openChat();
    expect(await screen.findByText(/This is a simulation\. No real office is contacted/)).toBeTruthy();
    await screen.findByText("Fictional Merit Scholarship", { selector: "option" });
    fireEvent.click(screen.getByRole("button", { name: "Tue" }));
    fireEvent.click(screen.getByRole("button", { name: "Start the chat" }));
    await screen.findByText(/I'd like to ask about document verification/);
    const create = backend.calls.find((c) => c.path.endsWith("/office-chats"))!;
    // no day picked means no constraint; auto-confirmation is off unless the applicant turns it on
    expect(create.body).toMatchObject({ scheme_id: "s1", preferred_days: ["tuesday"], pre_authorized_confirmation: false });
  });

  it("holds an offered slot for the applicant and confirms only when they approve", async () => {
    use([{ reply: "We have Monday at 11:00 AM.", assistant: "Please confirm.", chat_status: "awaiting_user_input", appointment_status: "awaiting_user_approval", appointment: { date: "2026-11-02", time: "11:00", status: "awaiting_user_approval" } }]);
    await start();
    fireEvent.click(screen.getByRole("button", { name: "Next reply" }));
    expect(await screen.findByText("The simulated office offered a slot")).toBeTruthy();
    expect(screen.getByText("Unlocked will not confirm this unless you approve it.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Next reply" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Approve this slot" }));
    expect(await screen.findByText("Simulated appointment confirmed for 2026-11-02 at 11:00.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Download calendar file/ })).toBeTruthy();
    expect(backend.calls.find((c) => c.path.endsWith("/user-input"))!.body).toMatchObject({ action: "approve_slot", user_approved_slot: true });
  });

  it("declining ends the chat without an appointment", async () => {
    use([{ reply: "We have Monday at 11:00 AM.", chat_status: "awaiting_user_input", appointment_status: "awaiting_user_approval", appointment: { date: "2026-11-02", time: "11:00", status: "awaiting_user_approval" } }]);
    await start();
    fireEvent.click(screen.getByRole("button", { name: "Next reply" }));
    fireEvent.click(await screen.findByRole("button", { name: "Decline" }));
    expect(await screen.findByText("The chat ended without an appointment.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Download calendar file/ })).toBeNull();
  });

  it("links to WhatsApp only with a number the office gave", async () => {
    use([{ reply: "Message us on +91 98765 43210.", chat_status: "awaiting_user_input", unresolved_questions: [{ question_id: "uq1", question_text: "Follow up with the office on WhatsApp: +919876543210", status: "open", receiver_whatsapp_number: "+919876543210", click_to_chat_url: "https://wa.me/919876543210?text=Hi" }] }]);
    await start();
    fireEvent.click(screen.getByRole("button", { name: "Next reply" }));
    const link = (await screen.findByRole("link", { name: /Open WhatsApp \(\+919876543210\)/ })) as HTMLAnchorElement;
    expect(link.href).toBe("https://wa.me/919876543210?text=Hi");
    fireEvent.click(screen.getByRole("button", { name: "I sent it" }));
    expect(await screen.findByRole("button", { name: "Marked as sent" })).toBeTruthy();
  });

  it("shows no link when no number was given", async () => {
    use([{ reply: "Please bring documents.", chat_status: "awaiting_user_input", unresolved_questions: [{ question_id: "uq1", question_text: "The office asked for: documents", status: "open" }] }]);
    await start();
    fireEvent.click(screen.getByRole("button", { name: "Next reply" }));
    expect(await screen.findByText("No contact number was given, so there is no link to open.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /WhatsApp/ })).toBeNull();
  });

  it("reports a refused step instead of failing silently", async () => {
    use([], { advanceConflicts: true });
    await start();
    fireEvent.click(screen.getByRole("button", { name: "Next reply" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/must approve or decline/);
  });

  it("asks for a search first when there is no live session", async () => {
    use([]);
    window.history.pushState({}, "", "/office-chat");
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Search for schemes first/)).toBeTruthy());
  });
});
