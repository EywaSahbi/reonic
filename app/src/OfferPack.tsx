import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { RunStep } from "./types";
import "./offerpack.css";

// reo's run timeline ("What reo did"): the steps of a harness run, live over SSE (reo/CONTRACT.md harness v1.2).

function plural(n: number, one: string, many = one + "s") { return `${n} ${n === 1 ? one : many}`; }

/** One readable line per step; raw JSON summaries from read/propose tools become plain words. */
function stepText(s: RunStep): string {
  const raw = (s.result_summary || s.args_summary || "").trim();
  let j: Record<string, unknown> | null = null;
  if (raw.startsWith("{")) { try { j = JSON.parse(raw); } catch { j = null; } }
  switch (s.tool) {
    case "llm": return /tool call/.test(raw) ? `planned next step (${raw})` : raw;
    case "plan.read": return "read the handed-over plan";
    case "evidence.percentile": {
      const n = j && typeof j.n === "number" ? j.n : Number(raw.match(/"n":\s*(\d+)/)?.[1]); // reo truncates long summaries
      return n ? `compared with ${n.toLocaleString("en")} similar homes` : "compared with similar homes";
    }
    case "evidence.similar": return j && Array.isArray(j.projects) ? `looked at ${plural(j.projects.length, "similar home")}` : raw;
    case "calendar.slots": return j && Array.isArray(j.slots) ? `found ${plural(j.slots.length, "free visit slot")}` : "checked the calendar";
    case "plan.propose_variant": return `proposed a variant: ${raw}`;
    case "plan.propose_action": return "proposed a next step (waiting for your approval)";
    case "plan.add_question": return j?.added === "site_visit" ? "added a site-visit check" : "added an open question";
    case "plan.draft_message": return "drafted the message to the customer";
    case "finish": return "finished the offer pack";
  }
  if (j) return raw.length > 90 ? raw.slice(0, 90) + "…" : raw;
  return raw;
}

// Live run timeline: SSE steps from the harness when the pack has a run_id, else the pack's short trace.
export function RunTimeline({ runId, trace, live }: { runId?: string; trace: { step: number; tool: string; summary: string }[]; live: boolean }) {
  const [steps, setSteps] = useState<RunStep[] | null>(null);
  useEffect(() => {
    if (!runId) { setSteps(null); return; }
    setSteps([]);
    return api.watchRun(runId, (s) => setSteps((prev) => [...(prev ?? []).filter((x) => x.n !== s.n), s]), () => {});
  }, [runId]);

  const rows: RunStep[] = useMemo(() => {
    if (steps && steps.length) return steps;
    return trace.map((t) => ({ n: t.step, kind: t.tool === "guard" || t.tool === "grounding" ? "guard" : "tool", tool: t.tool, args_summary: "", result_summary: t.summary, ms: 0 }));
  }, [steps, trace]);

  return (
    <details className="op-trace" open={live}>
      <summary>{live ? "What reo is doing" : `What reo did · ${rows.length} steps`}</summary>
      <ol>
        {rows.map((s) => (
          <li key={s.n} className={`op-step is-${s.kind} ${s.ok === false ? "is-fail" : ""}`}>
            <span className="op-step-dot" aria-hidden>{s.kind === "guard" ? (s.ok === false ? "!" : "✓") : ""}</span>
            <span className="op-step-text">
              {s.kind === "guard"
                ? (s.ok === false ? <><strong>check failed</strong> {s.tool}: {s.result_summary}</> : <><strong>numbers verified</strong> <span className="muted">{s.tool === "grounding" ? "every number matches an engine result" : s.tool}</span></>)
                : s.kind === "think" ? <span className="muted">{stepText(s)}</span>
                : <>{s.tool && <code>{s.tool}</code>} {stepText(s)}</>}
            </span>
            {s.ms > 0 && <span className="op-step-ms">{s.ms < 1000 ? `${s.ms} ms` : `${(s.ms / 1000).toFixed(1)} s`}</span>}
          </li>
        ))}
        {live && <li className="op-step is-live"><span className="op-step-dot" aria-hidden /> <span className="op-step-text muted">working…</span></li>}
      </ol>
    </details>
  );
}
