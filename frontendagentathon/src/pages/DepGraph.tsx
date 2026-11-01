import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Check } from "lucide-react";
import type { PlanDocVM, PlanVM } from "../model";

/** "What each document unlocks": documents on the left, schemes on the right, one curve per requirement. */

const W = 540;
const HEAD = 30; // room for the column labels
const NODE_H = 44;
const PITCH = 62;
const DOC_X = 28;
const DOC_W = 204; // wide enough for real document names ("College Admission Letter") without clipping
const SCH_X = 326;
const SCH_W = 214;
const MID = (DOC_X + DOC_W + SCH_X) / 2;

export type Layout = {
  docs: PlanDocVM[];
  docY: Record<string, number>;
  schemeY: Record<string, number>;
  height: number;
};

/**
 * Orders documents by the schemes they feed (top schemes first) so the curves cross as little as possible,
 * puts a document that waits on another below its siblings, and centres each scheme on the documents it needs.
 */
export function layoutGraph(plan: Pick<PlanVM, "docs" | "schemes" | "edges">): Layout {
  const schemeIndex = (id: string) => plan.schemes.findIndex((s) => s.id === id);
  const avg = (docId: string) => {
    const idx = plan.edges.filter((e) => e.doc === docId).map((e) => schemeIndex(e.scheme));
    return idx.length ? idx.reduce((a, b) => a + b, 0) / idx.length : 99;
  };
  const docs = [...plan.docs].sort((a, b) => avg(a.id) - avg(b.id) || Number(a.after.length > 0) - Number(b.after.length > 0));
  const docY: Record<string, number> = Object.fromEntries(docs.map((d, i) => [d.id, HEAD + i * PITCH]));

  let prev = -Infinity;
  const schemeY: Record<string, number> = {};
  plan.schemes.forEach((s) => {
    const ys = plan.edges.filter((e) => e.scheme === s.id).map((e) => docY[e.doc]).filter((y) => y !== undefined);
    const mean = ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : HEAD;
    prev = Math.max(mean, prev + PITCH);
    schemeY[s.id] = prev;
  });
  const bottom = Math.max(HEAD, ...Object.values(docY), ...Object.values(schemeY));
  return { docs, docY, schemeY, height: bottom + NODE_H + 6 };
}

type Edge = { doc: string; scheme: string };

export default function DepGraph({
  plan, isReady, hover, setHover,
}: { plan: PlanVM; isReady: (id: string) => boolean; hover: string | null; setHover: (id: string | null) => void }) {
  const [hoverScheme, setHoverScheme] = useState<string | null>(null);
  const L = layoutGraph(plan);
  const { schemeY, docY } = L;

  const curve = (e: Edge) => {
    const y1 = docY[e.doc] + NODE_H / 2;
    const y2 = schemeY[e.scheme] + NODE_H / 2;
    const x1 = DOC_X + DOC_W;
    return { d: `M${x1} ${y1} C${MID} ${y1} ${MID} ${y2} ${SCH_X} ${y2}`, x1, y1, y2 };
  };
  // "Get after": a dashed arc down the left side, from the document you need first to the one that waits on it.
  const arcs = plan.deps.flatMap((p) => {
    if (docY[p.pre] === undefined || docY[p.doc] === undefined) return [];
    const y1 = docY[p.pre] + NODE_H / 2;
    const y2 = docY[p.doc] + NODE_H / 2;
    const bulge = 22 + Math.min(40, Math.abs(y2 - y1) / 6);
    return [{ key: `${p.pre}-${p.doc}`, d: `M${DOC_X} ${y1} C${DOC_X - bulge} ${y1} ${DOC_X - bulge} ${y2} ${DOC_X} ${y2}` }];
  });

  // Hovering a document lights its schemes; hovering a scheme lights the documents it needs. Everything else dims.
  const active = (e: Edge) => (hover ? e.doc === hover : hoverScheme ? e.scheme === hoverScheme : false);
  const focused = hover !== null || hoverScheme !== null;
  const litDocs = new Set(plan.edges.filter(active).map((e) => e.doc));
  const litSchemes = new Set(plan.edges.filter(active).map((e) => e.scheme));

  const progress = Object.fromEntries(plan.schemes.map((s) => {
    const ids = plan.edges.filter((e) => e.scheme === s.id).map((e) => e.doc);
    return [s.id, { have: ids.filter(isReady).length, total: ids.length }];
  }));

  return (
    <FitStage width={W} height={L.height}>
      <svg width={W} height={L.height} viewBox={`0 0 ${W} ${L.height}`} aria-hidden style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        <defs>
          <marker id="dep-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0 0 L8 4 L0 8 z" style={{ fill: "var(--secondary-dark)" }} />
          </marker>
        </defs>
        <text className="gcol" x={DOC_X + 4} y={12}>DOCUMENTS</text>
        <text className="gcol" x={SCH_X + 4} y={12}>SCHEMES</text>
        {plan.edges.map((e) => {
          const c = curve(e);
          const shared = plan.docs.find((d) => d.id === e.doc)?.shared;
          const cls = !focused ? (shared ? "edge sh" : "edge") : active(e) ? "edge on" : "edge dim";
          return (
            <g key={`${e.doc}-${e.scheme}`}>
              <path className={cls} d={c.d} />
              <circle className={active(e) ? "port on" : "port"} cx={c.x1} cy={c.y1} r={3.5} />
              <circle className={active(e) ? "port on" : "port"} cx={SCH_X} cy={c.y2} r={3.5} />
            </g>
          );
        })}
        {arcs.map((p) => <path key={p.key} className="dep" d={p.d} markerEnd="url(#dep-arrow)" />)}
      </svg>

      {L.docs.map((d) => (
        <div
          key={d.id}
          title={d.name}
          className={`node doc${focused ? (litDocs.has(d.id) ? " on" : " dim") : d.shared ? " sh" : ""}`}
          style={{ left: DOC_X, top: docY[d.id], width: DOC_W }}
          onMouseEnter={() => setHover(d.id)}
          onMouseLeave={() => setHover(null)}
        >
          <span className={isReady(d.id) ? "ndot ready" : "ndot"}>{isReady(d.id) && <Check size={9} strokeWidth={3.4} aria-hidden />}</span>
          <span className="nlabel">{d.name}</span>
        </div>
      ))}

      {plan.schemes.map((s) => {
        const p = progress[s.id];
        return (
          <a
            key={s.id}
            href={`#next-${s.id}`}
            title={s.name}
            className={`node sch${focused ? (litSchemes.has(s.id) ? " on" : " dim") : ""}`}
            style={{ left: SCH_X, top: schemeY[s.id], width: SCH_W, textDecoration: "none", cursor: "pointer", justifyContent: "space-between" }}
            onMouseEnter={() => setHoverScheme(s.id)}
            onMouseLeave={() => setHoverScheme(null)}
            onFocus={() => setHoverScheme(s.id)}
            onBlur={() => setHoverScheme(null)}
          >
            <span className="nlabel">{s.name}</span>
            <span className={p.total > 0 && p.have === p.total ? "ncount done" : "ncount"}>{p.have}/{p.total}</span>
          </a>
        );
      })}
    </FitStage>
  );
}

/** Lays out a fixed-size stage and scales it to the width it is given, so a diagram never needs to scroll. */
function FitStage({ width, height, children }: { width: number; height: number; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(1);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const fit = () => setK(Math.min(1.25, el.clientWidth / width));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [width]);
  return (
    <div ref={box} style={{ width: "100%", height: height * k, position: "relative" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width, height, transform: `scale(${k})`, transformOrigin: "top left" }}>{children}</div>
    </div>
  );
}
