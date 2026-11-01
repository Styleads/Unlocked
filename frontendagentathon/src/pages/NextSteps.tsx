import { useState } from "react";
import type { ReactNode } from "react";
import { BadgeCheck, CalendarPlus, Check, CircleDashed, ClipboardCopy, Mail, MessageCircle, PartyPopper, Send } from "lucide-react";
import { ArrowChip } from "../ui";
import { useSession } from "../session";
import { useLive } from "../live";
import { useRouter } from "../router";
import { APPLY_STAGES, SCHEMES } from "../data";
import type { ApplyStage } from "../data";
import type { PlanDocVM, PlanVM } from "../model";
import type { ApiProgress } from "../api";
import { buildIcs, downloadText } from "../ics";

/** Documents a scheme needs: the ones listed for it, plus any document those must come after. */
function docsFor(plan: PlanVM, schemeId: string): PlanDocVM[] {
  const need = new Set(plan.docs.filter((d) => d.forIds.includes(schemeId)).map((d) => d.id));
  for (let grew = true; grew; ) {
    grew = false;
    for (const d of plan.docs) {
      if (!need.has(d.id)) continue;
      for (const n of d.after) {
        const pre = plan.docs.find((p) => p.name === n);
        if (pre && !need.has(pre.id)) { need.add(pre.id); grew = true; }
      }
    }
  }
  return plan.docs.filter((d) => need.has(d.id));
}

/** One icon and colour per application condition, so the state reads at a glance. */
const STAGE_ICON: Record<ApplyStage, ReactNode> = {
  todo: <CircleDashed size={14} aria-hidden />,
  submitted: <Send size={14} aria-hidden />,
  approved: <BadgeCheck size={14} aria-hidden />,
  received: <PartyPopper size={14} aria-hidden />,
};

/** What the user tells us, in the backend's vocabulary. Nothing here is a decision by Unlocked. */
const STAGE_UPDATES: Record<ApplyStage, { field: string; state: string }[]> = {
  todo: [{ field: "submitted", state: "no" }],
  submitted: [{ field: "submitted", state: "yes" }],
  approved: [{ field: "submitted", state: "yes" }, { field: "decision", state: "approved" }],
  received: [{ field: "submitted", state: "yes" }, { field: "decision", state: "approved" }, { field: "benefit_received", state: "yes" }],
};

const today = () => new Date().toISOString().slice(0, 10);

/**
 * A plain enquiry to the scheme's office, used when no backend is connected. It uses only what the plan already
 * shows (scheme, documents, official page): no answers or personal details, no invented address or deadline.
 */
function draftEmail(name: string, url: string, docs: PlanDocVM[], isReady: (id: string) => boolean) {
  const have = docs.filter((d) => isReady(d.id)).map((d) => `- ${d.name}`);
  const pending = docs.filter((d) => !isReady(d.id)).map((d) => `- ${d.name}`);
  const body = [
    "Dear Sir or Madam,",
    "",
    `I am planning to apply for ${name} and would like to confirm a few details before I submit my application.`,
    "",
    have.length ? `Documents I have ready:\n${have.join("\n")}` : "I have not collected any documents yet.",
    ...(pending.length ? ["", `Documents I am still arranging:\n${pending.join("\n")}`] : []),
    "",
    "Could you please confirm:",
    "1. That the documents above are the complete list required.",
    "2. The last date to apply.",
    "3. Where and how the application should be submitted.",
    "",
    ...(url ? [`The official page I referred to: ${url}`, ""] : []),
    "Thank you for your time.",
    "",
    "Regards,",
    "[Your name]",
  ].join("\n");
  return { subject: `Query about applying for ${name}`, body };
}

const DEFAULT_QUESTION = "Could you confirm the complete list of required documents, the last date to apply, and where to submit the application?";

/** What happens after the document plan: apply, remind yourself, and record how the application goes. */
export default function NextSteps({ plan, isReady }: { plan: PlanVM; isReady: (id: string) => boolean }) {
  const { session, update } = useSession();
  const live = useLive();
  if (plan.schemes.length === 0) return null;

  const urlOf = (id: string) => {
    if (!live.active) return SCHEMES.find((s) => s.id === id)?.url ?? "";
    const s = live.schemes.find((x) => x.id === id);
    return s?.application_url ?? s?.official_sources[0] ?? "";
  };

  return (
    <section id="next" className="stack" style={{ gap: 20, scrollMarginTop: 96 }}>
      <div className="stack" style={{ gap: 8, maxWidth: 720 }}>
        <span className="eyebrow">_ What happens next</span>
        <h2 className="serif" style={{ fontSize: "clamp(26px, 2.8vw, 36px)", lineHeight: 1.05 }}>Apply, and keep track.</h2>
        <p style={{ fontSize: 15, color: "var(--muted)" }}>
          Each scheme below is applied for on its own official page. Unlocked can't submit anything for you. Record your own progress here, and the authority makes the decision.
        </p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(420px, 100%), 1fr))", gap: 14 }}>
        {plan.schemes.map((n) => {
          const docs = docsFor(plan, n.id);
          return (
            <SchemeStep
              key={n.id}
              id={n.id}
              name={n.name}
              url={urlOf(n.id)}
              docs={docs}
              ready={isReady}
              missing={docs.filter((d) => !isReady(d.id))}
              stage={session.apply[n.id] ?? "todo"}
              setStage={(v) => update((s) => ({ apply: { ...s.apply, [n.id]: v } }))}
            />
          );
        })}
      </div>
    </section>
  );
}

function SchemeStep({
  id, name, url, docs, ready, missing, stage, setStage,
}: {
  id: string; name: string; url: string; docs: PlanDocVM[]; ready: (id: string) => boolean; missing: PlanDocVM[];
  stage: ApplyStage; setStage: (s: ApplyStage) => void;
}) {
  const live = useLive();
  const { navigate } = useRouter();
  const [date, setDate] = useState("");
  const [copied, setCopied] = useState(false);
  const [note, setNote] = useState("");
  const [mailOpen, setMailOpen] = useState(false);
  const [mailCopied, setMailCopied] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [mailMeta, setMailMeta] = useState<{ to?: string | null; by: string; warnings: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<ApiProgress | null>(null);
  const allReady = missing.length === 0;

  const remind = async () => {
    if (!date) return;
    setNote("");
    const file = `${name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-reminder.ics`;
    if (live.active) {
      try {
        const a = await live.calendar(id, date);
        if (a.status === "ready" && a.body_content) downloadText(a.filename ?? file, a.body_content);
        else setNote(a.instructions || `Missing: ${a.missing_fields.join(", ")}`);
      } catch (e) {
        setNote(e instanceof Error ? e.message : "The reminder couldn't be created.");
      }
      return;
    }
    downloadText(
      file,
      buildIcs({
        title: `Apply: ${name}`,
        isoDate: date,
        description: `Apply on the official page. Documents: ${docs.map((d) => d.name).join(", ")}. This is your own reminder; the date was set by you.`,
        url,
      }),
    );
  };

  const copyChecklist = async () => {
    const text = `${name}: documents\n${docs.map((d) => `${ready(d.id) ? "[x]" : "[ ]"} ${d.name}`).join("\n")}${url ? `\nApply at: ${url}` : ""}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  };

  // Demo: rebuild the template draft each time it opens, so it never lists stale document states.
  const toggleMail = () => {
    if (!mailOpen && !live.active) {
      const d = draftEmail(name, url, docs, ready);
      setSubject(d.subject);
      setBody(d.body);
    }
    setMailOpen((v) => !v);
  };
  const generate = async () => {
    setBusy(true);
    setNote("");
    try {
      const a = await live.email(id, question);
      setSubject(a.subject ?? a.title);
      setBody(a.body_content);
      setMailMeta({ to: a.target_destination, by: a.generated_by, warnings: a.warnings });
      if (a.status === "needs_input") setNote(a.instructions);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "The draft couldn't be created.");
    } finally {
      setBusy(false);
    }
  };
  const mailto = `mailto:${mailMeta?.to ?? ""}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  const copyMail = async () => {
    try {
      await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
      setMailCopied(true);
      window.setTimeout(() => setMailCopied(false), 2000);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  };

  const choose = (v: ApplyStage) => {
    setStage(v);
    if (live.active) void live.progress(id, STAGE_UPDATES[v]).then(setProgress).catch(() => undefined);
  };

  return (
    <article id={`next-${id}`} className="card nx" style={{ scrollMarginTop: 96 }}>
      <div className="row-between" style={{ gap: 12, alignItems: "flex-start" }}>
        <h3 className="serif" style={{ fontSize: 22, lineHeight: 1.05 }}>{name}</h3>
        <span className={docs.length > 0 && allReady ? "nx-badge ok" : "nx-badge"}>
          {docs.length === 0 ? "No confirmed documents" : allReady ? "Documents ready" : `${missing.length} ${missing.length === 1 ? "document" : "documents"} to go`}
        </span>
      </div>

      <ul className="nx-docs">
        {docs.map((d) => (
          <li key={d.id} className={ready(d.id) ? "on" : ""}>
            {ready(d.id) ? <Check size={13} strokeWidth={2.6} aria-hidden /> : <i aria-hidden />}
            {d.name}
          </li>
        ))}
      </ul>

      <div className="nx-actions">
        {url ? (
          <a className={allReady && docs.length > 0 ? "btn" : "btn-ghost"} href={url} target="_blank" rel="noopener noreferrer">
            Open official application page
            {allReady && docs.length > 0 && <ArrowChip />}
          </a>
        ) : (
          <span style={{ fontSize: 13, color: "var(--faint)" }}>No official application page was found for this scheme.</span>
        )}
        {!allReady && <span style={{ fontSize: 13, color: "var(--faint)" }}>Still needed: {missing.map((d) => d.name).join(", ")}</span>}
      </div>

      <div className="nx-row">
        <label htmlFor={`d-${id}`} style={{ fontSize: 13, color: "var(--muted)" }}>Remind me on</label>
        <input id={`d-${id}`} className="inp" type="date" min={today()} value={date} onChange={(e) => setDate(e.target.value)} />
        <button className="btn-ghost nx-sm" onClick={remind} disabled={!date}>
          <CalendarPlus size={15} aria-hidden /> Add to calendar
        </button>
        <button className="btn-ghost nx-sm" onClick={copyChecklist}>
          {copied ? <Check size={15} aria-hidden /> : <ClipboardCopy size={15} aria-hidden />} {copied ? "Copied" : "Copy checklist"}
        </button>
        <button className="btn-ghost nx-sm" onClick={toggleMail} aria-expanded={mailOpen}>
          <Mail size={15} aria-hidden /> {mailOpen ? "Hide email draft" : "Draft email"}
        </button>
        {live.active && (
          <button className="btn-ghost nx-sm" onClick={() => { live.select(id); navigate("/office-chat"); }}>
            <MessageCircle size={15} aria-hidden /> Try an office chat (simulated)
          </button>
        )}
      </div>
      {note && <p role="status" style={{ fontSize: 13, color: "var(--warn-text)" }}>{note}</p>}

      {mailOpen && (
        <div className="nx-mail pop">
          {live.active && (
            <>
              <label htmlFor={`q-${id}`} className="label">WHAT DO YOU WANT TO ASK?</label>
              <textarea id={`q-${id}`} className="inp" rows={3} value={question} maxLength={2000} onChange={(e) => setQuestion(e.target.value)} />
              <div className="nx-row">
                <button className="btn nx-sm" onClick={generate} disabled={busy || question.trim() === ""}>{busy ? "Writing…" : body ? "Write it again" : "Write the draft"}</button>
              </div>
            </>
          )}
          {(!live.active || body) && (
            <>
              <label htmlFor={`s-${id}`} className="label">SUBJECT</label>
              <input id={`s-${id}`} className="inp" value={subject} onChange={(e) => setSubject(e.target.value)} />
              <label htmlFor={`b-${id}`} className="label">MESSAGE</label>
              <textarea id={`b-${id}`} className="inp" rows={14} value={body} onChange={(e) => setBody(e.target.value)} />
              <p style={{ fontSize: 13, color: "var(--faint)" }}>
                {mailMeta
                  ? `${mailMeta.by === "llm" ? "AI-assisted draft" : "Template draft"}. We don't send it. ${mailMeta.to ? `Official address: ${mailMeta.to}.` : "We don't know a confirmed address for this office, so add it in your email app."} Review it and fill in any placeholders, such as [Your name] or {{Name}}, before sending.`
                  : "Draft only. We don't send it and don't know the office's address, so add it in your email app. It includes no personal answers; replace [Your name] before sending."}
              </p>
              {mailMeta?.warnings.map((w) => <p key={w} style={{ fontSize: 13, color: "var(--warn-text)" }}>{w}</p>)}
              <div className="nx-row">
                <a className="btn nx-sm" href={mailto}>Open in my email app <ArrowChip /></a>
                <button className="btn-ghost nx-sm" onClick={copyMail}>
                  {mailCopied ? <Check size={15} aria-hidden /> : <ClipboardCopy size={15} aria-hidden />} {mailCopied ? "Copied" : "Copy draft"}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <div className="stack" style={{ gap: 8, paddingTop: 14, borderTop: "1px solid var(--line-2)" }}>
        <span className="label">YOUR APPLICATION PROGRESS (SELF-REPORTED)</span>
        <div className="segc nx-seg" role="group" aria-label={`Application progress for ${name}`}>
          {APPLY_STAGES.map(([v, label]) => (
            <button key={v} data-stage={v} className={stage === v ? "on" : ""} aria-pressed={stage === v} onClick={() => choose(v)}>
              {STAGE_ICON[v]}
              {label}
            </button>
          ))}
        </div>
        {progress && (
          <p style={{ fontSize: 13, color: "var(--muted)" }}>
            {progress.summary}
            {progress.warnings.map((w) => <span key={w} style={{ display: "block", color: "var(--warn-text)" }}>{w}</span>)}
          </p>
        )}
      </div>
    </article>
  );
}
