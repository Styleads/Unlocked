import { useState } from "react";
import { ChevronDown, FileText, PartyPopper } from "lucide-react";
import { Disclaimer, FlowHeader, SourceLink } from "../ui";
import { useSession } from "../session";
import { PLAN_DOCS } from "../data";
import type { DocStatus } from "../data";
import NextSteps from "./NextSteps";
import DepGraph from "./DepGraph";

const CHOICES: [DocStatus, string][] = [["needed", "Needed"], ["have", "I have it"], ["obtained", "Obtained"]];

export default function Plan() {
  const { session, update } = useSession();
  const [hover, setHover] = useState<string | null>(null);
  const st = session.docStatus;
  const isReady = (id: string) => st[id] === "have" || st[id] === "obtained";
  const setSt = (id: string, v: DocStatus) => update((s) => ({ docStatus: { ...s.docStatus, [id]: v } }));
  const ready = PLAN_DOCS.filter((d) => isReady(d.id)).length;
  const allReady = ready === PLAN_DOCS.length;
  // The next document to get: not ready yet, and not waiting on one that isn't ready.
  const nextDoc = PLAN_DOCS.find((d) => {
    if (isReady(d.id)) return false;
    const pre = d.after ? PLAN_DOCS.find((p) => p.name === d.after) : undefined;
    return !pre || isReady(pre.id);
  });

  return (
    <div className="page">
      <FlowHeader current={4} />
      <main className="main wide" style={{ paddingBottom: 72 }}>
        <div className="row-between" style={{ alignItems: "flex-end", gap: 24 }}>
          <div className="stack" style={{ gap: 14, maxWidth: 720 }}>
            <span className="eyebrow rise">_ Step 4 of 4 · Document plan</span>
            <h1 className="serif display rise d1">Your document plan.</h1>
            <p className="lede rise d2" style={{ textWrap: "pretty" }}>
              Five documents cover the three schemes you can act on now. Start with the Income Certificate, and get your Domicile Certificate before the Caste Certificate, which depends on it.
            </p>
          </div>
          <div className="stack rise d2" style={{ minWidth: 260, gap: 10 }}>
            <span className="serif" style={{ fontSize: 29, lineHeight: 1 }}>
              {ready} <span style={{ color: "var(--faintest)" }}>of {PLAN_DOCS.length} ready</span>
            </span>
            <div style={{ display: "flex", gap: 4 }} aria-hidden>
              {PLAN_DOCS.map((d) => <span key={d.id} className={isReady(d.id) ? "plan-pip on" : "plan-pip hatch"} />)}
            </div>
          </div>
        </div>

        <div className="rise d3" style={{ display: "flex", alignItems: "center", gap: 16, padding: "18px 20px", borderRadius: 22, background: "var(--primary)", color: "var(--on-accent)", flexWrap: "wrap", boxShadow: "var(--shadow-sm)" }}>
          <span className="callout-icon" style={{ width: 42, height: 42 }}>{allReady ? <PartyPopper size={18} aria-hidden /> : <FileText size={18} aria-hidden />}</span>
          <span style={{ flex: "1 1 300px", fontSize: 17 }}>
            {allReady ? (
              <><strong style={{ fontWeight: 600 }}>All your documents are ready.</strong> You can apply for each scheme on its official page.</>
            ) : nextDoc ? (
              <><strong style={{ fontWeight: 600 }}>Get your {nextDoc.name} next.</strong> It's needed for {nextDoc.for.length} {nextDoc.for.length === 1 ? "scheme" : "schemes"}: {nextDoc.for.join(" and ")}.</>
            ) : (
              <><strong style={{ fontWeight: 600 }}>Finish the documents marked "Needed".</strong> Some wait on another document first.</>
            )}
          </span>
          <a className="btn-ghost" href="#next" style={{ background: "var(--surface)", color: "var(--text)" }}>{allReady ? "Start applying" : "Jump to next steps"}</a>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "flex-start" }}>
          <ol style={{ flex: "999 1 520px", minWidth: 0, margin: 0, padding: 0, listStyle: "none", display: "grid", gridAutoRows: "1fr", gap: 10 }}>
            {PLAN_DOCS.map((d, i) => {
              const cur = st[d.id] ?? "needed";
              const r = isReady(d.id);
              return (
                <li key={d.id} className={`item rise d${i + 3} ${r ? "ready" : ""}`} onMouseEnter={() => setHover(d.id)} onMouseLeave={() => setHover(null)}>
                  <span className={r ? "num ready" : "num"}>{String(i + 1).padStart(2, "0")}</span>
                  <div className="item-main">
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <h2 className="serif" style={{ fontSize: 21, lineHeight: 1.05 }}>{d.name}</h2>
                      {d.shared && <span className="shared">SHARED</span>}
                    </div>
                    <p style={{ fontSize: 14, color: "var(--muted)" }}>{d.reason}</p>
                    <div className="item-meta">
                      <span className="item-label">FOR</span>
                      {d.for.map((s) => <span key={s} className="for-chip">{s}</span>)}
                      {d.after && <span className="after-chip">after {d.after}</span>}
                      <SourceLink href={d.url}>Official source</SourceLink>
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
              <DepGraph isReady={isReady} hover={hover} setHover={setHover} />
              <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 13, color: "var(--muted)", paddingTop: 12, borderTop: "1px solid var(--line-2)" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><i style={{ width: 18, height: 2, background: "var(--primary)" }} />Shared document</span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><i className="legend-dot" style={{ background: "var(--primary-dark)" }} />Ready</span>
              </div>
            </div>

            <details className="notes" style={{ background: "var(--surface)", border: "1px solid var(--line-2)", borderRadius: 22, padding: "6px 20px" }}>
              <summary>Notes<ChevronDown size={16} className="chev" aria-hidden /></summary>
              <div className="stack" style={{ gap: 10, padding: "4px 0 18px", fontSize: 14, color: "var(--muted)" }}>
                <span>Certificate validity periods vary by issuing office. Check the date before you apply.</span>
                <span><span style={{ color: "var(--faint)" }}>Not included:</span> Demo Pension E's documents, since that scheme is unlikely to match.</span>
              </div>
            </details>
          </aside>
        </div>

        <NextSteps />
      </main>
      <Disclaimer />
    </div>
  );
}
