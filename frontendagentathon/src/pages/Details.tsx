import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { BackLink, FlowHeader, PrimaryLink } from "../ui";
import { useSession } from "../session";
import type { Details as DetailsT } from "../session";

const NEXT = [
  "We search official government sources",
  "Read each scheme's eligibility rules",
  "Check them against what you tell us here",
];

export default function Details() {
  const { session, update } = useSession();
  const d = session.details;
  const set = (k: keyof DetailsT) => (e: { target: { value: string } }) =>
    update((s) => ({ details: { ...s.details, [k]: e.target.value } }));

  return (
    <div className="page">
      <FlowHeader current={1} />
      <main className="main" style={{ flexDirection: "row", flexWrap: "wrap", gap: 56, alignItems: "flex-start" }}>
        <div className="stack" style={{ flex: "1 1 340px", gap: 20 }}>
          <span className="eyebrow rise">_ Step 1 of 4 · Your details</span>
          <h1 className="serif display rise d1">A little about you.</h1>
          <p className="lede rise d2" style={{ maxWidth: 400 }}>
            Only your state is required. Every field says why we ask, and anything you leave blank never counts against you.
          </p>
          <div className="stack rise d3" style={{ marginTop: 16, borderTop: "1px solid var(--line-2)" }}>
            <span className="label" style={{ color: "var(--faintest)", padding: "16px 0 6px" }}>WHAT HAPPENS NEXT</span>
            {NEXT.map((t) => (
              <div key={t} style={{ display: "flex", gap: 14, alignItems: "baseline", padding: "10px 0" }}>
                <span className="mono" style={{ fontSize: 12, color: "var(--primary-dark)", fontWeight: 600 }}>→</span>
                <span style={{ fontSize: 15, color: "var(--text-2)" }}>{t}</span>
              </div>
            ))}
          </div>
        </div>

        <form
          className="rise d2"
          onSubmit={(e) => e.preventDefault()}
          style={{ flex: "999 1 520px", minWidth: 0, background: "var(--surface)", border: "1px solid var(--line-2)", borderRadius: 28, padding: "8px 28px 28px", boxShadow: "var(--shadow-sm)" }}
        >
          <Field id="f-state" label="State" required hint="Why we ask: most schemes depend on where you live." first>
            <Select id="f-state" value={d.state} onChange={set("state")} required>
              <option value="Karnataka">Karnataka</option>
              <option value="Other">Another state (limited results)</option>
            </Select>
          </Field>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))", columnGap: 20 }}>
            <Field id="f-district" label="District" hint="Some schemes run in specific districts only.">
              <input id="f-district" className="inp" type="text" placeholder="e.g. Mysuru" value={d.district} onChange={set("district")} />
            </Field>
            <Field id="f-age" label="Age" hint="Pensions and youth schemes set age limits.">
              <input id="f-age" className="inp" type="number" min={0} max={120} inputMode="numeric" value={d.age} onChange={set("age")} />
            </Field>
          </div>

          <Field id="f-edu" label="Education level" hint="Scholarships are usually tied to a course level.">
            <Select id="f-edu" value={d.edu} onChange={set("edu")}>
              <option value="">Choose one</option>
              <option value="10">Class 10</option>
              <option value="12">Class 12 / PUC</option>
              <option value="diploma">Diploma</option>
              <option value="ug">Undergraduate</option>
              <option value="pg">Postgraduate</option>
            </Select>
          </Field>

          <Field id="f-need" label="What do you need help with?" hint="A sentence is enough. It helps us rank what we find.">
            <textarea id="f-need" className="inp" placeholder="e.g. Paying college fees for my first year" value={d.need} onChange={set("need")} />
          </Field>

          <div className="row-between" style={{ paddingTop: 22, borderTop: "1px solid var(--line-2)" }}>
            <BackLink to="/start" />
            <PrimaryLink to="/discovering">Find schemes</PrimaryLink>
          </div>
        </form>
      </main>
    </div>
  );
}

function Field({ id, label, required, hint, first, children }: { id: string; label: string; required?: boolean; hint: string; first?: boolean; children: ReactNode }) {
  return (
    <div className="field" style={first ? { borderTop: 0 } : undefined}>
      <label htmlFor={id}>
        {label} {required ? <span className="req">REQUIRED</span> : <span className="opt-tag">OPTIONAL</span>}
      </label>
      {children}
      <span className="hint">{hint}</span>
    </div>
  );
}

function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="select-wrap">
      <select className="inp" {...props} />
      <ChevronDown size={16} aria-hidden />
    </div>
  );
}
