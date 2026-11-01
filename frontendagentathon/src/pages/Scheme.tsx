import { useState } from "react";
import { useLive } from "../live";
import { fromApiScheme } from "../model";
import type { ApiRequirement } from "../api";
import type { ReactNode } from "react";
import { ArrowRight, Check, CircleAlert, X, ShieldCheck } from "lucide-react";
import { ArrowChip, BackLink, Disclaimer, FlowHeader, OutcomeSourceBadge, SourceLink, StatusBadge } from "../ui";
import { Link } from "../router";
import { useSession } from "../session";
import { QUESTIONS, SCHEMES } from "../data";
import { evaluateScheme } from "../eligibility";
import type { Evaluated } from "../eligibility";

const NOTICE = "https://example.gov.in/scholarship-a/notice";
const INCOME_Q = QUESTIONS.find((q) => q.id === "income")!;

const SCHEME_A = SCHEMES.find((s) => s.id === "a")!;

const RESULT_REASON: Record<string, string> = {
  ok: "Your answer meets this rule.",
  no: "Your answer appears not to meet this rule.",
  unanswered: "You haven't answered this yet.",
  not_sure: "You marked this as not sure. That's fine.",
  private: "You chose to keep this private.",
};
const STEPS = [
  "Create an account on the official scholarship portal.",
  "Fill in the application and upload your documents.",
  "Submit it for verification by your institution.",
  "Track your application status on the portal.",
];

function DemoScheme() {
  const { session, update } = useSession();
  const income = session.answers.income;
  // Shares the income answer with the Questions step, so answering in either place counts.
  const [stage, setStage] = useState<"idle" | "ask" | "done">(income !== undefined ? "done" : "idle");

  // Same evaluation as the Results page, so the status and criteria here always match the card there.
  const ev = evaluateScheme(SCHEME_A, session);
  const status = ev.status === "ok" || ev.status === "warn" ? ev.status : "info";
  const incomeEval = ev.criteria.find((e) => e.criterion.id === "income")!;
  const doneTitle = incomeEval.pip === "ok" ? "Income is within the limit." : incomeEval.pip === "no" ? "Income appears above the limit." : "Still needs your income.";
  const answerLabel = income === "__unsure" ? "Not sure" : income === "__prefer" ? "Prefer not to say" : income ?? "";
  const answer = (v: string) => {
    update((s) => ({ answers: { ...s.answers, income: v } }));
    setStage("done");
  };

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
            <h1 className="serif rise d1" style={{ fontSize: "clamp(36px, 4.6vw, 64px)", lineHeight: 0.95 }}>Demo Scholarship A</h1>
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
              <p style={{ fontSize: 16, color: "var(--text-2)", textWrap: "pretty" }}>{ev.expl}</p>
            </Section>

            <Section n="02" title="Criteria" className="rise d3">
              {ev.criteria.map((e, i) => (
                <Criterion key={e.criterion.id} rule={`“${e.criterion.rule}”`} result={<ResultChip e={e} />} reason={RESULT_REASON[e.pip === "unk" ? (e.cause ?? "unanswered") : e.pip]} clause={i + 2} />
              ))}            </Section>

            <Section n="03" title="Benefit">
              <p style={{ fontSize: 15, color: "var(--text-2)" }}>An annual grant toward tuition and books. The exact amount is set in each year's notice.</p>
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
              <div className="note-box" style={{ padding: "18px 20px", borderRadius: 20, border: "1px solid var(--line-3)", display: "flex", gap: 12, alignItems: "flex-start" }}>
                <CircleAlert size={20} color="var(--secondary-dark)" aria-hidden style={{ flex: "none", marginTop: 2 }} />
                <span style={{ fontSize: 15, lineHeight: 1.5, color: "var(--text-2)" }}>
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
                  <span className="serif" style={{ fontSize: 24, lineHeight: 1.05 }}>Check this scheme against your income.</span>
                  <span style={{ fontSize: 15, color: "var(--muted)" }}>{ev.criteria.some((e) => e.pip === "unk" && e.criterion.id !== "income") ? "Other rules for this scheme also still need answers." : "It's the only criterion we couldn't check yet."}</span>
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
                  <span className="serif" style={{ fontSize: 22, lineHeight: 1.1 }}>{INCOME_Q.text}</span>
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
                  <span className="serif" style={{ fontSize: 24, lineHeight: 1.05 }}>{doneTitle}</span>
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

function ResultChip({ e }: { e: Evaluated }) {
  if (e.pip === "ok") return <MeetsChip />;
  if (e.pip === "no") return <span className="rchip r-no pop"><X size={14} strokeWidth={2.4} aria-hidden />Doesn't appear to meet</span>;
  return <span className="rchip r-unk hatch pop">{e.cause === "unanswered" || !e.cause ? "? Not answered yet" : "? Still unknown"}</span>;
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

export default function Scheme() {
  const live = useLive();
  return live.active ? <LiveScheme /> : <DemoScheme />;
}

const CHIP: Record<ApiRequirement["status"], { cls: string; text: string }> = {
  satisfied: { cls: "rchip r-ok pop", text: "Meets" },
  not_satisfied: { cls: "rchip r-no pop", text: "Doesn't appear to meet" },
  unknown: { cls: "rchip r-unk hatch pop", text: "? Not answered yet" },
  needs_clarification: { cls: "rchip r-unk hatch pop", text: "? Needs clarification" },
  unverified: { cls: "rchip r-unk hatch pop", text: "Not verified yet" },
};

/** A scheme the backend found: every field comes from its official-source record and the current assessment. */
function LiveScheme() {
  const live = useLive();
  const raw = live.schemes.find((s) => s.id === live.selected) ?? live.schemes[0];
  if (!raw) {
    return (
      <div className="page">
        <FlowHeader current={3} />
        <main className="main wide"><BackLink to="/results">Back to results</BackLink><p>No scheme selected.</p></main>
        <Disclaimer />
      </div>
    );
  }
  const vm = fromApiScheme(raw);
  const benefit = typeof raw.benefit === "string" ? raw.benefit : "";
  const unverified = raw.assessment_status === "not_yet_verified";

  return (
    <div className="page">
      <FlowHeader current={3} />
      <main className="main wide" style={{ paddingTop: 36, paddingBottom: 72 }}>
        <div style={{ alignSelf: "flex-start" }}><BackLink to="/results">Back to results</BackLink></div>

        <div className="stack" style={{ gap: 16 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {vm.dept && <span className="eyebrow rise">{vm.dept}</span>}
            <OutcomeSourceBadge type={vm.sourceType} />
          </div>
          <div className="row-between" style={{ alignItems: "flex-end", gap: 20 }}>
            <h1 className="serif rise d1" style={{ fontSize: "clamp(36px, 4.6vw, 64px)", lineHeight: 0.95 }}>{raw.name}</h1>
            <div className="rise d2"><StatusBadge status={vm.status} large /></div>
          </div>
          {raw.summary && <p className="lede rise d2" style={{ maxWidth: 720 }}>{raw.summary}</p>}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 40, alignItems: "flex-start" }}>
          <div className="stack" style={{ flex: "999 1 640px", minWidth: 0 }}>
            <Section n="01" title="Why this status" className="rise d2">
              <p style={{ fontSize: 16, color: "var(--text-2)", textWrap: "pretty" }}>{raw.assessment_explanation}</p>
            </Section>

            <Section n="02" title="Criteria" className="rise d3">
              {raw.requirements.length === 0 && <p style={{ fontSize: 15, color: "var(--muted)" }}>No criteria were found for this scheme.</p>}
              {raw.requirements.map((r) => (
                <div key={r.requirement_id} className="crit">
                  <div className="row-between" style={{ gap: 12, alignItems: "flex-start" }}>
                    <span style={{ fontSize: 16 }}>“{r.criterion}”</span>
                    <span className={CHIP[r.status].cls}>{CHIP[r.status].text}</span>
                  </div>
                  <span style={{ fontSize: 14, color: "var(--faint)" }}>{r.reason}</span>
                  {r.source_url ? <SourceLink href={r.source_url}>{r.source_url.replace(/^https?:\/\//, "")}</SourceLink> : <span className="unsrc">SOURCE NOT CONFIRMED</span>}
                </div>
              ))}
            </Section>

            {benefit && !unverified && (
              <Section n="03" title="Benefit">
                <p style={{ fontSize: 15, color: "var(--text-2)" }}>{benefit}</p>
              </Section>
            )}

            <Section n="04" title="Documents" gap={0}>
              {raw.documents.length === 0 && <p style={{ fontSize: 15, color: "var(--muted)" }}>No document list was confirmed from an official source.</p>}
              {raw.documents.map((d) => (
                <div key={d.name} className="list-row">
                  <span style={{ fontSize: 16 }}>{d.name}</span>
                  {d.source_url ? <a className="src" href={d.source_url} target="_blank" rel="noopener noreferrer">Source</a> : <span className="unsrc">SOURCE NOT CONFIRMED</span>}
                </div>
              ))}
            </Section>

            {raw.application_steps.length > 0 && (
              <Section n="05" title="How to apply">
                <ol className="stack" style={{ margin: 0, padding: 0, listStyle: "none" }}>
                  {raw.application_steps.map((t, i) => (
                    <li key={t} style={{ display: "flex", gap: 16, alignItems: "baseline", padding: "12px 0", borderBottom: i < raw.application_steps.length - 1 ? "1px solid var(--line-2)" : 0 }}>
                      <span className="mono" style={{ fontSize: 13, color: "var(--primary-dark)", fontWeight: 600 }}>{String(i + 1).padStart(2, "0")}</span>
                      <span style={{ color: "var(--text-2)" }}>{t}</span>
                    </li>
                  ))}
                </ol>
                {raw.application_url && (
                  <a className="btn" href={raw.application_url} target="_blank" rel="noopener noreferrer" style={{ alignSelf: "flex-start" }}>
                    Open official application page
                    <ArrowChip />
                  </a>
                )}
              </Section>
            )}

            <Section n="06" title="Official sources" gap={4}>
              {raw.official_sources.length === 0 && <p style={{ fontSize: 15, color: "var(--muted)" }}>No official source was recorded.</p>}
              {raw.official_sources.map((u) => <SourceLink key={u} href={u}>{u.replace(/^https?:\/\//, "")}</SourceLink>)}
            </Section>
          </div>

          <aside className="stack rise d3" style={{ flex: "1 1 340px", gap: 14 }}>
            {vm.missing.length > 0 && (
              <div className="card stack" style={{ padding: 24, gap: 12 }}>
                <span className="label">STILL MISSING</span>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>{vm.missing.map((m) => <span key={m} className="miss">{m}</span>)}</div>
                <Link to="/questions" className="btn" style={{ alignSelf: "flex-start" }}>
                  Answer questions
                  <ArrowChip />
                </Link>
              </div>
            )}
            <Link to="/plan" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "20px 22px", borderRadius: 22, border: "1px solid var(--line-2)", textDecoration: "none", color: "var(--text)", background: "var(--surface)", boxShadow: "var(--shadow-sm)" }}>
              <span className="stack" style={{ gap: 2 }}>
                <span style={{ fontSize: 15, fontWeight: 600 }}>See it in your document plan</span>
                <span style={{ fontSize: 14, color: "var(--faint)" }}>{raw.documents.length} {raw.documents.length === 1 ? "document" : "documents"} listed</span>
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