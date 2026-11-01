import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError, Unreachable } from "./api";
import type { AnswerPayload, ApiArtifact, ApiPlan, ApiProgress, ApiQuestion, ApiScheme } from "./api";
import { CATEGORIES, EDU_OPTIONS } from "./data";
import type { Session } from "./session";

/**
 * Live mode: the session, schemes, questions and plan that come from the backend.
 * It only switches on once a session has really been created, so with no backend the app stays on its demo data.
 */

export type Choice = { label: string; state: AnswerPayload["state"]; value?: unknown };
export type ShownAnswer = { label: string; state: AnswerPayload["state"] };

type Saved = {
  sessionId: string | null;
  discoveredKey: string | null;
  answers: Record<string, ShownAnswer>;
  shown: ApiQuestion[];
  selected: string | null;
  sourceMode: string | null;
  warnings: string[];
};

const KEY = "unlocked_live_v1";
const EMPTY: Saved = { sessionId: null, discoveredKey: null, answers: {}, shown: [], selected: null, sourceMode: null, warnings: [] };

const load = (): Saved => {
  forceFallback(); // record ?fallback= while it is still in the URL: in-app navigation drops the query string
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
  } catch {
    return EMPTY;
  }
};

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Demo switch: open the site with ?fallback=1 to search the offline fallback schemes (?fallback=0 turns it off).
 * It is remembered for the tab, so it survives moving between pages.
 */
export function forceFallback(): boolean {
  try {
    const p = new URLSearchParams(window.location.search).get("fallback");
    if (p !== null) sessionStorage.setItem("unlocked_force_fallback", p === "0" || p === "false" ? "0" : "1");
    return sessionStorage.getItem("unlocked_force_fallback") === "1";
  } catch {
    return false;
  }
}

/** Backend attributes the Context form can supply (see contextFrom). */
export const CONTEXT_ATTRIBUTES = new Set(["state", "district", "age", "education_level"]);

/** What we tell the backend about the user, built only from what they typed on the Context page. */
export function contextFrom(session: Session): { context: Record<string, unknown>; scope: "guided" | "all" | "fallback" } {
  const d = session.details;
  const edu = EDU_OPTIONS.find((o) => o.value === d.edu)?.api;
  const age = d.age.trim() === "" ? undefined : Number(d.age);
  const guided = session.scope === "guided";
  const context: Record<string, unknown> = {
    state: d.state,
    ...(d.district.trim() ? { district: d.district.trim() } : {}),
    ...(age !== undefined && Number.isFinite(age) ? { age } : {}),
    ...(edu ? { education_level: edu } : {}),
    ...(d.need.trim() ? { other_details: { need: d.need.trim() } } : {}),
    interests: guided ? CATEGORIES.filter((c) => session.categories[c]) : [],
  };
  return { context, scope: forceFallback() ? "fallback" : guided ? "guided" : "all" };
}

type Begin = { ok: true } | { ok: false; reason: "unreachable" | "error"; message: string };

type LiveApi = {
  /** A backend session exists and discovery has produced data. */
  active: boolean;
  sessionId: string | null;
  schemes: ApiScheme[];
  questions: ApiQuestion[];
  /** Every question shown so far, so an answered one stays on screen after the backend stops asking it. */
  shown: ApiQuestion[];
  answers: Record<string, ShownAnswer>;
  plan: ApiPlan | null;
  sourceMode: string | null;
  warnings: string[];
  selected: string | null;
  select: (id: string) => void;
  /** Create the session (once per distinct context) and run discovery. `force` re-runs it. */
  discover: (session: Session, force?: boolean) => Promise<Begin>;
  answer: (q: ApiQuestion, choice: Choice) => Promise<void>;
  /** Change one answer from outside the Questions page; results and plan are refreshed in place, not blanked. */
  updateAnswer: (attribute: string, label: string, value: unknown) => Promise<void>;
  loadPlan: () => Promise<void>;
  setDoc: (docId: string, status: string) => Promise<void>;
  email: (schemeId: string, question: string) => Promise<ApiArtifact>;
  calendar: (schemeId: string, isoDate: string) => Promise<ApiArtifact>;
  progress: (schemeId: string, updates: { field: string; state: string }[]) => Promise<ApiProgress>;
  /** Forget the live session and go back to demo data (also deletes it on the server, best effort). */
  leave: () => Promise<void>;
};

const Ctx = createContext<LiveApi | null>(null);

export function LiveProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<Saved>(load);
  const [schemes, setSchemes] = useState<ApiScheme[]>([]);
  const [questions, setQuestions] = useState<ApiQuestion[]>([]);
  const [plan, setPlan] = useState<ApiPlan | null>(null);
  const inflight = useRef<Map<string, Promise<Begin>>>(new Map());

  const patch = useCallback((p: Partial<Saved>) => setSaved((s) => ({ ...s, ...p })), []);

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(saved));
    } catch {
      /* storage blocked: live state then lives in memory only */
    }
  }, [saved]);

  // After a refresh the backend still has everything; fetch it again instead of trusting stale copies.
  useEffect(() => {
    const id = saved.sessionId;
    if (!id || !saved.discoveredKey) return;
    let live = true;
    Promise.all([api.schemes(id), api.questions(id)])
      .then(([s, q]) => {
        if (!live) return;
        setSchemes(s);
        setQuestions(q);
      })
      .catch((e) => {
        // The session is gone (backend restarted with a new database): fall back to demo data.
        if (live && e instanceof ApiError && e.status === 404) setSaved(EMPTY);
      });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requireId = useCallback(() => {
    if (!saved.sessionId) throw new Error("No live session.");
    return saved.sessionId;
  }, [saved.sessionId]);

  const discover = useCallback<LiveApi["discover"]>(
    (session, force = false) => {
      const { context, scope } = contextFrom(session);
      const key = JSON.stringify({ context, scope });
      if (!force && saved.sessionId && saved.discoveredKey === key) return Promise.resolve({ ok: true } as Begin);
      const running = inflight.current.get(key);
      if (running && !force) return running; // React StrictMode mounts effects twice: share one run
      const run = (async (): Promise<Begin> => {
        try {
          let id = saved.discoveredKey === key ? saved.sessionId : null;
          if (!id) {
            // new details mean a new session; don't leave the previous one (and its answers) on the server
            if (saved.sessionId) void api.deleteSession(saved.sessionId).catch(() => undefined);
            id = (await api.createSession(context, scope)).session_id;
          }
          // the email from step 1 turns on confirmations, reminders and follow-ups for this session
          const address = session.email.trim();
          if (EMAIL_RE.test(address)) {
            await api.savePrefs(id, {
              email: address, email_enabled: true, consent_version: "step1",
              categories: { action_plan_summary: true, appointment_reminders: true, appointment_follow_up: true, simulated_appointment_confirmed: true },
            }).catch(() => undefined); // email is a convenience: discovery goes on without it
          }
          const found = await api.discover(id);
          setSchemes(found.schemes);
          setQuestions(found.questions);
          setPlan(null);
          setSaved({ ...EMPTY, sessionId: id, discoveredKey: key, sourceMode: found.source_mode, warnings: found.warnings });
          return { ok: true };
        } catch (e) {
          if (e instanceof Unreachable) return { ok: false, reason: "unreachable", message: e.message };
          return { ok: false, reason: "error", message: e instanceof Error ? e.message : "Discovery failed." };
        } finally {
          inflight.current.delete(key);
        }
      })();
      inflight.current.set(key, run);
      return run;
    },
    [saved.sessionId, saved.discoveredKey],
  );

  const answer = useCallback<LiveApi["answer"]>(
    async (q, choice) => {
      const id = requireId();
      const payload: AnswerPayload = { attribute: q.attribute, state: choice.state, ...(choice.state === "answered" ? { value: choice.value } : {}) };
      const result = await api.answers(id, [payload]);
      setSaved((s) => ({
        ...s,
        answers: { ...s.answers, [q.attribute]: { label: choice.label, state: choice.state } },
        shown: s.shown.some((x) => x.id === q.id) ? s.shown : [...s.shown, q],
      }));
      setQuestions(result.next_questions);
      setSchemes(await api.schemes(id)); // every section reads the same fresh assessment
      setPlan(null); // a new answer can change which schemes (and documents) are in play
    },
    [requireId],
  );

  const updateAnswer = useCallback<LiveApi["updateAnswer"]>(
    async (attribute, label, value) => {
      const id = requireId();
      const result = await api.answers(id, [{ attribute, state: "answered", value } as AnswerPayload]);
      setSaved((s) => ({ ...s, answers: { ...s.answers, [attribute]: { label, state: "answered" } } }));
      setQuestions(result.next_questions);
      const [fresh, freshPlan] = await Promise.all([api.schemes(id), api.plan(id)]);
      setSchemes(fresh);
      setPlan(freshPlan);
    },
    [requireId],
  );

  const loadPlan = useCallback(async () => {
    setPlan(await api.plan(requireId()));
  }, [requireId]);

  const setDoc = useCallback<LiveApi["setDoc"]>(
    async (docId, status) => {
      const id = requireId();
      // Show the change at once, then take the server's recomputed plan as the truth.
      setPlan((p) => (p ? { ...p, checklist: p.checklist.map((c) => (c.id === docId ? { ...c, status: status as ApiPlan["checklist"][number]["status"] } : c)) } : p));
      setPlan(await api.setDoc(id, docId, status));
    },
    [requireId],
  );

  const email = useCallback<LiveApi["email"]>(
    (schemeId, question) => api.email(requireId(), { scheme_id: schemeId, purpose: "inquiry", question }),
    [requireId],
  );
  const calendar = useCallback<LiveApi["calendar"]>(
    (schemeId, isoDate) => api.calendar(requireId(), { scheme_id: schemeId, kind: "deadline", event_date: isoDate, date_confirmed_by_user: true }),
    [requireId],
  );
  const progress = useCallback<LiveApi["progress"]>((schemeId, updates) => api.progress(requireId(), schemeId, updates), [requireId]);

  const leave = useCallback(async () => {
    const id = saved.sessionId;
    setSaved(EMPTY);
    setSchemes([]);
    setQuestions([]);
    setPlan(null);
    if (id) await api.deleteSession(id).catch(() => undefined);
  }, [saved.sessionId]);

  const value = useMemo<LiveApi>(
    () => ({
      active: !!saved.sessionId && !!saved.discoveredKey,
      sessionId: saved.sessionId,
      schemes, questions, plan,
      shown: saved.shown,
      answers: saved.answers,
      sourceMode: saved.sourceMode,
      warnings: saved.warnings,
      selected: saved.selected,
      select: (id) => patch({ selected: id }),
      discover, answer, updateAnswer, loadPlan, setDoc, email, calendar, progress, leave,
    }),
    [saved, schemes, questions, plan, patch, discover, answer, updateAnswer, loadPlan, setDoc, email, calendar, progress, leave],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLive(): LiveApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLive must be used inside LiveProvider");
  return ctx;
}
