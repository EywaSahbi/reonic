import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AddressSuggestion, Ask, HomeFacts, Plan, Turn } from "./types";
import { PlanCard } from "./PlanCard";
import { PlanChat } from "./PlanChat";
import { iconFor } from "./Icons";
import { doneSteps, explain, greeting, kindOf, pendingSteps, sayFor, type Kind, type Say, type Topic, type TraceStep } from "./live/narrate";

// Living stage (three.js) loads after the first paint; the step card works without it.
const LiveStage = lazy(() => import("./live/LiveStage"));

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
const cardKey = (a: Ask) => String(a.field) + a.input;

export function Widget({ onClose, variant }: { onClose: () => void; variant?: "stage" }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [ask, setAsk] = useState<Ask | undefined>();
  const [back, setBack] = useState<Ask[]>([]);          // asks already shown, for ‹ Back
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null); // one line above the step, e.g. "✓ Roof found · 48 m²"
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [say, setSay] = useState<Say | null>(null);         // the advisor's line in the scene
  const [trace, setTrace] = useState<TraceStep[]>([]);      // what is being done right now
  const [chatAsk, setChatAsk] = useState<{ text: string; n: number } | null>(null);
  const started = useRef(false);

  async function run(p: () => Promise<Turn>, from?: Ask, kind: Kind = "other") {
    setBusy(true);
    setError(null);
    setDir("fwd");
    setTrace(pendingSteps(kind));   // the advisor's last line stays until the new one replaces it
    try {
      const t = await p();
      setTrace(kind === "start" ? [] : doneSteps(kind, t));
      setSay(kind === "start" ? greeting() : sayFor(kind, t));
      if (from) setBack((b) => [...b, from]);
      setPlan(t.plan);
      setAsk(t.ask);
      if (t.roof) setNote(`✓ Roof found${t.plan.facts.roof_area_sqm != null ? ` · about ${Math.round(t.plan.facts.roof_area_sqm)} m²` : ""}`);
      else if (t.ask?.input === "dimensions" && from?.input === "address") setNote("Address not found. Enter the roof size instead.");
      else setNote(null);
    } catch (e) {
      setError(errText(e));
      setTrace((s) => s.map((x) => (x.state === "run" ? { ...x, state: "fail", detail: "try again" } : x)));
    } finally {
      setBusy(false);
    }
  }

  // Resume a handed-over plan after a reload (the customer waits for the final quote); a draft starts over.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const saved = readSaved();
    if (!saved) { run(() => api.startSession(), undefined, "start"); return; }
    api.getSession(saved)
      .then((p) => {
        if (p.status === "drafting") { writeSaved(null); run(() => api.startSession(), undefined, "start"); return; }
        setPlan(p);
      })
      .catch(() => { writeSaved(null); run(() => api.startSession(), undefined, "start"); });
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
    setPlan(null); setAsk(undefined); setBack([]); setNote(null); setHandoffOpen(false); setError(null); setSay(null); setTrace([]);
    run(() => api.startSession(), undefined, "start");
  }

  const id = plan?.id;
  const facts = (f: Partial<HomeFacts>, skip?: string[]) => id && ask && run(() => api.sendFacts(id, f, skip), ask, kindOf(ask, f, skip));
  const onExplain = (topic: Topic) => plan && setSay(explain(topic, plan.design));
  const askMore = (q: string) => setChatAsk((c) => ({ text: q, n: (c?.n ?? 0) + 1 }));
  const goBack = () => {
    const prev = back.at(-1);
    if (!prev) return;
    setBack((b) => b.slice(0, -1));
    setDir("back");
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

  // Crossfade between questions: the answered card slides out while the next slides in (reversed for Back).
  // The outgoing card keeps its React key, so it keeps its state (the tile you tapped stays lit) while it leaves.
  const [leaving, setLeaving] = useState<Ask | null>(null);
  const [dir, setDir] = useState<"fwd" | "back">("fwd");
  const shown = useRef<Ask | undefined>(undefined);
  useEffect(() => {
    const prev = shown.current;
    shown.current = ask;
    if (!prev || !ask || cardKey(prev) === cardKey(ask)) return;
    setLeaving(prev);
    const t = setTimeout(() => setLeaving(null), 520);
    return () => clearTimeout(t);
  }, [ask]);
  const card = (a: Ask, out: boolean) => (
    <div className={`step-card ${out ? "is-leaving" : "is-current"} ${busy && !out ? "is-busy" : ""}`} key={cardKey(a)} aria-hidden={out || undefined}>
      {!out && note && <p className="step-note">{note}</p>}
      <h2 className="step-title">{TITLE[a.field] ?? a.prompt}</h2>
      <StepInput ask={a} busy={busy || out} onFacts={facts} onAddress={(addr, point) => id && run(() => api.sendAddress(id, addr, point), a, "address")}
        suggest={(q) => (id ? api.suggestAddress(id, q).then((r) => r.suggestions) : Promise.resolve([]))}
        onDims={() => { setDir("fwd"); setBack((b) => [...b, a]); setAsk(DIMS_ASK); setNote(null); }} />
      {!out && error && <div className="chat-error">Something went wrong: {error}</div>}
      <div className="step-foot">
        {back.length > 0 && !out ? <button type="button" className="step-back" onClick={goBack} disabled={busy}>‹ Back</button> : <span />}
      </div>
    </div>
  );

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
        {/* One flow container for steps and results: the 3D stage is always its first child, so it stays mounted
            (no reload, no flash) from the first question to the final plan. */}
        <div className={`flow ${results ? "results is-results" : "live-split is-steps"}`}>
          <div className="flow-stage">
            <Suspense fallback={<div className="live-stage" />}>
              <LiveStage plan={plan} say={say} trace={trace} busy={busy} tall={results} onMore={results ? askMore : undefined} />
            </Suspense>
            {results && !busy && <p className="explain-hint">Tap any number to see why.</p>}
          </div>
          {results && plan ? (
            <>
              <div className="results-main">
                {drafting && back.length > 0 && <button type="button" className="step-back" onClick={goBack} disabled={busy}>‹ Back</button>}
                {plan.status === "handed_over" && <div className="sent-banner">✓ Sent to Sonnfeld. Your final quote appears here once your planner has confirmed it.</div>}
                {plan.status === "quoted" && <div className="sent-banner">✓ Your planner has confirmed your plan.</div>}
                <PlanCard plan={plan}
                  onHandoff={drafting && !handoffOpen ? () => setHandoffOpen(true) : undefined}
                  onToggleHeatpump={drafting && !busy ? (on) => id && run(() => api.sendFacts(id, { heatpump_option: on } as Partial<HomeFacts>), undefined, "toggle") : undefined}
                  onExplain={onExplain} />
                {handoffOpen && drafting && <HandoffForm busy={busy} onSubmit={handoff} onCancel={() => setHandoffOpen(false)} />}
                {error && <div className="chat-error">Something went wrong: {error}</div>}
              </div>
              <PlanChat plan={plan} onPlan={setPlan} ask={chatAsk} />
            </>
          ) : (
            <div className="stepper">
              <div className="step-shell">
                <div className="step-progress" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS} aria-valuenow={step}>
                  <span>Step {step} of {STEPS}</span>
                  <div className="step-bar"><i style={{ transform: `scaleX(${plan ? step / STEPS : 0})` }} /></div>
                </div>
                <div className={`step-stack dir-${dir}`}>
                  {leaving && card(leaving, true)}
                  {ask && card(ask, false)}
                </div>
              </div>
            </div>
          )}
        </div>
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

function StepInput({ ask, busy, onFacts, onAddress, onDims, suggest }: {
  ask: Ask; busy: boolean;
  onFacts: (f: Partial<HomeFacts>, skip?: string[]) => void;
  onAddress: (a: string, point?: AddressSuggestion) => void;
  onDims: () => void;
  suggest: (q: string) => Promise<AddressSuggestion[]>;
}) {
  const [v, setV] = useState("");
  const [width, setWidth] = useState("");
  const [length, setLength] = useState("");
  const [hits, setHits] = useState<AddressSuggestion[]>([]);
  const [chosen, setChosen] = useState<string | null>(null);   // the tile you tapped stays lit while the answer goes out
  const picked = useRef(false);

  // Address type-ahead: from 3 characters, 250 ms after the last keystroke; the latest answer wins.
  useEffect(() => {
    if (ask.input !== "address" || picked.current || v.trim().length < 3) { setHits([]); return; }
    let live = true;
    const t = setTimeout(() => suggest(v.trim()).then((s) => live && setHits(s)).catch(() => {}), 250);
    return () => { live = false; clearTimeout(t); };
  }, [v, ask.input]);
  const link = (text: string, onClick: () => void) => <button type="button" className="step-link" disabled={busy} onClick={onClick}>{text}</button>;

  if (ask.input === "choice" || ask.input === "boolean") {
    const options = ask.input === "boolean" ? ["Yes", "No"] : ask.options ?? [];
    return <>
      <div className="step-tiles">
        {options.map((o) => (
          <button key={o} type="button" className={`step-tile ${chosen === o ? "is-chosen" : ""}`} disabled={busy} aria-pressed={chosen === o}
            onClick={() => { setChosen(o); onFacts(ask.input === "boolean" ? { [ask.field]: o === "Yes" } as Partial<HomeFacts> : choiceFacts(ask, o)); }}>
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
    const pick = (s: AddressSuggestion) => { picked.current = true; setV(s.label); setHits([]); onAddress(s.label, s.lat != null ? s : undefined); };
    return <form className="step-form" onSubmit={(e) => { e.preventDefault(); if (hits[0] && hits[0].label.toLowerCase().startsWith(v.trim().toLowerCase())) pick(hits[0]); else if (v.trim()) onAddress(v.trim()); }}>
      <div className="step-address">
        <div className="step-bar-input">
          <input value={v} onChange={(e) => { picked.current = false; setV(e.target.value); }} placeholder="Musterstraße 12, München" aria-label="Your address"
            autoComplete="off" role="combobox" aria-expanded={hits.length > 0} aria-controls="address-hits" autoFocus />
          <button type="submit" className="btn-primary" disabled={!v.trim() || busy}>Find roof</button>
        </div>
        {hits.length > 0 && (
          <ul className="address-hits" id="address-hits" role="listbox">
            {hits.map((s) => (
              <li key={s.label} role="option" aria-selected={false}>
                <button type="button" disabled={busy} onClick={() => pick(s)}>{s.label}</button>
              </li>
            ))}
          </ul>
        )}
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
