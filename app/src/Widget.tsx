import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Ask, HomeFacts, Message, Plan, Turn } from "./types";
import { PlanCard } from "./PlanCard";
import { iconFor } from "./Icons";
import { MicButton, useReoAudio, voiceForced } from "./Voice";
import { ReoAvatar } from "./ReoAvatar";

const errText = (e: unknown) => String(e instanceof Error ? e.message : e);
const SESSION_KEY = "reo-session-id";
const readSaved = () => { try { return localStorage.getItem(SESSION_KEY); } catch { return null; } };
const writeSaved = (id: string | null) => { try { if (id) localStorage.setItem(SESSION_KEY, id); else localStorage.removeItem(SESSION_KEY); } catch { /* ignore */ } };
const stamp = () => new Date().toISOString();

// The reo chat widget: messages, quick-reply chips, inline input for `ask`, live plan card, handoff.
export function Widget({ onClose, variant }: { onClose: () => void; variant?: "stage" }) {
  const [messages, setMessages] = useState<Message[]>([]);
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
    setChips([]);
    setAsk(undefined);
    try {
      const t = await p();
      setMessages((m) => [...m, ...t.messages]);
      setPlan(t.plan);
      setChips(t.suggestions);
      setAsk(t.ask);
    } catch (e) {
      setError(errText(e));
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
        setPlan(p);
        setMessages(p.transcript);
        if (p.status === "drafting") setChips(["Why this size?", "What does it cost?", "Send to installer"]);
      })
      .catch(() => { writeSaved(null); run(() => api.startSession()); });
  }, []);

  useEffect(() => { if (plan?.id) writeSaved(plan.id); }, [plan?.id]);

  function startOver() {
    writeSaved(null);
    setMessages([]); setPlan(null); setChips([]); setAsk(undefined); setHandoffOpen(false); setError(null);
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

  // Chips that repeat a tap card are hidden; others (e.g. "I know my yearly kWh") stay.
  const cardLabels = new Set((ask?.input === "boolean" ? ["Yes", "No"] : ask?.input === "choice" ? ask.options ?? [] : []).flatMap((o) => [o, label(o)].map((x) => x.toLowerCase())));
  const visibleChips = chips.filter((c) => !cardLabels.has(c.toLowerCase()) && !(ask?.field === "heating_type" && /^(gas|oil|other|heat pump already)$/i.test(c)));
  const handedOver = plan?.status === "handed_over" || plan?.status === "quoted";
  const hasDesign = !!plan && (plan.history.length > 0 || Object.keys(plan.facts).length > 0);

  return (
    <div className={`widget ${hasDesign ? "widget-wide" : ""} ${variant === "stage" ? "widget-stage" : ""}`} role="dialog" aria-label="Sonnfeld energy advisor">
      <div className="widget-head">
        <div className="reo-id">
          <span className="reo-avatar-slot" aria-hidden><ReoAvatar size={36} greet={false} winkKey={messages.length} /></span>
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
              <div key={i} className={`bubble bubble-${m.role}`}>{m.text}</div>
            ))}
            {busy && <div className="bubble bubble-reo typing"><span /><span /><span /></div>}
            {error && <div className="chat-error">Something went wrong: {error}</div>}
            {handoffOpen && !handedOver && (
              <HandoffForm onSubmit={handoff} onCancel={() => { setHandoffOpen(false); setChips(["Send to installer", "Why this size?"]); }} />
            )}
            <div ref={bottom} />
          </div>

          {!handedOver && !handoffOpen && (
            <div className="chat-controls">
              {ask && !busy && (
                <AskInput
                  ask={ask}
                  onFacts={(f, label) => id && run(() => api.sendFacts(id, f), label)}
                  onAddress={(a) => id && run(() => api.sendAddress(id, a), a)}
                />
              )}
              {visibleChips.length > 0 && !busy && (
                <div className="chips">
                  {visibleChips.map((c) => <button key={c} className="chip" onClick={() => say(c)}>{c}</button>)}
                </div>
              )}
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
