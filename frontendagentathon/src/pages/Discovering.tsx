import { useCallback, useEffect, useRef, useState } from "react";
import { Check, RotateCcw } from "lucide-react";
import { ArrowChip, FlowHeader, PrimaryLink } from "../ui";
import { useRouter } from "../router";
import { SCHEMES } from "../data";
import { useSession } from "../session";
import { useLive } from "../live";

const LABELS = ["Searching official sources", "Reading eligibility rules", "Checking against your answers"];
const PHASE_TIMES = [1700, 3500, 5200];

/** Demo: append ?error to the URL to see the "couldn't reach sources" state. */
const startsInError = () => new URLSearchParams(window.location.search).has("error");

export default function Discovering() {
  const { session } = useSession();
  const live = useLive();
  const { navigate } = useRouter();
  const [phase, setPhase] = useState(0);
  const [error, setError] = useState(startsInError);
  const [errorDetail, setErrorDetail] = useState("");
  const timers = useRef<number[]>([]);
  // run() must stay stable: the latest session and live store are read through refs
  const latest = useRef({ session, live });
  latest.current = { session, live };

  const run = useCallback((force = false) => {
    timers.current.forEach(clearTimeout);
    setPhase(0);
    setErrorDetail("");
    // With a backend the work really happens in one request: the first step shows as running until it
    // returns, then every step completes together. Nothing is marked done before the backend says so.
    void latest.current.live.discover(latest.current.session, force).then((r) => {
      if (r.ok) return setPhase(3);
      if (r.reason === "unreachable") {
        // No backend: play the demo sequence on the built-in data.
        timers.current = PHASE_TIMES.map((ms, i) => window.setTimeout(() => setPhase(i + 1), ms));
        return;
      }
      setErrorDetail(r.message);
      setError(true);
    });
  }, []);

  useEffect(() => {
    if (!error) run();
    return () => timers.current.forEach(clearTimeout);
  }, [error, run]);

  const retry = () => (error ? setError(false) : run(true));
  const found = live.active ? live.schemes.length : SCHEMES.length;
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
            {errorDetail && <p className="mono" style={{ fontSize: 12, color: "var(--faint)", maxWidth: 440 }}>{errorDetail}</p>}
            <div className="rise d3" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <button className="btn" onClick={retry}>
                Try again
                <ArrowChip icon={<RotateCcw size={16} strokeWidth={2.2} aria-hidden />} />
              </button>
              <button
                className="btn-ghost"
                style={{ minHeight: 52 }}
                onClick={() => {
                  void live.leave();
                  navigate("/questions");
                }}
              >
                Use demo data
              </button>
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
            {/* Always laid out, only hidden until done: the column keeps one height, so the vertically
                centred document card on the right never moves when the result appears. */}
            <div
              className={done ? "pop row-between" : "row-between"}
              aria-hidden={!done}
              style={{ padding: 20, borderRadius: 22, background: "var(--surface)", border: "1px solid var(--line-3)", boxShadow: "var(--shadow-sm)", visibility: done ? "visible" : "hidden" }}
            >
              <div className="stack" style={{ gap: 2 }}>
                <span style={{ fontSize: 17, fontWeight: 600 }}>{found} potential {found === 1 ? "scheme" : "schemes"} identified.</span>
                <span style={{ fontSize: 15, color: "var(--muted)" }}>Answer a few questions to narrow down your matches and check your eligibility.</span>
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {/* Replay is a demo nicety; a real search is not repeated for show */}
                {!live.active && <button className="btn-ghost" onClick={() => run()}>Replay</button>}
                <PrimaryLink to="/questions">Continue</PrimaryLink>
              </div>
            </div>
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
  // Both the line and its label are always in the DOM, so identification is a CSS transition (no layout shift).
  // `delay` only staggers clauses that the same phase identifies; the trigger is still the real phase state.
  const Hit = ({ on, w, flag, delay = 0 }: { on: boolean; w: string; flag: string; delay?: number }) => (
    <div className={on ? "hit on" : "hit"} style={{ ["--hit-delay" as string]: `${delay}s` }}>
      <div className="hit-line" style={{ width: w }} />
      <span className="hit-flag">{flag}</span>
    </div>
  );

  return (
    <div className="card rise d2" aria-hidden style={{ position: "relative", borderRadius: 30, padding: 28, overflow: "hidden", minHeight: 420 }}>
      <div className="row-between" style={{ marginBottom: 26 }}>
        <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>example.gov.in / scheme-notice.pdf</span>
      </div>
      <div className="stack" style={{ gap: 16 }}>
        <div className="doc-line" style={{ width: "58%", height: 14, background: "var(--line-3)" }} />
        <Line w="92%" />
        <Line w="86%" />
        <Hit on={phase >= 2} w="64%" flag="COURSE LEVEL" />
        <Line w="78%" />
        <Line w="90%" hatch />
        <Hit on={phase >= 2} w="52%" flag="INCOME LIMIT" delay={0.5} />
        <Line w="84%" />
        <Line w="70%" />
        <Hit on={phase >= 3} w="40%" flag="DOMICILE" />
        <Line w="88%" />
        <Line w="62%" hatch />
      </div>
      <div className={scanning ? "scan" : "scan off"} />
    </div>
  );
}
