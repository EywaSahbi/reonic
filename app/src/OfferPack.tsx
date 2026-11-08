import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { Action, Plan, RunStep, Variant, VariantName } from "./types";
import "./offerpack.css";

// Installer offer pack (reo/CONTRACT.md v1.1 + harness v1.2): reo's offer agent prepares one quotation, a checklist,
// a draft message and proposed actions; the planner chooses, edits and approves. Nothing runs without a click here.
const eur = (n: number) => "€" + Math.round(n).toLocaleString("en");
const num = (n: number | null | undefined) => (n == null ? "–" : String(Math.round(n * 10) / 10));
const errText = (e: unknown) => String(e instanceof Error ? e.message : e);

export function OfferPackPanel({ plan, onPlan, onDesignChange }: {
  plan: Plan;
  onPlan: (p: Plan) => void; // silent refresh (polling)
  onDesignChange: (p: Plan) => void; // planner action that changes the design (highlight + banner)
}) {
  const pack = plan.offer_pack;
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const quoted = plan.status === "quoted";

  // Poll while reo prepares the pack.
  useEffect(() => {
    if (pack?.status !== "preparing") return;
    const t = setInterval(() => api.getPlan(plan.id).then(onPlan).catch(() => {}), 1200);
    return () => clearInterval(t);
  }, [plan.id, pack?.status]);

  async function act(key: string, f: () => Promise<Plan>, changesDesign = false) {
    setBusy(key);
    setError(null);
    try {
      const next = await f();
      (changesDesign ? onDesignChange : onPlan)(next);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  if (!pack) {
    return (
      <section className="card op-empty">
        <div>
          <h3>Offer pack</h3>
          <p className="muted">reo can prepare a quotation, a site-visit checklist, a draft message and next steps for you to approve.</p>
        </div>
        <button className="btn-primary" disabled={!!busy || quoted} onClick={() => act("prepare", () => api.preparePlan(plan.id))}>Prepare offer pack</button>
      </section>
    );
  }

  const preparing = pack.status === "preparing";
  const model = pack.model === "scripted" ? "Scripted" : pack.model.includes("opus") ? "Opus 5.5" : pack.model.includes("sonnet") ? "Sonnet 5.5" : pack.model;

  return (
    <section className="card op">
      <header className="op-head">
        <div>
          <h3>Offer pack</h3>
          <p className="op-sub">
            {preparing ? <><span className="op-spinner" aria-hidden /> reo is preparing the offer…</>
              : pack.status === "failed" ? "reo could not finish the offer pack."
              : <>reo prepared this in <strong>{num(pack.duration_s)} s</strong></>}
            {pack.model && <span className={`op-model ${pack.model === "scripted" ? "is-scripted" : ""}`}>{model}</span>}
          </p>
        </div>
        {!preparing && !quoted && (
          <button className="btn-ghost small" disabled={!!busy} onClick={() => act("prepare", () => api.preparePlan(plan.id))}>Prepare again</button>
        )}
      </header>

      <RunTimeline runId={pack.run_id} trace={pack.trace} live={preparing} />

      {pack.status === "ready" && (
        <>
          {/* one quotation (reo prepares only the engine's design): no 'pick' badge, nothing to choose between */}
          <div className={`op-variants ${pack.variants.length === 1 ? "is-single" : ""}`}>
            {pack.variants.map((v) => (
              <VariantCard key={v.name} v={v} single={pack.variants.length === 1} recommended={pack.recommended === v.name} chosen={pack.chosen === v.name}
                disabled={!!busy || quoted} busy={busy === `variant-${v.name}`}
                onChoose={() => act(`variant-${v.name}`, () => api.chooseVariant(plan.id, v.name as VariantName), true)} />
            ))}
          </div>

          <div className="op-grid">
            <div>
              <h4>Site-visit checklist</h4>
              <ul className="op-check">{pack.site_visit_checklist.map((c, i) => <li key={i}>{c}</li>)}</ul>
            </div>
            <div>
              <h4>Open questions</h4>
              {pack.open_questions.length ? <ul className="op-list">{pack.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul> : <p className="muted small">None.</p>}
            </div>
          </div>

          <Actions plan={plan} busy={busy} error={error} quoted={quoted} act={act} />
        </>
      )}
      {error && pack.status !== "ready" && <div className="chat-error">{error}</div>}
    </section>
  );
}

function VariantCard({ v, single, recommended, chosen, disabled, busy, onChoose }: {
  v: Variant; single: boolean; recommended: boolean; chosen: boolean; disabled: boolean; busy: boolean; onChoose: () => void;
}) {
  const c = v.design.components;
  const e = v.design.economics;
  const rows: [string, string][] = [
    ["Solar", c.pv.recommended ? `${num(c.pv.size)} kWp` : "–"],
    ["Battery", c.battery.recommended ? `${num(c.battery.size)} kWh` : "–"],
    ["Heat pump", c.heatpump.recommended ? `${num(c.heatpump.size)} kW` : "–"],
    ["Wallbox", c.wallbox.recommended ? `${num(c.wallbox.size)} kW` : "–"],
  ];
  return (
    <article className={`op-variant ${recommended ? "is-recommended" : ""} ${chosen ? "is-chosen" : ""}`}>
      <div className="op-variant-top">
        <h4>{single ? "Quotation" : v.name}</h4>
        {recommended && !single && <span className="pill pill-quoted">reo's pick</span>}
        {v.stale && <span className="pill pill-handed_over" title="Facts changed after reo prepared this">outdated</span>}
      </div>
      <div className="op-price">{eur(v.design.price.total_eur)}</div>
      <dl className="op-rows">
        {rows.map(([k, val]) => <div key={k}><dt>{k}</dt><dd>{val}</dd></div>)}
        <div><dt>Own power</dt><dd>{Math.round(e.autarky_pct)}%</dd></div>
        <div><dt>Payback</dt><dd>{e.payback_years == null ? "–" : `~${Math.round(e.payback_years)} yrs`}</dd></div>
        <div><dt>Range</dt><dd>{eur(v.design.price.range_eur[0])}–{eur(v.design.price.range_eur[1]).slice(1)}</dd></div>
      </dl>
      <p className="op-why">{v.why}</p>
      {!single && <button className={chosen ? "btn-ghost small op-inuse" : "btn-small op-use"} disabled={disabled || chosen} onClick={onChoose}>
        {busy ? "Applying…" : chosen ? "In use" : "Use this variant"}
      </button>}
    </article>
  );
}

const ACTION_ICON: Record<Action["kind"], string> = { book_visit: "Calendar", send_quote: "Quote", create_crm_task: "CRM", request_document: "Request" };

function Actions({ plan, busy, error, quoted, act }: {
  plan: Plan; busy: string | null; error: string | null; quoted: boolean;
  act: (key: string, f: () => Promise<Plan>, changesDesign?: boolean) => void;
}) {
  const pack = plan.offer_pack!;
  const current: VariantName = pack.chosen ?? pack.recommended;
  const [draft, setDraft] = useState(pack.customer_message_draft);
  // Which variant the text in the box describes: reo's draft_for if it sends it, else the variant in use when the draft arrived.
  const [draftFor, setDraftFor] = useState<VariantName>(pack.draft_for ?? current);
  const [edited, setEdited] = useState(false); // planner typed in the box: never overwrite silently
  const [incoming, setIncoming] = useState<string | null>(null); // a newer reo draft held back because of planner edits
  const [slots, setSlots] = useState<string[]>([]);
  const [slot, setSlot] = useState<string>("");
  useEffect(() => {
    const fresh = pack.customer_message_draft;
    if (fresh === draft) return;
    if (edited) { setIncoming(fresh); return; }
    setDraft(fresh);
    setDraftFor(pack.draft_for ?? current);
  }, [pack.customer_message_draft]);
  const stale = draftFor !== current;
  const visit = pack.actions.find((a) => a.kind === "book_visit");
  useEffect(() => {
    if (!visit || visit.status !== "proposed") return;
    api.calendarSlots().then((r) => {
      const proposed = String(visit.payload.slot ?? "");
      setSlots(proposed && !r.slots.includes(proposed) ? [proposed, ...r.slots] : r.slots);
      setSlot(proposed || r.slots[0] || "");
    }).catch(() => {});
  }, [visit?.id, visit?.status]);

  const sendQuote = pack.actions.find((a) => a.kind === "send_quote");
  return (
    <>
      <div className="op-draft">
        <label htmlFor="op-draft"><h4>Message to the customer</h4><span className="muted small">sent with the quote, as you leave it here</span></label>
        {stale && sendQuote?.status === "proposed" && (
          <div className="op-draft-warn" role="status">
            This message was written for the <strong>{draftFor}</strong> offer, but you chose <strong>{current}</strong>. Check the sizes and price before sending.
            {incoming && <button type="button" className="btn-ghost small" onClick={() => { setDraft(incoming); setDraftFor(pack.draft_for ?? current); setIncoming(null); setEdited(false); }}>Use reo's updated message</button>}
          </div>
        )}
        <textarea id="op-draft" rows={4} value={draft} disabled={quoted || sendQuote?.status !== "proposed"}
          onChange={(e) => { setDraft(e.target.value); setEdited(true); setDraftFor(current); }} />
      </div>

      <div>
        <h4>Next steps <span className="muted small">nothing happens until you approve</span></h4>
        <ul className="op-actions">
          {pack.actions.map((a) => {
            const payload = a.kind === "send_quote" ? { message: draft } : a.kind === "book_visit" && slot ? { slot } : undefined;
            return (
              <li key={a.id} className={`op-action is-${a.status}`}>
                <span className="op-kind">{ACTION_ICON[a.kind]}</span>
                <div className="op-action-main">
                  <span>{a.label}</span>
                  {a.kind === "book_visit" && a.status === "proposed" && slots.length > 0 && (
                    <select value={slot} onChange={(e) => setSlot(e.target.value)} aria-label="Visit slot">
                      {slots.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  )}
                  {a.result && <span className="muted small">{a.result}</span>}
                </div>
                {a.status === "proposed" ? (
                  <div className="op-action-btns">
                    <button className="btn-ghost small" disabled={!!busy || quoted} onClick={() => act(`reject-${a.id}`, () => api.rejectAction(plan.id, a.id))}>Reject</button>
                    <button className="btn-small" disabled={!!busy || quoted} onClick={() => act(`approve-${a.id}`, () => api.approveAction(plan.id, a.id, payload))}>
                      {busy === `approve-${a.id}` ? "Running…" : "Approve"}
                    </button>
                  </div>
                ) : (
                  <span className={`pill pill-${a.status === "rejected" ? "drafting" : "quoted"}`}>{a.status}</span>
                )}
              </li>
            );
          })}
        </ul>
        {error && <div className="chat-error">{error}</div>}
      </div>
    </>
  );
}

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
