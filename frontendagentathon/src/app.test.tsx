// @vitest-environment jsdom
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import App from "./App";

// jsdom has no layout engine or these observers; the app only needs them to exist.
beforeAll(() => {
  window.matchMedia = ((q: string) => ({ matches: q.includes("reduce"), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false })) as typeof window.matchMedia;
  class Obs { observe() {} unobserve() {} disconnect() {} }
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = Obs;
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = Obs;
  window.scrollTo = (() => {}) as typeof window.scrollTo;
  // These tests run the demo path: the backend must look unreachable even if one is running locally.
  globalThis.fetch = (() => Promise.reject(new TypeError("offline"))) as typeof fetch;
  // Node 25 ships its own half-working localStorage that shadows jsdom's; use a plain in-memory Storage.
  for (const key of ["localStorage", "sessionStorage"] as const) {
    const m = new Map<string, string>();
    const store = {
      getItem: (k: string) => m.get(k) ?? null,
      setItem: (k: string, v: string) => void m.set(k, String(v)),
      removeItem: (k: string) => void m.delete(k),
      clear: () => m.clear(),
      key: (i: number) => [...m.keys()][i] ?? null,
      get length() { return m.size; },
    };
    Object.defineProperty(window, key, { value: store, configurable: true });
    Object.defineProperty(globalThis, key, { value: store, configurable: true });
  }
});

const open = (path: string) => {
  window.history.pushState({}, "", path);
  return render(<App />);
};
const click = (name: string | RegExp, nth = 0) => fireEvent.click(screen.getAllByRole("button", { name })[nth]);
const goResults = () => fireEvent.click(screen.getAllByRole("link", { name: /Update my results/ })[0]);

const answerAll = () => {
  click("₹1–2.5 lakh");
  click("Government");
  click("Yes");
  click("Undergraduate");
};

beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

describe("Results after the Questions page", () => {
  it("does not ask for more answers once all four are answered, and names what is still unknown", () => {
    open("/questions");
    answerAll();
    expect(screen.getByRole("img", { name: "4 of 4 questions answered" })).toBeTruthy();
    goResults();
    expect(screen.getByRole("heading", { name: /We found 5 schemes/ })).toBeTruthy();
    expect(screen.queryByText(/Answer \d+ more/)).toBeNull();
    expect(screen.getByText("All 4 questions answered.")).toBeTruthy();
    expect(screen.getByText(/Still unknown: age \(add it on the Context page\)/)).toBeTruthy();
  });

  it("keeps the answers and the same results after a refresh", () => {
    open("/questions");
    answerAll();
    goResults();
    const before = screen.getByText("All 4 questions answered.").closest("a")?.textContent;
    cleanup(); // simulate a refresh: a fresh app, same tab storage
    open("/results");
    expect(screen.getByText("All 4 questions answered.").closest("a")?.textContent).toBe(before);
    expect(screen.queryByText(/Answer \d+ more/)).toBeNull();
  });

  it("shows the real count when two questions are unanswered", () => {
    open("/questions");
    click("₹1–2.5 lakh");
    click("Undergraduate");
    goResults();
    expect(screen.getByText(/Answer 2 more questions to check/)).toBeTruthy();
  });

  it('counts "Not sure" as a response but keeps the criterion unknown', () => {
    open("/questions");
    click("Not sure", 0); // Q1 income
    click("Government");
    click("Yes");
    click("Undergraduate");
    goResults();
    expect(screen.queryByText(/Answer \d+ more/)).toBeNull();
    // both schemes that use income say so, and the card names the same item\n    expect(screen.getAllByText(/family income \(you marked not sure\)/).length).toBeGreaterThanOrEqual(2);\n    expect(screen.getByText(/Still unknown: .*family income \(you marked not sure\)/)).toBeTruthy();
  });

  it("recalculates when income changes: a high bracket makes Scholarship A unlikely", () => {
    open("/questions");
    click("Above ₹8 lakh");
    click("Government");
    click("Yes");
    click("Undergraduate");
    goResults();
    expect(screen.getByRole("button", { name: /Unlikely/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Show \d+ unlikely/ }));
    const card = screen.getByRole("heading", { name: "Demo Scholarship A" }).closest("article")!;
    expect(within(card as HTMLElement).getByText(/not to meet a stated rule: family income/)).toBeTruthy();
  });
});

describe("Discover all vs Guided", () => {
  it("dims and disables the category chips in Discover all, and restores the choices in Guided", () => {
    open("/start");
    const chip = () => screen.getByRole("button", { name: /Scholarships/ }) as HTMLButtonElement;
    expect(chip().getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: /Discover all/ }));
    expect(chip().disabled).toBe(true);
    expect(chip().getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText("SCANNING ALL 5 CATEGORIES")).toBeTruthy();
    expect(screen.getByText(/Continue with everything/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Guided discovery/ }));
    expect(chip().disabled).toBe(false);
    expect(chip().getAttribute("aria-pressed")).toBe("true");
  });
});

describe("Plan page", () => {
  it("shows a diagram with every document and scheme, and no scrolling wrapper", () => {
    const { container } = open("/plan");
    const docs = container.querySelectorAll(".node.doc");
    const schemes = container.querySelectorAll(".node.sch");
    expect(docs).toHaveLength(5);
    expect(schemes).toHaveLength(3);
    expect(container.querySelectorAll("path.edge")).toHaveLength(6);
    for (const el of container.querySelectorAll<HTMLElement>(".card *")) expect(el.style.overflowX).not.toBe("auto");
  });

  it("recomputes readiness and the next-document banner when a status changes", () => {
    open("/plan");
    expect(screen.getByText("Get your Income Certificate next.", { exact: false })).toBeTruthy();
    const income = screen.getByRole("group", { name: "Status of Income Certificate" });
    fireEvent.click(within(income).getByRole("button", { name: "I have it" }));
    expect(screen.queryByText("Get your Income Certificate next.", { exact: false })).toBeNull();
  });

  it("opens an editable email draft that includes no personal answers and no invented address", () => {
    open("/plan");
    click(/Draft email/, 0);
    const subject = screen.getAllByDisplayValue(/Query about applying for/)[0] as HTMLInputElement;
    expect(subject.value).toMatch(/Demo Scholarship A/);
    const body = screen.getAllByRole("textbox").find((t) => (t as HTMLTextAreaElement).value.includes("Dear Sir or Madam")) as HTMLTextAreaElement;
    expect(body.value).toContain("[Your name]");
    expect(body.value).not.toMatch(/lakh|@/);
    const mail = screen.getByRole("link", { name: /Open in my email app/ }) as HTMLAnchorElement;
    expect(mail.getAttribute("href")).toMatch(/^mailto:\?subject=/);
  });

  it("tracks application progress per scheme and keeps it after a refresh", () => {
    open("/plan");
    const g = screen.getByRole("group", { name: "Application progress for Demo Scholarship A" });
    fireEvent.click(within(g).getByRole("button", { name: /Submitted/ }));
    expect(within(g).getByRole("button", { name: /Submitted/ }).getAttribute("aria-pressed")).toBe("true");
    cleanup();
    open("/plan");
    const again = screen.getByRole("group", { name: "Application progress for Demo Scholarship A" });
    expect(within(again).getByRole("button", { name: /Submitted/ }).getAttribute("aria-pressed")).toBe("true");
  });
});

describe("copy and theme", () => {
  it("uses the agreed headings and no Light-lavender theme", () => {
    open("/details");
    expect(screen.getByRole("heading", { name: "Let's understand your needs." })).toBeTruthy();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    const names = screen.getAllByRole("button").map((b) => b.textContent);
    expect(names.some((n) => n?.includes("Dark"))).toBe(true);
    expect(names.filter((n) => n?.trim() === "Light")).toHaveLength(1); // the soft-green theme, relabelled
  });
  it("shows the agreed discovery result text", () => {
    open("/discovering");
    expect(screen.getByText("5 potential schemes identified.")).toBeTruthy();
  });
});
