import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Ask, GoalResult, HomeFacts, Message, Plan, Turn } from "./types";
import { PlanCard } from "./PlanCard";
import { iconFor } from "./Icons";
import { MicButton, useReoAudio, voiceForced } from "./Voice";
import { ReoAvatar } from "./ReoAvatar";
import { AddressLookup, RoofResultCard, type RoofResult } from "./AddressLookup";

const errText = (e: unknown) => String(e instanceof Error ? e.message : e);
const SESSION_KEY = "reo-session-id";
type ChatMessage = Message & { roofResult?: RoofResult };   // roofResult: the roof box that stays under this reply
const readSaved = () => { try { return localStorage.getItem(SESSION_KEY); } catch { return null; } };
const writeSaved = (id: string | null) => { try { if (id) localStorage.setItem(SESSION_KEY, id); else localStorage.removeItem(SESSION_KEY); } catch { /* ignore */ } };
const stamp = () => new Date().toISOString();

// The reo chat widget: messages, quick-reply chips, inline input for `ask`, live plan card, handoff.
export function Widget({ onClose, variant }: { onClose: () => void; variant?: "stage" }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [chips, setChips] = useState<string[]>([]);
  const [ask, setAsk] = useState<Ask | undefined>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [handoffOpen, setHandoffOpen] = useState(false);
  const started = useRef(false);
  const bottom = useRef<HTMLDivElement>(null);
  const [voiceOn, setVoiceOn] = useState(voiceForced());
  const [notice, setNotice] = useState<string | null>(null);
  const [billRead, setBillRead] = useState<Turn["bill"]>();
  const [goalResult, setGoalResult] = useState<GoalResult>();
  const [roofResult, setRoofResult] = useState<RoofResult>();
  const [lookingUpRoof, setLookingUpRoof] = useState(false);
  const roofReturn = useRef<{ ask?: Ask; chips: string[] } | null>(null);
  const billInput = useRef<HTMLInputElement>(null);
  const reoAudio = useReoAudio();

  // Mic only when reo can do voice (ElevenLabs key set in reo/.env), or forced with ?voice=1.
  useEffect(() => {
    api.health().then((h) => setVoiceOn((v) => v || h.voice)).catch(() => {});
  }, []);

  // One spoken turn: reo transcribes (ElevenLabs), runs the normal turn, and returns its reply as mp3.
  async function sendVoice(audio: Blob) {
    if (!id) return;
    setBusy(true);
    setError(null);
    setChips([]);
    setAsk(undefined);
    try {
      const t = await api.sendVoice(id, audio);
      setMessages((m) => [...m, ...(t.heard ? [{ role: "customer" as const, text: t.heard, at: stamp() }] : []), ...t.messages]);
      setPlan(t.plan);
      setChips(t.suggestions);
      setAsk(t.ask);
      setBillRead(t.bill);
      setGoalResult(t.goal_result);
      if (t.audio) reoAudio.play(t.audio);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function run(p: () => Promise<Turn>, customerText?: string) {
    if (customerText) setMessages((m) => [...m, { role: "customer", text: customerText, at: stamp() }]);
    setBusy(true);
    setError(null);
    const previousChips = chips;
    setChips([]);
    try {
      const t = await p();
      // the roof box belongs to the reply it came with: it stays under that message while the chat goes on below it
      const attach = (x: Message, i: number): ChatMessage => (t.roof && i === t.messages.length - 1 ? { ...x, roofResult: { roof: t.roof, facts: t.plan.facts } } : x);
      setMessages((m) => [...m, ...t.messages.map(attach)]);
      roofReturn.current = null;
      setPlan(t.plan);
      setChips(t.suggestions);
      setAsk(t.ask);
      setBillRead(t.bill);
      setGoalResult(t.goal_result);
      if (t.roof) setRoofResult({ roof: t.roof, facts: t.plan.facts });
      else if (t.plan.facts.roof_area_sqm !== roofResult?.facts.roof_area_sqm) setRoofResult(undefined);
    } catch (e) {
      setError(errText(e));
      setChips(previousChips);
    } finally {
      setBusy(false);
    }
  }

  // Resume the last session in this browser (so the customer sees the final quote after a reload), else start one.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const saved = readSaved();
    if (!saved) { run(() => api.startSession()); return; }
    api.getSession(saved)
      .then((p) => {
        // a plan still being drafted starts over on reload: the house and the numbers build up from zero (EywaSahbi)
        if (p.status === "drafting") { writeSaved(null); run(() => api.startSession()); return; }
        setPlan(p);
        setMessages(p.transcript);
      })
      .catch(() => { writeSaved(null); run(() => api.startSession()); });
  }, []);

  useEffect(() => { if (plan?.id) writeSaved(plan.id); }, [plan?.id]);

  function startOver() {
    writeSaved(null);
    roofReturn.current = null;
    setMessages([]); setPlan(null); setChips([]); setAsk(undefined); setBillRead(undefined); setGoalResult(undefined); setRoofResult(undefined); setHandoffOpen(false); setError(null);
    run(() => api.startSession());
  }

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy, handoffOpen]);

  // After handoff, poll for the installer's final quote.
  useEffect(() => {
    if (!plan || plan.status !== "handed_over") return;
    const t = setInterval(async () => {
      try {
        const p = await api.getSession(plan.id);
        if (p.status === "quoted") {
          setPlan(p);
          const last = p.transcript.at(-1);
          if (last) setMessages((m) => [...m, last]);
        }
      } catch {
        /* keep polling */
      }
    }, 4000);
    return () => clearInterval(t);
  }, [plan?.id, plan?.status]);

  const id = plan?.id;

  function say(s: string) {
    if (!id || !s.trim()) return;
    if (/^skip$/i.test(s.trim()) && roofReturn.current && ask?.field === "roof_area_sqm") {
      setAsk(roofReturn.current.ask); setChips(roofReturn.current.chips); roofReturn.current = null;
      return;
    }
    if (billRead && /^(yes, that's right|not quite)$/i.test(s.trim())) {
      const read = billRead.read;
      setBillRead(undefined);
      if (/^yes/i.test(s.trim())) run(() => api.sendFacts(id, { total_demand_kwh: read.total_demand_kwh, electricity_price_eur_per_kwh: read.electricity_price_eur_per_kwh }), s);
      else { setAsk({ field: "total_demand_kwh", prompt: "What yearly use does your bill show?", input: "number" }); setChips([]); setMessages((m) => [...m, { role: "customer", text: s, at: stamp() }, { role: "reo", text: "No problem. You can enter the correct yearly use here.", at: stamp() }]); }
      return;
    }
    if (/^(yes, send it|send to installer|send it)\b/i.test(s.trim())) {
      // Handoff is an app-side form posting to /handoff (experience/flow.md Stage 5).
      setMessages((m) => [...m, { role: "customer", text: s, at: stamp() }]);
      setChips([]);
      setAsk(undefined);
      setHandoffOpen(true);
      return;
    }
    setText("");
    run(() => api.sendMessage(id, s), s);
  }

  async function uploadBill(file?: File) {
    if (!id || !file) return;
    setBusy(true); setError(null); setChips([]); setAsk(undefined);
    try {
      const t = await api.sendBill(id, file);
      setMessages((m) => [...m, { role: "customer", text: "Uploaded an electricity bill", at: stamp() }, ...t.messages]);
      setPlan(t.plan); setChips(t.suggestions); setAsk(t.ask); setBillRead(t.bill);
      setGoalResult(t.goal_result);
    } catch (e) { setError(errText(e)); }
    finally { setBusy(false); if (billInput.current) billInput.current.value = ""; }
  }

  async function handoff(name: string, email?: string) {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api.handoff(plan.id, name, email);
      setPlan(p);
      const last = p.transcript.at(-1);
      setMessages((m) => [...m, last?.role === "reo" ? last : { role: "reo", text: `Done. Your plan is with Sonnfeld, ${name}. You'll see the final quote here once your planner has confirmed it.`, at: stamp() }]);
      setHandoffOpen(false);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  function openRoofLookup() {
    if (!roofReturn.current && ask?.field !== "roof_area_sqm") roofReturn.current = { ask, chips };
    setAsk({ field: "roof_area_sqm", prompt: "Enter your address to estimate the roof area, or add dimensions yourself.", input: "address" });
    setChips([]);
  }

  async function lookupRoof(address: string) {
    if (!id) return;
    setLookingUpRoof(true);
    setRoofResult(undefined);
    try { await run(() => api.sendAddress(id, address), address); }
    finally { setLookingUpRoof(false); }
  }

  // Chips that repeat a tap card are hidden; others (e.g. "I know my yearly kWh") stay.
  const cardLabels = new Set((ask?.input === "boolean" ? ["Yes", "No"] : ask?.input === "choice" ? ask.options ?? [] : []).flatMap((o) => [o, label(o)].map((x) => x.toLowerCase())));
  const visibleChips = chips.filter((c) => !(ask?.input === "address" && /^(enter width × length|skip)$/i.test(c)) && !cardLabels.has(c.toLowerCase()) && !(ask?.field === "heating_type" && /^(gas|oil|other|heat pump already)$/i.test(c)));
  const handedOver = plan?.status === "handed_over" || plan?.status === "quoted";
  const latestAdvisorIndex = messages.map((m) => m.role).lastIndexOf("reo");
  const hasDesign = !!plan && (plan.history.length > 0 || Object.keys(plan.facts).length > 0);

  return (
    <div className={`widget ${hasDesign ? "widget-wide" : ""} ${variant === "stage" ? "widget-stage" : ""}`} role="dialog" aria-label="Sonnfeld energy advisor">
      <div className="widget-head">
        <div className="reo-id">
          <div>
            <strong>Energy advisor</strong>
            <span>Sonnfeld</span>
          </div>
        </div>
        <div className="widget-actions">
          <button className="btn-ghost small" onClick={startOver} disabled={busy}>Start over</button>
          <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
        </div>
      </div>

      <div className="widget-body">
        <div className="chat">
          <div className="chat-log" aria-live="polite">
            {messages.map((m, i) => (
              <Fragment key={i}>
                {m.role === "reo" && i === latestAdvisorIndex ? (
                  <div className="reo-message">
                    <span className="reo-message-avatar" aria-hidden><ReoAvatar size={104} greet={false} interactive={false} /></span>
                    <div className="bubble bubble-reo">{m.text}</div>
                  </div>
                ) : <div className={`bubble bubble-${m.role}`}>{m.text}</div>}
                {m.roofResult && <RoofResultCard result={m.roofResult} onChange={!handedOver && !busy && m.roofResult.roof === roofResult?.roof ? openRoofLookup : undefined} />}
              </Fragment>
            ))}
            {busy && <div className="bubble bubble-reo typing"><span /><span /><span /></div>}
            {lookingUpRoof && <div className="address-progress" role="status">Looking up your building and estimating the sunny roof area…</div>}
            {goalResult && <div className="goal-result"><strong>Matched to your goal · {goalResult.goal.replace("_", " ")}</strong><GoalVariant variant={goalResult.recommendation} /><div className="goal-alternatives">{goalResult.alternatives.map((v) => <GoalVariant key={v.name} variant={v} />)}</div></div>}
            {error && <div className="chat-error">Something went wrong: {error}</div>}
            {handoffOpen && !handedOver && (
              <HandoffForm onSubmit={handoff} onCancel={() => { setHandoffOpen(false); setChips(["Send to installer", "Why this size?"]); }} />
            )}
            <div ref={bottom} />
          </div>

          {!handedOver && !handoffOpen && (
            <div className="chat-controls">
              {ask?.input === "address" ? <AddressLookup prompt={ask.prompt} busy={busy} onSubmit={lookupRoof}
                onDimensions={() => { setAsk({ field: "roof_area_sqm", prompt: "Width and length of the sunny roof area", input: "dimensions" }); setChips(["Skip"]); }}
                onSkip={() => say("Skip")} /> : ask && !busy && (
                <AskInput
                  ask={ask}
                  onFacts={(f, label) => id && run(() => api.sendFacts(id, f), label)}
                  onAddress={lookupRoof}
                />
              )}
              {billRead && visibleChips.length > 0 && !busy && ( /* suggestion chips removed (EywaSahbi); only the bill confirmation stays */
                <div className="chips">
                  {visibleChips.map((c) => <button key={c} className="chip" onClick={() => say(c)}>{c}</button>)}
                </div>
              )}
              {!billRead && !handedOver && <div className="customer-tools">
                <button type="button" className="chip" onClick={openRoofLookup} disabled={busy}>⌖ Find my roof</button>
                <button type="button" className="chip" onClick={() => billInput.current?.click()} disabled={busy}>▧ Add a bill photo</button>
                <input ref={billInput} type="file" accept="image/*,.pdf" hidden onChange={(e) => uploadBill(e.target.files?.[0])} />
                {[["Keep it under €20,000", "Keep it under €20,000"], ["As independent as possible", "As independent as possible"], ["Lowest monthly bill", "Lowest monthly bill"]].map(([label, value]) => <button key={value} type="button" className="chip" disabled={busy} onClick={() => say(value)}>{label}</button>)}
              </div>}
              {notice && <div className="voice-hint">{notice}</div>}
              {reoAudio.speaking && (
                <div className="speaking"><span className="mic-dot" /> Speaking <button type="button" onClick={reoAudio.stop}>Stop</button></div>
              )}
              <form className="composer" onSubmit={(e) => { e.preventDefault(); say(text); }}>
                {voiceOn && <MicButton disabled={busy || !id} onRecorded={sendVoice} onStart={() => { reoAudio.stop(); setNotice(null); }} onError={setNotice} />}
                <input value={text} onChange={(e) => setText(e.target.value)} placeholder={voiceOn ? "Type or tap the mic…" : "Type a message…"} disabled={busy || !id} aria-label="Message the energy advisor" />
                <button type="submit" disabled={busy || !text.trim()}>Send</button>
              </form>
            </div>
          )}
        </div>

        {hasDesign && plan && <PlanCard plan={plan} onHandoff={!handedOver && !handoffOpen ? () => say("Send to installer") : undefined} />}
      </div>
    </div>
  );
}

function GoalVariant({ variant }: { variant: GoalResult["recommendation"] }) {
  const d = variant.design;
  return <div className="goal-variant"><strong>{variant.name}{variant.name === "Recommended" ? " · reo's pick" : ""}</strong><span>{d.components.pv.recommended ? `${d.components.pv.size} kWp solar` : "No solar"}{d.components.battery.recommended ? ` · ${d.components.battery.size} kWh battery` : ""} · €{Math.round(d.price.total_eur).toLocaleString("en")}</span><small>{variant.why}</small></div>;
}

const CHOICE_LABEL: Record<string, string> = { heatpump: "Heat pump", district: "District heating", semi: "Semi-detached", gable: "Gable roof", flat: "Flat roof", mono: "Mono-pitch", "1": "Just me", "5+": "5 or more" };
const STATES: Record<string, string> = {
  BW: "Baden-Württemberg", BY: "Bavaria", BE: "Berlin", BB: "Brandenburg", HB: "Bremen", HH: "Hamburg", HE: "Hesse", MV: "Mecklenburg-Vorpommern",
  NI: "Lower Saxony", NW: "North Rhine-Westphalia", RP: "Rhineland-Palatinate", SL: "Saarland", SN: "Saxony", ST: "Saxony-Anhalt", SH: "Schleswig-Holstein", TH: "Thuringia",
};
const label = (o: string) => STATES[o] ?? CHOICE_LABEL[o] ?? o.charAt(0).toUpperCase() + o.slice(1);

// Maps a choice answer to HomeFacts. EV options map to has_ev / ev_planned per experience/flow.md.
function choiceFacts(ask: Ask, o: string): Partial<HomeFacts> {
  if (ask.field === "has_ev" || ask.field === "ev_planned") {
    if (o === "Yes, already") return { has_ev: true };
    if (o === "Planned") return { ev_planned: true };
    return { has_ev: false, ev_planned: false };
  }
  if (ask.field === "has_existing_pv") return { has_existing_pv: /^yes/i.test(o) };
  const n = parseInt(o, 10); // numeric choices like "4" or "5+" (experience/flow.md Stage 1)
  return { [ask.field]: Number.isFinite(n) && /^\d/.test(o) ? n : o } as Partial<HomeFacts>;
}

// Inline input for Turn.ask.
function AskInput({ ask, onFacts, onAddress }: {
  ask: Ask;
  onFacts: (f: Partial<HomeFacts>, label: string) => void;
  onAddress: (a: string) => void;
}) {
  const [v, setV] = useState("");
  const [width, setWidth] = useState("");
  const [length, setLength] = useState("");

  if (ask.input === "choice" && (ask.options?.length ?? 0) > 8 && !ask.options?.some((o) => iconFor(o))) {
    // Long lists (e.g. 16 federal states): one picker instead of a wall of cards.
    return (
      <form className="ask" onSubmit={(e) => { e.preventDefault(); if (v) onFacts(choiceFacts(ask, v), label(v)); }}>
        <label className="ask-label" htmlFor="ask-select">{ask.prompt}</label>
        <div className="ask-field">
          <select id="ask-select" value={v} onChange={(e) => setV(e.target.value)} autoFocus>
            <option value="">Choose…</option>
            {ask.options!.map((o) => <option key={o} value={o}>{label(o)}</option>)}
          </select>
          <button type="submit" className="btn-small" disabled={!v}>OK</button>
        </div>
      </form>
    );
  }
  if (ask.input === "choice" || ask.input === "boolean") {
    const options = ask.input === "boolean" ? ["Yes", "No"] : ask.options ?? [];
    return (
      <div className="ask">
        <span className="ask-label">{ask.prompt}</span>
        <div className={options.some((o) => iconFor(o)) ? "tap-cards" : "chips"}>
          {options.map((o, i) => (
            <button key={o} className={iconFor(o) ? "tap-card" : "chip chip-solid"} style={{ animationDelay: `${i * 40}ms` }}
              onClick={() => onFacts(ask.input === "boolean" ? { [ask.field]: o === "Yes" } as Partial<HomeFacts> : choiceFacts(ask, o), label(o))}>
              {iconFor(o)}
              <span>{label(o)}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (ask.input === "dimensions") {
    const valid = Number(width) > 0 && Number(length) > 0;
    return <form className="ask dimensions" onSubmit={(e) => { e.preventDefault(); if (valid) onFacts({ roof_width_m: Number(width), roof_length_m: Number(length) }, `${width} × ${length} m`); }}>
      <span className="ask-label">{ask.prompt}</span>
      <div className="ask-field">
        <label>Width (m)<input type="number" min="0.01" step="any" required value={width} onChange={(e) => setWidth(e.target.value)} autoFocus /></label>
        <span aria-hidden>×</span>
        <label>Length (m)<input type="number" min="0.01" step="any" required value={length} onChange={(e) => setLength(e.target.value)} /></label>
        <button type="submit" className="btn-small" disabled={!valid}>OK</button>
      </div>
    </form>;
  }

  const isAddress = ask.input === "address";
  return (
    <form
      className="ask"
      onSubmit={(e) => {
        e.preventDefault();
        const raw = v.trim();
        if (!raw) return;
        const n = Number(raw.replace(/[^\d.,]/g, "").replace(",", "."));
        const plainNumber = /^\d+([.,]\d+)?\s*(m²|m2|sqm|kwh)?$/i.test(raw);
        if (isAddress && !plainNumber) onAddress(raw);
        else if (Number.isFinite(n) && n > 0) onFacts({ [isAddress ? "roof_area_sqm" : ask.field]: n } as Partial<HomeFacts>, raw);
        setV("");
      }}
    >
      <label className="ask-label" htmlFor="ask-input">{ask.prompt}</label>
      <div className="ask-field">
        <input id="ask-input" value={v} onChange={(e) => setV(e.target.value)} inputMode={isAddress ? "text" : "decimal"}
          placeholder={isAddress ? "50 m² or Musterstraße 12, München" : "e.g. 4500"} autoFocus />
        <button type="submit" className="btn-small">OK</button>
      </div>
    </form>
  );
}

function HandoffForm({ onSubmit, onCancel }: { onSubmit: (name: string, email?: string) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  return (
    <form className="handoff" onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim(), email.trim() || undefined); }}>
      <strong>Send this plan to Sonnfeld</strong>
      <p>A planner checks it, usually visits to see the roof, and sends you a final quote. You're not committing to anything.</p>
      <label>Your name<input value={name} onChange={(e) => setName(e.target.value)} required autoFocus /></label>
      <label>Email <em>(optional)</em><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <div className="handoff-actions">
        <button type="submit" className="btn-primary" disabled={!name.trim()}>Send plan</button>
        <button type="button" className="btn-ghost" onClick={onCancel}>Not yet</button>
      </div>
    </form>
  );
}
