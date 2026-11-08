import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Ask, HomeFacts, Plan, Turn } from "./types";
import { PlanCard } from "./PlanCard";
import { iconFor } from "./Icons";

const errText = (e: unknown) => String(e instanceof Error ? e.message : e);
const SESSION_KEY = "reo-session-id";
const readSaved = () => { try { return localStorage.getItem(SESSION_KEY); } catch { return null; } };
const writeSaved = (id: string | null) => { try { if (id) localStorage.setItem(SESSION_KEY, id); else localStorage.removeItem(SESSION_KEY); } catch { /* ignore */ } };

// Step form (EywaSahbi, 2026-11-08): one question per screen, buttons, almost no text. reo's Turn.ask decides the
// next step; every number is the engine's and appears only on the results screen (PlanCard) after the last step.
const STEP: Record<string, number> = { total_demand_kwh: 1, num_inhabitants: 1, roof_area_sqm: 2, roof_dims: 2, has_ev: 3, heating_type: 4 };
const STEPS = 4;
const TITLE: Record<string, string> = {
  total_demand_kwh: "Yearly electricity use", num_inhabitants: "People at home", roof_area_sqm: "Your address",
  roof_dims: "Roof size", has_ev: "Electric car?", heating_type: "Current heating",
};
const DIMS_ASK: Ask = { field: "roof_dims" as keyof HomeFacts, prompt: "Roof size", input: "dimensions" };
const ROOF_SKIP = ["roof_area_sqm", "roof_dims"];

export function Widget({ onClose, variant }: { onClose: () => void; variant?: "stage" }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [ask, setAsk] = useState<Ask | undefined>();
  const [back, setBack] = useState<Ask[]>([]);          // asks already shown, for ‹ Back
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null); // one line above the step, e.g. "✓ Roof found · 48 m²"
  const [handoffOpen, setHandoffOpen] = useState(false);
  const started = useRef(false);

  async function run(p: () => Promise<Turn>, from?: Ask) {
    setBusy(true);
    setError(null);
    try {
      const t = await p();
      if (from) setBack((b) => [...b, from]);
      setPlan(t.plan);
      setAsk(t.ask);
      if (t.roof) setNote(`✓ Roof found${t.plan.facts.roof_area_sqm != null ? ` · about ${Math.round(t.plan.facts.roof_area_sqm)} m²` : ""}`);
      else if (t.ask?.input === "dimensions" && from?.input === "address") setNote("Address not found. Enter the roof size instead.");
      else setNote(null);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  // Resume a handed-over plan after a reload (the customer waits for the final quote); a draft starts over.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const saved = readSaved();
    if (!saved) { run(() => api.startSession()); return; }
    api.getSession(saved)
      .then((p) => {
        if (p.status === "drafting") { writeSaved(null); run(() => api.startSession()); return; }
        setPlan(p);
      })
      .catch(() => { writeSaved(null); run(() => api.startSession()); });
  }, []);

  useEffect(() => { if (plan?.id) writeSaved(plan.id); }, [plan?.id]);

  // After handoff, poll for the installer's final quote.
  useEffect(() => {
    if (!plan || plan.status !== "handed_over") return;
    const t = setInterval(async () => {
      try {
        const p = await api.getSession(plan.id);
        if (p.status === "quoted") setPlan(p);
      } catch { /* keep polling */ }
    }, 4000);
    return () => clearInterval(t);
  }, [plan?.id, plan?.status]);

  function startOver() {
    writeSaved(null);
    setPlan(null); setAsk(undefined); setBack([]); setNote(null); setHandoffOpen(false); setError(null);
    run(() => api.startSession());
  }

  const id = plan?.id;
  const facts = (f: Partial<HomeFacts>, skip?: string[]) => id && ask && run(() => api.sendFacts(id, f, skip), ask);
  const goBack = () => {
    const prev = back.at(-1);
    if (!prev) return;
    setBack((b) => b.slice(0, -1));
    setAsk(prev);
    setNote(null);
    setHandoffOpen(false);
  };

  async function handoff(name: string, email?: string) {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      setPlan(await api.handoff(plan.id, name, email));
      setHandoffOpen(false);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  const drafting = plan?.status === "drafting";
  const results = !!plan && (!drafting || !ask);   // flow done (no ask) or already handed over
  const step = ask ? STEP[ask.field] ?? 1 : STEPS;

  return (
    <div className={`widget ${results ? "widget-wide" : ""} ${variant === "stage" ? "widget-stage" : ""}`} role="dialog" aria-label="Sonnfeld energy advisor">
      <div className="widget-head">
        <div className="reo-id"><div><strong>Energy advisor</strong><span>Sonnfeld</span></div></div>
        <div className="widget-actions">
          <button className="btn-ghost small" onClick={startOver} disabled={busy}>Start over</button>
          <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
        </div>
      </div>

      <div className="widget-body">
        {!plan ? <div className="stepper"><div className="step-card is-busy" aria-busy /></div> : results ? (
          <div className="results">
            {drafting && back.length > 0 && <button type="button" className="step-back" onClick={goBack} disabled={busy}>‹ Back</button>}
            {plan.status === "handed_over" && <div className="sent-banner">✓ Sent to Sonnfeld. Your final quote appears here once your planner has confirmed it.</div>}
            {plan.status === "quoted" && <div className="sent-banner">✓ Your planner has confirmed your plan.</div>}
            <PlanCard plan={plan}
              onHandoff={drafting && !handoffOpen ? () => setHandoffOpen(true) : undefined}
              onToggleHeatpump={drafting && !busy ? (on) => id && run(() => api.sendFacts(id, { heatpump_option: on } as Partial<HomeFacts>)) : undefined} />
            {handoffOpen && drafting && <HandoffForm busy={busy} onSubmit={handoff} onCancel={() => setHandoffOpen(false)} />}
            {error && <div className="chat-error">Something went wrong: {error}</div>}
          </div>
        ) : ask && (
          <div className="stepper">
            <div className={`step-card ${busy ? "is-busy" : ""}`} key={String(ask.field) + ask.input}>
              <div className="step-progress" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS} aria-valuenow={step}>
                <span>Step {step} of {STEPS}</span>
                <div className="step-bar"><i style={{ transform: `scaleX(${step / STEPS})` }} /></div>
              </div>
              {note && <p className="step-note">{note}</p>}
              <h2 className="step-title">{TITLE[ask.field] ?? ask.prompt}</h2>
              <StepInput ask={ask} busy={busy} onFacts={facts} onAddress={(a) => id && run(() => api.sendAddress(id, a), ask)}
                onDims={() => { setBack((b) => [...b, ask]); setAsk(DIMS_ASK); setNote(null); }} />
              {error && <div className="chat-error">Something went wrong: {error}</div>}
              <div className="step-foot">
                {back.length > 0 ? <button type="button" className="step-back" onClick={goBack} disabled={busy}>‹ Back</button> : <span />}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const CHOICE_LABEL: Record<string, string> = { heatpump: "Heat pump", district: "District heating", "1": "Just me", "5+": "5 or more", "Yes, already": "Yes" };
const label = (o: string) => CHOICE_LABEL[o] ?? o.charAt(0).toUpperCase() + o.slice(1);

// Maps a choice answer to HomeFacts. EV options map to has_ev / ev_planned per experience/flow.md.
function choiceFacts(ask: Ask, o: string): Partial<HomeFacts> {
  if (ask.field === "has_ev" || ask.field === "ev_planned") {
    if (o === "Yes, already") return { has_ev: true, ev_planned: false };
    if (o === "Planned") return { has_ev: false, ev_planned: true };
    return { has_ev: false, ev_planned: false };
  }
  const n = parseInt(o, 10); // numeric choices like "4" or "5+"
  return { [ask.field]: Number.isFinite(n) && /^\d/.test(o) ? n : o } as Partial<HomeFacts>;
}

function StepInput({ ask, busy, onFacts, onAddress, onDims }: {
  ask: Ask; busy: boolean;
  onFacts: (f: Partial<HomeFacts>, skip?: string[]) => void;
  onAddress: (a: string) => void;
  onDims: () => void;
}) {
  const [v, setV] = useState("");
  const [width, setWidth] = useState("");
  const [length, setLength] = useState("");
  const link = (text: string, onClick: () => void) => <button type="button" className="step-link" disabled={busy} onClick={onClick}>{text}</button>;

  if (ask.input === "choice" || ask.input === "boolean") {
    const options = ask.input === "boolean" ? ["Yes", "No"] : ask.options ?? [];
    return <>
      <div className="step-tiles">
        {options.map((o) => (
          <button key={o} type="button" className="step-tile" disabled={busy}
            onClick={() => onFacts(ask.input === "boolean" ? { [ask.field]: o === "Yes" } as Partial<HomeFacts> : choiceFacts(ask, o))}>
            {iconFor(o)}<span>{label(o)}</span>
          </button>
        ))}
      </div>
      {ask.field === "num_inhabitants" && <div className="step-links">{link("Skip", () => onFacts({}, ["num_inhabitants"]))}</div>}
    </>;
  }

  if (ask.input === "dimensions") {
    const valid = Number(width) > 0 && Number(length) > 0;
    return <form className="step-form" onSubmit={(e) => { e.preventDefault(); if (valid) onFacts({ roof_width_m: Number(width), roof_length_m: Number(length) }); }}>
      <div className="step-bar-input dims">
        <input type="number" min="0.01" step="any" inputMode="decimal" placeholder="Width (m)" aria-label="Roof width in metres" value={width} onChange={(e) => setWidth(e.target.value)} autoFocus />
        <span aria-hidden>×</span>
        <input type="number" min="0.01" step="any" inputMode="decimal" placeholder="Length (m)" aria-label="Roof length in metres" value={length} onChange={(e) => setLength(e.target.value)} />
        <button type="submit" className="btn-primary" disabled={!valid || busy}>Next</button>
      </div>
      <div className="step-links">{link("Skip", () => onFacts({}, ROOF_SKIP))}</div>
    </form>;
  }

  if (ask.input === "address") {
    return <form className="step-form" onSubmit={(e) => { e.preventDefault(); if (v.trim()) onAddress(v.trim()); }}>
      <div className="step-bar-input">
        <input value={v} onChange={(e) => setV(e.target.value)} placeholder="Musterstraße 12, München" aria-label="Your address" autoComplete="street-address" autoFocus />
        <button type="submit" className="btn-primary" disabled={!v.trim() || busy}>Find roof</button>
      </div>
      <div className="step-links">{link("Enter width × length", onDims)}{link("Skip", () => onFacts({}, ROOF_SKIP))}</div>
    </form>;
  }

  // number (yearly kWh)
  const n = Number(v.replace(/[.,\s]/g, ""));
  return <form className="step-form" onSubmit={(e) => { e.preventDefault(); if (n > 0) onFacts({ [ask.field]: n } as Partial<HomeFacts>); }}>
    <div className="step-bar-input">
      <input value={v} onChange={(e) => setV(e.target.value)} inputMode="numeric" placeholder="e.g. 4,500" aria-label={ask.prompt} autoFocus />
      <span className="step-unit">kWh</span>
      <button type="submit" className="btn-primary" disabled={!(n > 0) || busy}>Next</button>
    </div>
    {ask.field === "total_demand_kwh" && <div className="step-links">{link("Don't know", () => onFacts({}, ["total_demand_kwh"]))}</div>}
  </form>;
}

function HandoffForm({ busy, onSubmit, onCancel }: { busy: boolean; onSubmit: (name: string, email?: string) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  return (
    <form className="handoff" onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim(), email.trim() || undefined); }}>
      <strong>Send this plan to Sonnfeld</strong>
      <p>A planner checks it and sends you a final quote. No commitment.</p>
      <label>Your name<input value={name} onChange={(e) => setName(e.target.value)} required autoFocus /></label>
      <label>Email <em>(optional)</em><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <div className="handoff-actions">
        <button type="submit" className="btn-primary" disabled={!name.trim() || busy}>Send plan</button>
        <button type="button" className="btn-ghost" onClick={onCancel}>Not yet</button>
      </div>
    </form>
  );
}
