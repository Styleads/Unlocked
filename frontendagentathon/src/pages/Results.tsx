import { useMemo, useState } from "react";
import { ArrowUpRight, Check, ChevronDown, TriangleAlert } from "lucide-react";
import { Disclaimer, FlowHeader, OutcomeSourceBadge, PrimaryLink, SourceLink, StatusBadge, statusLabel } from "../ui";
import { Link } from "../router";
import { useSession } from "../session";
import { evaluateAll, improvement } from "../eligibility";
import { forceFallback, useLive } from "../live";
import { fromApiScheme, fromEvaluated, improveFromApi } from "../model";
import type { SchemeVM } from "../model";

type Filter = "all" | SchemeVM["status"];

/** Demo: append ?limited to the URL to see the "live search had trouble" banner. */
const liveSearchFailed = () => new URLSearchParams(window.location.search).has("limited");

export default function Results() {
  const { session } = useSession();
  const live = useLive();
  const [filter, setFilter] = useState<Filter>("all");
  const [showUnlikely, setShowUnlikely] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  // A session that was searched while the live sources were failing keeps its offline results until searched again.
  const searchAgain = async () => {
    setSearching(true);
    setSearchError("");
    const r = await live.discover(session, true);
    setSearching(false);
    if (!r.ok) setSearchError(r.message);
  };
  const hasAnswers = Object.values(session.answers).some((a) => a !== undefined);

  // Everything below comes from one list of schemes (the backend's when connected, else the demo
  // evaluation of the saved answers), so the cards, breakdown, summary and improve card always agree.
  const demo = useMemo(() => evaluateAll(session), [session.answers, session.details]);
  const evals: SchemeVM[] = useMemo(() => (live.active ? live.schemes.map(fromApiScheme) : demo.map(fromEvaluated)), [live.active, live.schemes, demo]);
  const skippedAny = Object.values(live.answers).some((a) => a.state !== "answered");
  const improve = useMemo(
    () => (live.active ? improveFromApi(evals, live.questions, skippedAny) : improvement(demo, session)),
    [live.active, live.questions, evals, skippedAny, demo, session.answers],
  );

  const counts = { ok: 0, info: 0, nv: 0, warn: 0, unclear: 0 };
  evals.forEach((e) => counts[e.status]++);
  const filters: { k: Filter; label: string; count: number }[] = [
    { k: "all", label: "All", count: evals.length },
    ...(["ok", "info", "nv", "unclear", "warn"] as const).filter((k) => counts[k] > 0).map((k) => ({ k, label: statusLabel(k, true), count: counts[k] })),
  ];
  const visible = filter === "all" ? evals.filter((e) => e.status !== "warn" || showUnlikely) : evals.filter((e) => e.status === filter);
  // Unverified schemes are left out of the criteria summary: their rules were never checked.
  const checked = evals.filter((e) => e.verified);
  const totalCriteria = checked.reduce((n, e) => n + e.pips.length, 0);
  const met = checked.reduce((n, e) => n + e.met, 0);
  const unknown = checked.reduce((n, e) => n + e.pips.filter((p) => p === "unk").length, 0);

  return (
    <div className="page">
      <FlowHeader current={3} />
      <main className="main wide">
        <div className="row-between" style={{ alignItems: "flex-end", gap: 24 }}>
          <div className="stack" style={{ gap: 12 }}>
            <span className="eyebrow rise">_ Step 3 of 4 · Results</span>
            <h1 className="serif display rise d1">We found {evals.length} {evals.length === 1 ? "scheme" : "schemes"}.</h1>
            <p className="lede rise d2">Sorted by how well your answers fit. Every card links to its official source.</p>
          </div>
          <PrimaryLink to="/plan" className="rise d2">Build my document plan</PrimaryLink>
        </div>

        {(liveSearchFailed() || (live.active && live.sourceMode === "fallback")) && (
          <div role="status" className="hatch" style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 20px", borderRadius: 20, border: "1px solid var(--line-3)" }}>
            <TriangleAlert size={20} color="var(--warn-text)" aria-hidden style={{ flex: "none" }} />
            <span style={{ fontSize: 15 }}>
              {forceFallback()
                ? <><strong style={{ fontWeight: 600 }}>Demo data is on.</strong> These are the offline fallback schemes (open the site with ?fallback=0 to search live).</>
                : <><strong style={{ fontWeight: 600 }}>Live search had trouble.</strong> Showing limited results. Schemes from fallback data are clearly tagged.</>}{live.active && live.warnings.length > 0 && ` ${live.warnings[0]}`}
              {searchError && <span style={{ display: "block", marginTop: 4, color: "var(--warn-text)" }}>{searchError}</span>}
            </span>
            {live.active && live.sourceMode === "fallback" && !forceFallback() && (
              <button className="btn-ghost" style={{ marginLeft: "auto", background: "var(--surface)" }} onClick={searchAgain} disabled={searching}>
                {searching ? "Searching… this can take a minute" : "Search again"}
              </button>
            )}
          </div>
        )}

        <div className="rise d3" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))", gap: 14 }}>
          <div className="card stack" style={{ padding: 22, gap: 18 }}>
            <div className="row-between">
              <span style={{ fontSize: 15, fontWeight: 600 }}>Status breakdown</span>
              <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>{evals.length} {evals.length === 1 ? "SCHEME" : "SCHEMES"}</span>
            </div>
            <div style={{ display: "flex", gap: 4 }} role="img" aria-label={`${counts.ok} potential match, ${counts.info} need more info, ${counts.nv + counts.unclear} not verified or uncertain, ${counts.warn} unlikely`}>
              <div className="seg s1" style={{ flex: counts.ok, background: "var(--primary)" }} />
              <div className="seg s2" style={{ flex: counts.info, background: "var(--secondary)" }} />
              <div className="seg s3 hatch" style={{ flex: counts.nv + counts.unclear, border: "1px dashed var(--line-4)" }} />
              <div className="seg s4" style={{ flex: counts.warn, background: "var(--warn)" }} />
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13, color: "var(--muted)" }}>
              <LegendItem color="var(--primary-dark)">{counts.ok} match</LegendItem>
              <LegendItem color="var(--secondary-dark)">{counts.info} need info</LegendItem>
              <LegendItem dashed>{counts.nv + counts.unclear} unverified</LegendItem>
              <LegendItem color="var(--warn-text)">{counts.warn} unlikely</LegendItem>
            </div>
          </div>

          <div className="card stack" style={{ padding: 22, gap: 18 }}>
            <div className="row-between">
              <span style={{ fontSize: 15, fontWeight: 600 }}>Criteria checked</span>
              <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>ACROSS ALL</span>
            </div>
            <div className="hatch" style={{ position: "relative", height: 14, borderRadius: 999, overflow: "hidden", border: "1px solid var(--line-2)" }}>
              <div className="seg s2" style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${totalCriteria ? Math.round((met / totalCriteria) * 100) : 0}%`, background: "var(--primary)" }} />
            </div>
            <div className="row-between" style={{ alignItems: "baseline", gap: 12 }}>
              <span className="serif" style={{ fontSize: 27, lineHeight: 1 }}>{met} <span style={{ color: "var(--faintest)" }}>of {totalCriteria} met</span></span>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>{unknown} still unknown</span>
            </div>
          </div>

          <Link
            to={improve.to}
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
            <div className="stack" style={{ gap: 8 }}>
              <span className="serif" style={{ fontSize: 24, lineHeight: 1.05 }}>{improve.title}</span>
              {improve.detail && <span style={{ fontSize: 13, lineHeight: 1.45, color: "var(--muted)" }}>{improve.detail}</span>}
              {improve.cta && <span style={{ fontSize: 13, color: "var(--primary-dark)", fontWeight: 500 }}>{improve.cta}</span>}
            </div>
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
          {visible.map((e, i) => (
            <SchemeCard key={e.id} s={e} delay={Math.min(i + 1, 6)} onOpen={() => live.select(e.id)} />
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

function SchemeCard({ s, delay, onOpen }: { s: SchemeVM; delay: number; onOpen: () => void }) {
  const { status, pips, met, missing, expl } = s;
  return (
    <article className={`card scard rise d${delay}`}>
      <div className="row-between" style={{ alignItems: "flex-start", gap: 12 }}>
        <div className="stack" style={{ gap: 6, minWidth: 0 }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>{s.dept}</span>
          <h2 className="serif" style={{ fontSize: 24, lineHeight: 1.05 }}>{s.name}</h2>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <OutcomeSourceBadge type={s.sourceType} label={s.sourceType === "verified" && !s.verified ? "Official source · rules unverified" : undefined} />
          <StatusBadge status={status} />
        </div>
      </div>
      <p style={{ fontSize: 16, color: "var(--text-2)" }}>{s.summary}</p>
      {expl && <p className="clamp" style={{ fontSize: 15, color: "var(--faint)" }}>{expl}</p>}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 4 }} aria-hidden>
          {pips.map((p, i) => <span key={i} className={`pip p-${p}`} />)}
        </div>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>
          {status === "nv" ? "Rules not verified yet" : `${met} of ${pips.length} criteria met`}
        </span>
      </div>
      {missing.length > 0 && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "var(--faint)" }}>Missing:</span>
          {missing.map((m) => <span key={m} className="miss">{m}</span>)}
        </div>
      )}
      <div className="row-between" style={{ gap: 12, paddingTop: 14, borderTop: "1px solid var(--line-2)", marginTop: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <SourceLink href={s.url}>Official source</SourceLink>
          {s.lastVerified && <span className="mono" style={{ fontSize: 11, color: "var(--faintest)" }}>{s.lastVerified}</span>}
        </div>
        <Link className="btn-ghost" to="/scheme" onClick={onOpen}>View details</Link>
      </div>
    </article>
  );
}
