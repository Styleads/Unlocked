import { useState } from "react";
import { Lightbulb } from "lucide-react";
import type { ApiWhatIf } from "../api";
import { useLive } from "../live";
import { statusFromApi } from "../model";
import { SourceLink, StatusBadge } from "../ui";

/**
 * Shown straight after a rejection is reported: which of the user's answers didn't meet which verified rule, which other
 * answer would meet it, and what that answer would do to every scheme. Computed by the backend's assessment code.
 * An answer is changed only when the user says it is true for them; nothing changes on its own.
 */
export default function WhatIfPanel({ data }: { data: ApiWhatIf }) {
  const live = useLive();
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const apply = async (attribute: string, proposed: string, value: unknown) => {
    setBusy(`${attribute}:${proposed}`);
    setError("");
    try {
      // saved like any answer, so every result is reassessed; the plan refreshes in place
      await live.updateAnswer(attribute, proposed, value);
      setApplied((a) => ({ ...a, [attribute]: proposed }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Your answer couldn't be updated.");
    } finally {
      setBusy("");
    }
  };

  const byQuestion = data.changes.reduce<Record<string, ApiWhatIf["changes"]>>((acc, c) => ((acc[c.attribute] ??= []).push(c), acc), {});

  return (
    <div className="stack" style={{ gap: 14, paddingTop: 12, borderTop: "1px solid var(--line-2)" }} aria-label={`What would change the result for ${data.scheme_name}`}>
      <div className="row-between" style={{ gap: 12 }}>
        <span className="label">WHAT DECIDED IT · {data.scheme_name.toUpperCase()}</span>
        <Lightbulb size={17} color="var(--faint)" aria-hidden />
      </div>
      <p style={{ fontSize: 14, color: "var(--muted)" }}>{data.note}</p>

      {data.failed.length > 0 && (
        <ul className="stack" style={{ gap: 10, listStyle: "none", margin: 0, padding: 0 }}>
          {data.failed.map((f) => (
            <li key={f.requirement_id} className="stack" style={{ gap: 2 }}>
              <span style={{ fontSize: 15 }}><strong style={{ fontWeight: 600 }}>{f.label}</strong>{f.your_answer ? `: you answered ${f.your_answer}` : ""}</span>
              <span style={{ fontSize: 14, color: "var(--faint)" }}>Rule: “{f.criterion}”</span>
              {f.source_url && <SourceLink href={f.source_url}>{f.source_url.replace(/^https?:\/\//, "")}</SourceLink>}
            </li>
          ))}
        </ul>
      )}

      {Object.entries(byQuestion).map(([attribute, changes]) => (
        <div key={attribute} className="stack" style={{ gap: 8 }}>
          <span className="label">IF YOUR {changes[0].label.toUpperCase()} WERE…</span>
          {changes.map((c) => {
            const key = `${attribute}:${c.proposed}`;
            const done = applied[attribute] === c.proposed;
            return (
              <div key={key} className="stack" style={{ gap: 6, padding: "10px 14px", borderRadius: 14, border: "1px solid var(--line-2)", background: "var(--surface)" }}>
                <div className="row-between" style={{ gap: 10, flexWrap: "wrap" }}>
                  <strong style={{ fontWeight: 600 }}>{c.proposed}</strong>
                  <span style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, color: "var(--muted)" }}>
                    {data.scheme_name}: <StatusBadge status={statusFromApi(c.target_after)} short />
                  </span>
                </div>
                {c.effects.filter((e) => e.scheme_id !== data.scheme_id).map((e) => (
                  <span key={e.scheme_id} style={{ fontSize: 13, color: "var(--muted)", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    {e.name}: <StatusBadge status={statusFromApi(e.before)} short /> → <StatusBadge status={statusFromApi(e.after)} short />
                  </span>
                ))}
                <div className="nx-row">
                  <button className="btn-ghost nx-sm" onClick={() => apply(attribute, c.proposed, c.value)} disabled={!!busy || done}>
                    {done ? "Answer updated" : busy === key ? "Updating…" : "This is true for me: update my answer"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ))}

      {data.changes.length > 0 && data.all_fixed_status && Object.keys(byQuestion).length > 1 && (
        <p style={{ fontSize: 14, color: "var(--muted)", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          With a fitting answer to every question above, {data.scheme_name} would be <StatusBadge status={statusFromApi(data.all_fixed_status)} short />
        </p>
      )}
      {data.unanswered.length > 0 && <p style={{ fontSize: 14, color: "var(--muted)" }}>Still unanswered for this scheme: {data.unanswered.join(", ")}.</p>}

      {data.already_matching.length > 0 && (
        <div className="stack" style={{ gap: 6 }}>
          <span className="label">SCHEMES THAT ALREADY FIT YOUR ANSWERS</span>
          <ul className="nx-docs">{data.already_matching.map((s) => <li key={s.scheme_id}>{s.name}</li>)}</ul>
        </div>
      )}
      {Object.keys(applied).length > 0 && <p role="status" style={{ fontSize: 14, color: "var(--primary-dark)" }}>Your results have been updated with the new answer.</p>}
      {error && <p role="alert" style={{ fontSize: 14, color: "var(--warn-text)" }}>{error}</p>}
      <p style={{ fontSize: 13, color: "var(--faint)" }}>Change an answer only if it is true for you: the office checks your documents. These are Unlocked's estimates, not official decisions.</p>
    </div>
  );
}
