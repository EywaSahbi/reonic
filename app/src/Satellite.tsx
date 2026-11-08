import { useState, type ReactNode } from "react";
import type { RoofLocation } from "./types";

// Satellite picture of the customer's own building (Esri World Imagery tiles, no key) with the OpenStreetMap outline
// reo used for the roof estimate drawn on top. Replaces the drawn house once an address was found.
// Tiles and outline share one Web-Mercator pixel space, so the outline sits exactly on the building.
const W = 640, H = 380; // same shape as the drawn house (320 x 190)
const TILE = 256, MAX_ZOOM = 19; // Esri has real imagery up to 19 in Germany; 20 is a placeholder
const FILL = 0.5, MAX_UPSCALE = 2.5; // beyond zoom 19 we enlarge: house fills ~50% of the frame (some street and garden around it), at most 2.5x
const URL = (z: number, x: number, y: number) =>
  `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`;

// World pixel coordinates at zoom z.
function px(lat: number, lon: number, z: number): [number, number] {
  const n = TILE * 2 ** z, r = (lat * Math.PI) / 180;
  return [((lon + 180) / 360) * n, ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n];
}

/** The photo frame for a roof: zoom, visible part of the map (viewBox units = zoom-z pixels), tiles, and the lat/lon -> unit mapping.
 *  Shared by the customer's satellite view and the planner's module editor. */
export function roofView(loc: RoofLocation) {
  const pts = loc.outline?.length ? loc.outline : [[loc.lat, loc.lon] as [number, number]];
  // Zoom: the largest at which the building plus a margin still fits the frame.
  let z = MAX_ZOOM;
  for (; z > 15; z--) {
    const p = pts.map(([la, lo]) => px(la, lo, z));
    const w = Math.max(...p.map((q) => q[0])) - Math.min(...p.map((q) => q[0]));
    const h = Math.max(...p.map((q) => q[1])) - Math.min(...p.map((q) => q[1]));
    if (w <= W * 0.45 && h <= H * 0.45) break;
  }
  const p = pts.map(([la, lo]) => px(la, lo, z));
  const cx = (Math.max(...p.map((q) => q[0])) + Math.min(...p.map((q) => q[0]))) / 2;
  const cy = (Math.max(...p.map((q) => q[1])) + Math.min(...p.map((q) => q[1]))) / 2;
  const bw = Math.max(...p.map((q) => q[0])) - Math.min(...p.map((q) => q[0]));
  const bh = Math.max(...p.map((q) => q[1])) - Math.min(...p.map((q) => q[1]));
  const scale = Math.min(MAX_UPSCALE, Math.max(1, Math.min((FILL * W) / (bw || 1), (FILL * H) / (bh || 1))));
  const vw = W / scale, vh = H / scale; // the part of the zoom-z map shown in the frame
  const left = cx - vw / 2, top = cy - vh / 2;
  const tiles: { x: number; y: number }[] = [];
  for (let x = Math.floor(left / TILE); x <= Math.floor((left + vw) / TILE); x++)
    for (let y = Math.floor(top / TILE); y <= Math.floor((top + vh) / TILE); y++) tiles.push({ x, y });
  const toUnits = (la: number, lo: number): [number, number] => { const [x, y] = px(la, lo, z); return [x - left, y - top]; };
  return { z, left, top, vw, vh, tiles, toUnits, tileUrl: (x: number, y: number) => URL(z, x, y) };
}

/** Metres per viewBox unit of a roofView at this latitude (Web Mercator: same in both axes). */
export const metresPerUnit = (lat: number, z: number) => (40075016.686 * Math.cos((lat * Math.PI) / 180)) / (TILE * 2 ** z);

export function Satellite({ loc, fallback }: { loc: RoofLocation; fallback: ReactNode }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <>{fallback}</>;

  const { z, left, top, vw, vh, tiles, toUnits } = roofView(loc);
  const outline = loc.outline?.length ? loc.outline.map(([la, lo]) => toUnits(la, lo).join(",")).join(" ") : "";

  return (
    <figure className="house satellite" aria-label={`Satellite view of ${loc.label}`}>
      <svg viewBox={`0 0 ${vw} ${vh}`} role="img" className="satellite-frame">
        {tiles.map(({ x, y }, i) => (
          <image key={`${x}-${y}`} href={URL(z, x, y)} x={x * TILE - left} y={y * TILE - top} width={TILE} height={TILE}
            onError={i === 0 ? () => setFailed(true) : undefined} />
        ))}
        {outline && <polygon points={outline} className={`satellite-outline ${loc.checked ? "is-checked" : ""}`} vectorEffect="non-scaling-stroke" />}
      </svg>
      {loc.checked && <span className="satellite-checked">✓ Roof outline traced from this photo</span>}
      <span className="satellite-credit">© Esri, Maxar, Earthstar Geographics</span>
    </figure>
  );
}
