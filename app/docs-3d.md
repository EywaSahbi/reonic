# 3D house + planner design studio (app/)

Replaces the flat SVG house (`src/House.tsx`) with a real 3D scene. Owner: app. Started Sun 8 Nov.

## Goal

- **Customer (plan card):** a small, friendly 3D house that builds itself as the plan grows: panels on the roof, battery on the wall, heat pump in the yard, car at the wallbox. Slowly turns, can be dragged to look around. Read-only.
- **Planner (`#/installer` → plan → "Design studio"):** a "build mode" view like a life-sim game: isometric camera over a lot, a palette of components, drag a component into the scene to place it, drag panels across the roof to paint rows, click to remove, drag to move. "Apply to plan" sends the result to reo, the engine re-derives everything, and the scene redraws from the engine's answer.

Inspiration: Reonic's planner (module grid on the roof face, components placed around the house). Open source engine: **three.js** through **@react-three/fiber** + **@react-three/drei** (MIT). No external 3D assets; everything is built from primitives so it loads instantly and works offline.

## Hard rule 2 still holds

The scene computes no number a user sees. It only:
- draws the engine's design (`components.pv.quantity`, `battery/heatpump/wallbox.recommended`, `pv.max_modules`),
- turns the planner's placement into **locks**: `pv = { recommended, size: modules × (pv.size / pv.quantity) }` (the engine's own kWp per module), `battery/heatpump/wallbox = { recommended }`, battery size kept from the current design.
- sends them through the existing `PATCH /plans/{id}` (`api.editPlan`), which already re-derives the design. The engine may cut a PV lock to `max_modules`; the scene shows what came back, plus the engine's reason.

Prices, savings and payback in the studio sidebar are the engine's values from the last response. While the planner has unapplied changes the sidebar says "not applied yet" and shows no new number.

No contract change for reo or engine. `max_modules` is in engine/CONTRACT.md already; added to `src/types.ts`.

## Geometry (display only)

- Module 1.722 × 1.134 m portrait, 0.3 m edge margin (same as engine/CONTRACT.md).
- Sunny roof face: `roof_width_m × roof_length_m` if known, else from `roof_area_sqm` (slope ≈ 5 m), else a default 11 × 5 m face. Tilt from `roof_tilt_deg` (default 35°). Gable roof unless `roof_type` is flat.
- Grid on the sunny face holds up to `max_modules` when the engine gives it, else what fits. More engine modules than the face shows → extra rows on the back face and a caption "(n shown)".

## Files

- `src/scene/HouseScene.tsx` — the lot, house, roof grid, components, lighting. Shared by both views.
- `src/scene/House3D.tsx` — customer wrapper (auto-rotate, caption). Lazy-loaded; WebGL missing → old SVG `House`.
- `src/scene/DesignStudio.tsx` — planner build mode: palette, drag-and-drop, paint/remove panels, apply/reset.
- `src/scene/layout.ts` — roof grid + lock building (pure functions, tested by `scene/layout.check.ts`).

## Done when

- [ ] Customer plan card shows the 3D house; panel count = engine count; works in mock mode.
- [ ] Planner can drag panels/battery/heat pump/wallbox in and out, apply, and see the engine's re-derived design.
- [ ] `npm run build` passes; desktop + mobile checked in the browser; bundle split so the customer site's first load is not slower.
- [ ] Board DONE to qa with SHA.

## Later (if time)

- Roof orientation compass, shading by sun position, east-west flat-roof racks.
- Snapshot of the studio view in the offer pack / quote.
