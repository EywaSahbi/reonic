// Run: node scripts/check-scene.mjs — checks the studio's geometry and lock building (src/scene/layout.ts).
import assert from "node:assert/strict";
const L = await import("../src/scene/layout.ts");

const pv = (o = {}) => ({ recommended: true, size: 10.5, unit: "kWp", range: null, quantity: 24, confidence: "high", locked: false, reasons: [], ...o });
const off = (unit) => ({ recommended: false, size: null, unit, range: null, confidence: "high", locked: false, reasons: [] });
const design = (p = pv()) => ({ components: { pv: p, battery: { ...off("kWh"), recommended: true, size: 8 }, heatpump: off("kW"), wallbox: off("kW") } });

// measured 10 x 6 m face: engine rule (0.3 m margin) fits 8 x 3 portrait = 24; only the sunny face is used
const roof = L.roofFrom({ roof_width_m: 10, roof_length_m: 6 });
const cells = L.roofCells(roof);
assert.equal(cells.length, 24);
assert.ok(cells.every((c) => c.face === 0));
assert.equal(L.roofCells(roof, 20).length, 20, "max_modules caps the grid");
assert.ok(L.roofCells(L.roofFrom({})).some((c) => c.face === 1), "unknown roof offers the back face");
assert.equal(L.roofCells(roof, undefined, 30).length, 48, "engine count above the drawn face spills to the back face");

const d = design();
assert.equal(L.enginePanels(d, cells).size, 24);
const items = L.defaultItems(d, roof);
assert.ok(items.battery && !items.heatpump && !items.wallbox);

// unchanged layout -> no locks; one module less -> pv lock = 23 x engine kWp/module; heat pump added -> on lock
assert.deepEqual(L.locksFrom(d, 24, items, L.kwpPerModule(d)), {});
assert.deepEqual(L.locksFrom(d, 23, items, L.kwpPerModule(d)), { pv: { recommended: true, size: 10.06 } });
assert.deepEqual(L.locksFrom(d, 0, { ...items, heatpump: [0, 0] }, 0.4375), { pv: { recommended: false }, heatpump: { recommended: true } });
assert.deepEqual(L.locksFrom(d, 24, { ...items, battery: null }, 0.4375), { battery: { recommended: false } });
assert.deepEqual(L.locksFrom(design(pv({ quantity: undefined })), 10, items, null), { pv: { recommended: true } }, "no module size -> engine picks");

// items stay on the lot and out of the house
const [x, z] = L.placeOnLot([0, 0], roof);
const { length, depth } = L.houseDims(roof);
assert.ok(Math.abs(x) >= length / 2 || Math.abs(z) >= depth / 2);
console.log("scene checks passed");
