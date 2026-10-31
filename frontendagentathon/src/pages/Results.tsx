import { useState } from "react";
import { ArrowUpRight, Check, ChevronDown, TriangleAlert } from "lucide-react";
import { Disclaimer, FlowHeader, OutcomeSourceBadge, PrimaryLink, SourceLink, StatusBadge, statusLabel } from "../ui";
import { Link } from "../router";
import { useSession } from "../session";
import { SCHEMES } from "../data";
import type { Scheme } from "../data";

type Filter = "all" | Scheme["status"];

/** Demo: append ?limited to the URL to see the "live search had trouble" banner. */
const liveSearchFailed = () => new URLSearchParams(window.location.search).has("limited");

export default function Results() {
  const { session } = useSession();
  const [filter, setFilter] = useState<Filter>("all");
  const [showUnlikely, setShowUnlikely] = useState(false);
  const hasAnswers = Object.values(session.answers).some((a) => a !== undefined);

  const counts = { ok: 0, info: 0, nv: 0, warn: 0 };
  SCHEMES.forEach((s) => counts[s.status]++);
  const filters: { k: Filter; label: string; count: number }[] = [
    { k: "all", label: "All", count: SCHEMES.length },
    ...(["ok", "info", "nv", "warn"] as const).filter((k) => counts[k] > 0).map((k) => ({ k, label: statusLabel(k, true), count: counts[k] })),
  ];
  const visible = filter === "all" ? SCHEMES.filter((s) => s.status !== "warn" || showUnlikely) : SCHEMES.filter((s) => s.status === filter);
  const totalCriteria = SCHEMES.reduce((n, s) => n + s.pips.length, 0);
  const met = SCHEMES.reduce((n, s) => n + s.met, 0);
  const unknown = SCHEMES.reduce((n, s) => n + s.pips.filter((p) => p === "unk").length, 0);

  return (
    <div className="page">
      <FlowHeader current={3} />
      <main className="main wide">
        <div className="row-between" style={{ alignItems: "flex-end", gap: 24 }}>
          <div className="stack" style={{ gap: 12 }}>
            <span className="eyebrow rise">_ Step 3 of 4 · Results</span>
            <h1 className="serif display rise d1">We found {SCHEMES.length} schemes.</h1>
            <p className="lede rise d2">Sorted by how well your answers fit. Every card links to its official source.</p>
          </div>
          <PrimaryLink to="/plan" className="rise d2">Build my document plan</PrimaryLink>
        </div>

        {liveSearchFailed() && (
          <div role="status" className="hatch" style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 20px", borderRadius: 20, border: "1px solid var(--line-3)" }}>
            <TriangleAlert size={20} color="var(--warn-text)" aria-hidden style={{ flex: "none" }} />
            <span style={{ fontSize: 15 }}>
              <strong style={{ fontWeight: 600 }}>Live search had trouble.</strong> Showing limited results. Schemes from fallback data are clearly tagged.
            </span>
          </div>
        )}

        <div className="rise d3" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))", gap: 14 }}>
          <div className="card stack" style={{ padding: 22, gap: 18 }}>
            <div className="row-between">
              <span style={{ fontSize: 15, fontWeight: 600 }}>Status breakdown</span>
              <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>{SCHEMES.length} SCHEMES</span>
            </div>
            <div style={{ display: "flex", gap: 4 }} role="img" aria-label={`${counts.ok} potential match, ${counts.info} need more info, ${counts.nv} not yet verified, ${counts.warn} unlikely`}>
              <div className="seg s1" style={{ flex: counts.ok, background: "var(--primary)" }} />
              <div className="seg s2" style={{ flex: counts.info, background: "var(--secondary)" }} />
              <div className="seg s3 hatch" style={{ flex: counts.nv, border: "1px dashed var(--line-4)" }} />
              <div className="seg s4" style={{ flex: counts.warn, background: "var(--warn)" }} />
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13, color: "var(--muted)" }}>
              <LegendItem color="var(--primary-dark)">{counts.ok} match</LegendItem>
              <LegendItem color="var(--secondary-dark)">{counts.info} need info</LegendItem>
              <LegendItem dashed>{counts.nv} unverified</LegendItem>
              <LegendItem color="var(--warn-text)">{counts.warn} unlikely</LegendItem>
            </div>
          </div>

          <div className="card stack" style={{ padding: 22, gap: 18 }}>
            <div className="row-between">
              <span style={{ fontSize: 15, fontWeight: 600 }}>Criteria checked</span>
              <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>ACROSS ALL</span>
            </div>
            <div className="hatch" style={{ position: "relative", height: 14, borderRadius: 999, overflow: "hidden", border: "1px solid var(--line-2)" }}>
              <div className="seg s2" style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${Math.round((met / totalCriteria) * 100)}%`, background: "var(--primary)" }} />
            </div>
            <div className="row-between" style={{ alignItems: "baseline", gap: 12 }}>
              <span className="serif" style={{ fontSize: 34, lineHeight: 1 }}>{met} <span style={{ color: "var(--faintest)" }}>of {totalCriteria} met</span></span>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>{unknown} still unknown</span>
            </div>
          </div>

          <Link
            to="/questions"
            className="card"
            style={{
              padding: 22,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              gap: 14,
              textDecoration: "none",
              color: "var(--text)",
              background: "var(--surface)",
              border: "1.5px solid var(--primary-dark)",
            }}
          >
            <div className="row-between">
              <span style={{ fontSize: 15, fontWeight: 600, color: "var(--primary-dark)" }}>Improve your results</span>
              <span style={{ width: 36, height: 36, borderRadius: 999, background: "var(--primary)", color: "var(--on-accent)", display: "grid", placeItems: "center" }}>
                <ArrowUpRight size={16} strokeWidth={2.2} aria-hidden />
              </span>
            </div>
            <span className="serif" style={{ fontSize: 30, lineHeight: 1.05 }}>Answer 2 more questions to check 2 schemes.</span>
          </Link>
        </div>

        <div className="rise d4" role="group" aria-label="Filter by status" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {filters.map((f) => (
            <button key={f.k} className={filter === f.k ? "fchip on" : "fchip"} aria-pressed={filter === f.k} onClick={() => setFilter(f.k)}>
              {f.label}
              <span className="c">{f.count}</span>
            </button>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(460px, 100%), 1fr))", gap: 14 }}>
          {visible.map((s, i) => (
            <SchemeCard key={s.id} scheme={s} delay={Math.min(i + 1, 6)} />
          ))}
        </div>

        {filter === "all" && counts.warn > 0 && (
          <div style={{ display: "flex", justifyContent: "center" }}>
            <button className="toggle" aria-expanded={showUnlikely} onClick={() => setShowUnlikely((v) => !v)}>
              {showUnlikely ? "Hide unlikely matches" : `Show ${counts.warn} unlikely ${counts.warn === 1 ? "match" : "matches"}`}
              <ChevronDown size={16} className={showUnlikely ? "chev open" : "chev"} aria-hidden />
            </button>
          </div>
        )}
      </main>

      <Disclaimer />

      {hasAnswers && (
        <div className="toast" role="status">
          <span style={{ width: 28, height: 28, borderRadius: 999, background: "var(--primary)", color: "var(--on-accent)", display: "grid", placeItems: "center" }}>
            <Check size={15} strokeWidth={2.6} aria-hidden />
          </span>
          Results updated with your answers.
        </div>
      )}
    </div>
  );
}

function LegendItem({ color, dashed, children }: { color?: string; dashed?: boolean; children: React.ReactNode }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <i className="legend-dot" style={dashed ? { border: "1px dashed var(--line-4)" } : { background: color }} />
      {children}
    </span>
  );
}

function SchemeCard({ scheme: s, delay }: { scheme: Scheme; delay: number }) {
  return (
    <article className={`card scard rise d${delay}`}>
      <div className="row-between" style={{ alignItems: "flex-start", gap: 12 }}>
        <div className="stack" style={{ gap: 6, minWidth: 0 }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>{s.dept}</span>
          <h2 className="serif" style={{ fontSize: 30, lineHeight: 1.05 }}>{s.name}</h2>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <OutcomeSourceBadge type={s.sourceType} />
          <StatusBadge status={s.status} />
        </div>
      </div>
      <p style={{ fontSize: 16, color: "var(--text-2)" }}>{s.summary}</p>
      <p className="clamp" style={{ fontSize: 15, color: "var(--faint)" }}>{s.expl}</p>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 4 }} aria-hidden>
          {s.pips.map((p, i) => <span key={i} className={`pip p-${p}`} />)}
        </div>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>
          {s.status === "nv" ? "Rules not verified yet" : `${s.met} of ${s.pips.length} criteria met`}
        </span>
      </div>
      {s.missing.length > 0 && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "var(--faint)" }}>Missing:</span>
          {s.missing.map((m) => <span key={m} className="miss">{m}</span>)}
        </div>
      )}
      <div className="row-between" style={{ gap: 12, paddingTop: 14, borderTop: "1px solid var(--line-2)", marginTop: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <SourceLink href={s.url}>Official source</SourceLink>
          <span className="mono" style={{ fontSize: 11, color: "var(--faintest)" }}>{s.lastVerified}</span>
        </div>
        <Link className="btn-ghost" to="/scheme">View details</Link>
      </div>
    </article>
  );
}
