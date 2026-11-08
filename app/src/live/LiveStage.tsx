import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
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
function Guide({ to, say, busy, side, onMore }: { to: [number, number, number]; say: Say | null; busy: boolean; side: boolean; onMore?: (q: string) => void }) {
  const g = useRef<THREE.Group>(null);
  const target = useMemo(() => new THREE.Vector3(...to), [to[0], to[1], to[2]]); // eslint-disable-line react-hooks/exhaustive-deps
  const [moving, setMoving] = useState(false);
  useFrame((_, dt) => {
    const o = g.current; if (!o) return;
    const d = o.position.distanceTo(target);
    if (d > 0.02) { o.position.lerp(target, 1 - Math.exp(-3.2 * dt)); if (!moving) setMoving(true); }
    else if (moving) setMoving(false);
  });
  return (
    <group ref={g} position={to}>
      <Html zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
        <div className={`guide ${moving ? "is-moving" : ""} ${side ? "is-side" : ""}`}>
          {say && (
            <div className={`guide-bubble ${busy ? "is-stale" : ""}`} key={say.key} role="status" aria-live="polite" style={{ pointerEvents: "auto" }}>
              <p>{say.text}</p>
              {say.lines && say.lines.length > 0 && <ul>{say.lines.map((l) => <li key={l}>{l}</li>)}</ul>}
              {say.more && onMore && <button type="button" className="guide-more" onClick={() => onMore(say.more!)}>Ask more ›</button>}
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
          <Guide to={to} say={say} busy={busy} side={say?.spot === "roof"} onMore={onMore} />
          <OrbitControls autoRotate autoRotateSpeed={0.35} enablePan={false} enableZoom={false} minPolarAngle={0.7} maxPolarAngle={1.2} minAzimuthAngle={-0.9} maxAzimuthAngle={1.4} target={[0, 2.2, 0]} />
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
