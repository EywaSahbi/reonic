import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Ask, HomeFacts, Message, Plan, Turn } from "./types";
import { PlanCard } from "./PlanCard";

const errText = (e: unknown) => String(e instanceof Error ? e.message : e);
const SESSION_KEY = "reo-session-id";
const readSaved = () => { try { return localStorage.getItem(SESSION_KEY); } catch { return null; } };
const writeSaved = (id: string | null) => { try { if (id) localStorage.setItem(SESSION_KEY, id); else localStorage.removeItem(SESSION_KEY); } catch { /* ignore */ } };
const stamp = () => new Date().toISOString();

// The reo chat widget: messages, quick-reply chips, inline input for `ask`, live plan card, handoff.
export function Widget({ onClose }: { onClose: () => void }) {
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
      setMessages((m) => [...m, last?.role === "reo" ? last : { role: "reo", text: `Done. Your plan is with SolarHaus Müller, ${name}. You'll see the final quote here once your planner has confirmed it.`, at: stamp() }]);
      setHandoffOpen(false);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  const handedOver = plan?.status === "handed_over" || plan?.status === "quoted";
  const hasDesign = !!plan && (plan.history.length > 0 || Object.keys(plan.facts).length > 0);

  return (
    <div className={`widget ${hasDesign ? "widget-wide" : ""}`} role="dialog" aria-label="reo energy advisor">
      <div className="widget-head">
        <div className="reo-id">
          <span className="reo-avatar">reo</span>
          <div>
            <strong>Energy advisor</strong>
            <span>reo · powered by Reonic</span>
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
              {chips.length > 0 && !busy && !(ask && (ask.input === "choice" || ask.input === "boolean")) && (
                <div className="chips">
                  {chips.map((c) => <button key={c} className="chip" onClick={() => say(c)}>{c}</button>)}
                </div>
              )}
              <form className="composer" onSubmit={(e) => { e.preventDefault(); say(text); }}>
                <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a message…" disabled={busy || !id} aria-label="Message reo" />
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

const CHOICE_LABEL: Record<string, string> = { heatpump: "Heat pump", district: "District heating" };
const label = (o: string) => CHOICE_LABEL[o] ?? o.charAt(0).toUpperCase() + o.slice(1);

// Maps a choice answer to HomeFacts. EV options map to has_ev / ev_planned per experience/flow.md.
function choiceFacts(ask: Ask, o: string): Partial<HomeFacts> {
  if (ask.field === "has_ev" || ask.field === "ev_planned") {
    if (o === "Yes, already") return { has_ev: true };
    if (o === "Planned") return { ev_planned: true };
    return { has_ev: false, ev_planned: false };
  }
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

  if (ask.input === "choice" || ask.input === "boolean") {
    const options = ask.input === "boolean" ? ["Yes", "No"] : ask.options ?? [];
    return (
      <div className="ask">
        <span className="ask-label">{ask.prompt}</span>
        <div className="chips">
          {options.map((o) => (
            <button key={o} className="chip chip-solid" onClick={() => onFacts(ask.input === "boolean" ? { [ask.field]: o === "Yes" } as Partial<HomeFacts> : choiceFacts(ask, o), label(o))}>
              {label(o)}
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
      <strong>Send this plan to SolarHaus Müller</strong>
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
