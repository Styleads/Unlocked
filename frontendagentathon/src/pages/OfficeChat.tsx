import { useEffect, useRef, useState } from "react";
import { Download, MessageCircle } from "lucide-react";
import { api, ApiError } from "../api";
import type { ApiOfficeChat, ApiOfficeOutcome } from "../api";
import { useLive } from "../live";
import { BackLink, Brand, Disclaimer, ThemeSwitcher } from "../ui";
import { downloadText } from "../ics";

/**
 * A simulated enquiry to a scheme's office. Nothing here contacts a real office: a scripted desk replies, Unlocked's
 * Action Agent answers on the applicant's behalf, and anything that needs the applicant (approving a slot, following
 * up on WhatsApp) is left to them. The backend decides every status; this page only shows and relays.
 */

// The simulated desk's scripts, as the backend names them.
const SCENARIOS: [string, string][] = [
  ["scenario_a_success", "The office offers a slot and confirms it"],
  ["scenario_b_no_availability", "The office has no slots"],
  ["scenario_c_missing_info", "The office asks for details and shares a WhatsApp number"],
  ["scenario_d_unclear_unsupported", "The office can't handle this by chat"],
];
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const ENDED = new Set(["completed", "no_availability", "unable_to_resolve", "cancelled", "manual_followup_required"]);

const STATUS_TEXT: Record<string, string> = {
  completed: "Simulated appointment confirmed",
  no_availability: "No slots available",
  unable_to_resolve: "Couldn't be handled over chat",
  cancelled: "Cancelled",
  manual_followup_required: "Needs your follow-up",
  awaiting_user_input: "Waiting for you",
  appointment_offered: "A slot was offered",
  in_progress: "In progress",
};

export default function OfficeChat() {
  const live = useLive();
  const sessionId = live.sessionId;
  const [picked, setPicked] = useState("");
  // schemes load after a refresh, so the choice is derived rather than frozen at first render
  const schemeId = picked || live.selected || live.schemes[0]?.id || "";
  const [scenario, setScenario] = useState(SCENARIOS[0][0]);
  const [days, setDays] = useState<string[]>([]);
  const [preAuth, setPreAuth] = useState(false);
  const [chat, setChat] = useState<ApiOfficeChat | null>(null);
  const [outcome, setOutcome] = useState<ApiOfficeOutcome | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState<Set<string>>(new Set());
  const logEnd = useRef<HTMLDivElement | null>(null);

  useEffect(() => { logEnd.current?.scrollIntoView?.({ block: "nearest" }); }, [chat?.messages.length]);

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

  const loadOutcome = async (c: ApiOfficeChat) => {
    if (ENDED.has(c.chat_status)) setOutcome(await api.officeOutcome(c.chat_id));
  };
  const apply = async (c: ApiOfficeChat) => { setChat(c); await loadOutcome(c); };

  const start = () => run(async () => {
    if (!sessionId) return;
    setOutcome(null);
    setSent(new Set());
    await apply(await api.startOfficeChat(sessionId, { scheme_id: schemeId, scenario_id: scenario, preferred_days: days, pre_authorized_confirmation: preAuth }));
  });
  const next = () => chat && run(async () => apply(await api.advanceOfficeChat(chat.chat_id)));
  const decide = (approved: boolean) => chat && run(async () => apply(await api.decideOfficeSlot(chat.chat_id, approved)));
  const finish = () => chat && run(async () => apply(await api.finishOfficeChat(chat.chat_id)));
  const markSent = (qid: string) => run(async () => {
    await api.markQuestionSent(qid);
    setSent((s) => new Set(s).add(qid));
  });

  const waiting = chat?.appointment_status === "awaiting_user_approval";
  const ended = !!chat && ENDED.has(chat.chat_status);
  const schemeName = live.schemes.find((s) => s.id === (chat?.scheme_id ?? schemeId))?.name ?? "this scheme";

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
          <h1 className="serif" style={{ fontSize: "clamp(30px, 3.6vw, 44px)", lineHeight: 1 }}>Try asking the office.</h1>
          <p className="oc-banner" role="note">
            This is a simulation. No real office is contacted and no personal details are shared. It shows how Unlocked could ask about a document-verification slot for you, and what is left for you to decide.
          </p>
        </div>

        {!live.active || !sessionId ? (
          <div className="card nx stack" style={{ gap: 12 }}>
            <p>The office chat works on a search you have run. Search for schemes first, then come back from your plan.</p>
          </div>
        ) : !chat ? (
          <form className="card nx stack" style={{ gap: 16 }} onSubmit={(e) => { e.preventDefault(); void start(); }}>
            <label className="stack" style={{ gap: 6 }}>
              <span className="label">SCHEME</span>
              <select className="inp" value={schemeId} onChange={(e) => setPicked(e.target.value)}>
                {live.schemes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label className="stack" style={{ gap: 6 }}>
              <span className="label">WHAT SHOULD THE SIMULATED OFFICE DO?</span>
              <select className="inp" value={scenario} onChange={(e) => setScenario(e.target.value)}>
                {SCENARIOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
              </select>
            </label>
            <div className="stack" style={{ gap: 8 }}>
              <span className="label">DAYS YOU CAN GO (LEAVE EMPTY IF ANY DAY WORKS)</span>
              <div className="segc oc-days" role="group" aria-label="Days you can go">
                {DAYS.map((d) => (
                  <button key={d} type="button" className={days.includes(d) ? "on" : ""} aria-pressed={days.includes(d)}
                    onClick={() => setDays((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]))}>
                    {d[0].toUpperCase() + d.slice(1, 3)}
                  </button>
                ))}
              </div>
            </div>
            <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 15 }}>
              <input type="checkbox" checked={preAuth} onChange={(e) => setPreAuth(e.target.checked)} style={{ marginTop: 4 }} />
              <span>Let Unlocked confirm a slot that matches my days without asking me first. <span style={{ color: "var(--faint)" }}>Off by default: otherwise you approve each slot.</span></span>
            </label>
            <div className="nx-row">
              <button className="btn nx-sm" type="submit" disabled={busy || !schemeId}>{busy ? "Starting…" : "Start the chat"}</button>
            </div>
          </form>
        ) : (
          <section className="stack" style={{ gap: 16 }} aria-label={`Simulated chat about ${schemeName}`}>
            <div className="oc-log" role="log" aria-live="polite">
              {chat.messages.map((m) => (
                <div key={m.message_id} className={`oc-msg ${m.sender === "unlocked" ? "me" : "them"}`}>
                  <small>{m.sender === "unlocked" ? "Unlocked (for you)" : "Office desk (simulated)"}</small>
                  {m.message_text}
                </div>
              ))}
              <div ref={logEnd} />
            </div>

            <p role="status" style={{ fontSize: 14, color: "var(--muted)" }}>Status: {STATUS_TEXT[chat.chat_status] ?? chat.chat_status.replace(/_/g, " ")}</p>

            {waiting && chat.appointment && (
              <div className="card nx stack" style={{ gap: 12 }}>
                <strong style={{ fontWeight: 600 }}>The simulated office offered a slot</strong>
                <span>{[chat.appointment.date, chat.appointment.time].filter(Boolean).join(" at ") || "Time to be agreed"}</span>
                <span style={{ fontSize: 14, color: "var(--faint)" }}>Unlocked will not confirm this unless you approve it.</span>
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
                <span style={{ fontSize: 13, color: "var(--faint)" }}>The number comes from the simulated desk in this demo; it is not a real office's number.</span>
              </div>
            ))}

            {ended && outcome && (
              <div className="card nx stack" style={{ gap: 10 }}>
                <strong style={{ fontWeight: 600 }}>Outcome (simulated)</strong>
                <p>{outcome.summary}</p>
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

            <div className="nx-row">
              {!ended && <button className="btn nx-sm" onClick={next} disabled={busy || waiting}>{busy ? "Waiting for the desk…" : "Next reply"}</button>}
              {!ended && <button className="btn-ghost nx-sm" onClick={finish} disabled={busy}>End the chat</button>}
              {ended && <button className="btn-ghost nx-sm" onClick={() => { setChat(null); setOutcome(null); }}>Start another</button>}
            </div>
          </section>
        )}

        {error && <p role="alert" style={{ color: "var(--warn-text)" }}>{error}</p>}
        <Disclaimer />
      </main>
    </div>
  );
}
