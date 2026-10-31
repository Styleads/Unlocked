import { FlowHeader, PrimaryLink } from "../ui";
import { Link } from "../router";
import { useSession } from "../session";
import type { Answer } from "../session";
import { QUESTIONS, SCHEMES } from "../data";
import { questionsAffecting } from "../eligibility";

const AFFECTS = SCHEMES.filter((s) => s.verified)
  .map((s) => ({ name: s.name, qs: questionsAffecting(s) }))
  .filter((r) => r.qs !== "");

const CIRC = 213.6; // 2πr for r = 34

export default function Questions() {
  const { session, update } = useSession();
  const ans = session.answers;
  const set = (id: string, v: Answer) =>
    update((s) => ({ answers: { ...s.answers, [id]: s.answers[id] === v ? undefined : v } }));
  const answered = QUESTIONS.filter((q) => ans[q.id] !== undefined).length;
  const total = QUESTIONS.length;

  return (
    <div className="page">
      <FlowHeader current={2} />
      <main className="main" style={{ paddingTop: 56, gap: 40 }}>
        <div className="row-between" style={{ alignItems: "flex-end", gap: 24 }}>
          <div className="stack" style={{ gap: 14, maxWidth: 700 }}>
            <span className="eyebrow rise">_ Step 2 of 4 · Questions</span>
            <h1 className="serif rise d1" style={{ fontSize: "clamp(30px, 3.6vw, 48px)", lineHeight: 1 }}>Four questions to sharpen your results.</h1>
            <p className="lede rise d2">Answer what you can. Skipping is fine and never counts against you.</p>
          </div>
          <Link className="rise d2" to="/results" style={{ fontSize: 15, minHeight: 44, display: "inline-flex", alignItems: "center", textUnderlineOffset: 4, color: "var(--primary-dark)", fontWeight: 500 }}>
            Skip for now, show results
          </Link>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "flex-start" }}>
          <form onSubmit={(e) => e.preventDefault()} className="stack" style={{ flex: "999 1 600px", minWidth: 0, gap: 14 }}>
            {QUESTIONS.map((q, i) => {
              const a = ans[q.id];
              const isVal = a !== undefined && a !== "__unsure" && a !== "__prefer";
              const stateText = isVal
                ? "Answered"
                : a === "__unsure" ? "Marked not sure. That's fine."
                : a === "__prefer" ? "Kept private. That’s fine."
                : "Not answered yet";
              return (
                <fieldset key={q.id} className={a !== undefined ? "q done" : "q"}>
                  <legend>
                    <span style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                      <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>Q{i + 1}</span>
                      {q.sensitive && <span className="sens">SENSITIVE · YOU CAN SKIP THIS</span>}
                    </span>
                    <span className="serif" style={{ fontSize: 24, lineHeight: 1.1, color: "var(--text)" }}>{q.text}</span>
                  </legend>
                  <p style={{ fontSize: 14, color: "var(--faint)", clear: "both" }}>
                    <span style={{ color: "var(--text-2)", fontWeight: 500 }}>Why we ask:</span> {q.why}
                  </p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {q.opts.map((o) => (
                      <button key={o} type="button" className={a === o ? "opt on" : "opt"} aria-pressed={a === o} onClick={() => set(q.id, o)}>
                        {o}
                      </button>
                    ))}
                  </div>
                  <div className="row-between" style={{ gap: 12, paddingTop: 6, borderTop: "1px solid var(--line-2)" }}>
                    <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
                      <button type="button" className={a === "__unsure" ? "text-link on" : "text-link"} aria-pressed={a === "__unsure"} onClick={() => set(q.id, "__unsure")}>
                        Not sure
                      </button>
                      {q.allowPrefer && (
                        <button type="button" className={a === "__prefer" ? "text-link on" : "text-link"} aria-pressed={a === "__prefer"} onClick={() => set(q.id, "__prefer")}>
                          Prefer not to say
                        </button>
                      )}
                    </div>
                    <span className={isVal ? "q-state ok" : "q-state"}>{stateText}</span>
                  </div>
                </fieldset>
              );
            })}

            <div className="row-between" style={{ paddingTop: 18 }}>
              <Link to="/results" style={{ color: "var(--muted)", fontSize: 15, minHeight: 44, display: "inline-flex", alignItems: "center", textUnderlineOffset: 4 }}>
                Skip for now, show results
              </Link>
              <PrimaryLink to="/results">Update my results</PrimaryLink>
            </div>
          </form>

          <aside className="stack rise d3" style={{ flex: "1 1 300px", gap: 14 }}>
            <div className="card" style={{ padding: 24, display: "flex", alignItems: "center", gap: 20 }}>
              <svg width="84" height="84" viewBox="0 0 84 84" role="img" aria-label={`${answered} of ${total} questions answered`}>
                <circle cx="42" cy="42" r="34" fill="none" stroke="var(--line-2)" strokeWidth="8" />
                <circle
                  className="progress-ring" cx="42" cy="42" r="34" fill="none" stroke="var(--primary)" strokeWidth="8" strokeLinecap="round"
                  strokeDasharray={CIRC} style={{ strokeDashoffset: CIRC * (1 - answered / total) }} transform="rotate(-90 42 42)"
                />
              </svg>
              <div className="stack" style={{ gap: 2 }}>
                <span className="serif" style={{ fontSize: 32, lineHeight: 1 }}>
                  {answered} <span style={{ color: "var(--faintest)" }}>/ {total}</span>
                </span>
                <span style={{ fontSize: 14, color: "var(--muted)" }}>questions answered</span>
              </div>
            </div>
            <div className="card stack" style={{ padding: 24, gap: 4 }}>
              <span className="label" style={{ paddingBottom: 10 }}>WHAT YOUR ANSWERS AFFECT</span>
              {AFFECTS.map((r) => (
                <div key={r.name} className="affect-row">
                  <span style={{ fontSize: 15, color: "var(--text-2)" }}>{r.name}</span>
                  <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>{r.qs}</span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
