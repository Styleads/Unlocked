import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../api";
import type { ApiFollowUp, ApiOutcome } from "../api";
import { Brand, Disclaimer, ThemeSwitcher } from "../ui";

/**
 * The page behind the link in an Unlocked email. The link's token is the only credential: it shows just the one
 * appointment or application it was made for, and lets the person report what happened.
 */

const ATTENDED: [string, string][] = [["yes", "I went"], ["rescheduled", "It was rescheduled"], ["missed", "I missed it"], ["cancelled", "It was cancelled"]];
const OUTCOMES: [string, string][] = [
  ["documents_accepted", "My documents were accepted"],
  ["additional_documents_requested", "They asked for more documents"],
  ["application_submitted", "I submitted the application"],
  ["pending_review", "It is under review"],
  ["approved", "It was approved"],
  ["rejected", "It was rejected"],
  ["return_scheduled", "I have to go back"],
  ["unknown", "Not sure"],
];
const APP_STATUS: [string, string][] = [
  ["not_started", "Not started"], ["preparing", "Preparing"], ["submitted", "Submitted"], ["under_review", "Under review"],
  ["approved", "Approved"], ["rejected", "Rejected"], ["benefit_received", "Benefit received"], ["closed", "Closed"],
];
const label = (list: [string, string][], v: string) => list.find(([k]) => k === v)?.[1] ?? v;
const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "");

export default function FollowUp() {
  const token = decodeURIComponent(window.location.pathname.split("/")[2] ?? "");
  const [data, setData] = useState<ApiFollowUp | null>(null);
  const [problem, setProblem] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attended, setAttended] = useState("yes");
  const [outcome, setOutcome] = useState("");
  const [appStatus, setAppStatus] = useState("");
  const [notes, setNotes] = useState("");
  const [docs, setDocs] = useState("");

  useEffect(() => {
    let alive = true;
    api.followUp(token)
      .then((d) => {
        if (!alive) return;
        setData(d);
        setAppStatus(d.application?.status ?? "submitted");
      })
      .catch((e) => {
        if (!alive) return;
        setProblem(
          e instanceof ApiError && e.status === 410 ? "This link has expired. Open Unlocked and add your update there."
          : e instanceof ApiError && e.status === 404 ? "This link isn't valid any more. It may have been turned off."
          : "We couldn't load this page. Please try again in a moment.",
        );
      });
    return () => { alive = false; };
  }, [token]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!data) return;
    const body: ApiOutcome = data.scope_type === "appointment"
      ? { attended, ...(outcome ? { outcome } : {}), ...(docs.trim() ? { additional_documents: docs.split(",").map((s) => s.trim()).filter(Boolean) } : {}), ...(notes.trim() ? { notes: notes.trim() } : {}) }
      : { application_status: appStatus, ...(notes.trim() ? { notes: notes.trim() } : {}) };
    setBusy(true);
    setError("");
    try {
      await api.followUpOutcome(token, body);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your update couldn't be saved.");
    } finally {
      setBusy(false);
    }
  };

  const a = data?.appointment;
  return (
    <div className="page">
      <header className="site-header" style={{ padding: "18px var(--gutter)" }}>
        <Brand size={22} />
        <ThemeSwitcher />
      </header>
      <main className="main" style={{ maxWidth: 720, gap: 24 }}>
        <div className="stack" style={{ gap: 12 }}>
          <span className="eyebrow">_ Follow-up</span>
          <h1 className="serif" style={{ fontSize: "clamp(30px, 3.6vw, 44px)", lineHeight: 1 }}>
            {problem ? "This link can't be used." : done ? "Thanks, that's saved." : data?.scope_type === "appointment" ? "How did your appointment go?" : "How is your application going?"}
          </h1>
          {problem && <p className="lede" role="alert">{problem}</p>}
          {!problem && !data && <p className="lede">Loading…</p>}
        </div>

        {data && !done && (
          <form className="card nx" onSubmit={submit}>
            {a && (
              <div className="stack" style={{ gap: 4 }}>
                <strong style={{ fontWeight: 600, fontSize: 17 }}>{a.purpose}</strong>
                <span style={{ fontSize: 14, color: "var(--faint)" }}>{[when(a.scheduled_at_utc), a.location].filter(Boolean).join(" · ")}</span>
              </div>
            )}
            {data.application && (
              <div className="stack" style={{ gap: 4 }}>
                <strong style={{ fontWeight: 600, fontSize: 17 }}>{data.scheme_name ?? "Your application"}</strong>
                <span style={{ fontSize: 14, color: "var(--faint)" }}>Last reported: {label(APP_STATUS, data.application.status)}</span>
              </div>
            )}

            {data.scope_type === "appointment" ? (
              <>
                <div className="stack" style={{ gap: 8 }}>
                  <span className="label">DID YOU GO?</span>
                  <div className="segc nx-seg" role="group" aria-label="Did you go?">
                    {ATTENDED.map(([v, t]) => <button key={v} type="button" className={attended === v ? "on" : ""} aria-pressed={attended === v} onClick={() => setAttended(v)}>{t}</button>)}
                  </div>
                </div>
                <label className="stack" style={{ gap: 6 }}>
                  <span className="label">WHAT HAPPENED? (OPTIONAL)</span>
                  <select className="inp" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                    <option value="">Choose one</option>
                    {OUTCOMES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                  </select>
                </label>
                {outcome === "additional_documents_requested" && (
                  <label className="stack" style={{ gap: 6 }}>
                    <span className="label">WHICH DOCUMENTS? (SEPARATE WITH COMMAS)</span>
                    <input className="inp" value={docs} onChange={(e) => setDocs(e.target.value)} placeholder="e.g. Caste certificate, bank passbook" />
                  </label>
                )}
              </>
            ) : data.scope_type === "application" ? (
              <label className="stack" style={{ gap: 6 }}>
                <span className="label">WHERE IS IT NOW?</span>
                <select className="inp" value={appStatus} onChange={(e) => setAppStatus(e.target.value)}>
                  {APP_STATUS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              </label>
            ) : (
              <p style={{ color: "var(--muted)" }}>There is nothing to update here.</p>
            )}

            {data.scope_type !== "session" && (
              <label className="stack" style={{ gap: 6 }}>
                <span className="label">NOTES (OPTIONAL)</span>
                <textarea className="inp" rows={3} maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Anything you want to remember" />
              </label>
            )}
            {error && <p role="alert" style={{ fontSize: 14, color: "var(--warn-text)" }}>{error}</p>}
            {data.scope_type !== "session" && (
              <div className="nx-row"><button className="btn nx-sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Save my update"}</button></div>
            )}
            <p style={{ fontSize: 13, color: "var(--faint)" }}>This is your own report. Unlocked doesn't contact the authority, and the authority makes every decision.</p>
          </form>
        )}

        {done && (
          <div className="card nx">
            <p style={{ color: "var(--text-2)" }}>We've recorded your update. You can close this page.</p>
            <a className="btn-ghost nx-sm" href="/" style={{ alignSelf: "flex-start" }}>Open Unlocked</a>
          </div>
        )}
      </main>
      <Disclaimer />
    </div>
  );
}
