import { useState } from "react";
import type { ReactNode } from "react";
import { ArrowRight, Check, CircleAlert, X, ShieldCheck } from "lucide-react";
import { ArrowChip, BackLink, Disclaimer, FlowHeader, OutcomeSourceBadge, SourceLink, StatusBadge } from "../ui";
import { Link } from "../router";
import { useSession } from "../session";
import { INCOME_WITHIN_LIMIT, QUESTIONS } from "../data";

const NOTICE = "https://example.gov.in/scholarship-a/notice";
const INCOME_Q = QUESTIONS.find((q) => q.id === "income")!;

const EXPLANATION = {
  info: "Your course and domicile meet the rules. We still need your family income to check the income limit.",
  ok: "Your answers appear to meet all three criteria we checked.",
  warn: "Your family income appears to be above the limit stated in the notice.",
};
const DONE_TITLE = { ok: "Now a potential match.", warn: "Now unlikely to match.", info: "Still needs your income." };

const STEPS = [
  "Create an account on the official scholarship portal.",
  "Fill in the application and upload your documents.",
  "Submit it for verification by your institution.",
  "Track your application status on the portal.",
];

export default function Scheme() {
  const { session, update } = useSession();
  const income = session.answers.income;
  // Shares the income answer with the Questions step, so answering in either place counts.
  const [stage, setStage] = useState<"idle" | "ask" | "done">(income !== undefined ? "done" : "idle");

  const status: "ok" | "warn" | "info" =
    income === undefined || income === "__unsure" || income === "__prefer" ? "info" : INCOME_WITHIN_LIMIT.has(income) ? "ok" : "warn";
  const answerLabel = income === "__unsure" ? "Not sure" : income === "__prefer" ? "Prefer not to say" : income ?? "";
  const answer = (v: string) => {
    update((s) => ({ answers: { ...s.answers, income: v } }));
    setStage("done");
  };

  const incomeReason =
    status === "ok" ? "Your bracket is within the stated limit."
    : status === "warn" ? "Your bracket is above the stated limit."
    : income === "__unsure" ? "You marked this as not sure. That's fine."
    : income === "__prefer" ? "You chose to keep this private."
    : "You haven't answered this yet.";

  return (
    <div className="page">
      <FlowHeader current={3} />
      <main className="main wide" style={{ paddingTop: 36, paddingBottom: 72 }}>
        <div style={{ alignSelf: "flex-start" }}><BackLink to="/results">Back to results</BackLink></div>

        <div className="stack" style={{ gap: 16 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span className="eyebrow rise">STATE SCHEME · DEPT. OF COLLEGIATE EDUCATION (DEMO)</span>
            <OutcomeSourceBadge type="verified" label="Official Government Scheme" />
            <span className="mono" style={{ fontSize: 11, color: "var(--faintest)" }}>Last verified: Oct 2026</span>
          </div>
          <div className="row-between" style={{ alignItems: "flex-end", gap: 20 }}>
            <h1 className="serif rise d1" style={{ fontSize: "clamp(52px, 6.4vw, 96px)", lineHeight: 0.95 }}>Demo Scholarship A</h1>
            <div className="rise d2" aria-live="polite">
              <StatusBadge key={status} status={status} large className="pop" />
            </div>
          </div>
        </div>

        {/* Claim lifecycle progression (plan.md section 2.6) */}
        <div className="rise d2 stack" style={{ gap: 8 }}>
          <span className="label">CLAIM LIFECYCLE STAGES</span>
          <div className="claim-lifecycle">
            <div className="claim-stage-item current">
              <ShieldCheck size={16} aria-hidden />
              <span>1. Potential eligibility assessed</span>
            </div>
            <div className="claim-stage-item pending">
              <span>2. Application submitted by you</span>
            </div>
            <div className="claim-stage-item pending">
              <span>3. Approved by authority</span>
            </div>
            <div className="claim-stage-item pending">
              <span>4. Benefit received</span>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 40, alignItems: "flex-start" }}>
          <div className="stack" style={{ flex: "999 1 640px", minWidth: 0 }}>
            <Section n="01" title="Why this status" className="rise d2">
              <p style={{ fontSize: 18, color: "var(--text-2)", textWrap: "pretty" }}>{EXPLANATION[status]}</p>
            </Section>

            <Section n="02" title="Criteria" className="rise d3">
              <Criterion rule="“Must be enrolled in an undergraduate degree course.”" result={<MeetsChip />} reason="You said you're studying for an undergraduate degree." clause={2} />
              <Criterion rule="“Applicant must be a resident of Karnataka.”" result={<MeetsChip />} reason="You said you have Karnataka domicile." clause={3} />
              <Criterion
                rule="“Annual family income up to ₹2.5 lakh.”"
                result={
                  status === "ok" ? <MeetsChip key="ok" />
                  : status === "warn" ? <span key="no" className="rchip r-no pop"><X size={14} strokeWidth={2.4} aria-hidden />Doesn't appear to meet</span>
                  : <span key="unk" className="rchip r-unk hatch pop">? Not answered yet</span>
                }
                reason={incomeReason}
                clause={4}
              />
            </Section>

            <Section n="03" title="Benefit">
              <p style={{ fontSize: 17, color: "var(--text-2)" }}>An annual grant toward tuition and books. The exact amount is set in each year's notice.</p>
            </Section>

            <Section n="04" title="Documents" gap={0}>
              <div className="list-row"><span style={{ fontSize: 16 }}>Income Certificate</span><a className="src" href={NOTICE} target="_blank" rel="noopener noreferrer">Source</a></div>
              <div className="list-row"><span style={{ fontSize: 16 }}>Admission Letter</span><a className="src" href={NOTICE} target="_blank" rel="noopener noreferrer">Source</a></div>
              <div className="list-row"><span style={{ fontSize: 16 }}>Bank account details</span><span className="unsrc">SOURCE NOT CONFIRMED</span></div>
            </Section>

            <Section n="05" title="How to apply">
              <ol className="stack" style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {STEPS.map((t, i) => (
                  <li key={t} style={{ display: "flex", gap: 16, alignItems: "baseline", padding: "12px 0", borderBottom: i < STEPS.length - 1 ? "1px solid var(--line-2)" : 0 }}>
                    <span className="mono" style={{ fontSize: 13, color: "var(--primary-dark)", fontWeight: 600 }}>{String(i + 1).padStart(2, "0")}</span>
                    <span style={{ color: "var(--text-2)" }}>{t}</span>
                  </li>
                ))}
              </ol>
              <a className="btn" href="https://example.gov.in/scholarship-a/apply" target="_blank" rel="noopener noreferrer" style={{ alignSelf: "flex-start" }}>
                Open official application page
                <ArrowChip />
              </a>
            </Section>

            <Section n="06" title="Official sources" gap={4}>
              <SourceLink href="https://example.gov.in/scholarship-a">example.gov.in/scholarship-a</SourceLink>
              <SourceLink href={NOTICE}>example.gov.in/scholarship-a/notice</SourceLink>
            </Section>

            <Section n="07" title="Uncertainties">
              <div className="hatch" style={{ padding: "18px 20px", borderRadius: 20, border: "1px solid var(--line-3)", display: "flex", gap: 12, alignItems: "flex-start" }}>
                <CircleAlert size={20} color="var(--secondary-dark)" aria-hidden style={{ flex: "none", marginTop: 2 }} />
                <span style={{ fontSize: 15, background: "var(--surface)", padding: "4px 8px", borderRadius: 8, border: "1px solid var(--line-2)" }}>
                  The notice doesn't say whether diploma courses count as undergraduate.
                </span>
              </div>
            </Section>
          </div>

          <aside className="stack rise d3" style={{ flex: "1 1 340px", gap: 14 }}>
            <div className="card stack" style={{ padding: 24, gap: 16 }}>
              {stage === "idle" && (
                <>
                  <span className="label">1 QUESTION LEFT</span>
                  <span className="serif" style={{ fontSize: 30, lineHeight: 1.05 }}>Check this scheme against your income.</span>
                  <span style={{ fontSize: 15, color: "var(--muted)" }}>It's the only criterion we couldn't check yet.</span>
                  <button className="btn" onClick={() => setStage("ask")} style={{ alignSelf: "flex-start" }}>
                    Check my eligibility
                    <ArrowChip />
                  </button>
                </>
              )}
              {stage === "ask" && (
                <div className="pop stack" style={{ gap: 14 }}>
                  <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>Q1</span>
                    <span className="sens">SENSITIVE · YOU CAN SKIP THIS</span>
                  </span>
                  <span className="serif" style={{ fontSize: 28, lineHeight: 1.1 }}>{INCOME_Q.text}</span>
                  <span style={{ fontSize: 14, color: "var(--faint)" }}>We only keep the bracket, never an exact figure.</span>
                  <div role="group" aria-label="Income bracket" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {INCOME_Q.opts.map((o) => (
                      <button key={o} className={income === o ? "opt sm on" : "opt sm"} aria-pressed={income === o} onClick={() => answer(o)}>{o}</button>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
                    <button className="text-link" onClick={() => answer("__unsure")}>Not sure</button>
                    <button className="text-link" onClick={() => answer("__prefer")}>Prefer not to say</button>
                  </div>
                </div>
              )}
              {stage === "done" && (
                <div className="pop stack" style={{ gap: 12 }}>
                  <span className="label">ASSESSMENT UPDATED</span>
                  <span className="serif" style={{ fontSize: 30, lineHeight: 1.05 }}>{DONE_TITLE[status]}</span>
                  <span style={{ fontSize: 15, color: "var(--muted)" }}>Your answer: {answerLabel}</span>
                  <button className="text-link" onClick={() => setStage("ask")} style={{ alignSelf: "flex-start" }}>Change answer</button>
                </div>
              )}
            </div>
            <Link to="/plan" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "20px 22px", borderRadius: 22, border: "1px solid var(--line-2)", textDecoration: "none", color: "var(--text)", background: "var(--surface)", boxShadow: "var(--shadow-sm)" }}>
              <span className="stack" style={{ gap: 2 }}>
                <span style={{ fontSize: 15, fontWeight: 600 }}>See it in your document plan</span>
                <span style={{ fontSize: 14, color: "var(--faint)" }}>3 documents, 2 shared with other schemes</span>
              </span>
              <ArrowRight size={18} color="var(--primary-dark)" aria-hidden />
            </Link>
          </aside>
        </div>
      </main>
      <Disclaimer />
    </div>
  );
}

function Section({ n, title, gap, className = "", children }: { n: string; title: string; gap?: number; className?: string; children: ReactNode }) {
  return (
    <section className={`sec ${className}`}>
      <div className="sec-h">
        <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>_{n}</span>
        <h2 className="serif">{title}</h2>
      </div>
      <div className="sec-b" style={gap !== undefined ? { gap } : undefined}>{children}</div>
    </section>
  );
}

function MeetsChip() {
  return <span className="rchip r-ok pop"><Check size={14} strokeWidth={2.4} aria-hidden />Meets</span>;
}

function Criterion({ rule, result, reason, clause }: { rule: string; result: ReactNode; reason: string; clause: number }) {
  return (
    <div className="crit">
      <div className="row-between" style={{ gap: 12, alignItems: "flex-start" }}>
        <span style={{ fontSize: 16 }}>{rule}</span>
        {result}
      </div>
      <span style={{ fontSize: 14, color: "var(--faint)" }}>{reason}</span>
      <SourceLink href={NOTICE}>example.gov.in · notice, clause {clause}</SourceLink>
    </div>
  );
}
