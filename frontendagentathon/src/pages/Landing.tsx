import { ChartColumn, FileText } from "lucide-react";
import { Brand, Disclaimer, PrimaryLink, StatusBadge, ThemeSwitcher } from "../ui";
import { Link } from "../router";
import type { Status } from "../data";

const EXAMPLE_BARS = [
  { id: "C", pct: 100, color: "var(--primary)", label: "2/2" },
  { id: "A", pct: 67, color: "var(--secondary)", label: "2/3" },
  { id: "B", pct: 34, color: "var(--secondary)", label: "1/3" },
  { id: "D", pct: 20, color: "var(--line-4)", label: "?" },
  { id: "E", pct: 50, color: "var(--warn)", label: "1/2" },
];

const LABELS: { status: Status; text: string }[] = [
  { status: "ok", text: "Your answers appear to meet the criteria we checked." },
  { status: "info", text: "Answer a few questions to check this one." },
  { status: "nv", text: "We couldn't confirm these rules from an official source yet." },
  { status: "unclear", text: "The official wording is ambiguous or uncertain." },
  { status: "warn", text: "One of your answers appears not to meet a stated rule." },
];

const STEPS = [
  { n: "_01", title: "Tell us a little", body: "State, age, education. Only the state is required, and every field says why we ask." },
  { n: "_02", title: "We read the official rules", body: "Each criterion is checked against your answers, and every status links back to its government source." },
  { n: "_03", title: "Get a document plan", body: "Which certificate to get first, what it unlocks, and the official page to apply on." },
];

const PRIVACY = [
  "Only a random session ID is saved in your browser.",
  "Your personal answers never go into links, logs, or persistent tracking.",
  "Delete my data resets your session and erases all inputs immediately.",
];

const wrap = { maxWidth: 1280, margin: "0 auto" } as const;

export default function Landing() {
  return (
    <div className="page">
      <header className="site-header" style={{ padding: "18px var(--gutter)" }}>
        <Brand size={28} />
        <nav aria-label="Main" style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <a className="nav-a" href="#how">How it works</a>
          <a className="nav-a" href="#labels">What the labels mean</a>
          <a className="nav-a" href="#privacy">Privacy</a>
          <ThemeSwitcher />
          <Link className="btn-ghost" to="/start">Get started</Link>
        </nav>
      </header>

      <section className="hero">
        <div className="stack" style={{ gap: 28 }}>
          <span className="eyebrow rise" style={{ letterSpacing: ".04em", display: "flex", alignItems: "center", gap: 10 }}>
            <span className="live-dot" />_ Government benefits · Karnataka
          </span>
          <h1 className="serif rise d1">
            Find the schemes you <em className="underline">may qualify</em> for, and the paperwork to claim them.
          </h1>
          <p className="rise d2" style={{ maxWidth: 520, fontSize: 18, color: "var(--muted)", textWrap: "pretty" }}>
            Unlocked reads the official eligibility rules, asks only what it needs, and turns the result into a document plan you can act on this week.
          </p>
          <div className="rise d3" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <PrimaryLink to="/start">Get started</PrimaryLink>
            <a className="btn-ghost" href="#how">See how it works</a>
          </div>
          <p className="mono rise d4" style={{ fontSize: 12, color: "var(--faintest)" }}>No sign-up. Only your state is required.</p>
        </div>

        <div className="card rise d3" style={{ borderRadius: 30, padding: 28, display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="row-between" style={{ gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ width: 34, height: 34, borderRadius: 999, background: "var(--surface-sunk)", display: "grid", placeItems: "center", color: "var(--primary-dark)" }}>
                <ChartColumn size={16} aria-hidden />
              </span>
              <span style={{ fontSize: 16, fontWeight: 600 }}>Criteria met, by scheme</span>
            </div>
            <span className="tag">Example</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: 14 }}>
            {EXAMPLE_BARS.map((b, i) => (
              <div key={b.id} style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "center" }}>
                <div className="track hatch">
                  <div className="fill" style={{ height: `${b.pct}%`, background: b.color, animationDelay: `${0.5 + i * 0.12}s` }} />
                  <span className="bub">{b.label}</span>
                </div>
                <span className="mono" style={{ fontSize: 12, color: "var(--faint)" }}>{b.id}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <StatusBadge status="ok" />
            <StatusBadge status="info" />
            <StatusBadge status="warn" short />
          </div>
          <div className="callout">
            <span className="callout-icon"><FileText size={18} aria-hidden /></span>
            <span style={{ fontSize: 15, lineHeight: 1.35 }}>
              <strong style={{ fontWeight: 600 }}>Get your Income Certificate first.</strong> Two schemes need it.
            </span>
          </div>
        </div>
      </section>

      <section id="how" className="how">
        <div style={{ ...wrap, padding: "96px var(--gutter)", display: "flex", flexDirection: "column", gap: 56 }}>
          <div className="row-between" style={{ alignItems: "flex-end", gap: 24 }}>
            <h2 className="serif" style={{ fontSize: "clamp(40px, 4.6vw, 64px)", lineHeight: 1, maxWidth: 720, textWrap: "balance" }}>
              Three steps. Forms, not a chat window.
            </h2>
            <span className="mono" style={{ fontSize: 13, color: "var(--faint)" }}>_ How it works</span>
          </div>
          <div className="how-grid">
            {STEPS.map((s) => (
              <div key={s.n} className="how-card">
                <span className="mono" style={{ fontSize: 13, color: "var(--primary-dark)", fontWeight: 600 }}>{s.n}</span>
                <h3 className="serif" style={{ fontSize: 32, lineHeight: 1.05 }}>{s.title}</h3>
                <p style={{ fontSize: 16, color: "var(--text-2)", maxWidth: 340 }}>{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="labels" style={{ ...wrap, padding: "112px var(--gutter)", display: "flex", flexDirection: "column", gap: 48 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(420px, 100%), 1fr))", gap: 32, alignItems: "end" }}>
          <h2 className="serif" style={{ fontSize: "clamp(40px, 4.6vw, 64px)", lineHeight: 1 }}>
            Five labels. <em style={{ color: "var(--primary-dark)" }}>No verdicts.</em>
          </h2>
          <p className="lede" style={{ maxWidth: 520 }}>
            Unlocked never tells you you're eligible. It tells you how your answers line up with the official rules. The authorities make the decision.
          </p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))", gap: 14 }}>
          {LABELS.map((l) => (
            <div key={l.status} className="label-card">
              <StatusBadge status={l.status} className="" />
              <p style={{ fontSize: 15, color: "var(--muted)" }}>{l.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="privacy" style={{ borderTop: "1px solid var(--line)" }}>
        <div style={{ ...wrap, padding: "96px var(--gutter)", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(420px, 100%), 1fr))", gap: 48 }}>
          <div className="stack" style={{ gap: 18 }}>
            <span className="eyebrow">_ Privacy</span>
            <h2 className="serif" style={{ fontSize: "clamp(36px, 4vw, 56px)", lineHeight: 1.02 }}>Your answers stay in this session.</h2>
            <p style={{ fontSize: 15, color: "var(--muted)", maxWidth: 440 }}>
              No permanent profile or Aadhaar required. You can completely wipe every trace of your answers at any point.
            </p>
          </div>
          <div className="stack">
            {PRIVACY.map((p, i) => (
              <div key={p} className="numbered">
                <span className="mono" style={{ fontSize: 13, color: "var(--primary-dark)", fontWeight: 600 }}>{String(i + 1).padStart(2, "0")}</span>
                <p style={{ fontSize: 17 }}>{p}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section style={{ ...wrap, padding: "0 var(--gutter) 96px" }}>
        <div className="hatch row-between" style={{ borderRadius: 32, padding: "clamp(36px, 6vw, 72px)", gap: 32, border: "1px solid var(--line-2)" }}>
          <h2 className="serif" style={{ fontSize: "clamp(40px, 5vw, 72px)", lineHeight: 1, maxWidth: 680 }}>See what's open to you.</h2>
          <PrimaryLink to="/start">Get started</PrimaryLink>
        </div>
      </section>

      <Disclaimer demo />
    </div>
  );
}
