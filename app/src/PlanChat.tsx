import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Message, Plan } from "./types";
import { MicButton, useReoAudio, voiceForced } from "./Voice";
import { ReoAvatar } from "./ReoAvatar";

const stamp = () => new Date().toISOString();
const errText = (e: unknown) => String(e instanceof Error ? e.message : e);

// Questions about the plan on the results screen (EywaSahbi): typed or spoken. reo answers from the engine's
// reasons and price lines (POST /messages, /voice); a fact the customer adds updates the plan next to it.
export function PlanChat({ plan, onPlan, ask }: { plan: Plan; onPlan: (p: Plan) => void; ask?: { text: string; n: number } | null }) {
  const [msgs, setMsgs] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceOn, setVoiceOn] = useState(voiceForced());
  const reoAudio = useReoAudio();
  const bottom = useRef<HTMLDivElement>(null);

  // Mic only when reo can do voice (ElevenLabs key in reo/.env), or forced with ?voice=1.
  useEffect(() => { api.health().then((h) => setVoiceOn((v) => v || h.voice)).catch(() => {}); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [msgs, busy]);
  // "Ask more" from the advisor's bubble in the scene lands here as a real question.
  useEffect(() => { if (ask) send(ask.text); }, [ask?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  async function send(s: string) {
    if (!s.trim() || busy) return;
    setText(""); setNotice(null); setBusy(true);
    setMsgs((m) => [...m, { role: "customer", text: s.trim(), at: stamp() }]);
    try {
      const t = await api.sendMessage(plan.id, s.trim());
      setMsgs((m) => [...m, ...t.messages]);
      onPlan(t.plan);
    } catch (e) { setNotice(`Something went wrong: ${errText(e)}`); }
    finally { setBusy(false); }
  }

  async function sendVoice(audio: Blob) {
    setBusy(true); setNotice(null);
    try {
      const t = await api.sendVoice(plan.id, audio);
      setMsgs((m) => [...m, ...(t.heard ? [{ role: "customer" as const, text: t.heard, at: stamp() }] : []), ...t.messages]);
      onPlan(t.plan);
      if (t.audio) reoAudio.play(t.audio);
    } catch (e) { setNotice(`Something went wrong: ${errText(e)}`); }
    finally { setBusy(false); }
  }

  return (
    <section className="plan-chat" aria-label="Ask about your plan">
      <div className="plan-chat-head">
        <ReoAvatar size={40} interactive={false} greet={false} winkKey={msgs.length} title="Your energy advisor" />
        <div><strong>Ask your advisor</strong><small>{voiceOn ? "Type or talk, about anything in your plan" : "Ask about anything in your plan"}</small></div>
      </div>
      <div className="plan-chat-log" aria-live="polite">
        {msgs.length === 0 && (
          <div className="plan-chat-chips">
            {["Why this battery?", "What would make it cheaper?", "Is there funding?"].map((q) => <button key={q} type="button" disabled={busy} onClick={() => send(q)}>{q}</button>)}
          </div>
        )}
        {msgs.map((m, i) => <div key={i} className={`bubble bubble-${m.role}`}>{m.text}</div>)}
        {busy && <div className="bubble bubble-reo typing"><span /><span /><span /></div>}
        <div ref={bottom} />
      </div>
      {notice && <div className="voice-hint">{notice}</div>}
      {reoAudio.speaking && <div className="speaking"><span className="mic-dot" /> Speaking <button type="button" onClick={reoAudio.stop}>Stop</button></div>}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        {voiceOn && <MicButton disabled={busy} onRecorded={sendVoice} onStart={() => { reoAudio.stop(); setNotice(null); }} onError={setNotice} />}
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={voiceOn ? "Type or tap the mic…" : "Type a question…"} disabled={busy} aria-label="Ask about your plan" />
        <button type="submit" disabled={busy || !text.trim()}>Send</button>
      </form>
    </section>
  );
}
