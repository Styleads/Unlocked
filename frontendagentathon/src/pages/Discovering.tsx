import { useCallback, useEffect, useRef, useState } from "react";
import { Check, RotateCcw } from "lucide-react";
import { ArrowChip, FlowHeader, PrimaryLink } from "../ui";
import { Link } from "../router";
import { SCHEMES } from "../data";

const LABELS = ["Searching official sources", "Reading eligibility rules", "Checking against your answers"];
const PHASE_TIMES = [1700, 3500, 5200];

/** Demo: append ?error to the URL to see the "couldn't reach sources" state. */
const startsInError = () => new URLSearchParams(window.location.search).has("error");

export default function Discovering() {
  const [phase, setPhase] = useState(0);
  const [error, setError] = useState(startsInError);
  const timers = useRef<number[]>([]);

  const run = useCallback(() => {
    timers.current.forEach(clearTimeout);
    setPhase(0);
    timers.current = PHASE_TIMES.map((ms, i) => window.setTimeout(() => setPhase(i + 1), ms));
  }, []);

  useEffect(() => {
    if (!error) run();
    return () => timers.current.forEach(clearTimeout);
  }, [error, run]);

  const retry = () => (error ? setError(false) : run());
  const done = !error && phase >= 3;

  return (
    <div className="page">
      <FlowHeader current={2} />
      <main
        className="main"
        style={{ paddingTop: 72, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(460px, 100%), 1fr))", gap: 56, alignItems: "center" }}
      >
        {error ? (
          <div className="stack" style={{ gap: 24 }}>
            <span className="eyebrow rise" style={{ color: "var(--warn-text)", fontWeight: 600 }}>_ Search interrupted</span>
            <h1 className="serif display rise d1">We couldn't reach the official sources.</h1>
            <p className="lede rise d2" style={{ maxWidth: 440 }}>
              This is usually temporary. Your details are saved, so trying again won't ask you anything twice.
            </p>
            <div className="rise d3" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button className="btn" onClick={retry}>
                Try again
                <ArrowChip icon={<RotateCcw size={16} strokeWidth={2.2} aria-hidden />} />
              </button>
              <Link className="btn-ghost" to="/questions" style={{ minHeight: 52 }}>Use demo data</Link>
            </div>
          </div>
        ) : (
          <div className="stack" style={{ gap: 28 }}>
            <div className="stack" style={{ gap: 16 }}>
              <span className="eyebrow rise">_ Discovering</span>
              <h1 className="serif display rise d1">Reading the fine print for you.</h1>
              <p className="lede rise d2" style={{ maxWidth: 440 }}>
                We only use official sources. If a rule can't be confirmed, we'll say so instead of guessing.
              </p>
            </div>
            <div className="stack rise d3" aria-live="polite" style={{ borderBottom: "1px solid var(--line-2)" }}>
              {LABELS.map((label, i) => {
                const isDone = phase > i;
                const isRun = phase === i;
                return (
                  <div key={label} className={isDone || isRun ? "disc-row" : "disc-row wait"}>
                    {isDone ? (
                      <span className="ico okc"><Check size={16} strokeWidth={2.6} aria-hidden /></span>
                    ) : isRun ? (
                      <span className="ico"><span className="spin" /></span>
                    ) : (
                      <span className="ico pend" />
                    )}
                    <span style={{ flex: 1, fontSize: 17, color: "var(--text)" }}>{label}</span>
                    <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>
                      {isDone ? "done" : isRun ? "in progress" : "waiting"}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="bar" role="progressbar" aria-label="Discovery progress" aria-valuemin={0} aria-valuemax={3} aria-valuenow={phase}>
              <i style={{ width: `${Math.round((phase / 3) * 100)}%` }} />
            </div>
            {done && (
              <div className="pop row-between" style={{ padding: 20, borderRadius: 22, background: "var(--surface)", border: "1px solid var(--line-3)", boxShadow: "var(--shadow-sm)" }}>
                <div className="stack" style={{ gap: 2 }}>
                  <span style={{ fontSize: 17, fontWeight: 600 }}>Found {SCHEMES.length} schemes.</span>
                  <span style={{ fontSize: 15, color: "var(--muted)" }}>A few questions will sharpen the results.</span>
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <button className="btn-ghost" onClick={run}>Replay</button>
                  <PrimaryLink to="/questions">Continue</PrimaryLink>
                </div>
              </div>
            )}
          </div>
        )}

        <SourceDoc phase={error ? 0 : phase} scanning={!error && phase < 3} />
      </main>
    </div>
  );
}

/** Abstract official notice being "read"; criteria light up as the phases complete. */
function SourceDoc({ phase, scanning }: { phase: number; scanning: boolean }) {
  const Line = ({ w, hatch }: { w: string; hatch?: boolean }) => <div className={hatch ? "doc-line hatch" : "doc-line"} style={{ width: w }} />;
  const Hit = ({ on, w, flag }: { on: boolean; w: string; flag: string }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      {on ? (
        <>
          <div className="hl" style={{ width: w }} />
          <span className="flag">{flag}</span>
        </>
      ) : (
        <Line w={w} />
      )}
    </div>
  );

  return (
    <div className="card rise d2" aria-hidden style={{ position: "relative", borderRadius: 30, padding: 28, overflow: "hidden", minHeight: 420 }}>
      <div className="row-between" style={{ marginBottom: 26 }}>
        <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>example.gov.in / scheme-notice.pdf</span>
        <span className="mono" style={{ fontSize: 11, padding: "4px 9px", borderRadius: 999, color: "var(--muted)", background: "var(--surface-sunk)" }}>p. 2</span>
      </div>
      <div className="stack" style={{ gap: 16 }}>
        <div className="doc-line" style={{ width: "58%", height: 14, background: "var(--line-3)" }} />
        <Line w="92%" />
        <Line w="86%" />
        <Hit on={phase >= 2} w="64%" flag="COURSE LEVEL" />
        <Line w="78%" />
        <Line w="90%" hatch />
        <Hit on={phase >= 2} w="52%" flag="INCOME LIMIT" />
        <Line w="84%" />
        <Line w="70%" />
        <Hit on={phase >= 3} w="40%" flag="DOMICILE" />
        <Line w="88%" />
        <Line w="62%" hatch />
      </div>
      {scanning && <div className="scan" />}
    </div>
  );
}
