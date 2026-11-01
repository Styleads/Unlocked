import { useEffect, useRef, useState } from "react";
import { Download, MessageCircle } from "lucide-react";
import { api, ApiError } from "../api";
import type { ApiNotification, ApiOfficeChat, ApiOfficeOutcome } from "../api";
import { useLive } from "../live";
import { BackLink, Brand, Disclaimer, ThemeSwitcher } from "../ui";
import { downloadText } from "../ics";
import { APPOINTMENTS_CHANGED } from "./AfterAppointment";

/**
 * A simulated WhatsApp-style chat with a scheme's office. For the demo the user picks how the office will respond (the
 * simulator's scripts); the conversation then plays out on its own. No real office is contacted. When a slot is
 * confirmed the backend saves the appointment, emails the confirmation at once (if an email was given on step 1) and
 * schedules the reminder and the follow-up.
 */

// The simulator's scripts, as the backend names them, worded as the outcome the user picks.
export const SCENARIOS: [string, string][] = [
  ["scenario_a_success", "The office confirms an appointment"],
  ["scenario_b_no_availability", "The office has no slots"],
  ["scenario_c_missing_info", "The office asks for details and shares a WhatsApp number"],
  ["scenario_d_unclear_unsupported", "The office can't handle this by chat"],
];
const ENDED = new Set(["completed", "no_availability", "unable_to_resolve", "cancelled", "manual_followup_required"]);
const STATUS_TEXT: Record<string, string> = {
  completed: "Appointment confirmed (simulated)",
  no_availability: "No slots available",
  unable_to_resolve: "Couldn't be handled over chat",
  cancelled: "Cancelled",
  manual_followup_required: "Needs your follow-up",
  awaiting_user_input: "Waiting for you",
  appointment_offered: "A slot was offered",
  in_progress: "Chatting…",
};
// a short pause between messages so the conversation reads like a chat; none in tests
const TURN_DELAY_MS = import.meta.env.MODE === "test" ? 0 : 700;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type EmailState = { confirmation?: ApiNotification; reminders: number; followUps: number };

export function OfficeChatPanel({ schemeId: fixedScheme, schemeName }: { schemeId?: string; schemeName?: string }) {
  const live = useLive();
  const sessionId = live.sessionId;
  const [picked, setPicked] = useState("");
  const schemeId = fixedScheme || picked || live.selected || live.schemes[0]?.id || "";
  const [scenario, setScenario] = useState(SCENARIOS[0][0]);
  const [chat, setChat] = useState<ApiOfficeChat | null>(null);
  const [outcome, setOutcome] = useState<ApiOfficeOutcome | null>(null);
  const [emails, setEmails] = useState<EmailState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<Set<string>>(new Set());
  const logEnd = useRef<HTMLDivElement | null>(null);
  const alive = useRef(true);
  // set on every mount: StrictMode (dev) mounts, unmounts and mounts again, and a flag left false would stop the chat
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);
  useEffect(() => { logEnd.current?.scrollIntoView?.({ block: "nearest" }); }, [chat?.messages.length]);

  const finishUp = async (c: ApiOfficeChat) => {
    if (!sessionId || !ENDED.has(c.chat_status)) return;
    setOutcome(await api.officeOutcome(c.chat_id));
    if (c.appointment_status === "simulated_confirmed") {
      window.dispatchEvent(new Event(APPOINTMENTS_CHANGED));
      const list = await api.notifications(sessionId).catch(() => [] as ApiNotification[]);
      setEmails({
        confirmation: [...list].reverse().find((n) => n.notification_type === "simulated_appointment_confirmed"),
        reminders: list.filter((n) => n.notification_type === "appointment_reminders").length,
        followUps: list.filter((n) => n.notification_type === "appointment_follow_up").length,
      });
    }
  };

  /** Let the simulated office answer until there is a result or something for the user to do. */
  const play = async (start: ApiOfficeChat) => {
    let c = start;
    for (let i = 0; i < 8 && alive.current; i++) {
      if (ENDED.has(c.chat_status) || c.appointment_status === "awaiting_user_approval" || c.unresolved_questions.length > 0) break;
      await sleep(TURN_DELAY_MS);
      c = await api.advanceOfficeChat(c.chat_id);
      if (alive.current) setChat(c);
    }
    await finishUp(c);
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const start = () => run(async () => {
    if (!sessionId || !schemeId) return;
    setOutcome(null);
    setEmails(null);
    setSent(new Set());
    // demo: any day works and Unlocked may confirm the slot it is offered
    const c = await api.startOfficeChat(sessionId, { scheme_id: schemeId, scenario_id: scenario, preferred_days: [], pre_authorized_confirmation: true });
    setChat(c);
    await play(c);
  });
  const decide = (approved: boolean) => chat && run(async () => {
    const c = await api.decideOfficeSlot(chat.chat_id, approved);
    setChat(c);
    await finishUp(c);
  });
  const markSent = (qid: string) => run(async () => {
    await api.markQuestionSent(qid);
    setSent((s) => new Set(s).add(qid));
  });

  if (!live.active || !sessionId) {
    return <p style={{ fontSize: 14, color: "var(--muted)" }}>The office chat works on a search you have run. Search for schemes first.</p>;
  }

  const waiting = chat?.appointment_status === "awaiting_user_approval";
  const ended = !!chat && ENDED.has(chat.chat_status);
  const name = schemeName ?? live.schemes.find((s) => s.id === (chat?.scheme_id ?? schemeId))?.name ?? "this scheme";

  return (
    <div className="stack" style={{ gap: 14 }}>
      <p className="oc-banner" role="note">Simulation: no real office is contacted. Pick how the office responds and watch Unlocked handle the chat.</p>

      {!chat ? (
        <form className="stack" style={{ gap: 12 }} onSubmit={(e) => { e.preventDefault(); void start(); }}>
          {!fixedScheme && (
            <label className="stack" style={{ gap: 6 }}>
              <span className="label">SCHEME</span>
              <select className="inp" value={schemeId} onChange={(e) => setPicked(e.target.value)}>
                {live.schemes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
          )}
          <label className="stack" style={{ gap: 6 }}>
            <span className="label">HOW SHOULD THE OFFICE RESPOND?</span>
            <select className="inp" value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {SCENARIOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </label>
          <div className="nx-row">
            <button className="btn nx-sm" type="submit" disabled={busy || !schemeId}>
              <MessageCircle size={15} aria-hidden /> {busy ? "Starting…" : "Start the chat"}
            </button>
          </div>
        </form>
      ) : (
        <section className="stack" style={{ gap: 12 }} aria-label={`Simulated chat about ${name}`}>
          <div className="oc-log" role="log" aria-live="polite">
            {chat.messages.map((m) => (
              <div key={m.message_id} className={`oc-msg ${m.sender === "unlocked" ? "me" : "them"}`}>
                <small>{m.sender === "unlocked" ? "Unlocked (for you)" : "Office desk (simulated)"}</small>
                {m.message_text}
              </div>
            ))}
            {busy && !ended && <div className="oc-msg them" aria-hidden><small>Office desk (simulated)</small>typing…</div>}
            <div ref={logEnd} />
          </div>

          <p role="status" style={{ fontSize: 14, color: "var(--muted)" }}>Status: {STATUS_TEXT[chat.chat_status] ?? chat.chat_status.replace(/_/g, " ")}</p>

          {waiting && chat.appointment && (
            <div className="card nx stack" style={{ gap: 10 }}>
              <strong style={{ fontWeight: 600 }}>The simulated office offered a slot</strong>
              <span>{[chat.appointment.date, chat.appointment.time].filter(Boolean).join(" at ") || "Time to be agreed"}</span>
              <div className="nx-row">
                <button className="btn nx-sm" onClick={() => decide(true)} disabled={busy}>Approve this slot</button>
                <button className="btn-ghost nx-sm" onClick={() => decide(false)} disabled={busy}>Decline</button>
              </div>
            </div>
          )}

          {chat.unresolved_questions.map((q) => (
            <div key={q.question_id} className="card nx stack" style={{ gap: 10 }}>
              <strong style={{ fontWeight: 600 }}>Left for you</strong>
              <span>{q.question_text}</span>
              {q.click_to_chat_url && q.receiver_whatsapp_number ? (
                <div className="nx-row">
                  <a className="btn nx-sm" href={q.click_to_chat_url} target="_blank" rel="noopener noreferrer">
                    <MessageCircle size={15} aria-hidden /> Open WhatsApp ({q.receiver_whatsapp_number})
                  </a>
                  <button className="btn-ghost nx-sm" onClick={() => markSent(q.question_id)} disabled={busy || sent.has(q.question_id)}>
                    {sent.has(q.question_id) ? "Marked as sent" : "I sent it"}
                  </button>
                </div>
              ) : (
                <span style={{ fontSize: 14, color: "var(--faint)" }}>No contact number was given, so there is no link to open.</span>
              )}
            </div>
          ))}

          {ended && outcome && (
            <div className="card nx stack" style={{ gap: 10 }}>
              <strong style={{ fontWeight: 600 }}>Outcome (simulated)</strong>
              <p>{outcome.summary}</p>
              {emails && (
                <p style={{ fontSize: 14, color: emails.confirmation?.status === "failed" ? "var(--warn-text)" : "var(--primary-dark)" }}>
                  {!emails.confirmation
                    ? "Add your email on step 1 to get the confirmation, a reminder and a follow-up."
                    : emails.confirmation.status === "failed"
                      ? `The confirmation email couldn't be sent${emails.confirmation.last_error ? `: ${emails.confirmation.last_error}` : "."}`
                      : `Confirmation emailed to ${emails.confirmation.recipient}.`}
                  {emails.confirmation && (emails.reminders > 0 || emails.followUps > 0) && " A reminder before the appointment and a follow-up after it are scheduled."}
                </p>
              )}
              {outcome.next_steps.length > 0 && <ul className="nx-docs">{outcome.next_steps.map((n) => <li key={n}>{n}</li>)}</ul>}
              {outcome.calendar_ics && (
                <div className="nx-row">
                  <button className="btn-ghost nx-sm" onClick={() => downloadText(`simulated_appointment_${chat.chat_id}.ics`, outcome.calendar_ics ?? "", "text/calendar")}>
                    <Download size={15} aria-hidden /> Download calendar file
                  </button>
                </div>
              )}
            </div>
          )}

          {(ended || chat.unresolved_questions.length > 0) && (
            <div className="nx-row">
              <button className="btn-ghost nx-sm" onClick={() => { setChat(null); setOutcome(null); setEmails(null); }}>Try another response</button>
            </div>
          )}
        </section>
      )}

      {error && <p role="alert" style={{ color: "var(--warn-text)" }}>{error}</p>}
    </div>
  );
}

export default function OfficeChat() {
  return (
    <div className="page">
      <header className="site-header" style={{ padding: "18px var(--gutter)" }}>
        <Brand size={22} />
        <ThemeSwitcher />
      </header>
      <main className="main" style={{ maxWidth: 760, gap: 24 }}>
        <div className="stack" style={{ gap: 12 }}>
          <BackLink to="/plan">Back to your plan</BackLink>
          <span className="eyebrow">_ Office chat (simulated)</span>
          <h1 className="serif" style={{ fontSize: "clamp(30px, 3.6vw, 44px)", lineHeight: 1 }}>Chat with the office.</h1>
        </div>
        <OfficeChatPanel />
        <Disclaimer />
      </main>
    </div>
  );
}
