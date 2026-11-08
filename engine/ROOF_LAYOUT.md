# Roof layout (planner module placement): phase 0 draft

Local draft by engine, not posted, not committed. Decisions fixed by the human (2026-11-08):
customer view stays outline-only; orientation is visual only (no yield change); one module type, one roof plane.

## 1. What is shown

Planner opens a plan -> satellite photo + traced outline (same data the customer gets) + the PV modules already
placed on the roof, count = the engine's PV quantity. Planner drags / removes / adds / rotates modules. The module count
is the only thing the engine hears; positions are reo/app state.

## 2. The object (lives on the plan, owner: reo store, drawn by app)

```ts
type RoofLayout = {
  source: "auto" | "planner";            // auto = generated on first open, planner = touched by a human
  module: { w_m: number; h_m: number; wp: number; id: string };  // from the engine design (section 4); w_m = short side
  frame: { lat: number; lon: number; azimuth_deg: number };       // origin = outline centroid; azimuth = compass direction the roof faces
  modules: { x: number; y: number; rot_deg: number; portrait: boolean }[];
};
```

- Metres in a local frame: origin at `frame` (lat, lon), x = east, y = north, equirectangular. The app converts to photo
  pixels with the same projection it already uses for the outline. Metres survive zoom changes; pixels do not.
- `rot_deg` = rotation of the module rectangle clockwise from north. Default = roof azimuth snapped to the eave direction.
- `portrait` swaps w/h. Visual only.
- Count = `modules.length`. No other field feeds a number.

## 3. The only number that moves: module count -> pv lock

`size_kwp = count * module.wp / 1000`. Verified on the engine today (locks `{"pv": {"recommended": true, "size": n*0.43}}`):

| count | size kWp | quantity |
|---|---|---|
| 10 | 4.30 | 10 |
| 23 | 9.89 | 23 |
| 24 | 10.32 | 24 |

So count round-trips with no engine change. Rules:
- count 0 -> lock `{"recommended": false}`.
- count above the engine's `max_modules` -> engine cuts it and says why (existing behaviour); app shows the cut count and the reason.
- Rest of the design (battery, price, savings) re-derives as for any planner edit.
- Planner moves a module: no engine call (positions do not matter). Add/remove: one `/edit`, debounced.

## 4. Engine deliverable (phase 1, small)

Add to the PV component of the design output: `module: {id, w_m, h_m, wp}` so the front end draws real sizes.
Open point: two module definitions disagree today.
- `params.json`: 430 W, 1.722 x 1.134 m (Jinko), used for sizing, `max_modules` and the roof grid.
- `catalog.json`: JA Solar 440 W (priced item in the quote).
Proposed: expose the sizing module (430 W, 1.722 x 1.134) as `module`, since count x Wp must match `quantity`; the quote line keeps
the catalog label. Aligning the two (one product) is a separate decision for the engine owner and Eywa (catalog).

## 5. Who does what

| Phase | Owner | Folder | Needs ACK |
|---|---|---|---|
| 1 `module` in design output, tests | engine | `engine/` | no |
| 2 `roof_layout` in plan store, `roof_location` exposed to planner, PATCH layout -> pv lock | reo | `reo/` | yes (reo) |
| 3 auto-placement (setback, grid along azimuth, stop at count) | reo (Python, next to `roof.py`) | `reo/` | yes (reo) |
| 4 planner SVG layer: drag/remove/add/rotate/undo/reset | app | `app/` | yes (app) |
| 5 overlap/outside checks, rectangle fallback, e2e | app + qa | | |

Auto-placement in Python on reo (not in the browser) so the layout is the same for every viewer and testable.

## 6. Out of scope (fixed)

Customer-side panels, orientation affecting yield, several module types, several roof planes, layout surviving customer edits (stays as is).

## 7. Risks and guards

- Outline wrong -> panels wrong: auto layout only fills the checked outline; unchecked outline shows panels with a "rough outline" tag.
- Fewer cells than the engine count: show the smaller count and the reason, never overlap to hit the number.
- Demo addresses with no OSM outline: rectangle from width x length (`roof_dims`), so the view is never empty.
- Photo or vision fails: draw outline + panels without the photo.
- Layout stale after the engine count changes (planner edits PV size in the numbers table): regenerate from the new count, keep `source: "planner"` positions that still fit, drop/add at the end.
