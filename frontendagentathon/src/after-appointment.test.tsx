// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { installBrowserShims } from "./testkit";
import type { ApiDueFollowUp } from "./api";

beforeAll(installBrowserShims);

const OPTIONS = {
  attended_options: [
    { value: "yes", label: "I went" }, { value: "rescheduled", label: "It was moved to another day" },
    { value: "missed", label: "I couldn't go" }, { value: "cancelled", label: "It was cancelled" }, { value: "unknown", label: "Not sure" },
  ],
  outcome_options: [
    { value: "documents_accepted", label: "My documents were accepted" },
    { value: "additional_documents_requested", label: "They asked for more documents" },
    { value: "approved", label: "It was approved" },
  ],
};

/** The backend side of follow-up, shaped like api/main.py + agent4.follow_up. */
function fakeBackend(due: ApiDueFollowUp[]) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  let pending = [...due];
  const respond = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const fetchImpl = (async (url: string, init?: RequestInit) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    const method = (init?.method ?? "GET").toUpperCase();
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    if (path.endsWith("/schemes") || path.endsWith("/questions")) return respond(200, []);
    if (path.endsWith("/plan")) return respond(200, { checklist: [], nodes: [], edges: [], shared_prerequisites: [], explanation: "Nothing to collect.", warnings: [], excluded_documents: [] });
    if (path.endsWith("/notifications/preferences")) return respond(200, { session_id: "sess-1", email: null, email_enabled: false, categories: {}, timezone: "Asia/Kolkata" });
    if (path.endsWith("/follow-ups")) return respond(200, pending);
    if (path.endsWith("/outcome")) {
      const aid = path.split("/")[5];
      pending = pending.filter((d) => d.appointment_id !== aid);
      const docs: string[] = body.additional_documents ?? [];
      const plan = {
        appointment_id: aid, new_status: body.attended === "unknown" ? "outcome_unknown" : "attended",
        summary: body.attended === "unknown" ? "You weren't sure how it went, so nothing has been changed." : "You reported that you went. They asked for more documents.",
        next_steps: docs.map((d) => ({ kind: "collect_document", text: `Get: ${d}`, document: d })),
        ask_later: [], documents_to_add: docs, warnings: [],
      };
      return respond(200, { appointment_id: aid, purpose: "Document verification", timezone: "Asia/Kolkata", status: plan.new_status, outcome_details: { ...body, plan } });
    }
    return respond(404, { detail: `no route ${path}` });
  }) as typeof fetch;
  return { fetchImpl, calls };
}

const item = (aid: string, purpose = "Document verification at the taluk office"): ApiDueFollowUp => ({
  appointment_id: aid, purpose, scheduled_at_utc: "2026-11-02T05:30:00Z", location: "Taluk office", question: `How did it go? ${purpose}`, simulated: false, ...OPTIONS,
});

let backend: ReturnType<typeof fakeBackend>;
const openPlan = (due: ApiDueFollowUp[]) => {
  backend = fakeBackend(due);
  globalThis.fetch = backend.fetchImpl;
  sessionStorage.setItem("unlocked_live_v1", JSON.stringify({ sessionId: "sess-1", discoveredKey: "k", answers: {}, shown: [], selected: null, sourceMode: "live_search", warnings: [] }));
  window.history.pushState({}, "", "/plan");
  return render(<App />);
};
beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

describe("after an appointment", () => {
  it("asks how it went once it is over, with the backend's options", async () => {
    openPlan([item("a1")]);
    expect(await screen.findByRole("heading", { name: "How did it go?" })).toBeTruthy();
    expect(screen.getByText("Document verification at the taluk office")).toBeTruthy();
    for (const o of OPTIONS.attended_options) expect(screen.getByRole("button", { name: o.label })).toBeTruthy();
  });

  it("asks nothing when no appointment is over", async () => {
    openPlan([]);
    await screen.findByRole("heading", { name: "Your document plan." });
    await waitFor(() => expect(backend.calls.some((c) => c.path.endsWith("/follow-ups"))).toBe(true));
    expect(screen.queryByRole("heading", { name: "How did it go?" })).toBeNull();
  });

  it("sends only what the user reported and shows what to do next", async () => {
    openPlan([item("a1")]);
    fireEvent.click(await screen.findByRole("button", { name: "I went" }));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "additional_documents_requested" } });
    fireEvent.change(screen.getByPlaceholderText("Write them as the office named them"), { target: { value: "Caste certificate, Bank passbook" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Thanks, that's saved.")).toBeTruthy();
    expect(screen.getByText("Get: Caste certificate")).toBeTruthy();
    expect(screen.getByText("Get: Bank passbook")).toBeTruthy();
    const sent = backend.calls.find((c) => c.path.endsWith("/a1/outcome"))!.body;
    expect(sent).toEqual({ attended: "yes", outcome: "additional_documents_requested", additional_documents: ["Caste certificate", "Bank passbook"] });
    expect(screen.queryByRole("heading", { name: "How did it go?" })).toBeNull();
  });

  it("'Not sure' sends nothing more than that", async () => {
    openPlan([item("a1")]);
    fireEvent.click(await screen.findByRole("button", { name: "Not sure" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("You weren't sure how it went, so nothing has been changed.")).toBeTruthy();
    expect(backend.calls.find((c) => c.path.endsWith("/outcome"))!.body).toEqual({ attended: "unknown" });
  });

  it("asks for the new date when it was moved", async () => {
    openPlan([item("a1")]);
    fireEvent.click(await screen.findByRole("button", { name: "It was moved to another day" }));
    expect(screen.getByText("NEW DATE (IF YOU HAVE IT)")).toBeTruthy();
  });

  it("'Ask me later' hides it without answering", async () => {
    openPlan([item("a1"), item("a2", "Return visit")]);
    const later = await screen.findAllByRole("button", { name: "Ask me later" });
    fireEvent.click(later[0]);
    expect(screen.getAllByRole("heading", { name: "How did it go?" })).toHaveLength(1);
    expect(backend.calls.some((c) => c.path.endsWith("/outcome"))).toBe(false);
  });

  it("can't be saved before choosing what happened", async () => {
    openPlan([item("a1")]);
    expect(((await screen.findByRole("button", { name: "Save" })) as HTMLButtonElement).disabled).toBe(true);
  });
});
