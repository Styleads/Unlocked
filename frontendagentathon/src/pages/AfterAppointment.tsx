import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { CalendarCheck } from "lucide-react";
import { api } from "../api";
import type { ApiAfterPlan, ApiDueFollowUp, ApiWhatIf } from "../api";
import WhatIfPanel from "./WhatIf";
import { useLive } from "../live";

/**
 * After an appointment, ask how it went. The backend (Agent 4) decides which appointments are over and what follows
 * from the answer; the questions and their options come from it too. Nothing is filled in for the user: "Not sure"
 * changes nothing, and a step appears only because of something they reported.
 */

export const APPOINTMENTS_CHANGED = "unlocked:appointments-changed";
const CHECK_EVERY_MS = 20_000;
const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "");

export default function AfterAppointment() {
  const live = useLive();
  const id = live.sessionId;
  const [due, setDue] = useState<ApiDueFollowUp[]>([]);
  const [later, setLater] = useState<Set<string>>(new Set());
  const [done, setDone] = useState<Record<string, { plan: ApiAfterPlan; whatIf?: ApiWhatIf }>>({});

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setDue(await api.dueFollowUps(id));
    } catch {
      /* the question is a convenience: if it can't load, the page works without it */
    }
  }, [id]);

  useEffect(() => {
    void load();
    const again = () => void load();
    window.addEventListener(APPOINTMENTS_CHANGED, again);
    // check again now and then, so the question appears once an appointment is over without a page reload
    const timer = window.setInterval(again, CHECK_EVERY_MS);
    return () => {
      window.removeEventListener(APPOINTMENTS_CHANGED, again);
      window.clearInterval(timer);
    };
  }, [load]);

  if (!live.active || !id) return null;
  const shown = due.filter((d) => !later.has(d.appointment_id));
  const answered = Object.entries(done);
  if (shown.length === 0 && answered.length === 0) return null;

  return (
    <section className="stack" style={{ gap: 14 }} aria-label="Appointments to follow up">
      {answered.map(([aid, r]) => <PlanCard key={aid} plan={r.plan} whatIf={r.whatIf} onClose={() => setDone(({ [aid]: _, ...rest }) => rest)} />)}
      {shown.map((f) => (
        <AskCard
          key={f.appointment_id}
          sessionId={id}
          item={f}
          onLater={() => setLater((s) => new Set(s).add(f.appointment_id))}
          onDone={(plan, whatIf) => {
            setDone((d) => ({ ...d, [f.appointment_id]: { plan, whatIf } }));
            setDue((list) => list.filter((x) => x.appointment_id !== f.appointment_id));
            window.dispatchEvent(new Event(APPOINTMENTS_CHANGED));
          }}
        />
      ))}
    </section>
  );
}

function AskCard({ sessionId, item, onLater, onDone }: { sessionId: string; item: ApiDueFollowUp; onLater: () => void; onDone: (p: ApiAfterPlan, w?: ApiWhatIf) => void }) {
  const live = useLive();
  const [schemeId, setSchemeId] = useState(item.scheme_id ?? "");
  const [reason, setReason] = useState("");
  const [attended, setAttended] = useState("");
  const [outcome, setOutcome] = useState("");
  const [docs, setDocs] = useState("");
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const needsDate = attended === "rescheduled" || (attended === "yes" && outcome === "return_scheduled");
  const rejected = attended === "yes" && outcome === "rejected";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!attended) return setError("Choose what happened first.");
    setBusy(true);
    setError("");
    try {
      const res = await api.reportAppointment(sessionId, item.appointment_id, {
        attended,
        ...(attended === "yes" && outcome ? { outcome } : {}),
        ...(attended === "yes" && outcome === "additional_documents_requested" && docs.trim() ? { additional_documents: docs.split(",").map((s) => s.trim()).filter(Boolean) } : {}),
        ...(needsDate && date ? { rescheduled_date: date } : {}),
        ...(notes.trim() ? { notes: notes.trim() } : {}),
        ...(rejected && schemeId ? { scheme_id: schemeId } : {}),
        ...(rejected && reason.trim() ? { reason: reason.trim() } : {}),
      });
      const plan = res.outcome_details?.plan;
      if (plan) onDone(plan, res.outcome_details?.what_if);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Your answer couldn't be saved.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card nx stack pop" style={{ gap: 14 }} onSubmit={submit} aria-label={`How did it go: ${item.purpose}`}>
      <div className="row-between" style={{ gap: 12 }}>
        <span className="eyebrow">_ After your appointment</span>
        <CalendarCheck size={18} color="var(--faint)" aria-hidden />
      </div>
      <div className="stack" style={{ gap: 4 }}>
        <h2 className="serif" style={{ fontSize: 26, lineHeight: 1.05 }}>How did it go?</h2>
        <span style={{ fontSize: 15 }}>{item.purpose}</span>
        <span style={{ fontSize: 13, color: "var(--faint)" }}>
          {[when(item.scheduled_at_utc), item.location].filter(Boolean).join(" · ")}
          {item.simulated ? " · from the office chat simulation" : ""}
        </span>
      </div>

      <div className="stack" style={{ gap: 8 }}>
        <span className="label">DID YOU GO?</span>
        <div className="segc nx-seg" role="group" aria-label="Did you go?">
          {item.attended_options.map((o) => (
            <button key={o.value} type="button" className={attended === o.value ? "on" : ""} aria-pressed={attended === o.value} onClick={() => setAttended(o.value)}>{o.label}</button>
          ))}
        </div>
      </div>

      {attended === "yes" && (
        <label className="stack" style={{ gap: 6 }}>
          <span className="label">WHAT HAPPENED?</span>
          <select className="inp" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <option value="">Choose one</option>
            {item.outcome_options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
      )}
      {attended === "yes" && outcome === "additional_documents_requested" && (
        <label className="stack" style={{ gap: 6 }}>
          <span className="label">WHICH DOCUMENTS? (SEPARATE WITH COMMAS)</span>
          <input className="inp" value={docs} onChange={(e) => setDocs(e.target.value)} placeholder="Write them as the office named them" />
        </label>
      )}
      {rejected && (
        <>
          <label className="stack" style={{ gap: 6 }}>
            <span className="label">WHICH SCHEME WAS IT FOR?</span>
            <select className="inp" value={schemeId} onChange={(e) => setSchemeId(e.target.value)}>
              <option value="">Choose a scheme</option>
              {live.schemes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label className="stack" style={{ gap: 6 }}>
            <span className="label">WHAT REASON DID THEY GIVE? (OPTIONAL)</span>
            <input className="inp" maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="In your own words" />
          </label>
        </>
      )}
      {needsDate && (
        <label className="stack" style={{ gap: 6 }}>
          <span className="label">{attended === "rescheduled" ? "NEW DATE (IF YOU HAVE IT)" : "DATE OF YOUR RETURN VISIT (IF YOU HAVE IT)"}</span>
          <input className="inp" type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      )}
      <label className="stack" style={{ gap: 6 }}>
        <span className="label">NOTES (OPTIONAL)</span>
        <input className="inp" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Anything you want to remember" />
      </label>

      {error && <p role="alert" style={{ fontSize: 14, color: "var(--warn-text)" }}>{error}</p>}
      <div className="nx-row">
        <button className="btn nx-sm" type="submit" disabled={busy || !attended}>{busy ? "Saving…" : "Save"}</button>
        <button className="btn-ghost nx-sm" type="button" onClick={onLater}>Ask me later</button>
      </div>
      <p style={{ fontSize: 13, color: "var(--faint)" }}>This is your own report. Unlocked doesn't contact the office, and the office makes every decision.</p>
    </form>
  );
}

function PlanCard({ plan, whatIf, onClose }: { plan: ApiAfterPlan; whatIf?: ApiWhatIf; onClose: () => void }) {
  return (
    <div className="card nx stack" style={{ gap: 10 }} role="status">
      <strong style={{ fontWeight: 600, fontSize: 17 }}>Thanks, that's saved.</strong>
      <p style={{ color: "var(--text-2)" }}>{plan.summary}</p>
      {plan.next_steps.length > 0 && (
        <>
          <span className="label">WHAT TO DO NEXT</span>
          <ul className="nx-docs">{plan.next_steps.map((s) => <li key={s.text}>{s.text}</li>)}</ul>
        </>
      )}
      {plan.ask_later.length > 0 && (
        <p style={{ fontSize: 14, color: "var(--muted)" }}>Later, we'll ask: {plan.ask_later.map((q) => q.question).join(" ")}</p>
      )}
      {plan.warnings.map((w) => <p key={w} style={{ fontSize: 13, color: "var(--warn-text)" }}>{w}</p>)}
      {whatIf && <WhatIfPanel data={whatIf} />}
      <div className="nx-row"><button className="btn-ghost nx-sm" onClick={onClose}>Done</button></div>
    </div>
  );
}
