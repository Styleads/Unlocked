/**
 * Typed client for the Unlocked backend (api/main.py).
 * The base URL comes from VITE_API_URL; without a reachable backend the app keeps working on its demo data.
 */

export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** The request never reached the backend (not running, blocked, offline). */
export class Unreachable extends Error {}

// ---- Response shapes (the fields the UI reads; extra fields are ignored) ----

export type ApiRequirement = {
  requirement_id: string;
  attribute?: string | null;
  status: "satisfied" | "not_satisfied" | "unknown" | "needs_clarification" | "unverified";
  reason: string;
  criterion: string;
  source_url?: string | null;
};

export type ApiDocument = { name: string; source_url?: string | null; evidence?: string | null };

export type ApiScheme = {
  id: string;
  name: string;
  summary?: string | null;
  department?: string | null;
  government_level?: string | null;
  benefit?: unknown;
  documents: ApiDocument[];
  application_steps: string[];
  application_url?: string | null;
  official_sources: string[];
  source_type: string;
  assessment_status?: "potential_match" | "more_information_needed" | "not_yet_verified" | "unlikely_to_match" | "uncertain" | null;
  assessment_explanation?: string | null;
  requirements: ApiRequirement[];
  missing_attributes: string[];
};

export type ApiQuestion = {
  id: string;
  attribute: string;
  question: string;
  input_type: "number" | "range" | "select" | "boolean" | "text";
  options: string[];
  ranges: { label: string; min: number | null; max: number | null }[];
  why_asked: string;
  related_scheme_ids: string[];
  sensitivity: "low" | "medium" | "high";
  allow_prefer_not_to_answer: boolean;
};

export type ApiChecklistItem = {
  id: string;
  name: string;
  status: "have" | "obtained" | "needed" | "unknown";
  order: number;
  required_by_scheme_ids: string[];
  dependencies: string[];
  source_urls: string[];
  reason: string;
};

export type ApiPlan = {
  checklist: ApiChecklistItem[];
  nodes: { id: string; label: string; kind: string }[];
  edges: { source: string; target: string; relation: string; source_url: string }[];
  shared_prerequisites: string[];
  explanation: string;
  warnings: string[];
  excluded_documents: string[];
};

export type ApiDiscovery = {
  session_id: string;
  total_schemes: number;
  schemes: ApiScheme[];
  questions: ApiQuestion[];
  source_mode: "live_search" | "fallback";
  warnings: string[];
};

export type ApiReassessment = { session_id: string; next_questions: ApiQuestion[] };

export type ApiArtifact = {
  status: "ready" | "needs_input";
  title: string;
  body_content: string;
  subject?: string | null;
  target_destination?: string | null;
  instructions: string;
  filename?: string | null;
  missing_fields: string[];
  warnings: string[];
  generated_by: string;
};

export type ApiProgress = { summary: string; warnings: string[]; follow_ups: { id: string; question: string; field: string; options: string[] }[] };

export type AnswerPayload = { attribute: string; state: "answered" | "skipped" | "unknown" | "prefer_not_to_answer"; value?: unknown };

// ---- Transport ----

async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const ctl = new AbortController();
  const timer = init?.timeoutMs ? window.setTimeout(() => ctl.abort(), init.timeoutMs) : undefined;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: ctl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Unreachable("The backend could not be reached.");
  } finally {
    if (timer) window.clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : detail;
    } catch {
      /* keep the status text */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const sid = (id: string) => `/api/sessions/${encodeURIComponent(id)}`;
const post = <T>(path: string, body: unknown, timeoutMs?: number) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), timeoutMs });

export const api = {
  health: () => request<{ operational: boolean; services: Record<string, boolean> }>("/api/health", { timeoutMs: 2500 }),
  createSession: (context: Record<string, unknown>, scope: "guided" | "all" | "fallback") =>
    post<{ session_id: string }>("/api/sessions", { context, scope }, 15000),
  deleteSession: (id: string) => request<{ deleted: boolean }>(sid(id), { method: "DELETE", timeoutMs: 10000 }),
  // Discovery can take minutes against live sources, so it has no client-side timeout.
  discover: (id: string) => post<ApiDiscovery>(`${sid(id)}/discover`, { enable_fallback: true }),
  schemes: (id: string) => request<ApiScheme[]>(`${sid(id)}/schemes`, { timeoutMs: 20000 }),
  questions: (id: string) => request<ApiQuestion[]>(`${sid(id)}/questions`, { timeoutMs: 20000 }),
  answers: (id: string, answers: AnswerPayload[]) => post<ApiReassessment>(`${sid(id)}/answers`, { answers }, 30000),
  plan: (id: string) => request<ApiPlan>(`${sid(id)}/plan`, { timeoutMs: 30000 }),
  setDoc: (id: string, docId: string, status: string) => post<ApiPlan>(`${sid(id)}/checklist/${encodeURIComponent(docId)}`, { status }, 30000),
  email: (id: string, body: { scheme_id: string; purpose: string; question: string; user_details?: Record<string, string> }) =>
    post<ApiArtifact>(`${sid(id)}/actions/email`, body, 60000),
  calendar: (id: string, body: { scheme_id: string; kind: string; event_date: string; date_confirmed_by_user: boolean; notes?: string }) =>
    post<ApiArtifact>(`${sid(id)}/actions/calendar`, body, 30000),
  progress: (id: string, schemeId: string, updates: { field: string; state: string }[]) =>
    post<ApiProgress>(`${sid(id)}/progress`, { scheme_id: schemeId, updates }, 30000),
};
