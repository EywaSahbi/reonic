import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { metresPerUnit, roofView } from "./Satellite";
import type { LayoutModule, Plan, RoofLayout } from "./types";

// Planner's roof: the customer's satellite photo and traced outline with the PV modules already placed on it
// (reo places them, layout.py). The planner drags, rotates, removes and adds modules. Only the module COUNT is a number:
// reo turns it into the pv lock and the engine re-derives the design; positions are stored as drawn.
const GAP = 0.02;          // m between modules, same as reo/layout.py
const SNAP = 0.15;         // m: a dragged module snaps to the edges and rows of its neighbours within this distance
const BLANK_UNITS_PER_M = 50; // no photo (demo address): metres drawn on a plain background

type Pt = [number, number];
const rad = (d: number) => (d * Math.PI) / 180;

function pointInPoly(p: Pt, poly: Pt[]): boolean {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}

/** Corners of a module in metres (east, north). */
function corners(m: LayoutModule, mod: { w_m: number; h_m: number }): Pt[] {
  const w = m.portrait ? mod.w_m : mod.h_m, h = m.portrait ? mod.h_m : mod.w_m, b = rad(m.rot_deg);
  const s = Math.sin(b), c = Math.cos(b); // local y axis points along bearing b, local x axis along b + 90
  return ([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]] as Pt[])
    .map(([lx, ly]) => [m.x + lx * c + ly * s, m.y - lx * s + ly * c]);
}

function overlaps(a: Pt[], b: Pt[]): boolean {   // separating axis test, 1 cm tolerance so touching modules are fine
  for (const poly of [a, b]) {
    for (let i = 0; i < 4; i++) {
      const [x1, y1] = poly[i], [x2, y2] = poly[(i + 1) % 4];
      const nx = y2 - y1, ny = x1 - x2;
      const pa = a.map(([x, y]) => x * nx + y * ny), pb = b.map(([x, y]) => x * nx + y * ny);
      const len = Math.hypot(nx, ny) || 1;
      if (Math.max(...pa) - Math.min(...pb) <= 0.01 * len || Math.max(...pb) - Math.min(...pa) <= 0.01 * len) return false;
    }
  }
  return true;
}

export function RoofEditor({ plan, disabled, onPlan }: { plan: Plan; disabled: boolean; onPlan: (p: Plan) => void }) {
  const layout = plan.roof_layout;
  const loc = plan.roof_location;
  const [mods, setMods] = useState<LayoutModule[]>(layout?.modules ?? []);
  const [sel, setSel] = useState<number | null>(null);
  const [undo, setUndo] = useState<LayoutModule[][]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [noPhoto, setNoPhoto] = useState(false);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ i: number; dx: number; dy: number } | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const seq = useRef(0);
  const busy = useRef(false);   // local edits not yet answered by reo: do not overwrite them with an older plan
  const live = useRef(mods);
  live.current = mods;

  // A plan that arrives from elsewhere (reload, other edit, reset) replaces the local layout unless we are mid-edit.
  useEffect(() => { if (!busy.current && !drag.current) setMods(layout?.modules ?? []); }, [layout]);

  const photo = !!(loc && layout?.frame.lat != null && layout.frame.lon != null);
  const view = useMemo(() => (photo ? roofView(loc!) : null), [photo, loc]);

  const geo = useMemo(() => {
    if (!layout) return null;
    if (view) {
      const [ox, oy] = view.toUnits(layout.frame.lat!, layout.frame.lon!);
      const mpp = metresPerUnit(layout.frame.lat!, view.z);
      return { ox, oy, mpp, vb: [0, 0, view.vw, view.vh] as [number, number, number, number] };
    }
    const mpp = 1 / BLANK_UNITS_PER_M;
    const xs = layout.modules.flatMap((m) => corners(m, layout.module).map((c) => c[0]));
    const ys = layout.modules.flatMap((m) => corners(m, layout.module).map((c) => c[1]));
    const [x0, x1, y0, y1] = xs.length ? [Math.min(...xs) - 3, Math.max(...xs) + 3, Math.min(...ys) - 3, Math.max(...ys) + 3] : [-6, 6, -4, 4];
    return { ox: 0, oy: 0, mpp, vb: [x0 / mpp, -y1 / mpp, (x1 - x0) / mpp, (y1 - y0) / mpp] as [number, number, number, number] };
  }, [layout, view]);

  const outlineM = useMemo<Pt[] | null>(() => {   // roof outline in metres, to flag modules that leave it
    if (!view || !geo || !loc?.outline?.length) return null;
    return loc.outline.map(([la, lo]) => { const [ux, uy] = view.toUnits(la, lo); return [(ux - geo.ox) * geo.mpp, -(uy - geo.oy) * geo.mpp] as Pt; });
  }, [view, geo, loc]);

  const bad = useMemo(() => {
    const set = new Set<number>();
    if (!layout) return set;
    const polys = mods.map((m) => corners(m, layout.module));
    polys.forEach((p, i) => {
      if (outlineM && !p.every((c) => pointInPoly(c, outlineM))) set.add(i);
      for (let j = i + 1; j < polys.length; j++) if (overlaps(p, polys[j])) { set.add(i); set.add(j); }
    });
    return set;
  }, [mods, layout, outlineM]);

  if (!layout || !geo) return null;
  const { module: mod, frame } = layout;
  const pv = plan.design.components.pv;
  const wp = mod.wp;

  function persist(next: LayoutModule[]) {
    window.clearTimeout(timer.current);
    busy.current = true;
    const mine = ++seq.current;
    timer.current = window.setTimeout(async () => {
      setSaving(true);
      try {
        const p = await api.putLayout(plan.id, next, frame);
        if (mine === seq.current) { busy.current = false; onPlan(p); setError(null); }
      } catch (e) {
        if (mine === seq.current) { busy.current = false; setError(e instanceof Error ? e.message : "Could not save the layout"); }
      } finally {
        if (mine === seq.current) setSaving(false);
      }
    }, 300);
  }

  function change(next: LayoutModule[], keepSel = sel) {
    setUndo((u) => [...u.slice(-29), live.current]);
    setMods(next);
    setSel(keepSel);
    persist(next);
  }

  const toMetres = (e: { clientX: number; clientY: number }): Pt => {
    const s = svg.current!, pt = s.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const q = pt.matrixTransform(s.getScreenCTM()!.inverse());
    return [(q.x - geo!.ox) * geo!.mpp, -(q.y - geo!.oy) * geo!.mpp];
  };

  const ext = (m: LayoutModule): Pt => (m.portrait ? [mod.w_m, mod.h_m] : [mod.h_m, mod.w_m]);
  const b = rad(frame.azimuth_deg), cb = Math.cos(b), sb = Math.sin(b);   // roof frame: u along the eave, v up the slope
  const toUV = (x: number, y: number): Pt => [x * cb - y * sb, x * sb + y * cb];
  const fromUV = (u: number, v: number): Pt => [u * cb + v * sb, -u * sb + v * cb];

  function snap(i: number, x: number, y: number): Pt {
    let [u, v] = toUV(x, y);
    const [cw, ch] = ext(mods[i]);
    let bu = SNAP, bv = SNAP, su = u, sv = v;
    mods.forEach((o, j) => {
      if (j === i) return;
      const [ou, ov] = toUV(o.x, o.y), [ow, oh] = ext(o);
      for (const cand of [ou, ou - (cw + ow) / 2 - GAP, ou + (cw + ow) / 2 + GAP]) if (Math.abs(cand - u) < bu) { bu = Math.abs(cand - u); su = cand; }
      for (const cand of [ov, ov - (ch + oh) / 2 - GAP, ov + (ch + oh) / 2 + GAP]) if (Math.abs(cand - v) < bv) { bv = Math.abs(cand - v); sv = cand; }
    });
    return fromUV(su, sv);
  }

  function down(e: React.PointerEvent, i: number) {
    if (disabled) return;
    e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    const [x, y] = toMetres(e);
    drag.current = { i, dx: mods[i].x - x, dy: mods[i].y - y };
    setUndo((u) => [...u.slice(-29), live.current]);
    setSel(i);
  }
  function move(e: React.PointerEvent) {
    const d = drag.current;
    if (!d) return;
    const [x, y] = toMetres(e);
    const [sx, sy] = snap(d.i, x + d.dx, y + d.dy);
    setMods((ms) => ms.map((m, k) => (k === d.i ? { ...m, x: Math.round(sx * 1000) / 1000, y: Math.round(sy * 1000) / 1000 } : m)));
  }
  function up() {
    if (!drag.current) return;
    drag.current = null;
    persist(live.current);
  }

  const add = () => {
    const base = sel != null ? mods[sel] : mods[mods.length - 1];
    let m: LayoutModule = { x: 0, y: 0, rot_deg: frame.azimuth_deg, portrait: true };
    if (base) {
      const [u, v] = toUV(base.x, base.y), [cw] = ext(base);
      const [x, y] = fromUV(u + cw + GAP, v);
      m = { ...base, x: Math.round(x * 1000) / 1000, y: Math.round(y * 1000) / 1000 };
    }
    change([...mods, m], mods.length);
  };
  const remove = () => { if (sel != null) change(mods.filter((_, k) => k !== sel), null); };
  const rotate = () => { if (sel != null) change(mods.map((m, k) => (k === sel ? { ...m, portrait: !m.portrait } : m))); };
  const undoLast = () => {
    const prev = undo[undo.length - 1];
    if (!prev) return;
    setUndo((u) => u.slice(0, -1));
    setMods(prev);
    setSel(null);
    persist(prev);
  };
  async function reset() {
    window.clearTimeout(timer.current);
    setSaving(true);
    try {
      busy.current = false;
      seq.current++;
      onPlan(await api.resetLayout(plan.id));
      setUndo([]);
      setSel(null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reset the layout");
    } finally {
      setSaving(false);
    }
  }
  function keys(e: React.KeyboardEvent) {
    if (disabled) return;
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); remove(); }
    else if (e.key === "r" || e.key === "R") rotate();
    else if ((e.metaKey || e.ctrlKey) && e.key === "z") { e.preventDefault(); undoLast(); }
  }

  const w = mod.w_m / geo.mpp, h = mod.h_m / geo.mpp;
  const kwp = (mods.length * wp) / 1000;
  const cap = pv?.max_modules;
  const outline = loc?.outline?.length && view ? loc.outline.map(([la, lo]) => view.toUnits(la, lo).join(",")).join(" ") : "";

  return (
    <section className="card roof-editor" aria-label="Roof and solar modules">
      <div className="roof-head">
        <h3>Roof and solar modules</h3>
        {layout.source === "auto" && <span className="muted">Placed automatically from the roof outline. Drag to rearrange.</span>}
      </div>
      <div className="roof-stage" tabIndex={0} onKeyDown={keys}>
        <svg ref={svg} viewBox={geo.vb.join(" ")} className={`roof-svg ${view && !noPhoto ? "" : "is-blank"}`} onPointerMove={move} onPointerUp={up}
          onPointerDown={() => setSel(null)} role="img" aria-label={`${mods.length} solar modules on the roof`}>
          {view && !noPhoto && view.tiles.map(({ x, y }, i) => (
            <image key={`${x}-${y}`} href={view.tileUrl(x, y)} x={x * 256 - view.left} y={y * 256 - view.top} width={256} height={256}
              onError={i === 0 ? () => setNoPhoto(true) : undefined} />
          ))}
          {outline && <polygon points={outline} className={`satellite-outline ${loc?.checked ? "is-checked" : ""}`} vectorEffect="non-scaling-stroke" />}
          {mods.map((m, i) => (
            <g key={i} transform={`translate(${geo.ox + m.x / geo.mpp} ${geo.oy - m.y / geo.mpp}) rotate(${m.rot_deg})`}
              className={`pv-module ${sel === i ? "is-selected" : ""} ${bad.has(i) ? "is-bad" : ""} ${disabled ? "is-locked" : ""}`}
              onPointerDown={(e) => down(e, i)}>
              <rect x={-(m.portrait ? w : h) / 2} y={-(m.portrait ? h : w) / 2} width={m.portrait ? w : h} height={m.portrait ? h : w} rx={1.5} vectorEffect="non-scaling-stroke" />
              <line x1={-(m.portrait ? w : h) / 2} x2={(m.portrait ? w : h) / 2} y1={0} y2={0} vectorEffect="non-scaling-stroke" />
            </g>
          ))}
        </svg>
        {view && !noPhoto && <span className="satellite-credit">© Esri, Maxar, Earthstar Geographics</span>}
      </div>
      <div className="roof-bar">
        <strong className="roof-count">{mods.length} modules · {kwp.toFixed(2)} kWp</strong>
        <div className="roof-actions">
          <button className="btn-small" onClick={add} disabled={disabled}>Add module</button>
          <button className="btn-small" onClick={rotate} disabled={disabled || sel == null}>Rotate</button>
          <button className="btn-small" onClick={remove} disabled={disabled || sel == null}>Remove</button>
          <button className="btn-small" onClick={undoLast} disabled={disabled || !undo.length}>Undo</button>
          <button className="btn-small" onClick={reset} disabled={disabled || (layout.source === "auto" && !undo.length)}>Reset to automatic</button>
        </div>
      </div>
      {bad.size > 0 && <p className="roof-warn">⚠ {bad.size} module{bad.size === 1 ? "" : "s"} overlap or leave the roof outline (red). Move them before sending the quote.</p>}
      {layout.note && <p className="roof-warn">⚠ {layout.note}.</p>}
      {cap != null && mods.length > cap && <p className="roof-warn">⚠ The engine limits this roof to {cap} modules.</p>}
      {photo && !loc?.checked && <p className="muted roof-hint">Outline from OpenStreetMap, not traced on the photo: check it before relying on the placement.</p>}
      {!photo && <p className="muted roof-hint">No satellite photo for this address: modules are drawn on a plain background.</p>}
      {error && <div className="chat-error">{error}</div>}
      <p className="muted roof-hint">{saving ? "Saving…" : "Changing the number of modules re-derives the price and savings. Moving them does not. Keys: R rotates, Delete removes, ⌘/Ctrl+Z undoes."}</p>
    </section>
  );
}

export type { RoofLayout };
