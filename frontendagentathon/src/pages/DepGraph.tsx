import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { PLAN_DOCS, PLAN_SCHEME_NODES } from "../data";

/** "What each document unlocks": documents on the left, schemes on the right, one curve per requirement. */

const W = 540;
const HEAD = 30; // room for the column labels
const NODE_H = 44;
const PITCH = 62;
const DOC_X = 28;
const DOC_W = 170;
const SCH_X = 340;
const SCH_W = 196;
const MID = (DOC_X + DOC_W + SCH_X) / 2;

type Edge = { doc: string; scheme: string };

// Edges come from each document's "needed for" list, so the diagram can't drift from the cards.
const EDGES: Edge[] = PLAN_DOCS.flatMap((d) =>
  d.for.flatMap((name) => {
    const n = PLAN_SCHEME_NODES.find((s) => s.label === name);
    return n ? [{ doc: d.id, scheme: n.id }] : [];
  }),
);

const schemeIndex = (id: string) => PLAN_SCHEME_NODES.findIndex((s) => s.id === id);

// Order documents by the schemes they feed (top schemes first) so the curves cross as little as possible.
// A document that must come after another sits below its siblings, next to the one it waits on.
const avg = (docId: string) => {
  const idx = EDGES.filter((e) => e.doc === docId).map((e) => schemeIndex(e.scheme));
  return idx.length ? idx.reduce((a, b) => a + b, 0) / idx.length : 99;
};
const DOCS = [...PLAN_DOCS].sort((a, b) => avg(a.id) - avg(b.id) || Number(!!a.after) - Number(!!b.after));
const docY = (i: number) => HEAD + i * PITCH;

// Each scheme sits at the average height of the documents it needs, kept at least one row apart.
const SCHEME_Y: Record<string, number> = (() => {
  let prev = -Infinity;
  const out: Record<string, number> = {};
  PLAN_SCHEME_NODES.forEach((n) => {
    const rows = EDGES.filter((e) => e.scheme === n.id).map((e) => DOCS.findIndex((d) => d.id === e.doc));
    const mean = rows.length ? rows.reduce((a, b) => a + b, 0) / rows.length : 0;
    prev = Math.max(HEAD + mean * PITCH, prev + PITCH);
    out[n.id] = prev;
  });
  return out;
})();
const HEIGHT = Math.max(docY(DOCS.length - 1), ...Object.values(SCHEME_Y)) + NODE_H + 6;

const curve = (e: Edge) => {
  const y1 = docY(DOCS.findIndex((d) => d.id === e.doc)) + NODE_H / 2;
  const y2 = SCHEME_Y[e.scheme] + NODE_H / 2;
  const x1 = DOC_X + DOC_W;
  return { d: `M${x1} ${y1} C${MID} ${y1} ${MID} ${y2} ${SCH_X} ${y2}`, x1, y1, y2 };
};

// "Get after": a dashed arc down the left side, from the document you need first to the one that waits on it.
const DEPS = DOCS.flatMap((d, i) => {
  const pre = d.after ? DOCS.findIndex((p) => p.name === d.after) : -1;
  if (pre < 0) return [];
  const y1 = docY(pre) + NODE_H / 2;
  const y2 = docY(i) + NODE_H / 2;
  return [{ key: d.id, d: `M${DOC_X} ${y1} C${DOC_X - 26} ${y1} ${DOC_X - 26} ${y2} ${DOC_X} ${y2}` }];
});

export default function DepGraph({ isReady, hover, setHover }: { isReady: (id: string) => boolean; hover: string | null; setHover: (id: string | null) => void }) {
  const [hoverScheme, setHoverScheme] = useState<string | null>(null);

  // Hovering a document lights its schemes; hovering a scheme lights the documents it needs.
  const active = (e: Edge) => (hover ? e.doc === hover : hoverScheme ? e.scheme === hoverScheme : false);
  const focused = hover !== null || hoverScheme !== null;
  const litDocs = new Set(EDGES.filter(active).map((e) => e.doc));
  const litSchemes = new Set(EDGES.filter(active).map((e) => e.scheme));

  const progress = Object.fromEntries(PLAN_SCHEME_NODES.map((n) => {
    const ids = EDGES.filter((e) => e.scheme === n.id).map((e) => e.doc);
    return [n.id, { have: ids.filter(isReady).length, total: ids.length }];
  }));

  return (
    <FitStage width={W} height={HEIGHT}>
      <svg width={W} height={HEIGHT} viewBox={`0 0 ${W} ${HEIGHT}`} aria-hidden style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        <defs>
          <marker id="dep-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0 0 L8 4 L0 8 z" style={{ fill: "var(--secondary-dark)" }} />
          </marker>
        </defs>
        <text className="gcol" x={DOC_X + 4} y={12}>DOCUMENTS</text>
        <text className="gcol" x={SCH_X + 4} y={12}>SCHEMES</text>
        {EDGES.map((e) => {
          const c = curve(e);
          const cls = !focused ? (e.doc === "income" ? "edge sh" : "edge") : active(e) ? "edge on" : "edge dim";
          return (
            <g key={`${e.doc}-${e.scheme}`}>
              <path className={cls} d={c.d} />
              <circle className={active(e) ? "port on" : "port"} cx={c.x1} cy={c.y1} r={3.5} />
              <circle className={active(e) ? "port on" : "port"} cx={SCH_X} cy={c.y2} r={3.5} />
            </g>
          );
        })}
        {DEPS.map((p) => <path key={p.key} className="dep" d={p.d} markerEnd="url(#dep-arrow)" />)}
      </svg>

      {DOCS.map((d, i) => (
        <div
          key={d.id}
          className={`node doc${focused ? (litDocs.has(d.id) ? " on" : " dim") : d.shared ? " sh" : ""}`}
          style={{ left: DOC_X, top: docY(i), width: DOC_W }}
          onMouseEnter={() => setHover(d.id)}
          onMouseLeave={() => setHover(null)}
        >
          <span className={isReady(d.id) ? "ndot ready" : "ndot"}>{isReady(d.id) && <Check size={9} strokeWidth={3.4} aria-hidden />}</span>
          {d.name}
        </div>
      ))}

      {PLAN_SCHEME_NODES.map((n) => {
        const p = progress[n.id];
        return (
          <a
            key={n.id}
            href={`#next-${n.id}`}
            title="See the steps to apply"
            className={`node sch${focused ? (litSchemes.has(n.id) ? " on" : " dim") : ""}`}
            style={{ left: SCH_X, top: SCHEME_Y[n.id], width: SCH_W, textDecoration: "none", cursor: "pointer", justifyContent: "space-between" }}
            onMouseEnter={() => setHoverScheme(n.id)}
            onMouseLeave={() => setHoverScheme(null)}
            onFocus={() => setHoverScheme(n.id)}
            onBlur={() => setHoverScheme(null)}
          >
            <span>{n.label}</span>
            <span className={p.have === p.total ? "ncount done" : "ncount"}>{p.have}/{p.total}</span>
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
