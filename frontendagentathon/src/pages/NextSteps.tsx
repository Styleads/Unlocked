import { useState } from "react";
import { BadgeCheck, CalendarPlus, Check, CircleDashed, ClipboardCopy, Mail, PartyPopper, Send } from "lucide-react";
import type { ReactNode } from "react";
import { ArrowChip } from "../ui";
import { useSession } from "../session";
import { APPLY_STAGES, PLAN_DOCS, PLAN_SCHEME_NODES, SCHEMES } from "../data";
import type { ApplyStage, PlanDoc } from "../data";
import { buildIcs, downloadText } from "../ics";

/** Documents a scheme needs: the ones listed for it, plus any document those must come after. */
function docsFor(schemeName: string): PlanDoc[] {
  const need = new Set(PLAN_DOCS.filter((d) => d.for.includes(schemeName)).map((d) => d.id));
  for (let grew = true; grew; ) {
    grew = false;
    for (const d of PLAN_DOCS) {
      const pre = need.has(d.id) && d.after ? PLAN_DOCS.find((p) => p.name === d.after) : undefined;
      if (pre && !need.has(pre.id)) { need.add(pre.id); grew = true; }
    }
  }
  return PLAN_DOCS.filter((d) => need.has(d.id));
}

/** One icon and colour per application condition, so the state reads at a glance. */
const STAGE_ICON: Record<ApplyStage, ReactNode> = {
  todo: <CircleDashed size={14} aria-hidden />,
  submitted: <Send size={14} aria-hidden />,
  approved: <BadgeCheck size={14} aria-hidden />,
  received: <PartyPopper size={14} aria-hidden />,
};

const today = () => new Date().toISOString().slice(0, 10);

/**
 * A plain enquiry to the scheme's office. It uses only what the plan already shows (scheme, documents, official page):
 * no answers or personal details, no invented contact address or deadline. The user reviews it and presses send themselves.
 */
function draftEmail(name: string, url: string, docs: PlanDoc[], isReady: (id: string) => boolean) {
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
    `The official page I referred to: ${url}`,
    "",
    "Thank you for your time.",
    "",
    "Regards,",
    "[Your name]",
  ].join("\n");
  return { subject: `Query about applying for ${name}`, body };
}

/** What happens after the document plan: apply, remind yourself, and record how the application goes. */
export default function NextSteps() {
  const { session, update } = useSession();
  const isReady = (id: string) => session.docStatus[id] === "have" || session.docStatus[id] === "obtained";

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
        {PLAN_SCHEME_NODES.map((n) => {
          const scheme = SCHEMES.find((s) => s.id === n.id)!;
          const docs = docsFor(n.label);
          const missing = docs.filter((d) => !isReady(d.id));
          const stage = session.apply[n.id] ?? "todo";
          return (
            <SchemeStep
              key={n.id}
              id={n.id}
              name={n.label}
              url={scheme.url}
              docs={docs}
              ready={isReady}
              missing={missing}
              stage={stage}
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
  id: string; name: string; url: string; docs: PlanDoc[]; ready: (id: string) => boolean; missing: PlanDoc[];
  stage: ApplyStage; setStage: (s: ApplyStage) => void;
}) {
  const [date, setDate] = useState("");
  const [copied, setCopied] = useState(false);
  const [mailOpen, setMailOpen] = useState(false);
  const [mailCopied, setMailCopied] = useState(false);
  const initial = draftEmail(name, url, docs, ready);
  const [subject, setSubject] = useState(initial.subject);
  const [body, setBody] = useState(initial.body);
  const allReady = missing.length === 0;

  // Rebuild the draft from the current plan each time it is opened, so it never lists stale document states.
  const toggleMail = () => {
    if (!mailOpen) {
      const d = draftEmail(name, url, docs, ready);
      setSubject(d.subject);
      setBody(d.body);
    }
    setMailOpen((v) => !v);
  };
  const mailto = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  const copyMail = async () => {
    try {
      await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
      setMailCopied(true);
      window.setTimeout(() => setMailCopied(false), 2000);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  };

  const remind = () => {
    if (!date) return;
    downloadText(
      `${name.replace(/\s+/g, "-").toLowerCase()}-reminder.ics`,
      buildIcs({
        title: `Apply: ${name}`,
        isoDate: date,
        description: `Apply on the official page. Documents: ${docs.map((d) => d.name).join(", ")}. This is your own reminder; the date was set by you.`,
        url,
      }),
    );
  };

  const copyChecklist = async () => {
    const text = `${name}: documents\n${docs.map((d) => `${ready(d.id) ? "[x]" : "[ ]"} ${d.name}`).join("\n")}\nApply at: ${url}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  };

  return (
    <article id={`next-${id}`} className="card nx" style={{ scrollMarginTop: 96 }}>
      <div className="row-between" style={{ gap: 12, alignItems: "flex-start" }}>
        <h3 className="serif" style={{ fontSize: 22, lineHeight: 1.05 }}>{name}</h3>
        <span className={allReady ? "nx-badge ok" : "nx-badge"}>
          {allReady ? "Documents ready" : `${missing.length} ${missing.length === 1 ? "document" : "documents"} to go`}
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
        <a className={allReady ? "btn" : "btn-ghost"} href={url} target="_blank" rel="noopener noreferrer">
          Open official application page
          {allReady && <ArrowChip />}
        </a>
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
      </div>

      {mailOpen && (
        <div className="nx-mail pop">
          <label htmlFor={`s-${id}`} className="label">SUBJECT</label>
          <input id={`s-${id}`} className="inp" value={subject} onChange={(e) => setSubject(e.target.value)} />
          <label htmlFor={`b-${id}`} className="label">MESSAGE</label>
          <textarea id={`b-${id}`} className="inp" rows={14} value={body} onChange={(e) => setBody(e.target.value)} />
          <p style={{ fontSize: 13, color: "var(--faint)" }}>
            Draft only. We don't send it and don't know the office's address, so add it in your email app. It includes no personal answers; replace [Your name] before sending.
          </p>
          <div className="nx-row">
            <a className="btn nx-sm" href={mailto}>Open in my email app <ArrowChip /></a>
            <button className="btn-ghost nx-sm" onClick={copyMail}>
              {mailCopied ? <Check size={15} aria-hidden /> : <ClipboardCopy size={15} aria-hidden />} {mailCopied ? "Copied" : "Copy draft"}
            </button>
          </div>
        </div>
      )}

      <div className="stack" style={{ gap: 8, paddingTop: 14, borderTop: "1px solid var(--line-2)" }}>
        <span className="label">YOUR APPLICATION PROGRESS (SELF-REPORTED)</span>
        <div className="segc nx-seg" role="group" aria-label={`Application progress for ${name}`}>
          {APPLY_STAGES.map(([v, label]) => (
            <button key={v} data-stage={v} className={stage === v ? "on" : ""} aria-pressed={stage === v} onClick={() => setStage(v)}>
              {STAGE_ICON[v]}
              {label}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}
