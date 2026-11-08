import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api, USING_MOCK } from "./api";
import { getInstallerToken, setInstallerToken } from "./auth";
import { RunTimeline } from "./OfferPack";
import { SonnfeldMark } from "./Logo";
import { ReoAvatar } from "./ReoAvatar";
import { MicButton, voiceForced } from "./Voice";
import "./installer.css";

const DesignStudio = lazy(() => import("./scene/DesignStudio"));
import { COMPONENT_KEYS, isOffline, type ComponentKey, type Design, type HomeFacts, type Locks, type Plan, type PlanSummary, type PriceList } from "./types";

const NAMES: Record<ComponentKey, string> = { pv: "PV", battery: "Battery", heatpump: "Heat pump", wallbox: "Wallbox" };
const eur = (n: number) => "€" + Math.round(n).toLocaleString("en");
const errText = (e: unknown) => String(e instanceof Error ? e.message : e);
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

// Installer view: inbox of handed-over plans -> plan detail with edits, "ask reo why", finalise.
export function Installer() {
  const remote = !USING_MOCK && !["localhost", "127.0.0.1", "[::1]"].includes(new URL(import.meta.env.VITE_API_URL).hostname);
  const [unlocked, setUnlocked] = useState(() => !remote || !!getInstallerToken());
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);
  useEffect(() => {
    const denied = () => { setUnlocked(false); setError("Your planner access token is missing or invalid."); };
    window.addEventListener("reo-installer-unauthorized", denied);
    return () => window.removeEventListener("reo-installer-unauthorized", denied);
  }, []);
  if (unlocked) return <InstallerWorkspace onLock={!USING_MOCK ? () => { setInstallerToken(""); setToken(""); setUnlocked(false); } : undefined} />;
  return <main className="planner-access card"><SonnfeldMark /><h1>Planner access</h1>
    <p>Enter the access token provided by your team. It stays in this browser tab for the current session.</p>
    <form onSubmit={async (e) => { e.preventDefault(); setChecking(true); setError(""); setInstallerToken(token);
      try { await api.listPlans(); setToken(""); setUnlocked(true); }
      catch { setInstallerToken(""); setError("Could not unlock the planner. Check the token and backend connection."); }
      finally { setChecking(false); }
    }}><label>Access token<input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} required disabled={checking} /></label>
      {error && <p role="alert">{error}</p>}<button className="btn-primary" disabled={checking || !token.trim()}>{checking ? "Checking…" : "Unlock planner"}</button>
    </form><a href="#/">Back to customer site</a></main>;
}

function InstallerWorkspace({ onLock }: { onLock?: () => void }) {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  // deleting asks in the page's own dialog, not the browser's (EywaSahbi)
  const [confirming, setConfirming] = useState<PlanSummary | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  async function remove(p: PlanSummary) {
    setDeleting(p.id);
    setDeleteError(null);
    try {
      await api.deletePlan(p.id);
      setPlans((ps) => ps.filter((x) => x.id !== p.id));
      setSelected((s) => (s === p.id ? null : s));
      setConfirming(null);
    } catch (e) {
      setDeleteError(`Could not delete the plan: ${errText(e)}`);
    } finally {
      setDeleting(null);
    }
  }
  useEffect(() => {
    if (!confirming) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setConfirming(null); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [confirming]);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.listPlans().then((ps) => {
        if (!alive) return;
        const visible = ps.filter((p) => p.status !== "drafting");
        setPlans(visible);
        setSelected((s) => s ?? visible[0]?.id ?? null);
      }).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="inst">
      <header className="inst-nav">
        <div className="brand"><SonnfeldMark /> Sonnfeld</div>
        <span className="inst-tag">reo · powered by Reonic</span>
        {onLock && <button className="btn-ghost small" onClick={onLock}>Lock planner</button>}
        <a className="inst-link" href="#/">Customer site →</a>
      </header>
      <div className="inst-body">
        <aside className="inbox" aria-label="Handed-over plans">
          <h2>Inbox</h2>
          {plans.length === 0 && <p className="muted">No plans yet. Hand one over from the customer site.</p>}
          <ul>
            {plans.map((p) => (
              <li key={p.id}>
                <button className={`inbox-item ${selected === p.id ? "active" : ""}`} onClick={() => setSelected(p.id)}>
                  <span className="inbox-name">{p.customer.name ?? "Unnamed"}</span>
                  <span className={`pill pill-${p.status}`}>{p.status === "quoted" ? "quoted" : "new"}</span>
                  <span className="inbox-meta">{p.total_eur > 0 ? eur(p.total_eur) : "no price yet"} · {when(p.updated_at)}</span>
                </button>
                <button className="inbox-delete" onClick={() => { setDeleteError(null); setConfirming(p); }} disabled={deleting === p.id}
                  aria-label={`Delete plan for ${p.customer.name ?? "unnamed customer"}`} title="Delete plan">
                  <svg viewBox="0 0 24 24" aria-hidden><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" /></svg>
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <main className="detail">{selected ? <PlanDetail key={selected} id={selected} /> : <p className="muted">Select a plan.</p>}</main>
      </div>
      {confirming && (
        <div className="confirm-backdrop" onClick={() => setConfirming(null)}>
          <div className="confirm-dialog card" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" onClick={(e) => e.stopPropagation()}>
            <h3 id="confirm-title">Delete this plan?</h3>
            <p>The plan for <b>{confirming.customer.name ?? "this customer"}</b> will be removed from your inbox. This can't be undone.</p>
            {deleteError && <p className="confirm-error" role="alert">{deleteError}</p>}
            <div className="confirm-actions">
              <button className="btn-ghost" onClick={() => setConfirming(null)} autoFocus>Cancel</button>
              <button className="btn-primary confirm-delete" onClick={() => remove(confirming)} disabled={deleting === confirming.id}>
                {deleting === confirming.id ? "Deleting…" : "Delete plan"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

type Change = { keys: Set<string>; text: string };

// What changed between two designs, as before → after (engine numbers only, no arithmetic).
function diff(a: Design, b: Design): Change {
  const keys = new Set<string>();
  const parts: string[] = [];
  for (const k of COMPONENT_KEYS) {
    const x = a.components[k], y = b.components[k];
    if (x.recommended !== y.recommended || x.size !== y.size) {
      keys.add(k);
      const fmt = (c: typeof x) => (c.recommended && c.size !== null ? `${c.size} ${c.unit}` : "none");
      parts.push(`${NAMES[k]} ${fmt(x)} → ${fmt(y)}`);
    }
  }
  if (a.price.total_eur !== b.price.total_eur) { keys.add("total"); parts.push(`total ${eur(a.price.total_eur)} → ${eur(b.price.total_eur)}`); }
  if (a.economics.payback_years !== b.economics.payback_years) { keys.add("payback"); parts.push(`ROI ${a.economics.payback_years ?? "–"} → ${b.economics.payback_years ?? "–"} yrs`); }
  if (a.economics.annual_savings_eur !== b.economics.annual_savings_eur) keys.add("savings");
  return { keys, text: parts.length ? parts.join(" · ") : "No change to the design." };
}

function PlanDetail({ id }: { id: string }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [change, setChange] = useState<Change | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => { api.getPlan(id).then(setPlan).catch((e) => setError(errText(e))); }, [id]);

  async function edit(body: { locks?: Locks; facts?: Partial<HomeFacts>; prices?: PriceList }) {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.editPlan(plan.id, body);
      setChange(diff(plan.design, next.design));
      setPlan(next);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function finalize() {
    if (!plan) return;
    setBusy(true);
    try {
      setPlan(await api.finalizePlan(plan.id, note.trim() || undefined));
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!plan) return <p className="muted">{error ?? "Loading…"}</p>;
  const d = plan.design;
  const quoted = plan.status === "quoted";
  const hl = (k: string) => (change?.keys.has(k) ? "changed" : "");

  return (
    <div className={`plan-detail ${busy ? "is-busy" : ""}`}>
      <div className="detail-head">
        <div>
          <span className={`pill pill-${plan.status}`}>{quoted ? "Quote sent" : "Handed over"}</span>
          <h1>{plan.customer.name ?? "Unnamed customer"}</h1>
          <span className="muted">{plan.customer.email ?? "no email given"} · updated {when(plan.updated_at)}</span>
        </div>
        <div className={`detail-total ${hl("total")}`}>
          <span className="muted">Total</span>
          {isOffline(d) ? <strong>–</strong> : <>
            <strong>{eur(d.price.total_eur)}</strong>
          </>}
        </div>
      </div>

      <Summary plan={plan} />

      {isOffline(d) && <div className="flag flag-warn">⚠ Design engine unreachable: no sizes or prices in this plan yet. Edits and finalise need the engine.</div>}


      {change && (
        <div className="change-banner" role="status">
          <strong>Re-derived:</strong> {change.text}
          <button className="icon-btn" onClick={() => setChange(null)} aria-label="Dismiss">×</button>
        </div>
      )}
      {error && <div className="chat-error">{error}</div>}

      <Suspense fallback={<section className="card studio"><p className="muted">Loading design studio…</p></section>}>
        <DesignStudio design={d} facts={plan.facts} disabled={quoted || busy || isOffline(d)} onApply={(locks, prices) => edit({ locks, ...(prices ? { prices } : {}) })} />
      </Suspense>

      <div className="detail-grid">

        <section className="card">
          <h3>Price breakdown</h3>
          <table className="price-table">
            <tbody>
              {d.price.items.map((i) => (
                <tr key={i.label}><td>{i.label}</td><td className="num">{i.qty} {i.unit}</td><td className="num">{eur(i.unit_price_eur)}</td><td className="num">{eur(i.total_eur)}</td></tr>
              ))}
              <tr className={`price-total ${hl("total")}`}><td colSpan={3}>Total</td><td className="num">{eur(d.price.total_eur)}</td></tr>
            </tbody>
          </table>
        </section>

        <div className="detail-col">
          <AskReo id={plan.id} />
          <NextSteps plan={plan} onPlan={setPlan} />
        </div>
      </div>

      {/* the offer pack no longer carries a send-quote step: the planner finalises here (EywaSahbi) */}
      <section className="card finalize">
        {quoted ? (
          <p><strong>Quote sent.</strong> The customer now sees the confirmed plan and price on the website.</p>
        ) : (
          <>
            <label htmlFor="note">Note to the customer <span className="muted">(optional, sent as written)</span></label>
            <textarea id="note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="e.g. We checked your roof photos; 12 kWh fits your evening usage better." />
            <button className="btn-primary" onClick={finalize} disabled={busy || isOffline(d)}>Finalise and send quote · {eur(d.price.total_eur)}</button>
          </>
        )}
      </section>
    </div>
  );
}

// Planner summary (EywaSahbi): ordered sections built from the plan's facts and the engine's design (numbers rounded only).
const FIELD_LABEL: Partial<Record<string, string>> = {
  total_demand_kwh: "Yearly electricity use", annual_demand_kwh: "Household electricity use", num_inhabitants: "Household size",
  heating_type: "Heating", heating_demand_kwh: "Heat demand", has_ev: "Electric car", ev_planned: "Planned electric car",
  has_existing_pv: "Existing solar", existing_pv_kwp: "Existing solar size", roof_area_sqm: "Roof area", roof_orientation_deg: "Roof orientation",
  roof_tilt_deg: "Roof tilt", roof_type: "Roof shape", region: "Federal state", house_size_sqm: "Living space",
  electricity_price_eur_per_kwh: "Electricity tariff", building_type: "Type of house", budget_eur: "Budget",
};
const HEATING: Record<string, string> = { gas: "Gas", oil: "Oil", heatpump: "Heat pump", electric: "Electric", district: "District heating", other: "Other" };
const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

function Summary({ plan }: { plan: Plan }) {
  const f = plan.facts, d = plan.design, c = d.components;
  const use = f.total_demand_kwh ?? f.annual_demand_kwh;
  const home: [string, string][] = [
    ["Household", f.num_inhabitants ? `${f.num_inhabitants} ${f.num_inhabitants === 1 ? "person" : "people"}` : "–"],
    ["Electricity use", use ? `${Math.round(use).toLocaleString("en")} kWh/yr` : `about ${Math.round(d.economics.total_demand_kwh).toLocaleString("en")} kWh/yr (estimated)`],
    ["Heating", f.heating_type ? HEATING[f.heating_type] ?? f.heating_type : "unknown"],
    ["Electric car", f.has_ev ? "yes" : f.ev_planned ? "planned" : f.has_ev === false ? "no" : "unknown"],
    ["Roof", [f.roof_area_sqm ? `${f.roof_area_sqm} m²` : null, f.region].filter(Boolean).join(", ") || "not measured"],
  ];
  if (f.electricity_price_eur_per_kwh) home.push(["Tariff", `${Math.round(f.electricity_price_eur_per_kwh * 100)} ct/kWh`]);
  const offline = isOffline(d);
  const proposal: [string, string][] = offline ? [] : [
    ["Solar", c.pv.recommended && c.pv.size ? `${Math.round(c.pv.size * 10) / 10} kWp${c.pv.quantity ? ` · ${c.pv.quantity} modules` : ""}` : "–"],
    ["Battery", c.battery.recommended && c.battery.size ? `${Math.round(c.battery.size * 10) / 10} kWh` : "–"],
    ["Heat pump", c.heatpump.recommended && c.heatpump.size ? `${c.heatpump.size} kW` : "–"],
    ["Wallbox", c.wallbox.recommended && c.wallbox.size ? `${c.wallbox.size} kW` : "–"],
    ["Price", eur(d.price.total_eur)],
    ["ROI", d.economics.payback_years != null ? `about ${Math.round(d.economics.payback_years)} years` : "–"],
  ];
  const check = d.missing_inputs.filter((m) => m.impact !== "low");
  return (
    <section className="card summary">
      <h3 className="installer-reo-heading"><ReoAvatar size={52} outfit="vest" greet={false} interactive title="reo" />Summary</h3>
      <div className="summary-grid">
        <div><h4>Home</h4><dl className="summary-dl">{home.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></div>
        {!offline && <div><h4>Proposal</h4><dl className="summary-dl">{proposal.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></div>}
      </div>
      <div className="summary-grid summary-lists">
      {d.assumptions.length > 0 && <div className="summary-list"><h4>Assumed</h4><ul>{d.assumptions.map((a, i) => <li key={i}>{cap(a.note || String(a.field).replace(/_/g, " "))}</li>)}</ul></div>}
      {check.length > 0 && <div className="summary-list"><h4>To check</h4><ul>{check.map((m) => <li key={String(m.field)}><b>{FIELD_LABEL[String(m.field)] ?? cap(String(m.field).replace(/_/g, " "))}</b>: {m.why}</li>)}</ul></div>}
      </div>
    </section>
  );
}


const REGIONS = ["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"];

const FACT_FIELDS: { key: keyof HomeFacts; label: string; type: "number" | "heating" | "bool" | "region" }[] = [
  { key: "total_demand_kwh", label: "Total demand (kWh/yr)", type: "number" },
  { key: "num_inhabitants", label: "People", type: "number" },
  { key: "heating_type", label: "Heating", type: "heating" },
  { key: "ev_planned", label: "EV planned", type: "bool" },
  { key: "has_ev", label: "Has EV", type: "bool" },
  { key: "roof_area_sqm", label: "Roof area (m²)", type: "number" },
  { key: "region", label: "Federal state", type: "region" },
  { key: "house_size_sqm", label: "Living space (m²)", type: "number" },
  { key: "electricity_price_eur_per_kwh", label: "Tariff (€/kWh)", type: "number" },
];


// reo's proposed next steps from the offer pack (site visit, CRM follow-up, document request). Nothing runs until the
// planner approves; the quote itself goes out with "Finalise and send quote" below (EywaSahbi).
const STEP_KIND: Record<string, string> = { book_visit: "Calendar", create_crm_task: "CRM", request_document: "Request" };
function NextSteps({ plan, onPlan }: { plan: Plan; onPlan: (p: Plan) => void }) {
  const pack = plan.offer_pack;
  const steps = (pack?.actions ?? []).filter((a) => a.kind !== "send_quote");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slots, setSlots] = useState<string[]>([]);
  const [slot, setSlot] = useState("");
  const visit = steps.find((a) => a.kind === "book_visit");
  useEffect(() => {
    if (!visit || visit.status !== "proposed") return;
    api.calendarSlots().then((r) => {
      const proposed = String(visit.payload.slot ?? "");
      setSlots(proposed && !r.slots.includes(proposed) ? [proposed, ...r.slots] : r.slots);
      setSlot(proposed || r.slots[0] || "");
    }).catch(() => {});
  }, [visit?.id, visit?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  async function act(key: string, f: () => Promise<Plan>) {
    setBusy(key); setError(null);
    try { onPlan(await f()); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  if (!pack) return null;
  return (
    <section className="card next-steps">
      <h3>Next steps <span className="muted small">nothing happens until you approve</span></h3>
      {pack.status === "preparing" ? <p className="muted small">reo is preparing the next steps…</p>
        : steps.length === 0 ? <p className="muted small">No steps proposed.</p> : (
        <ul className="op-actions">
          {steps.map((a) => (
            <li key={a.id} className={`op-action is-${a.status}`}>
              <span className="op-kind">{STEP_KIND[a.kind] ?? a.kind}</span>
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
                  <button className="btn-ghost small" disabled={!!busy} onClick={() => act(`reject-${a.id}`, () => api.rejectAction(plan.id, a.id))}>Reject</button>
                  <button className="btn-small" disabled={!!busy} onClick={() => act(`approve-${a.id}`, () => api.approveAction(plan.id, a.id, a.kind === "book_visit" && slot ? { slot } : undefined))}>
                    {busy === `approve-${a.id}` ? "Running…" : "Approve"}
                  </button>
                </div>
              ) : (
                <span className={`pill pill-${a.status === "rejected" ? "drafting" : "quoted"}`}>{a.status}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <div className="chat-error">{error}</div>}
    </section>
  );
}

function AskReo({ id }: { id: string }) {
  const [q, setQ] = useState("");
  const [qa, setQa] = useState<{ q: string; a: string; runId?: string; voice?: boolean }[]>([]);
  const [busy, setBusy] = useState(false);
  const [voiceOn, setVoiceOn] = useState(voiceForced());
  const [note, setNote] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState<number | null>(null); // index of the answer being read aloud
  const player = useRef<HTMLAudioElement | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { api.health().then((h) => setVoiceOn((v) => v || h.voice)).catch(() => {}); }, []);
  useEffect(() => { if (qa.length) end.current?.scrollIntoView({ block: "nearest" }); }, [qa]);
  useEffect(() => () => { player.current?.pause(); }, []);

  function stopSpeaking() { player.current?.pause(); player.current = null; setSpeaking(null); }
  function play(src: string, i: number) {
    stopSpeaking();
    const el = new Audio(src);
    player.current = el;
    el.onended = el.onerror = () => setSpeaking(null);
    setSpeaking(i);
    el.play().catch(() => setSpeaking(null));
  }
  async function readAloud(i: number) {
    if (speaking === i) { stopSpeaking(); return; }
    const blob = await api.speak(qa[i].a).catch(() => null);
    if (blob) play(URL.createObjectURL(blob), i); else setNote("Voice isn't available right now.");
  }
  async function ask(text: string) {
    if (!text.trim()) return;
    setBusy(true); setNote(null); stopSpeaking();
    try {
      const { answer, run_id } = await api.askPlan(id, text);
      setQa((x) => [...x, { q: text, a: answer, runId: run_id }]);
      setQ("");
    } catch (e) {
      setQa((x) => [...x, { q: text, a: `Error: ${errText(e)}` }]);
    } finally {
      setBusy(false);
    }
  }
  async function askByVoice(audio: Blob) {
    setBusy(true); setNote(null);
    try {
      const r = await api.askPlanVoice(id, audio);
      if (!r.heard) { setNote(r.answer); return; }
      const i = qa.length;
      setQa((x) => [...x, { q: r.heard, a: r.answer, runId: r.run_id, voice: true }]);
      if (r.audio) play(`data:audio/mpeg;base64,${r.audio}`, i); // a spoken question gets a spoken answer
    } catch (e) {
      setNote(`Voice question failed: ${errText(e)}`);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card ask-reo">
      <div className="ask-reo-head">
        <ReoAvatar size={84} outfit="vest" greet interactive winkKey={qa.length} className={speaking !== null ? "is-waving" : ""} title="reo" />
        <div>
          <h3>Ask reo why</h3>
          <p className="muted small">{voiceOn ? "Type a question or tap the mic, reo answers out loud." : "Type a question about this plan."}</p>
        </div>
      </div>
      <div className="chips">
        {["Why this battery size?", "Why a heat pump?", "Why does it cost this much?"].map((s) => <button key={s} className="chip" disabled={busy} onClick={() => ask(s)}>{s}</button>)}
      </div>
      {qa.map((x, i) => (
        <div key={i} className="qa">
          <p className="qa-q">{x.voice ? "🎙 " : ""}{x.q}</p>
          <p className="qa-a">{x.a}</p>
          {voiceOn && !x.a.startsWith("Error:") && (
            <button type="button" className="qa-speak" onClick={() => readAloud(i)} aria-label={speaking === i ? "Stop reading" : "Read the answer aloud"}>
              {speaking === i ? "■ Stop" : "🔊 Listen"}
            </button>
          )}
          {x.runId && <RunTimeline runId={x.runId} trace={[]} live={false} />}
        </div>
      ))}
      <div ref={end} />
      {busy && <p className="muted small">reo is thinking…</p>}
      {note && <p className="muted small" role="status">{note}</p>}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Why …?" disabled={busy} aria-label="Ask reo about this plan" />
        {voiceOn && <MicButton disabled={busy} onStart={stopSpeaking} onRecorded={askByVoice} onError={setNote} />}
        <button type="submit" disabled={busy || !q.trim()}>Ask</button>
      </form>
    </section>
  );
}
