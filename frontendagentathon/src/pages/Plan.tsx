import { useState } from "react";
import { ChevronDown, FileText } from "lucide-react";
import { Disclaimer, FlowHeader, SourceLink } from "../ui";
import { useSession } from "../session";
import { PLAN_DOCS, PLAN_EDGES, PLAN_SCHEME_NODES } from "../data";
import type { DocStatus } from "../data";

const CHOICES: [DocStatus, string][] = [["needed", "Needed"], ["have", "I have it"], ["obtained", "Obtained"]];
const DOC_TOPS = [2, 62, 122, 182, 242];

export default function Plan() {
  const { session, update } = useSession();
  const [hover, setHover] = useState<string | null>(null);
  const st = session.docStatus;
  const isReady = (id: string) => st[id] === "have" || st[id] === "obtained";
  const setSt = (id: string, v: DocStatus) => update((s) => ({ docStatus: { ...s.docStatus, [id]: v } }));
  const ready = PLAN_DOCS.filter((d) => isReady(d.id)).length;

  const litSchemes = new Set(PLAN_EDGES.filter((e) => e.doc === hover).map((e) => e.scheme));
  const edgeCls = (doc: string) => (!hover ? (doc === "income" ? "edge sh" : "edge") : doc === hover ? "edge on" : "edge dim");

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
            <span className="serif" style={{ fontSize: 36, lineHeight: 1 }}>
              {ready} <span style={{ color: "var(--faintest)" }}>of {PLAN_DOCS.length} ready</span>
            </span>
            <div style={{ display: "flex", gap: 4 }} aria-hidden>
              {PLAN_DOCS.map((d) => <span key={d.id} className={isReady(d.id) ? "plan-pip on" : "plan-pip hatch"} />)}
            </div>
          </div>
        </div>

        <div className="rise d3" style={{ display: "flex", alignItems: "center", gap: 16, padding: "18px 20px", borderRadius: 22, background: "var(--primary)", color: "var(--text)", flexWrap: "wrap", boxShadow: "var(--shadow-sm)" }}>
          <span className="callout-icon" style={{ width: 42, height: 42 }}><FileText size={18} aria-hidden /></span>
          <span style={{ flex: "1 1 300px", fontSize: 17 }}>
            <strong style={{ fontWeight: 600 }}>Get your Income Certificate first.</strong> It's needed for 2 schemes: Demo Scholarship A and Demo Fee Concession B.
          </span>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "flex-start" }}>
          <ol className="stack" style={{ flex: "999 1 520px", minWidth: 0, margin: 0, padding: 0, listStyle: "none", gap: 12 }}>
            {PLAN_DOCS.map((d, i) => {
              const cur = st[d.id] ?? "needed";
              const r = isReady(d.id);
              return (
                <li key={d.id} className={`item rise d${i + 3} ${r ? "ready" : ""}`} onMouseEnter={() => setHover(d.id)} onMouseLeave={() => setHover(null)}>
                  <span className={r ? "num ready" : "num"}>{String(i + 1).padStart(2, "0")}</span>
                  <div className="stack" style={{ flex: 1, minWidth: 0, gap: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <h2 className="serif" style={{ fontSize: 28, lineHeight: 1.05 }}>{d.name}</h2>
                      {d.shared && <span className="shared">SHARED</span>}
                    </div>
                    <p style={{ fontSize: 15, color: "var(--muted)" }}>{d.reason}</p>
                    <div className="stack" style={{ gap: 2, fontSize: 14 }}>
                      <span><span style={{ color: "var(--faint)" }}>Needed for:</span> {d.for.join(", ")}</span>
                      {d.after && <span style={{ color: "var(--secondary-dark)", fontWeight: 500 }}><span style={{ color: "var(--faint)" }}>Get after:</span> {d.after}</span>}
                    </div>
                    <div className="row-between" style={{ gap: 12 }}>
                      <SourceLink href={d.url}>Official source</SourceLink>
                      <div className="segc" role="group" aria-label={`Status of ${d.name}`}>
                        {CHOICES.map(([v, label]) => (
                          <button key={v} className={cur === v ? (v === "needed" ? "on" : "on lime") : ""} aria-pressed={cur === v} onClick={() => setSt(d.id, v)}>
                            {label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>

          <aside className="stack rise d4" style={{ flex: "0 1 548px", minWidth: 0, gap: 12 }}>
            <div className="card stack" style={{ padding: 24, gap: 18 }}>
              <div className="row-between" style={{ gap: 12 }}>
                <span style={{ fontSize: 16, fontWeight: 600 }}>What each document unlocks</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>HOVER A DOCUMENT</span>
              </div>
              <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 11, letterSpacing: ".06em", color: "var(--faint)", maxWidth: 500 }}>
                <span style={{ paddingLeft: 24 }}>DOCUMENTS</span>
                <span style={{ paddingRight: 110 }}>SCHEMES</span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <div style={{ position: "relative", width: 500, height: 290 }}>
                  <svg width="500" height="290" viewBox="0 0 500 290" aria-hidden style={{ position: "absolute", inset: 0 }}>
                    {PLAN_EDGES.map((e) => <path key={e.d} className={edgeCls(e.doc)} d={e.d} />)}
                    <path className="dep" d="M24 84 C4 84 4 144 24 144" />
                  </svg>
                  {PLAN_DOCS.map((d, i) => (
                    <div
                      key={d.id}
                      className={`node doc${hover ? (hover === d.id ? " on" : " dim") : d.shared ? " sh" : ""}`}
                      style={{ left: 24, top: DOC_TOPS[i] }}
                      onMouseEnter={() => setHover(d.id)}
                      onMouseLeave={() => setHover(null)}
                    >
                      <span className={isReady(d.id) ? "ndot ready" : "ndot"} />
                      {d.name}
                    </div>
                  ))}
                  {PLAN_SCHEME_NODES.map((n) => (
                    <div key={n.id} className={`node sch${hover ? (litSchemes.has(n.id) ? " on" : " dim") : ""}`} style={{ left: 330, top: n.top }}>
                      {n.label}
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 13, color: "var(--muted)", paddingTop: 12, borderTop: "1px solid var(--line-2)" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><i style={{ width: 18, height: 2, background: "var(--primary)" }} />Shared document</span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><i style={{ width: 18, height: 0, borderTop: "2px dashed var(--secondary-dark)" }} />Get after</span>
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
      </main>
      <Disclaimer />
    </div>
  );
}
