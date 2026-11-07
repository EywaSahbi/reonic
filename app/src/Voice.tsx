import { useEffect, useRef, useState } from "react";
import "./voice.css";

// Push-to-talk for reo (reo/VOICE.md): tap to talk, tap again to send. Records webm/opus (or mp4 on Safari),
// stops by itself after 30 s. The audio goes to reo only; reo talks to ElevenLabs, the browser never sees a key.
const MAX_MS = 30_000;

function pickMime(): string | undefined {
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return types.find((t) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t));
}

export function MicButton({ disabled, onRecorded, onError, onStart }: {
  disabled: boolean;
  onRecorded: (audio: Blob) => void;
  onError: (msg: string) => void;
  onStart?: () => void;
}) {
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => stopAll(), []);

  function stopAll() {
    window.clearInterval(timer.current);
    if (rec.current && rec.current.state !== "inactive") rec.current.stop();
  }

  async function start() {
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      onError("Voice isn't supported in this browser. You can type instead.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("I can't use your microphone (permission blocked). You can type instead.");
      return;
    }
    const mime = pickMime();
    const r = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks: Blob[] = [];
    r.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    r.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
      window.clearInterval(timer.current);
      const blob = new Blob(chunks, { type: r.mimeType || mime || "audio/webm" });
      if (blob.size > 0) onRecorded(blob);
    };
    rec.current = r;
    r.start();
    onStart?.();
    setRecording(true);
    setElapsed(0);
    const t0 = Date.now();
    timer.current = window.setInterval(() => {
      const ms = Date.now() - t0;
      setElapsed(ms);
      if (ms >= MAX_MS) stopAll();
    }, 200);
  }

  return (
    <button
      type="button"
      className={`mic ${recording ? "is-recording" : ""}`}
      disabled={disabled && !recording}
      onClick={() => (recording ? stopAll() : start())}
      aria-label={recording ? "Stop and send voice message" : "Talk to the energy advisor"}
      aria-pressed={recording}
      title={recording ? "Tap to send" : "Tap to talk"}
    >
      {recording ? (
        <span className="mic-rec"><span className="mic-dot" />{Math.floor(elapsed / 1000)}s</span>
      ) : (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
        </svg>
      )}
    </button>
  );
}

/** Plays reo's spoken reply (base64 mp3 from /voice). Returns a stop() so a new recording silences reo. */
export function useReoAudio() {
  const current = useRef<HTMLAudioElement | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const stop = () => { current.current?.pause(); current.current = null; setSpeaking(false); };
  const play = (b64: string) => {
    stop();
    const a = new Audio(`data:audio/mpeg;base64,${b64}`);
    current.current = a;
    a.onended = () => setSpeaking(false);
    a.onerror = () => setSpeaking(false);
    setSpeaking(true);
    a.play().catch(() => setSpeaking(false));
  };
  useEffect(() => stop, []);
  return { play, stop, speaking };
}

/** Mic is shown when reo reports voice, or forced with ?voice=1 (tests the recording + upload path without a key). */
export const voiceForced = () => /[?&#]voice=1\b/.test(location.search + location.hash);
