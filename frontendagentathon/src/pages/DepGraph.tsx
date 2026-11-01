import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  return { docs, docY, schemeY, height: bottom + NODE_H + 10 };
}

type Edge = { doc: string; scheme: string };

export default function DepGraph({
  plan, isReady, hover, setHover,
}: { plan: PlanVM; isReady: (id: string) => boolean; hover: string | null; setHover: (id: string | null) => void }) {
  const [hoverScheme, setHoverScheme] = useState<string | null>(null);
  const L = useMemo(() => layoutGraph(plan), [plan]);
  const { schemeY, docY } = L;

  const feeds = useMemo(() => {
    const m = new Map<string, number>();
    plan.edges.forEach((e) => m.set(e.doc, (m.get(e.doc) ?? 0) + 1));
    return m;
  }, [plan.edges]);
  const isShared = (d: PlanDocVM) => Boolean(d.shared || (feeds.get(d.id) ?? 0) > 1);

  // Curves leave and arrive nearly flat, so they don't crowd the labels.
  const curves = useMemo(() => {
    const x1 = DOC_X + DOC_W;
    const dx = SCH_X - x1;
    const c1 = x1 + dx * 0.45;
    const c2 = x1 + dx * 0.55;
    return plan.edges
      .filter((e) => docY[e.doc] !== undefined && schemeY[e.scheme] !== undefined)
      .map((e) => {
        const y1 = docY[e.doc] + NODE_H / 2;
        const y2 = schemeY[e.scheme] + NODE_H / 2;
        return { edge: e, d: `M${x1} ${y1} C${c1} ${y1} ${c2} ${y2} ${SCH_X} ${y2}`, x1, y1, y2 };
      });
  }, [plan.edges, docY, schemeY]);

  // Hovering a document lights its schemes; hovering a scheme lights the documents it needs. Everything else dims.
  const active = useCallback((e: Edge) => (hover ? e.doc === hover : hoverScheme ? e.scheme === hoverScheme : false), [hover, hoverScheme]);
  const focused = hover !== null || hoverScheme !== null;
  const litDocs = useMemo(() => new Set(plan.edges.filter(active).map((e) => e.doc)), [plan.edges, active]);
  const litSchemes = useMemo(() => new Set(plan.edges.filter(active).map((e) => e.scheme)), [plan.edges, active]);

  const progress = Object.fromEntries(plan.schemes.map((s) => {
    const ids = plan.edges.filter((e) => e.scheme === s.id).map((e) => e.doc);
    return [s.id, { have: ids.filter(isReady).length, total: ids.length }];
  }));

  return (
    <FitStage width={W} height={L.height}>
      <svg width={W} height={L.height} viewBox={`0 0 ${W} ${L.height}`} aria-hidden style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        <text className="gcol" x={DOC_X + 4} y={14}>DOCUMENTS</text>
        <text className="gcol" x={SCH_X + 4} y={14}>SCHEMES</text>
        {curves.map(({ edge: e, d, x1, y1, y2 }) => {
          const doc = plan.docs.find((x) => x.id === e.doc);
          const cls = !focused ? (doc && isShared(doc) ? "edge sh" : "edge") : active(e) ? "edge on" : "edge dim";
          return (
            <g key={`${e.doc}-${e.scheme}`}>
              <path className={cls} d={d} />
              <circle className={active(e) ? "port on" : "port"} cx={x1} cy={y1} r={3.5} />
              <circle className={active(e) ? "port on" : "port"} cx={SCH_X} cy={y2} r={3.5} />
            </g>
          );
        })}
      </svg>

      {L.docs.map((d) => {
        const ready = isReady(d.id);
        return (
          <div
            key={d.id}
            role="button"
            tabIndex={0}
            title={d.name}
            aria-label={`${d.name}: ${ready ? "Ready" : "Missing"}${isShared(d) ? ", shared document" : ""}`}
            className={`node doc${focused ? (litDocs.has(d.id) ? " on" : " dim") : isShared(d) ? " sh" : ""}`}
            style={{ left: DOC_X, top: docY[d.id], width: DOC_W, cursor: "pointer", outlineOffset: 2 }}
            onMouseEnter={() => setHover(d.id)}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(d.id)}
            onBlur={() => setHover(null)}
            onClick={() => setHover(hover === d.id ? null : d.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setHover(hover === d.id ? null : d.id);
              }
            }}
          >
            {ready ? (
              <span className="ndot ready" title="Ready (obtained)"><Check size={9} strokeWidth={3.4} aria-hidden /></span>
            ) : (
              <span
                className="ndot"
                title="Missing (needed)"
                style={{ width: 15, height: 15, borderRadius: "50%", border: "1.5px dashed var(--line-4)", background: "var(--surface-sunk)", display: "grid", placeItems: "center", flex: "none" }}
              >
                <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)" }} />
              </span>
            )}
            <span className="nlabel">{d.name}</span>
          </div>
        );
      })}

      {plan.schemes.map((s) => {
        const p = progress[s.id] ?? { have: 0, total: 0 };
        return (
          <a
            key={s.id}
            href={`#next-${s.id}`}
            title={s.name}
            aria-label={`${s.name}: ${p.have} of ${p.total} required documents ready`}
            className={`node sch${focused ? (litSchemes.has(s.id) ? " on" : " dim") : ""}`}
            style={{ left: SCH_X, top: schemeY[s.id], width: SCH_W, textDecoration: "none", cursor: "pointer", justifyContent: "space-between", outlineOffset: 2 }}
            onMouseEnter={() => setHoverScheme(s.id)}
            onMouseLeave={() => setHoverScheme(null)}
            onFocus={() => setHoverScheme(s.id)}
            onBlur={() => setHoverScheme(null)}
          >
            <span className="nlabel">{s.name}</span>
            <span className={p.total > 0 && p.have === p.total ? "ncount done" : "ncount"} style={{ flexShrink: 0 }}>{p.have}/{p.total}</span>
          </a>
        );
      })}
    </FitStage>
  );
}

/** Lays out a fixed-size stage and scales it to the width it is given, so a diagram never needs to scroll or clip. */
function FitStage({ width, height, children }: { width: number; height: number; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(1);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const fit = () => {
      if (el.clientWidth > 0) setK(Math.min(1, el.clientWidth / width));
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [width]);
  return (
    <div
      ref={box}
      role="region"
      aria-label="What each document unlocks dependency graph"
      style={{ width: "100%", height: Math.ceil(height * k), position: "relative", overflow: "hidden" }}
    >
      <div style={{ position: "absolute", left: 0, top: 0, width, height, transform: `scale(${k})`, transformOrigin: "top left" }}>{children}</div>
    </div>
  );
}
