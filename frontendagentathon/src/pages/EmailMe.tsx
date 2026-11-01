import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { BellOff, CalendarClock, Eye, Mail, Send, X } from "lucide-react";
import { api } from "../api";
import type { ApiAppointment, ApiEmailPreview, ApiNotification, ApiPrefs } from "../api";
import { useLive } from "../live";

/**
 * Email follow-through, built on the backend's notification endpoints. It is opt-in: nothing is sent until the
 * user gives an address and ticks the consent box, and one button turns everything off and cancels what is queued.
 */

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const KIND: Record<string, string> = {
  action_plan_summary: "Your plan",
  appointment_reminders: "Appointment reminder",
  appointment_follow_up: "Appointment follow-up",
  deadline_reminder: "Deadline reminder",
  application_status_update: "Status update",
};
const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "");
const message = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

export default function EmailMe() {
  const live = useLive();
  const id = live.sessionId;
  const [prefs, setPrefs] = useState<ApiPrefs | null>(null);
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [reminders, setReminders] = useState(true);
  const [preview, setPreview] = useState<ApiEmailPreview | null>(null);
  const [sent, setSent] = useState<string>("");
  const [notes, setNotes] = useState<ApiNotification[]>([]);
  const [appts, setAppts] = useState<ApiAppointment[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!id) return;
    // listing also makes the backend send anything that has become due, so this is how queued reminders go out
    const [n, a] = await Promise.all([api.notifications(id), api.appointments(id)]);
    setNotes(n);
    setAppts(a);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    api.prefs(id)
      .then(async (p) => {
        if (!alive) return;
        setPrefs(p);
        setEmail(p.email ?? "");
        setReminders(p.categories.appointment_reminders !== false);
        if (p.email_enabled) await refresh();
      })
      .catch((e) => alive && setError(message(e, "Email settings couldn't be loaded.")));
    return () => { alive = false; };
  }, [id, refresh]);

  if (!live.active || !id) return null;
  const on = !!prefs?.email_enabled;
  const showForm = !on || editing;

  const run = async (name: string, work: () => Promise<void>) => {
    setBusy(name);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(message(e, "That didn't work. Please try again."));
    } finally {
      setBusy("");
    }
  };

  const save = (e: FormEvent) => {
    e.preventDefault();
    if (!EMAIL.test(email.trim())) return setError("Enter a valid email address.");
    if (!consent && !on) return setError("Tick the box to let us email you.");
    void run("save", async () => {
      const p = await api.savePrefs(id, {
        email: email.trim(),
        email_enabled: true,
        categories: { action_plan_summary: true, appointment_reminders: reminders, appointment_follow_up: reminders },
        consent_version: "v1",
      });
      setPrefs(p);
      setEditing(false);
      setConsent(false);
      await refresh();
    });
  };

  const turnOff = () =>
    run("off", async () => {
      await api.disableNotifications(id);
      setPrefs(await api.prefs(id));
      setPreview(null);
      setSent("");
      await refresh();
    });

  const showPreview = () => run("preview", async () => setPreview(await api.previewPlanEmail(id)));

  const sendPlan = () =>
    run("send", async () => {
      setSent("");
      const r = await api.sendPlanEmail(id);
      const list = await api.notifications(id);
      setNotes(list);
      const row = list.find((n) => n.notification_id === r.notification_id);
      if (row?.status === "failed" || r.status === "failed") setError(row?.last_error ?? "The email couldn't be sent.");
      else setSent(`Sent to ${r.recipient}${row?.is_demo ? " (demo)" : ""}. It can take a minute to arrive; check spam too.`);
    });

  const cancel = (nid: string) => run(`cancel-${nid}`, async () => { await api.cancelNotification(id, nid); await refresh(); });

  return (
    <section id="email" className="stack" style={{ gap: 20, scrollMarginTop: 96 }}>
      <div className="stack" style={{ gap: 8, maxWidth: 720 }}>
        <span className="eyebrow">_ Email</span>
        <h2 className="serif" style={{ fontSize: "clamp(26px, 2.8vw, 36px)", lineHeight: 1.05 }}>Email me my plan and reminders.</h2>
        <p style={{ fontSize: 15, color: "var(--muted)" }}>
          Optional, and off until you turn it on. We email only the address you give, only about your plan and the appointments you add, and you can switch it off at any time.
        </p>
      </div>

      {error && <p role="alert" style={{ fontSize: 14, color: "var(--warn-text)" }}>{error}</p>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(420px, 100%), 1fr))", gap: 14, alignItems: "start" }}>
        <div className="card nx">
          <div className="row-between" style={{ gap: 12 }}>
            <h3 className="serif" style={{ fontSize: 22, lineHeight: 1.05 }}>Your plan by email</h3>
            <span className={on ? "nx-badge ok" : "nx-badge"}>{on ? "Emails on" : "Emails off"}</span>
          </div>

          {showForm ? (
            <form className="stack" style={{ gap: 12 }} onSubmit={save} noValidate>
              <label htmlFor="em-addr" className="label">YOUR EMAIL ADDRESS</label>
              <input id="em-addr" className="inp" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              {!on && (
                <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 14, color: "var(--text-2)", cursor: "pointer" }}>
                  <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} style={{ marginTop: 3 }} />
                  <span>Yes, email me my plan and any reminders I ask for. I understand I can turn this off at any time.</span>
                </label>
              )}
              <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 14, color: "var(--text-2)", cursor: "pointer" }}>
                <input type="checkbox" checked={reminders} onChange={(e) => setReminders(e.target.checked)} style={{ marginTop: 3 }} />
                <span>Also send reminders for appointments I add below.</span>
              </label>
              <div className="nx-row">
                <button className="btn nx-sm" type="submit" disabled={busy === "save"}>{busy === "save" ? "Saving…" : on ? "Save changes" : "Turn on emails"}</button>
                {on && <button className="btn-ghost nx-sm" type="button" onClick={() => setEditing(false)}>Cancel</button>}
              </div>
            </form>
          ) : (
            <div className="stack" style={{ gap: 12 }}>
              <p style={{ fontSize: 14, color: "var(--muted)" }}>
                Emails go to <strong style={{ color: "var(--text)", fontWeight: 600 }}>{prefs?.email}</strong>
                {prefs?.consent_at ? `, turned on ${when(prefs.consent_at)}` : ""}.
              </p>
              <div className="nx-row">
                <button className="btn-ghost nx-sm" onClick={showPreview} disabled={busy === "preview"}><Eye size={15} aria-hidden /> {busy === "preview" ? "Loading…" : "Preview the email"}</button>
                <button className="btn nx-sm" onClick={sendPlan} disabled={busy === "send"}><Send size={15} aria-hidden /> {busy === "send" ? "Sending…" : "Send it to me now"}</button>
                <button className="btn-ghost nx-sm" onClick={() => setEditing(true)}><Mail size={15} aria-hidden /> Change address</button>
                <button className="btn-ghost nx-sm" onClick={turnOff} disabled={busy === "off"}><BellOff size={15} aria-hidden /> Turn off all emails</button>
              </div>
              {sent && <p role="status" style={{ fontSize: 14, color: "var(--primary-dark)" }}>{sent}</p>}
            </div>
          )}

          {preview && on && (
            <div className="nx-mail pop">
              <span className="label">PREVIEW · NOT SENT</span>
              <strong style={{ fontWeight: 600 }}>{preview.subject}</strong>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontFamily: "var(--sans)", fontSize: 14, color: "var(--text-2)", maxHeight: 320, overflow: "auto" }}>{preview.body_text}</pre>
              <button className="btn-ghost nx-sm" style={{ alignSelf: "flex-start" }} onClick={() => setPreview(null)}>Close preview</button>
            </div>
          )}
        </div>

        <AppointmentsCard id={id} on={on} appts={appts} onChange={refresh} setError={setError} />
      </div>

      {on && (
        <div className="card nx">
          <div className="row-between" style={{ gap: 12 }}>
            <h3 className="serif" style={{ fontSize: 22, lineHeight: 1.05 }}>Emails sent and queued</h3>
            <button className="btn-ghost nx-sm" onClick={() => run("refresh", refresh)} disabled={busy === "refresh"}>{busy === "refresh" ? "Checking…" : "Refresh"}</button>
          </div>
          {notes.length === 0 ? (
            <p style={{ fontSize: 14, color: "var(--muted)" }}>Nothing yet. Send your plan above, or add an appointment with a reminder.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column" }}>
              {notes.map((n) => (
                <li key={n.notification_id} className="list-row" style={{ gap: 12, alignItems: "flex-start" }}>
                  <span className="stack" style={{ gap: 2, minWidth: 0 }}>
                    <span style={{ fontSize: 15 }}>{KIND[n.notification_type] ?? n.notification_type}{n.is_demo ? " · demo" : ""}</span>
                    <span style={{ fontSize: 13, color: "var(--faint)" }}>
                      {n.subject} · to {n.recipient} · {n.status === "scheduled" ? `scheduled for ${when(n.scheduled_at_utc)}` : when(n.sent_at_utc ?? n.created_at)}
                    </span>
                    {n.last_error && <span style={{ fontSize: 13, color: "var(--warn-text)" }}>{n.last_error}</span>}
                  </span>
                  <span style={{ display: "flex", gap: 8, alignItems: "center", flex: "none" }}>
                    <span className={n.status === "sent" || n.status === "delivered" ? "nx-badge ok" : "nx-badge"}>{n.status}</span>
                    {n.status === "scheduled" && (
                      <button className="btn-ghost nx-sm" onClick={() => cancel(n.notification_id)} disabled={busy === `cancel-${n.notification_id}`} aria-label={`Cancel ${KIND[n.notification_type] ?? "email"}`}>
                        <X size={14} aria-hidden /> Cancel
                      </button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function AppointmentsCard({
  id, on, appts, onChange, setError,
}: { id: string; on: boolean; appts: ApiAppointment[]; onChange: () => Promise<void>; setError: (m: string) => void }) {
  const [purpose, setPurpose] = useState("");
  const [at, setAt] = useState("");
  const [place, setPlace] = useState("");
  const [remind, setRemind] = useState(true);
  const [busy, setBusy] = useState(false);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!purpose.trim()) return setError("Say what the appointment is for.");
    setBusy(true);
    setError("");
    try {
      await api.createAppointment(id, {
        purpose: purpose.trim(),
        ...(at ? { scheduled_at_utc: new Date(at).toISOString() } : {}),
        ...(place.trim() ? { location: place.trim() } : {}),
        remind_email: on && remind,
      });
      setPurpose(""); setAt(""); setPlace("");
      await onChange();
    } catch (err) {
      setError(message(err, "The appointment couldn't be saved."));
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (aid: string) => {
    try {
      await api.updateAppointment(id, aid, { status: "cancelled" });
      await onChange();
    } catch (err) {
      setError(message(err, "The appointment couldn't be cancelled."));
    }
  };

  return (
    <div className="card nx">
      <div className="row-between" style={{ gap: 12 }}>
        <h3 className="serif" style={{ fontSize: 22, lineHeight: 1.05 }}>Appointments</h3>
        <CalendarClock size={18} color="var(--faint)" aria-hidden />
      </div>
      <form className="stack" style={{ gap: 10 }} onSubmit={add} noValidate>
        <label htmlFor="ap-purpose" className="label">WHAT IS IT FOR?</label>
        <input id="ap-purpose" className="inp" placeholder="e.g. Document verification at the taluk office" maxLength={500} value={purpose} onChange={(e) => setPurpose(e.target.value)} />
        <div className="nx-row">
          <label htmlFor="ap-at" style={{ fontSize: 13, color: "var(--muted)" }}>When</label>
          <input id="ap-at" className="inp" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
          <label htmlFor="ap-place" style={{ fontSize: 13, color: "var(--muted)" }}>Where</label>
          <input id="ap-place" className="inp" style={{ flex: 1, minWidth: 140 }} placeholder="Optional" value={place} onChange={(e) => setPlace(e.target.value)} />
        </div>
        <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14, color: on ? "var(--text-2)" : "var(--faint)" }}>
          <input type="checkbox" checked={on && remind} disabled={!on} onChange={(e) => setRemind(e.target.checked)} />
          <span>{on ? "Email me a reminder the day before" : "Turn on emails to get a reminder"}</span>
        </label>
        <div className="nx-row"><button className="btn nx-sm" type="submit" disabled={busy}>{busy ? "Saving…" : "Add appointment"}</button></div>
      </form>

      {appts.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {appts.map((a) => (
            <li key={a.appointment_id} className="list-row" style={{ gap: 12, alignItems: "flex-start" }}>
              <span className="stack" style={{ gap: 2, minWidth: 0 }}>
                <span style={{ fontSize: 15 }}>{a.purpose}</span>
                <span style={{ fontSize: 13, color: "var(--faint)" }}>{[when(a.scheduled_at_utc) || "No time set", a.location].filter(Boolean).join(" · ")}</span>
              </span>
              <span style={{ display: "flex", gap: 8, alignItems: "center", flex: "none" }}>
                <span className="nx-badge">{a.status}</span>
                {a.status === "scheduled" && <button className="btn-ghost nx-sm" onClick={() => cancel(a.appointment_id)}>Cancel</button>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
