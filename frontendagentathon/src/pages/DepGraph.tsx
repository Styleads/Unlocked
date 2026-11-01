import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { PLAN_DOCS, PLAN_SCHEME_NODES } from "../data";

/** "What each document unlocks": documents on the left, schemes on the right, one curve per requirement. */

const W = 550;
const HEAD = 30; // room for the column labels
const NODE_H = 44;
const PITCH = 62;
const DOC_X = 28;
const DOC_W = 172;
const SCH_X = 328;
const SCH_W = 196;

type Edge = { doc: string; scheme: string };

export default function DepGraph({
  isReady,
  hover,
  setHover,
}: {
  isReady: (id: string) => boolean;
  hover: string | null;
  setHover: (id: string | null) => void;
}) {
  const [hoverScheme, setHoverScheme] = useState<string | null>(null);

  // Edges come from each document's "needed for" list, so the diagram can't drift from the cards.
  const edges: Edge[] = useMemo(
    () =>
      PLAN_DOCS.flatMap((d) =>
        d.for.flatMap((name) => {
          const n = PLAN_SCHEME_NODES.find((s) => s.label === name);
          return n ? [{ doc: d.id, scheme: n.id }] : [];
        }),
      ),
    [],
  );

  const schemeIndex = useCallback((id: string) => PLAN_SCHEME_NODES.findIndex((s) => s.id === id), []);

  // Order documents by the schemes they feed (top schemes first) so curves cross as little as possible.
  const docs = useMemo(() => {
    const avg = (docId: string) => {
      const idx = edges.filter((e) => e.doc === docId).map((e) => schemeIndex(e.scheme));
      return idx.length ? idx.reduce((a, b) => a + b, 0) / idx.length : 99;
    };
    return [...PLAN_DOCS].sort(
      (a, b) => avg(a.id) - avg(b.id) || Number(!!a.after) - Number(!!b.after),
    );
  }, [edges, schemeIndex]);

  const docY = useCallback((i: number) => HEAD + i * PITCH, []);

  // Schemes sit at the average height of documents they need, kept at least one pitch apart.
  const schemeY: Record<string, number> = useMemo(() => {
    let prev = -Infinity;
    const out: Record<string, number> = {};
    PLAN_SCHEME_NODES.forEach((n) => {
      const rows = edges.filter((e) => e.scheme === n.id).map((e) => docs.findIndex((d) => d.id === e.doc));
      const mean = rows.length ? rows.reduce((a, b) => a + b, 0) / rows.length : 0;
      prev = Math.max(HEAD + mean * PITCH, prev + PITCH);
      out[n.id] = prev;
    });
    return out;
  }, [edges, docs]);

  const height = useMemo(
    () => Math.max(docY(docs.length - 1), ...Object.values(schemeY)) + NODE_H + 10,
    [docs.length, docY, schemeY],
  );

  const docFeedsCount = useMemo(() => {
    const map = new Map<string, number>();
    edges.forEach((e) => map.set(e.doc, (map.get(e.doc) ?? 0) + 1));
    return map;
  }, [edges]);

  const curveData = useMemo(() => {
    const dx = SCH_X - (DOC_X + DOC_W);
    const cp1x = DOC_X + DOC_W + dx * 0.45;
    const cp2x = DOC_X + DOC_W + dx * 0.55;
    return edges.map((e) => {
      const y1 = docY(docs.findIndex((d) => d.id === e.doc)) + NODE_H / 2;
      const y2 = schemeY[e.scheme] + NODE_H / 2;
      const x1 = DOC_X + DOC_W;
      return {
        edge: e,
        d: `M${x1} ${y1} C${cp1x} ${y1} ${cp2x} ${y2} ${SCH_X} ${y2}`,
        x1,
        y1,
        y2,
      };
    });
  }, [edges, docs, docY, schemeY]);

  // Hovering a document lights its schemes; hovering a scheme lights the documents it needs.
  const active = useCallback(
    (e: Edge) => (hover ? e.doc === hover : hoverScheme ? e.scheme === hoverScheme : false),
    [hover, hoverScheme],
  );
  const focused = hover !== null || hoverScheme !== null;

  const litDocs = useMemo(() => new Set(edges.filter(active).map((e) => e.doc)), [edges, active]);
  const litSchemes = useMemo(() => new Set(edges.filter(active).map((e) => e.scheme)), [edges, active]);

  const progress = useMemo(
    () =>
      Object.fromEntries(
        PLAN_SCHEME_NODES.map((n) => {
          const ids = edges.filter((e) => e.scheme === n.id).map((e) => e.doc);
          return [n.id, { have: ids.filter(isReady).length, total: ids.length }];
        }),
      ),
    [edges, isReady],
  );

  return (
    <FitStage width={W} height={height}>
      <svg
        width={W}
        height={height}
        viewBox={`0 0 ${W} ${height}`}
        aria-hidden
        style={{ position: "absolute", inset: 0, overflow: "visible" }}
      >
        <text className="gcol" x={DOC_X + 4} y={14}>
          DOCUMENTS
        </text>
        <text className="gcol" x={SCH_X + 4} y={14}>
          SCHEMES
        </text>

        {/* Dependency curves */}
        {curveData.map(({ edge: e, d, x1, y1, y2 }) => {
          const docRecord = docs.find((d) => d.id === e.doc);
          const isShared = Boolean(docRecord?.shared || (docFeedsCount.get(e.doc) ?? 0) > 1);
          const cls = !focused ? (isShared ? "edge sh" : "edge") : active(e) ? "edge on" : "edge dim";
          return (
            <g key={`${e.doc}-${e.scheme}`}>
              <path className={cls} d={d} />
              <circle className={active(e) ? "port on" : "port"} cx={x1} cy={y1} r={3.5} />
              <circle className={active(e) ? "port on" : "port"} cx={SCH_X} cy={y2} r={3.5} />
            </g>
          );
        })}
      </svg>

      {/* Document Nodes */}
      {docs.map((d, i) => {
        const ready = isReady(d.id);
        const isShared = Boolean(d.shared || (docFeedsCount.get(d.id) ?? 0) > 1);
        return (
          <div
            key={d.id}
            role="button"
            tabIndex={0}
            aria-label={`${d.name}: ${ready ? "Ready" : "Missing"}${isShared ? ", shared document" : ""}`}
            className={`node doc${focused ? (litDocs.has(d.id) ? " on" : " dim") : isShared ? " sh" : ""}`}
            style={{
              left: DOC_X,
              top: docY(i),
              width: DOC_W,
              cursor: "pointer",
              outlineOffset: 2,
            }}
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
              <span className="ndot ready" title="Ready (obtained)">
                <Check size={9} strokeWidth={3.4} aria-hidden />
              </span>
            ) : (
              <span
                className="ndot"
                title="Missing (needed)"
                style={{
                  width: 15,
                  height: 15,
                  borderRadius: "50%",
                  border: "1.5px dashed var(--line-4)",
                  background: "var(--surface-sunk)",
                  display: "grid",
                  placeItems: "center",
                  flex: "none",
                }}
              >
                <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--muted)" }} />
              </span>
            )}
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {d.name}
            </span>
          </div>
        );
      })}

      {/* Scheme Nodes */}
      {PLAN_SCHEME_NODES.map((n) => {
        const p = progress[n.id] ?? { have: 0, total: 0 };
        return (
          <a
            key={n.id}
            href={`#next-${n.id}`}
            title="See the steps to apply"
            aria-label={`${n.label}: ${p.have} of ${p.total} required documents ready`}
            className={`node sch${focused ? (litSchemes.has(n.id) ? " on" : " dim") : ""}`}
            style={{
              left: SCH_X,
              top: schemeY[n.id],
              width: SCH_W,
              textDecoration: "none",
              cursor: "pointer",
              justifyContent: "space-between",
              outlineOffset: 2,
            }}
            onMouseEnter={() => setHoverScheme(n.id)}
            onMouseLeave={() => setHoverScheme(null)}
            onFocus={() => setHoverScheme(n.id)}
            onBlur={() => setHoverScheme(null)}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{n.label}</span>
            <span className={p.have === p.total ? "ncount done" : "ncount"} style={{ flexShrink: 0 }}>
              {p.have}/{p.total}
            </span>
          </a>
        );
      })}
    </FitStage>
  );
}

/** Lays out a fixed-size stage and scales it cleanly to the width it is given, preventing clipping on smaller screens. */
function FitStage({ width, height, children }: { width: number; height: number; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(1);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const fit = () => {
      const cw = el.clientWidth;
      if (cw > 0) {
        setK(Math.min(1, cw / width));
      }
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
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width,
          height,
          transform: `scale(${k})`,
          transformOrigin: "top left",
        }}
      >
        {children}
      </div>
    </div>
  );
}
