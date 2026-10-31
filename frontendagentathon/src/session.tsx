import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { ApplyStage, Category, DocStatus } from "./data";

export type Theme = "sage" | "dark";

export type Details = { state: string; district: string; age: string; edu: string; need: string };

/** A question's answer: an option label, or one of the two "skip" markers. */
export type Answer = string | "__unsure" | "__prefer";

export type Session = {
  theme: Theme;
  scope: "guided" | "all";
  categories: Record<Category, boolean>;
  details: Details;
  answers: Record<string, Answer | undefined>;
  docStatus: Record<string, DocStatus>;
  /** Per-scheme application progress, as reported by the user. */
  apply: Record<string, ApplyStage>;
};

const getStoredTheme = (): Theme => {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const paramTheme = params.get("theme") as Theme | null;
    if (paramTheme === "sage" || paramTheme === "dark") return paramTheme;
    // A previously saved "light" falls through to dark: that theme was removed.
    const t = localStorage.getItem("unlocked_theme") as Theme | null;
    if (t === "sage" || t === "dark") return t;
  }
  return "dark";
};

const defaults = (): Omit<Session, "theme"> => ({
  scope: "guided",
  categories: { Scholarships: true, "Fee concessions": true, Healthcare: false, Pensions: false, Subsidies: false },
  details: { state: "Karnataka", district: "", age: "", edu: "", need: "" },
  answers: {},
  docStatus: { admission: "have" },
  apply: {},
});

// Per-tab storage: a refresh keeps the user's answers, closing the tab (or "Start over") drops them.
const STORE_KEY = "unlocked_session_v1";

const loadSaved = (): Partial<Omit<Session, "theme">> => {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    const saved = raw ? JSON.parse(raw) : null;
    return saved && typeof saved === "object" ? saved : {};
  } catch {
    return {};
  }
};

const initialSession = (): Session => {
  const base = defaults();
  const saved = loadSaved();
  // Merge field by field so a stale or partial saved object can never remove a field the app expects.
  return {
    theme: getStoredTheme(),
    scope: saved.scope === "all" ? "all" : "guided",
    categories: { ...base.categories, ...(saved.categories ?? {}) },
    details: { ...base.details, ...(saved.details ?? {}) },
    answers: { ...(saved.answers ?? {}) },
    docStatus: { ...base.docStatus, ...(saved.docStatus ?? {}) },
    apply: { ...(saved.apply ?? {}) },
  };
};

type SessionApi = {
  session: Session;
  update: (patch: Partial<Session> | ((s: Session) => Partial<Session>)) => void;
  reset: () => void;
  setTheme: (t: Theme) => void;
};

const SessionContext = createContext<SessionApi | null>(null);

/** Answers live only in memory for this tab; "Start over" wipes them. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>(initialSession);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", session.theme);
    localStorage.setItem("unlocked_theme", session.theme);
  }, [session.theme]);

  useEffect(() => {
    const { theme: _theme, ...rest } = session; // the theme has its own key
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify(rest));
    } catch {
      /* storage blocked: answers then live in memory only */
    }
  }, [session]);

  const update = useCallback<SessionApi["update"]>((patch) => {
    setSession((s) => ({ ...s, ...(typeof patch === "function" ? patch(s) : patch) }));
  }, []);

  const setTheme = useCallback((theme: Theme) => {
    setSession((s) => ({ ...s, theme }));
  }, []);

  const reset = useCallback(() => {
    try { sessionStorage.removeItem(STORE_KEY); } catch { /* nothing saved to clear */ }
    setSession((prev) => ({ theme: prev.theme, ...defaults() }));
  }, []);

  return <SessionContext.Provider value={{ session, update, reset, setTheme }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
