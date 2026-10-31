import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import type { Category, DocStatus } from "./data";

export type Theme = "light" | "sage" | "dark";

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
};

const getStoredTheme = (): Theme => {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const paramTheme = params.get("theme") as Theme | null;
    if (paramTheme === "light" || paramTheme === "sage" || paramTheme === "dark") return paramTheme;
    const t = localStorage.getItem("unlocked_theme") as Theme | null;
    if (t === "light" || t === "sage" || t === "dark") return t;
  }
  return "light";
};

const initialSession = (): Session => ({
  theme: getStoredTheme(),
  scope: "guided",
  categories: { Scholarships: true, "Fee concessions": true, Healthcare: false, Pensions: false, Subsidies: false },
  details: { state: "Karnataka", district: "", age: "", edu: "", need: "" },
  answers: {},
  docStatus: { admission: "have" },
});

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

  const update = useCallback<SessionApi["update"]>((patch) => {
    setSession((s) => ({ ...s, ...(typeof patch === "function" ? patch(s) : patch) }));
  }, []);

  const setTheme = useCallback((theme: Theme) => {
    setSession((s) => ({ ...s, theme }));
  }, []);

  const reset = useCallback(() => {
    setSession((prev) => ({ ...initialSession(), theme: prev.theme }));
  }, []);

  return <SessionContext.Provider value={{ session, update, reset, setTheme }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
