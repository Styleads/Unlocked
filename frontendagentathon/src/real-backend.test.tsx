// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App";
import { installBrowserShims } from "./testkit";

/**
 * Smoke test against a real backend: `python -m uvicorn api.main:app --port 8000` (no API keys needed, it serves its
 * offline fallback schemes). The suite skips itself when nothing is listening, so `npm test` works without one.
 */
const base = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://127.0.0.1:8000";
// (jsdom's AbortSignal is not the one Node's fetch expects, so the timeout is a race instead of a signal)
const up = await Promise.race([
  fetch(`${base}/api/health`).then((r) => r.ok, () => false),
  new Promise<boolean>((done) => setTimeout(() => done(false), 2000)),
]);
// jsdom's AbortController signal is rejected by Node's fetch, so drop it here; real browsers are unaffected.
const nodeFetch = globalThis.fetch;
const realFetch = ((url: RequestInfo | URL, init?: RequestInit) => nodeFetch(url, init ? { ...init, signal: undefined } : init)) as typeof fetch;

beforeAll(installBrowserShims);
beforeEach(() => {
  sessionStorage.clear();
  globalThis.fetch = realFetch;
});
afterEach(cleanup);

describe.skipIf(!up)("real backend", () => {
  it("runs the whole journey: discovery, results, plan, checklist, email, progress", async () => {
    window.history.pushState({}, "", "/details");
    render(<App />);
    fireEvent.change(screen.getByLabelText(/District/), { target: { value: "Mysuru" } });
    fireEvent.change(screen.getByLabelText(/^Age/), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText(/Education level/), { target: { value: "ug" } });
    fireEvent.click(screen.getByRole("link", { name: /Find schemes/ }));

    // discovery really ran: the card appears with the backend's count, and a real scheme is on Results
    // (the result card is laid out from the start but hidden until discovery finishes, so wait for its button)
    fireEvent.click(await screen.findByRole("link", { name: /Continue/ }, { timeout: 30000 }));
    fireEvent.click(await screen.findByRole("link", { name: /See my results/ }));
    const heading = await screen.findByRole("heading", { name: /Vidyasiri/ }, { timeout: 10000 });
    expect(heading).toBeTruthy();
    expect(screen.queryByText(/Demo Scholarship A/)).toBeNull();
    expect(screen.queryByText(/Answer \d+ more/)).toBeNull(); // the fallback scheme's rules are unverified: nothing to ask

    // plan: computed by the backend
    fireEvent.click(screen.getAllByRole("link", { name: /document plan/i })[0]);
    const income = await screen.findByRole("group", { name: "Status of Income Certificate" }, { timeout: 10000 });
    expect(document.querySelectorAll(".node.doc").length).toBeGreaterThanOrEqual(3);
    fireEvent.click(within(income).getByRole("button", { name: "I have it" }));
    await waitFor(() => expect(within(income).getByRole("button", { name: "I have it" }).getAttribute("aria-pressed")).toBe("true"), { timeout: 10000 });

    // actions
    fireEvent.click(screen.getByRole("button", { name: /Draft email/ }));
    fireEvent.click(screen.getByRole("button", { name: /Write the draft/ }));
    const subject = (await screen.findByLabelText("SUBJECT", undefined, { timeout: 20000 })) as HTMLInputElement;
    expect(subject.value).toMatch(/Vidyasiri/);
    expect(screen.getByText(/verified email address/i)).toBeTruthy(); // the backend declines to invent one

    const g = screen.getByRole("group", { name: /Application progress for Vidyasiri/ });
    fireEvent.click(within(g).getByRole("button", { name: /Submitted/ }));
    await screen.findByText(/You reported that you submitted the application/, undefined, { timeout: 10000 });
  }, 90000);
});
