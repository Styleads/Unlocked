import { useEffect, useState } from "react";
import { FlowHeader, PrimaryLink } from "../ui";
import { useLive } from "../live";
import type { Choice } from "../live";
import type { ApiQuestion } from "../api";
import { Link } from "../router";
import { useSession } from "../session";
import type { Answer } from "../session";
import { QUESTIONS, SCHEMES } from "../data";
import { questionsAffecting } from "../eligibility";

const AFFECTS = SCHEMES.filter((s) => s.verified)
  .map((s) => ({ name: s.name, qs: questionsAffecting(s) }))
  .filter((r) => r.qs !== "");

const CIRC = 213.6; // 2πr for r = 34

function DemoQuestions() {
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

export default function Questions() {
  const live = useLive();
  return live.active ? <LiveQuestions /> : <DemoQuestions />;
}

/** The backend decides which questions are worth asking; this renders whatever it sends, by input type. */
function LiveQuestions() {
  const live = useLive();
  const [order, setOrder] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<{ id: string; message: string } | null>(null);

  const byId = new Map([...live.shown, ...live.questions].map((q) => [q.id, q] as const));
  // Keep positions stable while answering: new questions are appended, answered ones stay where they were.
  useEffect(() => {
    setOrder((o) => {
      const fresh = [...byId.keys()].filter((id) => !o.includes(id));
      return fresh.length ? [...o, ...fresh] : o;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live.shown, live.questions]);

  const list = order.map((id) => byId.get(id)).filter((q): q is ApiQuestion => !!q);
  const answered = list.filter((q) => live.answers[q.attribute]).length;
  const send = async (q: ApiQuestion, c: Choice) => {
    setBusy(q.id);
    setFailed(null);
    try {
      await live.answer(q, c);
    } catch (e) {
      setFailed({ id: q.id, message: e instanceof Error ? e.message : "That answer couldn't be saved." });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page">
      <FlowHeader current={2} />
      <main className="main" style={{ paddingTop: 56, gap: 40 }}>
        <div className="row-between" style={{ alignItems: "flex-end", gap: 24 }}>
          <div className="stack" style={{ gap: 14, maxWidth: 700 }}>
            <span className="eyebrow rise">_ Step 2 of 4 · Questions</span>
            <h1 className="serif rise d1" style={{ fontSize: "clamp(30px, 3.6vw, 48px)", lineHeight: 1 }}>
              {list.length === 0 ? "Nothing more to ask." : `${list.length} ${list.length === 1 ? "question" : "questions"} to sharpen your results.`}
            </h1>
            <p className="lede rise d2">
              {list.length === 0 ? "We have what we need for the schemes we found." : "Answer what you can. Skipping is fine and never counts against you."}
            </p>
          </div>
          <Link className="rise d2" to="/results" style={{ fontSize: 15, minHeight: 44, display: "inline-flex", alignItems: "center", textUnderlineOffset: 4, color: "var(--primary-dark)", fontWeight: 500 }}>
            Show results
          </Link>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 24, alignItems: "flex-start" }}>
          <form onSubmit={(e) => e.preventDefault()} className="stack" style={{ flex: "999 1 600px", minWidth: 0, gap: 14 }}>
            {list.map((q, i) => (
              <LiveQuestion key={q.id} q={q} n={i + 1} answer={live.answers[q.attribute]} busy={busy === q.id} error={failed?.id === q.id ? failed.message : ""} send={(c) => send(q, c)} />
            ))}
            <div className="row-between" style={{ paddingTop: 18 }}>
              <span />
              <PrimaryLink to="/results">See my results</PrimaryLink>
            </div>
          </form>

          <aside className="stack rise d3" style={{ flex: "1 1 300px", gap: 14 }}>
            <div className="card" style={{ padding: 24, display: "flex", alignItems: "center", gap: 20 }}>
              <svg width="84" height="84" viewBox="0 0 84 84" role="img" aria-label={`${answered} of ${list.length} questions answered`}>
                <circle cx="42" cy="42" r="34" fill="none" stroke="var(--line-2)" strokeWidth="8" />
                <circle
                  className="progress-ring" cx="42" cy="42" r="34" fill="none" stroke="var(--primary)" strokeWidth="8" strokeLinecap="round"
                  strokeDasharray={CIRC} style={{ strokeDashoffset: CIRC * (1 - (list.length ? answered / list.length : 1)) }} transform="rotate(-90 42 42)"
                />
              </svg>
              <div className="stack" style={{ gap: 2 }}>
                <span className="serif" style={{ fontSize: 32, lineHeight: 1 }}>
                  {answered} <span style={{ color: "var(--faintest)" }}>/ {list.length}</span>
                </span>
                <span style={{ fontSize: 14, color: "var(--muted)" }}>questions answered</span>
              </div>
            </div>
            <div className="card stack" style={{ padding: 24, gap: 4 }}>
              <span className="label" style={{ paddingBottom: 10 }}>WHAT YOUR ANSWERS AFFECT</span>
              {live.schemes.filter((s) => s.assessment_status !== "not_yet_verified").map((s) => {
                const qs = list.flatMap((q, i) => (q.related_scheme_ids.includes(s.id) ? [`Q${i + 1}`] : []));
                return qs.length ? (
                  <div key={s.id} className="affect-row">
                    <span style={{ fontSize: 15, color: "var(--text-2)" }}>{s.name}</span>
                    <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>{qs.join(" · ")}</span>
                  </div>
                ) : null;
              })}
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

type Shown = { label: string; state: string } | undefined;

function LiveQuestion({ q, n, answer, busy, error, send }: { q: ApiQuestion; n: number; answer: Shown; busy: boolean; error: string; send: (c: Choice) => void }) {
  const [text, setText] = useState("");
  const done = !!answer;
  const isVal = answer?.state === "answered";
  const pick = (label: string, value: unknown) => send({ label, state: "answered", value });

  const options: { label: string; value: unknown }[] =
    q.input_type === "select" ? q.options.map((o) => ({ label: o, value: o }))
    : q.input_type === "boolean" ? [{ label: "Yes", value: true }, { label: "No", value: false }]
    : q.input_type === "range" ? q.ranges.map((r) => ({ label: r.label, value: { min: r.min, max: r.max } }))
    : [];

  const stateText = isVal ? "Answered"
    : answer?.state === "unknown" ? "Marked not sure. That's fine."
    : answer?.state === "prefer_not_to_answer" ? "Kept private. That’s fine."
    : busy ? "Saving…" : "Not answered yet";

  return (
    <fieldset className={done ? "q done" : "q"} disabled={busy}>
      <legend>
        <span style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>Q{n}</span>
          {q.sensitivity === "high" && <span className="sens">SENSITIVE · YOU CAN SKIP THIS</span>}
        </span>
        <span className="serif" style={{ fontSize: 24, lineHeight: 1.1, color: "var(--text)" }}>{q.question}</span>
      </legend>
      <p style={{ fontSize: 14, color: "var(--faint)", clear: "both" }}>
        <span style={{ color: "var(--text-2)", fontWeight: 500 }}>Why we ask:</span> {q.why_asked}
      </p>
      {options.length > 0 ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {options.map((o) => {
            const on = isVal && answer?.label === o.label;
            return (
              <button key={o.label} type="button" className={on ? "opt on" : "opt"} aria-pressed={on} onClick={() => !on && pick(o.label, o.value)}>
                {o.label}
              </button>
            );
          })}
        </div>
      ) : (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            className="inp" style={{ maxWidth: 260 }} type={q.input_type === "number" ? "number" : "text"} aria-label={q.question}
            value={text} onChange={(e) => setText(e.target.value)} placeholder={isVal ? answer?.label : ""}
          />
          <button type="button" className="opt" disabled={text.trim() === ""} onClick={() => pick(text.trim(), q.input_type === "number" ? Number(text) : text.trim())}>
            Save answer
          </button>
        </div>
      )}
      <div className="row-between" style={{ gap: 12, paddingTop: 6, borderTop: "1px solid var(--line-2)" }}>
        <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
          <button type="button" className={answer?.state === "unknown" ? "text-link on" : "text-link"} aria-pressed={answer?.state === "unknown"} onClick={() => send({ label: "Not sure", state: "unknown" })}>
            Not sure
          </button>
          {q.allow_prefer_not_to_answer && (
            <button type="button" className={answer?.state === "prefer_not_to_answer" ? "text-link on" : "text-link"} aria-pressed={answer?.state === "prefer_not_to_answer"} onClick={() => send({ label: "Prefer not to say", state: "prefer_not_to_answer" })}>
              Prefer not to say
            </button>
          )}
        </div>
        <span className={isVal ? "q-state ok" : "q-state"}>{error || stateText}</span>
      </div>
    </fieldset>
  );
}