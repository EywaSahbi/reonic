import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { Design, Plan } from "../types";
import { HouseScene } from "../scene/HouseScene";
import { defaultItems, enginePanels, fitRoof, frontCells, houseDims, WALL_H, type Roof } from "../scene/layout";
import { ReoAvatar } from "../ReoAvatar";
import { Satellite } from "../Satellite";
import type { Say, Spot, TraceStep } from "./narrate";
import "./live.css";

// The living stage: the customer's house builds itself from the engine's design while they answer, the advisor walks to
// whatever just changed and says one line, and a quiet step line shows what is being done right now.
// Draws engine numbers only (via HouseScene and the Say/TraceStep texts it is given); computes none.

const EMPTY: Design = {
  components: {
    pv: { recommended: false, size: null, unit: "kWp", range: null, confidence: "low", locked: false, reasons: [] },
    battery: { recommended: false, size: null, unit: "kWh", range: null, confidence: "low", locked: false, reasons: [] },
    heatpump: { recommended: false, size: null, unit: "kW", range: null, confidence: "low", locked: false, reasons: [] },
    wallbox: { recommended: false, size: null, unit: "kW", range: null, confidence: "low", locked: false, reasons: [] },
  },
  price: { items: [], total_eur: 0, range_eur: [0, 0] },
  economics: { total_demand_kwh: 0, self_consumption_pct: 0, autarky_pct: 0, annual_savings_eur: 0, payback_years: null },
  assumptions: [], missing_inputs: [], params_version: "",
};

/** How long the scene's own motion takes before the advisor speaks (matches HouseScene's queue and drive). */
const waitFor = (say: Say | null, panels: number) =>
  !say ? 0 : say.spot === "roof" ? Math.min(2400, 450 + panels * 70) : say.spot === "car" ? 1900 : say.spot === "heatpump" || say.spot === "battery" ? 800 : 0;

function spotPoint(spot: Spot, roof: Roof, items: ReturnType<typeof defaultItems>): [number, number, number] {
  const { length: L, depth: D } = houseDims(roof);
  const t = (roof.tilt * Math.PI) / 180;
  switch (spot) {
    case "roof": { const s = roof.flat ? 1 : roof.slope * 0.3; return [-L / 2 + 0.9, WALL_H + (roof.flat ? 0.4 : s * Math.sin(t)) + 0.15, D / 2 - (roof.flat ? 1 : s * Math.cos(t))]; }
    case "car": return [L / 2 - 0.4, 0, D / 2 + 2.2]; // beside the wallbox, kept inside the frame
    case "heatpump": { const p = items.heatpump; return p ? [p[0] + 1.1, 0, p[1] + 0.5] : [1.8, 0, D / 2 + 1.6]; }
    case "battery": { const p = items.battery; return p ? [p[0] - 0.9, 0, p[1] + 0.7] : [1.8, 0, D / 2 + 1.6]; }
    default: return [1.9, 0, D / 2 + 1.7];
  }
}

/** The advisor in the scene: glides to its spot, bubble above. An HTML overlay, so it stays crisp at any zoom. */
function Guide({ to, say: next, busy, side, wait, onMore }: { to: [number, number, number]; say: Say | null; busy: boolean; side: boolean; wait: number; onMore?: (q: string) => void }) {
  // Let the house move first (panels land, the car parks), then speak. Taps on numbers answer at once.
  const [say, setSay] = useState<Say | null>(next);
  const [hush, setHush] = useState(false);   // the previous line fades away while the scene moves
  useEffect(() => {
    if (!next || next.lines || next.more || wait <= 0) { setHush(false); setSay(next); return; }
    setHush(true);
    const t = setTimeout(() => { setHush(false); setSay(next); }, wait);
    return () => clearTimeout(t);
  }, [next?.key]); // eslint-disable-line react-hooks/exhaustive-deps
  const g = useRef<THREE.Group>(null);
  const target = useMemo(() => new THREE.Vector3(...to), [to[0], to[1], to[2]]); // eslint-disable-line react-hooks/exhaustive-deps
  const [moving, setMoving] = useState(false);
  const bubble = useRef<HTMLDivElement>(null);
  const fit = useRef({ dx: 0, below: false });
  const { gl } = useThree();
  // Keep the bubble inside the 3D window: measure it against the canvas each frame, slide it sideways (the arrow keeps
  // pointing at the advisor), flip it below the advisor when there is no room above, and cap it to the window.
  useFrame(() => {
    const b = bubble.current; if (!b) return;
    const st = gl.domElement.getBoundingClientRect(), r = b.getBoundingClientRect(), pad = 10, f = fit.current;
    b.style.maxWidth = `${Math.max(160, Math.min(300, st.width - 2 * pad))}px`;
    const left = r.left - f.dx, right = r.right - f.dx;            // where it would be without our shift
    let dx = 0;
    if (left < st.left + pad) dx = st.left + pad - left;
    else if (right > st.right - pad) dx = st.right - pad - right;
    // pick the side of the advisor with room; cap the bubble's height to that space (it scrolls inside if needed)
    const head = f.below ? r.top - 6 : r.bottom + 6;
    const roomUp = head - st.top - pad - 12, roomDown = st.bottom - head - pad - 70;   // keep the advisor visible below
    const inner = b.firstElementChild as HTMLElement | null;
    const needed = (inner?.scrollHeight ?? r.height) + 26;           // natural height, so the choice never flip-flops
    const below = needed > roomUp && roomDown > roomUp;
    if (inner) inner.style.maxHeight = `${Math.max(60, (below ? roomDown : roomUp) - 24)}px`;
    if (Math.abs(dx - f.dx) > 0.5) { f.dx = dx; b.style.setProperty("--dx", `${dx.toFixed(1)}px`); }
    if (below !== f.below) { f.below = below; b.classList.toggle("is-below", below); }
  });
  useFrame((_, dt) => {
    const o = g.current; if (!o) return;
    const d = o.position.distanceTo(target);
    if (d > 0.02) { o.position.lerp(target, 1 - Math.exp(-3.2 * dt)); if (!moving) setMoving(true); }
    else if (moving) setMoving(false);
  });
  return (
    <group ref={g} position={to}>
      <Html zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
        <div className={`guide ${moving ? "is-moving" : ""}`}>
          {say && (
            <div ref={bubble} className={`guide-bubble ${fit.current.below ? "is-below" : ""} ${hush ? "is-hidden" : busy ? "is-stale" : ""}`} key={say.key} role="status" aria-live="polite" style={{ pointerEvents: "auto" }}>
              <div className="guide-bubble-in">
                <p>{say.text}</p>
                {say.lines && say.lines.length > 0 && <ul>{say.lines.map((l) => <li key={l}>{l}</li>)}</ul>}
                {say.more && onMore && <button type="button" className="guide-more" onClick={() => onMore(say.more!)}>Ask more ›</button>}
              </div>
            </div>
          )}
          {busy && !say && <div className="guide-bubble guide-dots" aria-hidden><span /><span /><span /></div>}
          <div className="guide-body"><ReoAvatar size={62} interactive={false} greet winkKey={say?.key} title="Your energy advisor" /></div>
          <i className="guide-shadow" />
        </div>
      </Html>
    </group>
  );
}

export default function LiveStage({ plan, say, trace, busy, tall, onMore }: {
  plan: Plan | null; say: Say | null; trace: TraceStep[]; busy: boolean; tall?: boolean; onMore?: (q: string) => void;
}) {
  const design = plan?.design ?? EMPTY;
  const facts = plan?.facts ?? {};
  const pv = design.components.pv;
  const need = pv.recommended ? pv.quantity ?? 0 : 0;
  const roof = useMemo(() => fitRoof(facts, need), [facts.roof_width_m, facts.roof_length_m, facts.roof_area_sqm, facts.roof_tilt_deg, need]); // eslint-disable-line react-hooks/exhaustive-deps
  const cells = useMemo(() => frontCells(roof, pv.max_modules, need), [roof, pv.max_modules, need]);
  const panels = enginePanels(design, cells);
  const items = defaultItems(design, roof);
  const to = spotPoint(say?.spot ?? "door", roof, items);
  const [photo, setPhoto] = useState(false);
  // The step line steps back once everything is done, so the house stays the hero.
  const [quiet, setQuiet] = useState(false);
  const allDone = trace.length > 0 && trace.every((x) => x.state !== "run");
  useEffect(() => { setQuiet(false); if (!allDone) return; const t = setTimeout(() => setQuiet(true), 5000); return () => clearTimeout(t); }, [trace, allDone]);
  const loc = plan?.roof_location;

  return (
    <section className={`live-stage ${tall ? "is-tall" : ""}`} aria-label="Your home, built as you answer">
      <div className="live-canvas">
        <Canvas shadows dpr={[1, 2]} camera={{ position: [27, 18, 32], fov: 28 }} gl={{ antialias: true, alpha: true }}>
          <HouseScene roof={roof} cells={cells} panels={panels} items={items} />
          <Guide to={to} say={say} busy={busy} side={say?.spot === "roof"} wait={waitFor(say, panels.size)} onMore={onMore} />
          <OrbitControls autoRotate autoRotateSpeed={0.35} enablePan={false} enableZoom={false} minPolarAngle={0.7} maxPolarAngle={1.2} minAzimuthAngle={-0.9} maxAzimuthAngle={1.4} target={[1.6, 2, 1.4]} />
        </Canvas>
      </div>
      {photo && loc && <div className="live-photo"><Satellite loc={loc} fallback={null} /></div>}
      {loc && (
        <div className="live-seg" role="tablist" aria-label="View">
          <button role="tab" aria-selected={!photo} onClick={() => setPhoto(false)}>Your plan</button>
          <button role="tab" aria-selected={photo} onClick={() => setPhoto(true)}>Your roof</button>
        </div>
      )}
      {trace.length > 0 && (
        <ol className={`live-trace ${quiet ? "is-quiet" : ""}`} aria-label="What your advisor is doing">
          {trace.slice(-3).map((s, i) => (
            <li key={s.id + s.state + i} className={`is-${s.state}`} style={{ animationDelay: `${i * 90}ms` }}>
              <span className="live-trace-icon" aria-hidden>{s.state === "run" ? <i className="spin" /> : s.state === "done" ? "✓" : "!"}</span>
              <span className="live-trace-label">{s.label}</span>
              {s.detail && <span className="live-trace-detail">{s.detail}</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
