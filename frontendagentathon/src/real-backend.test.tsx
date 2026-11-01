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

    // discovery really ran; answer whatever the backend asks, by input type, through the real UI
    fireEvent.click(await screen.findByRole("link", { name: /Continue/ }, { timeout: 200000 }));
    await screen.findByRole("link", { name: /See my results/ });
    // Answer "Not sure" to the first question: it is a recorded response that keeps every scheme in play. (A real answer
    // can rule a scheme out, and then the backend rightly drops the questions that only it needed and plans no documents
    // for it, which would make this journey's later steps depend on which answer happens to be picked.)
    const notSure = screen.queryAllByRole("button", { name: "Not sure" })[0];
    if (notSure) {
      fireEvent.click(notSure);
      await waitFor(() => expect(document.querySelector("fieldset.q.done")).not.toBeNull(), { timeout: 15000 });
    }
    fireEvent.click(screen.getByRole("link", { name: /See my results/ }));
    await waitFor(() => expect(document.querySelector("article.scard h2")).not.toBeNull(), { timeout: 10000 });
    expect(screen.queryByText(/Demo Scholarship A/)).toBeNull();
    expect(screen.getByText("Improve your results")).toBeTruthy();

    // plan: computed by the backend
    fireEvent.click(screen.getAllByRole("link", { name: /document plan/i })[0]);
    const income = (await screen.findAllByRole("group", { name: /^Status of / }, { timeout: 10000 }))[0];
    expect(document.querySelectorAll(".node.doc").length).toBeGreaterThanOrEqual(3);
    fireEvent.click(within(income).getByRole("button", { name: "I have it" }));
    await waitFor(() => expect(within(income).getByRole("button", { name: "I have it" }).getAttribute("aria-pressed")).toBe("true"), { timeout: 10000 });

    // actions
    fireEvent.click(screen.getAllByRole("button", { name: /Draft email/ })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: /Write the draft/ })[0]);
    const subject = (await screen.findAllByLabelText("SUBJECT", undefined, { timeout: 20000 }))[0] as HTMLInputElement;
    expect(subject.value.length).toBeGreaterThan(5);
    expect(screen.getAllByText(/verified email address|confirmed address/i)[0]).toBeTruthy(); // the backend declines to invent one

    const g = screen.getAllByRole("group", { name: /Application progress for/ })[0];
    fireEvent.click(within(g).getByRole("button", { name: /Submitted/ }));
    await screen.findByText(/You reported that you submitted the application/, undefined, { timeout: 25000 });
  }, 300000); // a live search with real sources can take a minute or more
});
