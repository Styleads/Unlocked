import { useEffect, useMemo, useState } from "react";
import { ChevronDown, FileText, PartyPopper } from "lucide-react";
import { Disclaimer, FlowHeader, SourceLink } from "../ui";
import { useSession } from "../session";
import { useLive } from "../live";
import { planFromApi, planFromDemo } from "../model";
import type { DocStatus } from "../data";
import NextSteps from "./NextSteps";
import EmailMe from "./EmailMe";
import AfterAppointment from "./AfterAppointment";
import DepGraph from "./DepGraph";

const CHOICES: [DocStatus, string][] = [["needed", "Needed"], ["have", "I have it"], ["obtained", "Obtained"]];

export default function Plan() {
  const { session, update } = useSession();
  const live = useLive();
  const [hover, setHover] = useState<string | null>(null);
  const [loadError, setLoadError] = useState("");

  // With a backend the plan is computed there (and recomputed when a document's status changes).
  const { active, plan: livePlan, loadPlan } = live;
  useEffect(() => {
    if (!active || livePlan) return;
    setLoadError("");
    loadPlan().catch((e) => setLoadError(e instanceof Error ? e.message : "The plan couldn't be loaded."));
  }, [active, livePlan, loadPlan]);

  const plan = useMemo(
    () => (active ? (livePlan ? planFromApi(livePlan) : null) : planFromDemo(session.docStatus)),
    [active, livePlan, session.docStatus],
  );

  if (!plan) {
    return (
      <div className="page">
        <FlowHeader current={4} />
        <main className="main wide" style={{ paddingBottom: 72 }}>
          <div className="stack" style={{ gap: 14, maxWidth: 720 }}>
            <span className="eyebrow rise">_ Step 4 of 4 · Document plan</span>
            <h1 className="serif display rise d1">{loadError ? "We couldn't build your plan." : "Building your plan…"}</h1>
            <p className="lede rise d2">{loadError || "Working out which documents you need, and in what order."}</p>
            {loadError && <button className="btn-ghost" style={{ alignSelf: "flex-start" }} onClick={() => live.loadPlan().catch((e) => setLoadError(e instanceof Error ? e.message : "Try again."))}>Try again</button>}
          </div>
        </main>
        <Disclaimer />
      </div>
    );
  }

  const isReady = (id: string) => {
    const s = plan.docs.find((d) => d.id === id)?.status;
    return s === "have" || s === "obtained";
  };
  const setSt = (id: string, v: DocStatus) => {
    if (active) void live.setDoc(id, v).catch(() => undefined);
    else update((s) => ({ docStatus: { ...s.docStatus, [id]: v } }));
  };
  const docs = plan.docs;
  const ready = docs.filter((d) => isReady(d.id)).length;
  const allReady = docs.length > 0 && ready === docs.length;
  // The next document to get: not ready yet, and not waiting on one that isn't ready.
  const nextDoc = docs.find((d) => !isReady(d.id) && d.after.every((n) => isReady(docs.find((p) => p.name === n)?.id ?? "")));
  const lede = plan.explanation || `${docs.length} documents cover the ${plan.schemes.length} schemes you can act on now.`;

  return (
    <div className="page">
      <FlowHeader current={4} />
      <main className="main wide" style={{ paddingBottom: 72 }}>
        <AfterAppointment />
        <div className="row-between" style={{ alignItems: "flex-end", gap: 24 }}>
          <div className="stack" style={{ gap: 14, maxWidth: 720 }}>
            <span className="eyebrow rise">_ Step 4 of 4 · Document plan</span>
            <h1 className="serif display rise d1">Your document plan.</h1>
            <p className="lede rise d2" style={{ textWrap: "pretty" }}>{lede}</p>
          </div>
          <div className="stack rise d2" style={{ minWidth: 260, gap: 10 }}>
            <span className="serif" style={{ fontSize: 29, lineHeight: 1 }}>
              {ready} <span style={{ color: "var(--faintest)" }}>of {docs.length} ready</span>
            </span>
            <div style={{ display: "flex", gap: 4 }} aria-hidden>
              {docs.map((d) => <span key={d.id} className={isReady(d.id) ? "plan-pip on" : "plan-pip hatch"} />)}
            </div>
          </div>
        </div>

        {docs.length === 0 ? (
          <div className="card" style={{ padding: 24 }}>
            <strong style={{ fontWeight: 600 }}>No documents to plan yet.</strong>{" "}
            <span style={{ color: "var(--muted)" }}>None of the schemes we found has a document list we could confirm from an official source.</span>
          </div>
        ) : (
          <div className="rise d3" style={{ display: "flex", alignItems: "center", gap: 16, padding: "18px 20px", borderRadius: 22, background: "var(--primary)", color: "var(--on-accent)", flexWrap: "wrap", boxShadow: "var(--shadow-sm)" }}>
            <span className="callout-icon" style={{ width: 42, height: 42 }}>{allReady ? <PartyPopper size={18} aria-hidden /> : <FileText size={18} aria-hidden />}</span>
            <span style={{ flex: "1 1 300px", fontSize: 17 }}>
              {allReady ? (
                <><strong style={{ fontWeight: 600 }}>All your documents are ready.</strong> You can apply for each scheme on its official page.</>
              ) : nextDoc ? (
                <><strong style={{ fontWeight: 600 }}>Get your {nextDoc.name} next.</strong> It's needed for {nextDoc.forNames.length} {nextDoc.forNames.length === 1 ? "scheme" : "schemes"}: {nextDoc.forNames.join(" and ")}.</>
              ) : (
                <><strong style={{ fontWeight: 600 }}>Finish the documents marked "Needed".</strong> Some wait on another document first.</>
              )}
            </span>
            <a className="btn-ghost" href="#next" style={{ background: "var(--surface)", color: "var(--text)" }}>{allReady ? "Start applying" : "Jump to next steps"}</a>
            {active && <a className="btn-ghost" href="#email" style={{ background: "var(--surface)", color: "var(--text)" }}>Email me this plan</a>}
          </div>
        )}

        {docs.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "flex-start" }}>
            <ol style={{ flex: "999 1 520px", minWidth: 0, margin: 0, padding: 0, listStyle: "none", display: "grid", gridAutoRows: "1fr", gap: 10 }}>
              {docs.map((d, i) => {
                const cur = d.status;
                const r = isReady(d.id);
                return (
                  <li key={d.id} className={`item rise d${Math.min(i + 3, 6)} ${r ? "ready" : ""}`} onMouseEnter={() => setHover(d.id)} onMouseLeave={() => setHover(null)}>
                    <span className={r ? "num ready" : "num"}>{String(i + 1).padStart(2, "0")}</span>
                    <div className="item-main">
                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                        <h2 className="serif" style={{ fontSize: 21, lineHeight: 1.05 }}>{d.name}</h2>
                        {d.shared && <span className="shared">SHARED</span>}
                      </div>
                      {d.reason && <p style={{ fontSize: 14, color: "var(--muted)" }}>{d.reason}</p>}
                      <div className="item-meta">
                        <span className="item-label">FOR</span>
                        {d.forNames.map((s) => <span key={s} className="for-chip">{s}</span>)}
                        {d.after.map((n) => <span key={n} className="after-chip">after {n}</span>)}
                        {d.url && <SourceLink href={d.url}>Official source</SourceLink>}
                      </div>
                    </div>
                    <div className="segc item-seg" role="group" aria-label={`Status of ${d.name}`}>
                      {CHOICES.map(([v, label]) => (
                        <button key={v} className={cur === v ? (v === "needed" ? "on" : "on lime") : ""} aria-pressed={cur === v} onClick={() => setSt(d.id, v)}>
                          {label}
                        </button>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ol>

            <aside className="stack rise d4 plan-aside" style={{ flex: "0 1 520px", minWidth: 0, gap: 12 }}>
              <div className="card stack" style={{ padding: 24, gap: 18 }}>
                <div className="row-between" style={{ gap: 12 }}>
                  <span style={{ fontSize: 16, fontWeight: 600 }}>What each document unlocks</span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--faint)" }}>HOVER · CLICK A SCHEME</span>
                </div>
                <DepGraph plan={plan} isReady={isReady} hover={hover} setHover={setHover} />
                <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 13, color: "var(--muted)", paddingTop: 12, borderTop: "1px solid var(--line-2)" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><i style={{ width: 18, height: 2, background: "var(--primary)" }} />Shared document</span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><i className="legend-dot" style={{ background: "var(--primary-dark)" }} />Ready</span>
                </div>
              </div>

              <details className="notes" style={{ background: "var(--surface)", border: "1px solid var(--line-2)", borderRadius: 22, padding: "6px 20px" }}>
                <summary>Notes<ChevronDown size={16} className="chev" aria-hidden /></summary>
                <div className="stack" style={{ gap: 10, padding: "4px 0 18px", fontSize: 14, color: "var(--muted)" }}>
                  <span>Certificate validity periods vary by issuing office. Check the date before you apply.</span>
                  {active
                    ? plan.warnings.map((w) => <span key={w}>{w}</span>)
                    : <span><span style={{ color: "var(--faint)" }}>Not included:</span> Demo Pension E's documents, since that scheme is unlikely to match.</span>}
                </div>
              </details>
            </aside>
          </div>
        )}

        <NextSteps plan={plan} isReady={isReady} />
        <EmailMe />
      </main>
      <Disclaimer />
    </div>
  );
}
