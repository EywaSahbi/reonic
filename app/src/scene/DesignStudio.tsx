import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { Design, HomeFacts, Locks } from "../types";
import { HouseScene, Picker, type Pick, type SceneEvents } from "./HouseScene";
import { defaultItems, enginePanels, fitRoof, frontCells, kwpPerModule, locksFrom, placeOnLot, type ItemKey, type Items, type Spot } from "./layout";

// Planner "build mode": click roof spots to add or remove modules (drag across for many), drag components around.
// No tool modes (EywaSahbi). Modules sit on the front face only, so every module drawn is one the plan counts.
// The placement only becomes locks (modules x the engine's kWp per module, components on/off); reo + engine re-derive the
// design and the scene redraws from their answer. Every number in the sidebar is the engine's (hard rule 2).

type Kind = "panel" | ItemKey;
const LABEL: Record<Kind, string> = { panel: "Solar module", battery: "Battery", heatpump: "Heat pump", wallbox: "Wallbox + car" };
const HINT: Record<Kind, string> = { panel: "Click roof spots to add or remove", battery: "Wall-mounted storage", heatpump: "Air-source unit outside", wallbox: "Charger at the driveway" };
const eur = (n: number) => "€" + Math.round(n).toLocaleString("en");

export default function DesignStudio({ design, facts, disabled, onApply }: {
  design: Design; facts: HomeFacts; disabled: boolean; onApply: (locks: Locks) => Promise<void>;
}) {
  const need = design.components.pv.recommended ? design.components.pv.quantity ?? 0 : 0;
  const roof = useMemo(() => fitRoof(facts, need), [facts, need]);
  const cells = useMemo(() => frontCells(roof, design.components.pv.max_modules, need), [roof, design.components.pv.max_modules, need]);
  const [panels, setPanels] = useState<Set<string>>(() => enginePanels(design, cells));
  const [items, setItems] = useState<Items>(() => defaultItems(design, roof));
  const [selected, setSelected] = useState<ItemKey | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const dragging = useRef<ItemKey | null>(null);
  const paintTo = useRef<boolean | null>(null); // while the button is held on the roof: add (true) or remove (false)
  const [grabbing, setGrabbing] = useState(false); // dragging a component or painting: the camera holds still
  const pick = useRef<Pick | null>(null);
  const perModule = useRef<number | null>(kwpPerModule(design));

  // New design from the engine: redraw from it.
  useEffect(() => {
    perModule.current = kwpPerModule(design) ?? perModule.current;
    setPanels(enginePanels(design, cells));
    setItems((cur) => {
      const d = defaultItems(design, roof);
      return { battery: d.battery && (cur.battery ?? d.battery), heatpump: d.heatpump && (cur.heatpump ?? d.heatpump), wallbox: d.wallbox && (cur.wallbox ?? d.wallbox) };
    });
  }, [design, cells, roof]);

  useEffect(() => {
    const up = () => { paintTo.current = null; dragging.current = null; setGrabbing(false); };
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea")) return;
      if ((e.key === "Delete" || e.key === "Backspace") && selected) { remove(selected); e.preventDefault(); }
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("pointerup", up);
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("pointerup", up); window.removeEventListener("keydown", key); };
  });

  const setCell = (id: string, on: boolean) => setPanels((p) => {
    if (on === p.has(id)) return p;
    const n = new Set(p);
    if (on) n.add(id); else n.delete(id);
    return n;
  });
  const remove = (k: ItemKey) => { setItems((it) => ({ ...it, [k]: null })); setSelected(null); };
  const place = (k: ItemKey, at?: Spot) => {
    setItems((it) => ({ ...it, [k]: placeOnLot(at ?? it[k] ?? defaultItems({ ...design, components: { ...design.components, [k]: { ...design.components[k], recommended: true } } }, roof)[k]!, roof) }));
    setSelected(k);
  };

  const events: SceneEvents = {
    hoverCell: hover, selected,
    // click toggles a spot; keep the button down and drag to do the same to every spot you pass
    onCellDown: (id) => { if (disabled) return; paintTo.current = !panels.has(id); setGrabbing(true); setCell(id, paintTo.current); },
    onCellEnter: (id) => { setHover(id); if (id && paintTo.current !== null) setCell(id, paintTo.current); },
    onItemDown: (k) => { if (disabled) return; setSelected(k); dragging.current = k; setGrabbing(true); },
    onGroundMove: (p) => { const k = dragging.current; if (k) setItems((it) => ({ ...it, [k]: placeOnLot(p, roof) })); },
    onGroundDown: () => setSelected(null),
  };

  function onDrop(e: DragEvent) {
    e.preventDefault();
    const kind = e.dataTransfer.getData("text/x-studio") as Kind;
    const hit = pick.current?.(e.clientX, e.clientY);
    if (!kind || !hit || disabled) return;
    if (kind === "panel") { if (hit.cell) setCell(hit.cell, true); return; }
    place(kind, hit.ground ?? undefined);
  }

  const c = design.components;
  const engineModules = c.pv.recommended ? c.pv.quantity ?? null : 0;
  const locks = locksFrom(design, panels.size, items, perModule.current);
  const dirty = Object.keys(locks).length > 0;
  const tooMany = c.pv.max_modules != null && panels.size > c.pv.max_modules;

  async function apply() {
    setApplying(true);
    try { await onApply(locks); } finally { setApplying(false); }
  }

  return (
    <section className="card studio">
      <div className="studio-head">
        <div>
          <h3>Design studio</h3>
          <span className="muted small">Click the roof to add or remove modules, drag components to move them. Apply sends the layout to reo; the engine re-derives sizes and prices.</span>
        </div>
      </div>

      <div className="studio-body">
        <aside className="studio-palette" aria-label="Components">
          {(Object.keys(LABEL) as Kind[]).map((k) => {
            const placed = k === "panel" ? panels.size > 0 : items[k] !== null;
            return (
              <button key={k} className={`palette-item ${placed ? "placed" : ""}`} draggable={!disabled} disabled={disabled}
                onDragStart={(e) => { e.dataTransfer.setData("text/x-studio", k); e.dataTransfer.effectAllowed = "copy"; }}
                onClick={() => (k === "panel" ? undefined : items[k] ? setSelected(k) : place(k))}>
                <PaletteIcon k={k} />
                <span><b>{LABEL[k]}</b><small>{k === "panel" ? `${panels.size} placed` : placed ? "on the plan" : HINT[k]}</small></span>
                {k !== "panel" && placed && <span className="palette-x" role="button" aria-label={`Remove ${LABEL[k]}`} onClick={(e) => { e.stopPropagation(); remove(k); }}>×</span>}
              </button>
            );
          })}
          <div className="palette-row">
            <button className="btn-ghost" disabled={disabled} onClick={() => setPanels(new Set(cells.map((x) => x.id)))}>Fill roof</button>
            <button className="btn-ghost" disabled={disabled} onClick={() => setPanels(new Set())}>Clear roof</button>
          </div>
        </aside>

        <div className={`studio-canvas ${grabbing ? "grabbing" : ""}`} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }} onDrop={onDrop}>
          <Canvas shadows dpr={[1, 2]} camera={{ position: [16, 19, 33], fov: 32 }} gl={{ antialias: true, alpha: true }}>
            <HouseScene roof={roof} cells={cells} panels={panels} items={items} events={events} />
            <OrbitControls makeDefault enablePan={false} enableRotate={!grabbing && !hover} /* over a roof spot a press paints, it must not turn the view */ minDistance={14} maxDistance={75} minPolarAngle={0.35} maxPolarAngle={1.3} target={[0, 2, 0]} />
            <Picker api={pick} />
          </Canvas>
          <div className="studio-hud">
            {selected ? `${LABEL[selected]} selected · drag to move · Delete removes` : "Click a roof spot to add or remove a module · drag across for many · grab a component to move it · drag elsewhere to turn"}
          </div>
        </div>

        <aside className="studio-side">
          <h4>Layout</h4>
          <ul className="studio-diff">
            <li className={panels.size !== engineModules ? "changed" : ""}>
              <span>Modules</span><b>{panels.size}</b>
              <small>engine: {engineModules ?? "–"}{c.pv.max_modules != null ? ` · roof holds ${c.pv.max_modules}` : ""}</small>
            </li>
            {(["battery", "heatpump", "wallbox"] as ItemKey[]).map((k) => (
              <li key={k} className={(items[k] !== null) !== c[k].recommended ? "changed" : ""}>
                <span>{LABEL[k]}</span><b>{items[k] ? "yes" : "no"}</b><small>engine: {c[k].recommended ? `${c[k].size ?? "?"} ${c[k].unit}` : "no"}</small>
              </li>
            ))}
          </ul>
          {tooMany && <p className="studio-note warn">More modules than the measured roof holds; the engine will cut to {c.pv.max_modules}.</p>}
          {dirty && !perModule.current && locks.pv?.size === undefined && locks.pv?.recommended && <p className="studio-note">No module size known yet; the engine will choose the PV size.</p>}

          <h4>Engine design {dirty && <span className="muted small">· before your changes</span>}</h4>
          <dl className="studio-econ">
            <div><dt>PV</dt><dd>{c.pv.recommended ? `${c.pv.size} kWp` : "–"}</dd></div>
            <div><dt>Battery</dt><dd>{c.battery.recommended ? `${c.battery.size} kWh` : "–"}</dd></div>
            <div><dt>Total</dt><dd>{eur(design.price.total_eur)}</dd></div>
            <div><dt>Own power</dt><dd>{design.economics.autarky_pct}%</dd></div>
            <div><dt>Payback</dt><dd>{design.economics.payback_years ?? "–"} yrs</dd></div>
          </dl>
          {c.pv.reasons[0] && <p className="muted small studio-reason">{c.pv.reasons[0]}</p>}

          <div className="studio-actions">
            <button className="btn-primary" disabled={!dirty || disabled || applying} onClick={apply}>{applying ? "Re-deriving…" : dirty ? "Apply to plan" : "No changes"}</button>
            <button className="btn-ghost" disabled={!dirty || applying} onClick={() => { setPanels(enginePanels(design, cells)); setItems(defaultItems(design, roof)); setSelected(null); }}>Reset</button>
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
