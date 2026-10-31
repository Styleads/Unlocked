import { Check } from "lucide-react";
import { BackLink, FlowHeader, Intro, PrimaryLink } from "../ui";
import { useSession } from "../session";
import { CATEGORIES } from "../data";

export default function Start() {
  const { session, update } = useSession();
  const guided = session.scope === "guided";
  const count = CATEGORIES.filter((c) => session.categories[c]).length;
  const canGo = !guided || count > 0;

  return (
    <div className="page">
      <FlowHeader current={1} />
      <main className="main">
        <Intro eyebrow="_ Step 1 of 4 · Scope" title="How do you want to search?">
          Pick a few categories to keep results focused, or let us look across everything.
        </Intro>

        <div className="rise d3" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(440px, 100%), 1fr))", gap: 16 }}>
          <div className={guided ? "scope on" : "scope"}>
            <button className="pick" aria-pressed={guided} onClick={() => update({ scope: "guided" })}>
              <ScopeText tag="A · RECOMMENDED" title="Guided discovery" body="Search only the categories you care about. Fewer, sharper results." />
              <span className={guided ? "dot on" : "dot"}><i /></span>
            </button>
            <div className="stack" style={{ gap: 12, paddingTop: 24, borderTop: "1px solid var(--line-2)" }}>
              <span id="cat-l" style={{ fontSize: 14, color: "var(--muted)", fontWeight: 500 }}>
                {guided ? "Categories" : "Categories (not used while searching everything)"}
              </span>
              <div role="group" aria-labelledby="cat-l" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {CATEGORIES.map((c) => {
                  // The saved choice is kept while "Discover all" is active, but only shown as selected in Guided mode.
                  const saved = session.categories[c];
                  const on = guided && saved;
                  return (
                    <button
                      key={c}
                      className={on ? "chip on" : "chip"}
                      aria-pressed={on}
                      disabled={!guided}
                      onClick={() => update((s) => ({ categories: { ...s.categories, [c]: !saved } }))}
                    >
                      {on && <Check size={14} strokeWidth={2.6} aria-hidden />}
                      {c}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className={guided ? "scope" : "scope on"}>
            <button className="pick" aria-pressed={!guided} onClick={() => update({ scope: "all" })}>
              <ScopeText tag="B · BROADER" title="Discover all" body="Explore all five categories." />
              <span className={guided ? "dot" : "dot on"}><i /></span>
            </button>
            <div className="radar" aria-hidden>
              <span className="radar-glow" />
              <span className="ring-ping" />
              <span className="ring-ping r2" />
              <span className="ring-ping r3" />
              <span className="radar-orb">
                {/* A magnifier with a keyhole in the lens: searching, and unlocking. */}
                <svg width="34" height="34" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="14" cy="14" r="8.5" />
                  <path d="M20.5 20.5 27 27" />
                  <circle cx="14" cy="12.5" r="2" />
                  <path d="M14 14.5v4" />
                </svg>
              </span>
              <span className="radar-label">SCANNING ALL {CATEGORIES.length} CATEGORIES</span>
            </div>
          </div>
        </div>

        <div className="row-between rise d4" style={{ paddingTop: 28, borderTop: "1px solid var(--line)" }}>
          <BackLink to="/" />
          {canGo ? (
            <PrimaryLink to="/details">
              {guided ? `Continue with ${count} ${count === 1 ? "category" : "categories"}` : "Continue with everything"}
            </PrimaryLink>
          ) : (
            <span style={{ fontSize: 15, color: "var(--warn-text)", fontWeight: 500 }}>Pick at least one category to continue.</span>
          )}
        </div>
      </main>
    </div>
  );
}

function ScopeText({ tag, title, body }: { tag: string; title: string; body: string }) {
  return (
    <span className="stack" style={{ gap: 10 }}>
      <span className="label">{tag}</span>
      <span className="serif" style={{ fontSize: 32, lineHeight: 1 }}>{title}</span>
      <span style={{ fontSize: 16, color: "var(--muted)", maxWidth: 380 }}>{body}</span>
    </span>
  );
}
