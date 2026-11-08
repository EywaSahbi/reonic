import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { Design, HomeFacts, Locks, PriceList } from "../types";
import { HouseScene, Picker, type Pick, type SceneEvents } from "./HouseScene";
import { addPanel, clampToRoof, defaultItems, enginePanels, fitRoof, frontCells, kwpPerModule, layoutPanels, locksFrom, nextSlot,
  placeOnLot, roofArea, snapSlot, type FreePanel, type ItemKey, type Items, type Spot } from "./layout";

// Planner "build mode" (EywaSahbi): modules move freely on the front roof; added modules join the others as a rectangle,
// a dragged module snaps into line when it is let go next to others. The hardware (inverter, battery, heat pump, wallbox)
// is set to a fixed size in the sidebar. Every change goes to reo by itself; reo + engine re-derive sizes and prices and
// the plan's price breakdown follows. Every number shown is the engine's (hard rule 2).

type Kind = "panel" | ItemKey;
const LABEL: Record<Kind, string> = { panel: "Solar module", battery: "Battery", heatpump: "Heat pump", wallbox: "Wallbox + car" };
const HINT: Record<Kind, string> = { panel: "Adds next to the others", battery: "Wall-mounted storage", heatpump: "Air-source unit outside", wallbox: "Charger at the driveway" };
const eur = (n: number) => "€" + Math.round(n).toLocaleString("en");

// Sizes the planner can fix: the catalogue's real products (engine/catalog.json); 0 = none / automatic.
const OPTIONS: Record<"inverter" | ItemKey, number[]> = { inverter: [5, 6, 8, 10], battery: [5.12, 7.68, 10.24, 12.8], heatpump: [6, 8, 10, 12], wallbox: [11, 22] };
const UNIT: Record<"inverter" | ItemKey, string> = { inverter: "kW", battery: "kWh", heatpump: "kW", wallbox: "kW" };
type Hw = Record<"inverter" | ItemKey, number>;
const fmt = (n: number) => String(Math.round(n * 10) / 10);
const inverterOf = (d: Design) => Number(d.price.items.map((i) => /^Hybrid inverter ([\d.]+) kW/.exec(i.label)?.[1]).find(Boolean) ?? 0);
const sizeOf = (d: Design, k: ItemKey) => (d.components[k].recommended ? d.components[k].size ?? OPTIONS[k][0] : 0);
const hwFrom = (d: Design, inverter: number): Hw => ({ inverter, battery: sizeOf(d, "battery"), heatpump: sizeOf(d, "heatpump"), wallbox: sizeOf(d, "wallbox") });

const AUTO_APPLY_MS = 700; // after the last change the layout goes to reo; the engine re-derives sizes and prices

export default function DesignStudio({ design, facts, disabled, onApply }: {
  design: Design; facts: HomeFacts; disabled: boolean; onApply: (locks: Locks, prices?: PriceList) => Promise<void>;
}) {
  const c = design.components;
  const need = c.pv.recommended ? c.pv.quantity ?? 0 : 0;
  const roof = useMemo(() => fitRoof(facts, need), [facts, need]);
  const cells = useMemo(() => frontCells(roof, c.pv.max_modules, need), [roof, c.pv.max_modules, need]);
  const area = useMemo(() => roofArea(roof), [roof]);
  const engineCount = enginePanels(design, cells).size;

  const [panels, setPanels] = useState<FreePanel[]>(() => layoutPanels(engineCount, area));
  const [items, setItems] = useState<Items>(() => defaultItems(design, roof));
  const invApplied = useRef(inverterOf(design));
  const [hw, setHw] = useState<Hw>(() => hwFrom(design, invApplied.current));
  const [selected, setSelected] = useState<ItemKey | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [overRoof, setOverRoof] = useState(false);
  const [applying, setApplying] = useState(false);
  const [grabbing, setGrabbing] = useState(false); // dragging a module or a component: the camera holds still
  const dragging = useRef<ItemKey | null>(null);
  const moving = useRef<{ id: string; from: { x: number; y: number }; moved: boolean } | null>(null);
  const pick = useRef<Pick | null>(null);
  const perModule = useRef<number | null>(kwpPerModule(design));

  // New design from the engine: keep the planner's module positions and devices, follow the engine's count and sizes.
  useEffect(() => {
    perModule.current = kwpPerModule(design) ?? perModule.current;
    setPanels((cur) => layoutPanels(engineCount, area, cur));
    setHw((cur) => hwFrom(design, cur.inverter));
  }, [design, area, engineCount]);

  // A device is on the lot exactly when it has a size; a new one appears at its usual spot.
  useEffect(() => {
    setItems((it) => {
      const spot = (k: ItemKey) => defaultItems({ ...design, components: { ...c, [k]: { ...c[k], recommended: true } } }, roof)[k];
      return { battery: hw.battery ? it.battery ?? spot("battery") : null, heatpump: hw.heatpump ? it.heatpump ?? spot("heatpump") : null,
               wallbox: hw.wallbox ? it.wallbox ?? spot("wallbox") : null };
    });
  }, [hw.battery, hw.heatpump, hw.wallbox, roof]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const up = () => {
      const m = moving.current;
      if (m) {
        if (!m.moved) setPanels((ps) => ps.filter((p) => p.id !== m.id)); // a plain click on a module removes it
        else setPanels((ps) => ps.map((p) => {
          if (p.id !== m.id) return p;
          const s = snapSlot(p, ps, area, p.id); // let go next to others: snaps into line; on top of one: back where it was
          return s ? { ...p, ...s } : { ...p, ...m.from };
        }));
      }
      moving.current = null; dragging.current = null; setActive(null); setGrabbing(false);
    };
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea, select")) return;
      if ((e.key === "Delete" || e.key === "Backspace") && selected) { setSize(selected, 0); e.preventDefault(); }
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("pointerup", up);
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("pointerup", up); window.removeEventListener("keydown", key); };
  });

  const setSize = (k: "inverter" | ItemKey, v: number) => { setHw((h) => ({ ...h, [k]: v })); if (k !== "inverter" && !v) setSelected(null); };
  const addModule = () => setPanels((ps) => { const s = nextSlot(ps, area); return s ? addPanel(ps, s) : ps; });
  const place = (k: ItemKey, at?: Spot) => {
    if (!hw[k]) setSize(k, c[k].recommended && c[k].size ? c[k].size : OPTIONS[k][0]);
    if (at) setItems((it) => ({ ...it, [k]: placeOnLot(at, roof) }));
    setSelected(k);
  };

  const events: SceneEvents = {
    hoverCell: null, selected,
    // empty roof: a click adds a module beside the nearest one (rows stay connected); the first one where you click
    onRoofDown: (x, y) => {
      if (disabled) return;
      setSelected(null);
      setPanels((ps) => { const s = snapSlot({ x, y }, ps, area, undefined, ps.length ? Infinity : 0.6); return s ? addPanel(ps, s) : ps; });
    },
    // a module follows the pointer anywhere on the roof while the button is held
    onRoofMove: (x, y) => {
      const m = moving.current;
      if (!m) return;
      const p = clampToRoof({ x, y }, area);
      if (!m.moved && Math.hypot(p.x - m.from.x, p.y - m.from.y) > 0.08) m.moved = true;
      if (m.moved) setPanels((ps) => ps.map((q) => (q.id === m.id ? { ...q, ...p } : q)));
    },
    onRoofHover: setOverRoof,
    onPanelDown: (id) => {
      if (disabled) return;
      const p = panels.find((q) => q.id === id);
      if (!p) return;
      moving.current = { id, from: { x: p.x, y: p.y }, moved: false };
      setActive(id); setGrabbing(true);
    },
    onItemDown: (k) => { if (disabled) return; setSelected(k); dragging.current = k; setGrabbing(true); },
    onGroundMove: (p) => { const k = dragging.current; if (k) setItems((it) => ({ ...it, [k]: placeOnLot(p, roof) })); },
    onGroundDown: () => setSelected(null),
  };

  function onDrop(e: DragEvent) {
    e.preventDefault();
    const kind = e.dataTransfer.getData("text/x-studio") as Kind;
    const hit = pick.current?.(e.clientX, e.clientY);
    if (!kind || disabled) return;
    if (kind === "panel") { addModule(); return; }
    place(kind, hit?.ground ?? undefined);
  }

  // what goes to reo: the module count (as kWp) and every device whose size differs from the engine's design
  const locks: Locks = {};
  const pvLock = locksFrom(design, panels.length, { battery: null, heatpump: null, wallbox: null }, perModule.current).pv;
  if (pvLock) locks.pv = pvLock;
  for (const k of ["battery", "heatpump", "wallbox"] as ItemKey[]) {
    if (Math.abs(hw[k] - sizeOf(design, k)) > 1e-6) locks[k] = hw[k] ? { recommended: true, size: hw[k] } : { recommended: false };
  }
  const invChanged = hw.inverter !== invApplied.current;
  const dirty = Object.keys(locks).length > 0 || invChanged;
  const tooMany = c.pv.max_modules != null && panels.length > c.pv.max_modules;

  async function apply() {
    setApplying(true);
    try {
      await onApply(locks, invChanged ? { inverter_kw: hw.inverter } : undefined);
      invApplied.current = hw.inverter;
    } finally { setApplying(false); }
  }
  const changeKey = JSON.stringify([locks, hw.inverter]);
  useEffect(() => {
    if (!dirty || disabled || applying || grabbing) return;
    const t = setTimeout(apply, AUTO_APPLY_MS);
    return () => clearTimeout(t);
  }, [changeKey, disabled, applying, grabbing]); // eslint-disable-line react-hooks/exhaustive-deps

  const choice = (k: "inverter" | ItemKey) => {
    const opts = [...new Set([...OPTIONS[k], ...(k !== "inverter" && hw[k] ? [hw[k]] : [])])].sort((a, b) => a - b);
    return (
      <label className={`studio-hw-row ${k !== "inverter" && Math.abs(hw[k] - sizeOf(design, k)) > 1e-6 ? "changed" : ""}`}>
        <span>{k === "inverter" ? "Inverter" : LABEL[k].replace(" + car", "")}</span>
        <select value={hw[k]} disabled={disabled} onChange={(e) => setSize(k, Number(e.target.value))}>
          <option value={0}>{k === "inverter" ? "Automatic" : "None"}</option>
          {opts.map((v) => <option key={v} value={v}>{fmt(v)} {UNIT[k]}{k === "inverter" ? " hybrid" : ""}</option>)}
        </select>
      </label>
    );
  };

  return (
    <section className="card studio">
      <div className="studio-head">
        <div>
          <h3>Design studio</h3>
          <span className="muted small">Drag modules anywhere on the roof; added ones line up next to the others. Set the hardware on the right. Every change goes to reo by itself; the engine re-derives sizes and prices.</span>
        </div>
      </div>

      <div className="studio-body">
        <aside className="studio-palette" aria-label="Components">
          {(Object.keys(LABEL) as Kind[]).map((k) => {
            const placed = k === "panel" ? panels.length > 0 : items[k] !== null;
            return (
              <button key={k} className={`palette-item ${placed ? "placed" : ""}`} draggable={!disabled} disabled={disabled}
                onDragStart={(e) => { e.dataTransfer.setData("text/x-studio", k); e.dataTransfer.effectAllowed = "copy"; }}
                onClick={() => (k === "panel" ? addModule() : items[k] ? setSelected(k) : place(k))}>
                <PaletteIcon k={k} />
                <span><b>{LABEL[k]}</b><small>{k === "panel" ? `${panels.length} placed · click to add` : placed ? "on the plan" : HINT[k]}</small></span>
                {k !== "panel" && placed && <span className="palette-x" role="button" aria-label={`Remove ${LABEL[k]}`} onClick={(e) => { e.stopPropagation(); setSize(k, 0); }}>×</span>}
              </button>
            );
          })}
          <div className="palette-row">
            <button className="btn-ghost" disabled={disabled} onClick={() => setPanels((ps) => { let out = ps; for (let s = nextSlot(out, area); s; s = nextSlot(out, area)) out = addPanel(out, s); return out; })}>Fill roof</button>
            <button className="btn-ghost" disabled={disabled} onClick={() => setPanels([])}>Clear roof</button>
          </div>
        </aside>

        <div className={`studio-canvas ${grabbing ? "grabbing" : ""}`} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }} onDrop={onDrop}>
          <Canvas shadows dpr={[1, 2]} camera={{ position: [16, 19, 33], fov: 32 }} gl={{ antialias: true, alpha: true }}>
            <HouseScene roof={roof} cells={[]} panels={new Set()} items={items} events={events} free={{ panels, area, active }} />
            <OrbitControls makeDefault enablePan={false} enableRotate={!grabbing && !overRoof} /* on the roof a press places or moves modules */ minDistance={14} maxDistance={75} minPolarAngle={0.35} maxPolarAngle={1.3} target={[0, 2, 0]} />
            <Picker api={pick} />
          </Canvas>
          <div className="studio-hud">
            {selected ? `${LABEL[selected]} selected · drag to move · Delete removes` : "Drag a module anywhere on the roof · click the roof to add one in line · click a module to remove · drag beside the house to turn"}
          </div>
        </div>

        <aside className="studio-side">
          <h4>Hardware</h4>
          <div className="studio-hw">
            <div className={`studio-hw-row ${panels.length !== engineCount ? "changed" : ""}`}>
              <span>Modules</span><b>{panels.length}</b>
              <small>engine: {c.pv.recommended ? `${c.pv.size} kWp` : "–"}{c.pv.max_modules != null ? ` · roof holds ${c.pv.max_modules}` : ""}</small>
            </div>
            {choice("inverter")}
            {choice("battery")}
            {choice("heatpump")}
            {choice("wallbox")}
          </div>
          {tooMany && <p className="studio-note warn">More modules than the measured roof holds; the engine will cut to {c.pv.max_modules}.</p>}

          <h4>Engine design {dirty && <span className="muted small">· updating…</span>}</h4>
          <dl className="studio-econ">
            <div><dt>PV</dt><dd>{c.pv.recommended ? `${c.pv.size} kWp` : "–"}</dd></div>
            <div><dt>Battery</dt><dd>{c.battery.recommended ? `${c.battery.size} kWh` : "–"}</dd></div>
            <div><dt>Total</dt><dd>{eur(design.price.total_eur)}</dd></div>
            <div><dt>Own power</dt><dd>{design.economics.autarky_pct}%</dd></div>
            <div><dt>Payback</dt><dd>{design.economics.payback_years ?? "–"} yrs</dd></div>
          </dl>

          <div className="studio-actions">
            <button className="btn-primary" disabled={!dirty || disabled || applying} onClick={apply}>{applying ? "Updating prices…" : dirty ? "Update now" : "Prices up to date"}</button>
            <button className="btn-ghost" disabled={applying} onClick={() => { setPanels(layoutPanels(engineCount, area)); setHw(hwFrom(design, invApplied.current)); setItems(defaultItems(design, roof)); setSelected(null); }}>Reset layout</button>
          </div>
        </aside>
      </div>
    </section>
  );
}

function PaletteIcon({ k }: { k: Kind }) {
  return (
    <svg viewBox="0 0 40 40" className="palette-icon" aria-hidden>
      {k === "panel" && <g><rect x="6" y="9" width="28" height="22" rx="2" fill="#1d2b4f" /><path d="M15.3 9v22M24.6 9v22M6 16.3h28M6 23.6h28" stroke="#9fb3db" strokeWidth="1" /></g>}
      {k === "battery" && <g><rect x="12" y="5" width="16" height="30" rx="3" fill="#f4f5f7" stroke="#b9bec7" /><rect x="15" y="11" width="10" height="2" rx="1" fill="#10b981" /></g>}
      {k === "heatpump" && <g><rect x="5" y="10" width="30" height="21" rx="3" fill="#f4f5f7" stroke="#b9bec7" /><circle cx="16" cy="20.5" r="7" fill="none" stroke="#8e949e" strokeWidth="2" /><path d="M12 20.5h8M16 16.5v8" stroke="#8e949e" /></g>}
      {k === "wallbox" && <g><rect x="13" y="6" width="14" height="18" rx="2" fill="#2c3036" /><circle cx="20" cy="12" r="2.2" fill="#10b981" /><path d="M24 24c0 6 4 6 8 8" stroke="#2c3036" strokeWidth="2" fill="none" /></g>}
    </svg>
  );
}
