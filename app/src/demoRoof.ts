import type { LayoutModule, PvModule, RoofLayout, RoofLocation } from "./types";

// Demo roof for the video: Sandstraße 33, 80335 München (Maxvorstadt). Hardcoded, NOT reo output.
// The outline and obstacles were read off the Esri satellite photo (zoom 19): a light flat roof of about 14.6 x 19 m with a glazed skylight
// strip on its left and six rooftop units (hatches, vents, small air handlers). Modules keep 0.9 m from the roof edge and 0.65 m from every
// obstacle. The first 24 positions are the automatic layout (two long rows along the south-west eave, then four modules on the
// north-east edge); the rest are free spots that stay obstacle-free, so the planner can add modules there.
export const SAND33: RoofLocation = {
  label: "Sandstraße 33, 80335 München",
  lat: 48.14958, lon: 11.556517,
  outline: [[48.1496947, 11.5565506],[48.1496433, 11.5567308],[48.1494895, 11.5566176],[48.1495448, 11.5564399],[48.1496080, 11.5564835],[48.1496640, 11.5565020]],
  checked: true,
};

export const SAND33_MODULE: PvModule = { id: "430 W glass-glass", wp: 430, w_m: 1.134, h_m: 1.722 };
export const SAND33_FRAME: RoofLayout["frame"] = { lat: 48.1496074, lon: 11.5565541, azimuth_deg: 25.0 };

/** Free positions in priority order: the first N are the automatic layout for an N-module design. */
export const SAND33_MODULES: LayoutModule[] = [
  { x: -5.04, y: -5.34, rot_deg: 25.0, portrait: true },
  { x: -3.99, y: -5.83, rot_deg: 25.0, portrait: true },
  { x: -2.95, y: -6.31, rot_deg: 25.0, portrait: true },
  { x: -1.90, y: -6.80, rot_deg: 25.0, portrait: true },
  { x: -0.86, y: -7.29, rot_deg: 25.0, portrait: true },
  { x: 0.19, y: -7.78, rot_deg: 25.0, portrait: true },
  { x: 1.23, y: -8.27, rot_deg: 25.0, portrait: true },
  { x: 2.28, y: -8.75, rot_deg: 25.0, portrait: true },
  { x: 3.33, y: -9.24, rot_deg: 25.0, portrait: true },
  { x: 4.37, y: -9.73, rot_deg: 25.0, portrait: true },
  { x: -4.30, y: -3.76, rot_deg: 25.0, portrait: true },
  { x: -3.26, y: -4.25, rot_deg: 25.0, portrait: true },
  { x: -2.21, y: -4.74, rot_deg: 25.0, portrait: true },
  { x: -1.17, y: -5.22, rot_deg: 25.0, portrait: true },
  { x: -0.12, y: -5.71, rot_deg: 25.0, portrait: true },
  { x: 0.93, y: -6.20, rot_deg: 25.0, portrait: true },
  { x: 1.97, y: -6.69, rot_deg: 25.0, portrait: true },
  { x: 3.02, y: -7.18, rot_deg: 25.0, portrait: true },
  { x: 4.06, y: -7.66, rot_deg: 25.0, portrait: true },
  { x: 5.11, y: -8.15, rot_deg: 25.0, portrait: true },
  { x: 7.13, y: 4.36, rot_deg: 25.0, portrait: true },
  { x: 8.18, y: 3.87, rot_deg: 25.0, portrait: true },
  { x: 9.22, y: 3.38, rot_deg: 25.0, portrait: true },
  { x: 10.27, y: 2.90, rot_deg: 25.0, portrait: true },
  { x: -0.43, y: -3.65, rot_deg: 25.0, portrait: true },
  { x: 0.62, y: -4.13, rot_deg: 25.0, portrait: true },
  { x: 5.85, y: -6.57, rot_deg: 25.0, portrait: true },
  { x: 0.31, y: -2.07, rot_deg: 25.0, portrait: true },
  { x: 1.35, y: -2.55, rot_deg: 25.0, portrait: true },
  { x: 6.58, y: -5.00, rot_deg: 25.0, portrait: true },
  { x: 0.00, y: 0.00, rot_deg: 25.0, portrait: true },
  { x: 1.05, y: -0.49, rot_deg: 25.0, portrait: true },
  { x: 2.09, y: -0.98, rot_deg: 25.0, portrait: true },
  { x: 3.14, y: -1.46, rot_deg: 25.0, portrait: true },
  { x: 0.74, y: 1.58, rot_deg: 25.0, portrait: true },
  { x: 1.78, y: 1.09, rot_deg: 25.0, portrait: true },
  { x: 4.92, y: -0.37, rot_deg: 25.0, portrait: true },
  { x: 1.47, y: 3.16, rot_deg: 25.0, portrait: true },
  { x: 5.66, y: 1.20, rot_deg: 25.0, portrait: true },
  { x: 2.21, y: 4.74, rot_deg: 25.0, portrait: true },
  { x: 6.39, y: 2.78, rot_deg: 25.0, portrait: true },
  { x: 0.86, y: 7.29, rot_deg: 25.0, portrait: true },
  { x: 1.90, y: 6.80, rot_deg: 25.0, portrait: true },
  { x: 2.95, y: 6.31, rot_deg: 25.0, portrait: true },
];

export const SAND33_OBSTACLES = "glazed skylight strip and 6 rooftop units kept 0.65 m clear, 0.9 m from the roof edge";
