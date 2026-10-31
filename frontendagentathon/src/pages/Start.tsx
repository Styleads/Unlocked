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
              <span id="cat-l" style={{ fontSize: 14, color: "var(--muted)", fontWeight: 500 }}>Categories</span>
              <div role="group" aria-labelledby="cat-l" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {CATEGORIES.map((c) => {
                  const on = session.categories[c];
                  return (
                    <button
                      key={c}
                      className={on ? "chip on" : "chip"}
                      aria-pressed={on}
                      onClick={() => update((s) => ({ scope: "guided", categories: { ...s.categories, [c]: !on } }))}
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
              <ScopeText tag="B · BROADER" title="Discover all" body="Check every category at once. Takes a little longer, misses less." />
              <span className={guided ? "dot" : "dot on"}><i /></span>
            </button>
            <div className="hatch" aria-hidden style={{ position: "relative", height: 150, borderRadius: 20, overflow: "hidden", display: "grid", placeItems: "center", border: "1px solid var(--line-2)" }}>
              <span className="ring-ping" />
              <span className="ring-ping r2" />
              <span className="ring-ping r3" />
              <span className="mono" style={{ position: "relative", fontSize: 12, letterSpacing: ".06em", background: "var(--surface)", padding: "8px 14px", borderRadius: 999, color: "var(--primary-dark)", border: "1px solid var(--line-3)", fontWeight: 600 }}>
                ALL {CATEGORIES.length} CATEGORIES
              </span>
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
      <span className="serif" style={{ fontSize: 40, lineHeight: 1 }}>{title}</span>
      <span style={{ fontSize: 16, color: "var(--muted)", maxWidth: 380 }}>{body}</span>
    </span>
  );
}
