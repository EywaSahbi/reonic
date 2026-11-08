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
