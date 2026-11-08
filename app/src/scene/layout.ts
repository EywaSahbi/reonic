import type { Design, HomeFacts, Locks } from "../types";

// Pure geometry for the 3D house and the planner's design studio. Display only: the engine decides every size and price.
// Module and margin match engine/CONTRACT.md (1.722 × 1.134 m, 0.3 m edge margin).
export const MOD_LONG = 1.722, MOD_SHORT = 1.134, MARGIN = 0.3, GAP = 0.03;
export const WALL_H = 4.6; // one and a half storeys, reads well from an isometric camera

export type Roof = { width: number; slope: number; tilt: number; flat: boolean; known: boolean };
export type Cell = { id: string; face: 0 | 1; x: number; y: number; w: number; h: number };
export type ItemKey = "battery" | "heatpump" | "wallbox";
export type Spot = [number, number]; // ground x, z
export type Items = Record<ItemKey, Spot | null>; // null = not part of the design

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Sunny roof face from the facts: measured face > roof area > a typical detached house. */
export function roofFrom(f: HomeFacts & { roof_type?: string }): Roof {
  const tilt = clamp(f.roof_tilt_deg ?? 35, 0, 55);
  const flat = f.roof_type === "flat" || tilt < 5;
  if (f.roof_width_m && f.roof_length_m) {
    const [w, s] = f.roof_width_m >= f.roof_length_m ? [f.roof_width_m, f.roof_length_m] : [f.roof_length_m, f.roof_width_m];
    return { width: clamp(w, 5, 22), slope: clamp(s, 3, 9), tilt, flat, known: true };
  }
  if (f.roof_area_sqm) return { width: clamp(f.roof_area_sqm / 5, 6, 18), slope: 5, tilt, flat, known: true };
  return { width: 11, slope: 5, tilt, flat, known: false };
}

/** The drawn front face approximates the engine's roof: grow it (one more row, then longer) until `need` modules fit,
 * so the picture can show every module the engine counts, all on the front. */
export function fitRoof(f: HomeFacts, need: number): Roof {
  const r = roofFrom(f);
  while (r.width < 40 && roofCells(r).filter((c) => c.face === 0).length < need) { if (r.slope < 7) r.slope += 0.5; else r.width += 0.5; }
  return r;
}

/** Module spots on the front face only (nothing on the back that the plan would not count). */
export function frontCells(r: Roof, maxModules: number | null | undefined, need: number): Cell[] {
  return roofCells(r, maxModules ?? undefined, need).filter((c) => c.face === 0);
}

/** House footprint that carries this roof: length along the ridge, depth front to back. */
export function houseDims(r: Roof) {
  const rad = (r.tilt * Math.PI) / 180;
  const depth = r.flat ? r.slope : 2 * r.slope * Math.cos(rad);
  const rise = r.flat ? 0 : r.slope * Math.sin(rad);
  return { length: r.width, depth: clamp(depth, 6, 12), rise };
}

/** Module grid on one face, rows from the eave up, best of portrait or landscape (same rule as the engine). */
function faceGrid(width: number, slope: number) {
  const fit = (a: number, b: number) => ({ cols: Math.floor((width - 2 * MARGIN + GAP) / (a + GAP)), rows: Math.floor((slope - 2 * MARGIN + GAP) / (b + GAP)), w: a, h: b });
  const p = fit(MOD_SHORT, MOD_LONG), l = fit(MOD_LONG, MOD_SHORT);
  return p.cols * p.rows >= l.cols * l.rows ? p : l;
}

/** Cells on the sunny face (face 0) first, then the back face (face 1): offered when the roof is not measured, or when the
 * engine places more modules than our drawn face holds (our face is an approximation of the engine's roof). */
export function roofCells(r: Roof, maxModules?: number, need = 0): Cell[] {
  const g = faceGrid(r.width, r.slope);
  const out: Cell[] = [];
  for (const face of [0, 1] as const) {
    if (face === 1 && (r.flat || (r.known && need <= out.length))) break;
    for (let row = 0; row < g.rows; row++)
      for (let col = 0; col < g.cols; col++) {
        const usedW = g.cols * (g.w + GAP) - GAP;
        out.push({ id: `${face}-${row}-${col}`, face, w: g.w, h: g.h, x: -usedW / 2 + col * (g.w + GAP) + g.w / 2, y: MARGIN + row * (g.h + GAP) + g.h / 2 });
      }
  }
  if (maxModules != null && maxModules >= 0) return out.slice(0, Math.max(maxModules, need, 0));
  return out;
}

/** The engine's module count, drawn on the first cells. quantity missing but kWp given: show what one module per 0.43 kWp would look like. */
export function enginePanels(d: Design, cells: Cell[]): Set<string> {
  const pv = d.components.pv;
  const on = pv.recommended && (pv.size ?? 0) > 0;
  const n = !on ? 0 : pv.quantity ?? Math.round((pv.size ?? 0) / 0.43); // shortcut: 0.43 kWp/module only for drawing when quantity is absent
  return new Set(cells.slice(0, n).map((c) => c.id));
}

export function defaultItems(d: Design, r: Roof): Items {
  const { length: L, depth: D } = houseDims(r);
  const c = d.components;
  return {
    heatpump: c.heatpump.recommended ? [-L / 2 + 1.4, D / 2 + 0.9] : null,
    battery: c.battery.recommended ? [L / 2 - 1.0, D / 2 + 0.45] : null,
    wallbox: c.wallbox.recommended ? [L / 2 + 0.25, D / 2 - 2.6] : null,
  };
}

/** Keep an item on the lot and out of the house. */
export function placeOnLot([x, z]: Spot, r: Roof): Spot {
  const { length: L, depth: D } = houseDims(r);
  const lx = L / 2 + 5.5, lz = D / 2 + 5.5;
  x = clamp(x, -lx, lx); z = clamp(z, -lz, lz);
  const hx = L / 2 + 0.25, hz = D / 2 + 0.25;
  if (Math.abs(x) < hx && Math.abs(z) < hz) {
    const dx = hx - Math.abs(x), dz = hz - Math.abs(z);
    if (dx < dz) x = Math.sign(x || 1) * hx; else z = Math.sign(z || 1) * hz;
  }
  return [x, z];
}

/** kWp per module as the engine sized it; null when the engine has no module count to divide by. */
export const kwpPerModule = (d: Design) => {
  const pv = d.components.pv;
  return pv.quantity && pv.size ? pv.size / pv.quantity : null;
};

/**
 * Turn the planner's placement into locks for PATCH /plans/{id}. Only components that differ from the engine's design are locked.
 * pv size = modules × the engine's own kWp per module; the engine re-derives (and may cut to max_modules).
 */
export function locksFrom(d: Design, modules: number, items: Items, perModule: number | null): Locks {
  const c = d.components, locks: Locks = {};
  const engineModules = c.pv.recommended ? c.pv.quantity ?? null : 0;
  if (modules !== engineModules) {
    locks.pv = modules === 0 ? { recommended: false } : perModule ? { recommended: true, size: Math.round(modules * perModule * 100) / 100 } : { recommended: true };
  }
  for (const k of ["battery", "heatpump", "wallbox"] as const) {
    const want = items[k] !== null;
    if (want !== c[k].recommended) locks[k] = want ? { recommended: true } : { recommended: false };
  }
  return locks;
}


// ---------- free module placement (planner's design studio) ----------
// Face coordinates of the front roof: x along the eave (0 = middle), y up the slope from the eave. Module centres only.
export type FreePanel = { id: string; x: number; y: number };
export type RoofArea = { xMin: number; xMax: number; yMin: number; yMax: number; w: number; h: number; width: number; top: number };
type Pt = { x: number; y: number };
const EPS = 0.005;
let nextId = 0;
const newId = () => `m${++nextId}`;

/** Where module centres may sit (same module orientation and margins as the grid, so the engine's count always fits). */
export function roofArea(r: Roof): RoofArea {
  const { length: L } = houseDims(r);
  const g = faceGrid(r.width, r.slope);
  const [w, h] = g.cols > 0 && g.rows > 0 ? [g.w, g.h] : [MOD_SHORT, MOD_LONG];
  return { xMin: -L / 2 + MARGIN + w / 2, xMax: L / 2 - MARGIN - w / 2, yMin: MARGIN + h / 2, yMax: r.slope - MARGIN - h / 2, w, h, width: L, top: r.slope };
}

export const clampToRoof = (p: Pt, a: RoofArea): Pt => ({ x: clamp(p.x, a.xMin, a.xMax), y: clamp(p.y, a.yMin, a.yMax) });

/** Inside the roof and not overlapping another module (`skip`: the module being moved). */
export function fits(p: Pt, panels: FreePanel[], a: RoofArea, skip?: string): boolean {
  if (p.x < a.xMin - EPS || p.x > a.xMax + EPS || p.y < a.yMin - EPS || p.y > a.yMax + EPS) return false;
  return panels.every((q) => q.id === skip || Math.abs(q.x - p.x) >= a.w + GAP - EPS || Math.abs(q.y - p.y) >= a.h + GAP - EPS);
}

/** Free spots right beside another module (left, right, above, below): where a module joins the formation. */
function besides(panels: FreePanel[], a: RoofArea, skip?: string): Pt[] {
  const dx = a.w + GAP, dy = a.h + GAP;
  return panels.filter((q) => q.id !== skip)
    .flatMap((q) => [{ x: q.x + dx, y: q.y }, { x: q.x - dx, y: q.y }, { x: q.x, y: q.y + dy }, { x: q.x, y: q.y - dy }])
    .filter((s) => fits(s, panels, a, skip));
}

/** An added module joins the others as a rectangle: fill the lowest row first, left to right, then the next row up. */
export function nextSlot(panels: FreePanel[], a: RoofArea): Pt | null {
  if (!panels.length) return a.xMax >= a.xMin - EPS && a.yMax >= a.yMin - EPS ? { x: a.xMin, y: a.yMin } : null;
  const s = besides(panels, a);
  s.sort((p, q) => Math.round((p.y - q.y) * 100) || p.x - q.x);
  return s[0] ?? null;
}

/** A clicked or dropped spot: the nearest place beside another module within `reach` metres (so rows line up), else the
 * spot itself if it is free. */
export function snapSlot(p: Pt, panels: FreePanel[], a: RoofArea, skip?: string, reach = 0.6): Pt | null {
  const near = besides(panels, a, skip).map((q) => ({ q, d: Math.hypot(q.x - p.x, q.y - p.y) })).sort((m, n) => m.d - n.d)[0];
  if (near && near.d <= reach) return near.q;
  const c = clampToRoof(p, a);
  return fits(c, panels, a, skip) ? c : null;
}

/** `n` modules: keep the planner's own (those still on the roof), add the rest to the formation, drop the surplus. */
export function layoutPanels(n: number, a: RoofArea, keep: FreePanel[] = []): FreePanel[] {
  const out: FreePanel[] = [];
  for (const p of keep) if (out.length < n && fits(p, out, a)) out.push(p);
  while (out.length < n) {
    const s = nextSlot(out, a);
    if (!s) break;
    out.push({ id: newId(), ...s });
  }
  return out;
}

export const addPanel = (panels: FreePanel[], at: Pt): FreePanel[] => [...panels, { id: newId(), ...at }];
