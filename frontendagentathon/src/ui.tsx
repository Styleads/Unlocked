import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CircleCheck,
  CircleDashed,
  CircleHelp,
  CircleX,
  LockKeyholeOpen,
  MapPin,
  RotateCcw,
  ShieldCheck,
  ShieldQuestion,
  SquareArrowOutUpRight,
  Sun,
  Moon,
} from "lucide-react";
import { Link, useRouter } from "./router";
import type { Route } from "./router";
import { useSession } from "./session";
import { useLive } from "./live";
import type { Status } from "./data";

/* ---------- Buttons ---------- */

/** Primary pill with the rotating arrow chip. */
export function ArrowChip({ icon }: { icon?: ReactNode }) {
  return <span className="arr">{icon ?? <ArrowRight size={16} strokeWidth={2.2} aria-hidden />}</span>;
}

export function PrimaryLink({ to, children, className = "" }: { to: Route; children: ReactNode; className?: string }) {
  return (
    <Link to={to} className={`btn ${className}`}>
      {children}
      <ArrowChip />
    </Link>
  );
}

export function BackLink({ to, children = "Back" }: { to: Route; children?: ReactNode }) {
  return (
    <Link to={to} className="back-link">
      <ArrowLeft size={16} aria-hidden />
      {children}
    </Link>
  );
}

export function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a className="src" href={href} target="_blank" rel="noopener noreferrer" title={href}>
      <SquareArrowOutUpRight size={14} aria-hidden />
      {children}
    </a>
  );
}

/* ---------- Theme Switcher ---------- */

export function ThemeSwitcher() {
  const { session, setTheme } = useSession();

  return (
    <div className="theme-select" role="group" aria-label="Theme selection">
      <button
        type="button"
        className={`theme-btn ${session.theme === "sage" ? "on" : ""}`}
        onClick={() => setTheme("sage")}
        title="Light Theme (Soft Green)"
      >
        <Sun size={13} aria-hidden />
        Light
      </button>
      <button
        type="button"
        className={`theme-btn ${session.theme === "dark" ? "on" : ""}`}
        onClick={() => setTheme("dark")}
        title="Dark Theme"
      >
        <Moon size={13} aria-hidden />
        Dark
      </button>
    </div>
  );
}

/* ---------- Status badges ---------- */

const BADGES: Record<Status, { cls: string; icon: ReactNode; label: string; short: string }> = {
  ok: { cls: "b-ok", icon: <CircleCheck size={15} strokeWidth={2.2} aria-hidden />, label: "Potential match", short: "Potential match" },
  info: { cls: "b-info", icon: <CircleHelp size={15} strokeWidth={2.2} aria-hidden />, label: "More info needed", short: "More info needed" },
  nv: { cls: "b-neutral", icon: <ShieldQuestion size={15} strokeWidth={2.2} aria-hidden />, label: "Not yet verified", short: "Not yet verified" },
  unclear: { cls: "b-neutral", icon: <CircleDashed size={15} strokeWidth={2.2} aria-hidden />, label: "Uncertain", short: "Uncertain" },
  warn: { cls: "b-warn", icon: <CircleX size={15} strokeWidth={2.2} aria-hidden />, label: "Unlikely to match", short: "Unlikely" },
};

export const statusLabel = (s: Status, short = false) => (short ? BADGES[s].short : BADGES[s].label);

export function StatusBadge({ status, short, large, className = "" }: { status: Status; short?: boolean; large?: boolean; className?: string }) {
  const b = BADGES[status];
  return (
    <span className={`badge ${b.cls} ${large ? "lg" : ""} ${className}`}>
      {b.icon}
      {short ? b.short : b.label}
    </span>
  );
}

export function OutcomeSourceBadge({ type = "verified", label }: { type?: "verified" | "fallback" | "user-reported" | "simulated"; label?: string }) {
  if (type === "fallback" || type === "simulated") {
    return <span className="source-badge sb-fallback">{label ?? "Fallback · Demo data"}</span>;
  }
  if (type === "user-reported") {
    return <span className="source-badge sb-fallback">{label ?? "User-reported"}</span>;
  }
  return <span className="source-badge sb-verified">{label ?? "Verified official source"}</span>;
}

/* ---------- Header ---------- */

export function Brand({ size = 21 }: { size?: number }) {
  return (
    <Link to="/" className="brand">
      <span className="brand-mark">
        <LockKeyholeOpen size={18} strokeWidth={2.2} aria-hidden />
      </span>
      <span className="serif brand-name" style={{ fontSize: size }}>Unlocked</span>
    </Link>
  );
}

const STEPS: { n: string; label: string; to: Route }[] = [
  { n: "01", label: "Context", to: "/details" },
  { n: "02", label: "Questions", to: "/questions" },
  { n: "03", label: "Results", to: "/results" },
  { n: "04", label: "Plan", to: "/plan" },
];

/** Progress nav for the flow. Steps before `current` are links; later ones are inert. */
export function FlowHeader({ current }: { current: 1 | 2 | 3 | 4 }) {
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <header className="site-header">
        <Brand />
        <nav aria-label="Progress" className="steps">
          {STEPS.map((s, i) => {
            const idx = i + 1;
            const body = (
              <>
                <span className="n">{s.n}</span>
                {s.label}
              </>
            );
            return (
              <span key={s.n} style={{ display: "contents" }}>
                {i > 0 && <span className="sep" aria-hidden />}
                {idx === current ? (
                  <span className="step now" aria-current="step">{body}</span>
                ) : idx < current ? (
                  <Link className="step" to={s.to}>{body}</Link>
                ) : (
                  <span className="step">{body}</span>
                )}
              </span>
            );
          })}
        </nav>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <ThemeSwitcher />
          <button className="btn-ghost" onClick={() => setConfirm(true)} title="Clear all answers and reset">
            <RotateCcw size={15} aria-hidden />
            Delete my data
          </button>
        </div>
      </header>
      {confirm && <StartOverDialog onClose={() => setConfirm(false)} />}
    </>
  );
}

function StartOverDialog({ onClose }: { onClose: () => void }) {
  const { reset } = useSession();
  const live = useLive();
  const { navigate } = useRouter();
  const keepRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    keepRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="scrim fade" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog pop" role="dialog" aria-modal="true" aria-labelledby="so-t">
        <h2 id="so-t" className="serif">Delete session data?</h2>
        <p style={{ color: "var(--muted)" }}>
          In accordance with privacy standards (plan.md), this permanently deletes your session, responses, and saved progress from this browser. This action cannot be undone.
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", flexWrap: "wrap" }}>
          <button ref={keepRef} className="btn-ghost" onClick={onClose}>Keep my session</button>
          <button
            className="btn-danger"
            onClick={() => {
              void live.leave(); // also deletes the server-side session
              reset();
              navigate("/");
            }}
          >
            Delete my data & reset
          </button>
        </div>
      </div>
    </div>
  );
}

export function Disclaimer({ demo }: { demo?: boolean }) {
  return (
    <footer className="site-footer">
      <div>
        <p className="foot-note">
          <ShieldCheck size={15} aria-hidden />
          <span><strong>Assessment, not an official decision.</strong> Unlocked provides automated guidance; government authorities decide eligibility.</span>
        </p>
        <p className="foot-meta">
          <span>© {new Date().getFullYear()} Unlocked{demo ? " · Demo build" : ""}</span>
          <span className="foot-loc"><MapPin size={13} aria-hidden />Based on official Karnataka criteria</span>
        </p>
      </div>
    </footer>
  );
}

export function Intro({ eyebrow, title, children, className = "" }: { eyebrow: ReactNode; title: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <div className={`intro ${className}`}>
      <span className="eyebrow rise">{eyebrow}</span>
      <h1 className="serif display rise d1">{title}</h1>
      {children && <p className="lede rise d2">{children}</p>}
    </div>
  );
}
