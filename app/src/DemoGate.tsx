import { useEffect, useState, type ReactNode } from "react";
import { api, USING_MOCK, verifyDemoAccess } from "./api";
import { getDemoPin, setDemoPin } from "./auth";
import { SonnfeldMark } from "./Logo";

export function DemoGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"checking" | "locked" | "open" | "offline">(USING_MOCK ? "open" : "checking");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (USING_MOCK) return;
    let alive = true;
    setState("checking");
    void api.health().then(async (health) => {
      if (!health.demo_auth_required) { if (alive) setState("open"); return; }
      if (!getDemoPin()) { if (alive) setState("locked"); return; }
      try { await verifyDemoAccess(); if (alive) setState("open"); }
      catch { if (alive) { setDemoPin(""); setState("locked"); } }
    }).catch(() => { if (alive) setState("offline"); });
    const lock = () => { setState("locked"); setError("Please enter the demo access code again."); };
    window.addEventListener("reo-demo-unauthorized", lock);
    return () => { alive = false; window.removeEventListener("reo-demo-unauthorized", lock); };
  }, [attempt]);
  if (state === "open") return <>{children}</>;
  return <main className="planner-access card demo-access"><SonnfeldMark /><h1>Sonnfeld demo</h1>
    {state === "checking" ? <p role="status">Connecting to the demo…</p> : state === "offline" ? <><p>The demo is temporarily unavailable. Please try again shortly.</p><button className="btn-primary" onClick={() => setAttempt((n) => n + 1)}>Try again</button></> : <>
      <p>Enter your demo code to continue. Access is limited so everyone gets a smooth demo.</p>
      <form onSubmit={async (e) => { e.preventDefault(); setBusy(true); setError(""); setDemoPin(pin);
        try { await verifyDemoAccess(); setPin(""); setState("open"); }
        catch (err) { setDemoPin(""); setError(err instanceof Error ? err.message : "Could not verify the code."); }
        finally { setBusy(false); }
      }}><label>Demo code<input type="password" inputMode="numeric" autoComplete="off" value={pin} onChange={(e) => setPin(e.target.value)} required disabled={busy} autoFocus /></label>
        {error && <p role="alert">{error}</p>}<button className="btn-primary" disabled={busy || !pin.trim()}>{busy ? "Checking…" : "Enter demo"}</button>
      </form>
    </>}
  </main>;
}
