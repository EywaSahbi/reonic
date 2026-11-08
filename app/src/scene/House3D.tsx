import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { Design, HomeFacts } from "../types";
import { HouseScene } from "./HouseScene";
import { defaultItems, enginePanels, roofCells, roofFrom } from "./layout";

// Customer plan card: the house builds itself from the engine's design (module count, battery, heat pump, wallbox).
// Read-only; drag to look around. Lazy-loaded from PlanCard so the website's first paint stays light.
export default function House3D({ design, facts }: { design: Design; facts: HomeFacts }) {
  const pv = design.components.pv;
  const need = pv.recommended ? pv.quantity ?? 0 : 0;
  // The drawn front face is an approximation of the engine's roof: widen it until all of the engine's modules fit,
  // so the picture shows exactly the panel count on the plan card (EywaSahbi).
  const roof = useMemo(() => {
    const r = roofFrom(facts);
    // first a taller face (one more row, house stays compact for the camera), then a longer one
    while (r.width < 40 && roofCells(r).filter((c) => c.face === 0).length < need) { if (r.slope < 7) r.slope += 0.5; else r.width += 0.5; }
    return r;
  }, [facts.roof_width_m, facts.roof_length_m, facts.roof_area_sqm, facts.roof_tilt_deg, need]); // eslint-disable-line react-hooks/exhaustive-deps
  // customer view: panels only on the front (sunny) face, all of the engine's modules (EywaSahbi)
  const cells = useMemo(() => roofCells(roof, pv.max_modules, need).filter((c) => c.face === 0), [roof, pv.max_modules, need]);
  const panels = enginePanels(design, cells);
  const items = defaultItems(design, roof);
  const count = pv.recommended ? pv.quantity ?? null : 0;

  return (
    <figure className="house house-3d" aria-label={`3D view of your home with ${count ?? "some"} solar panels${items.battery ? ", a battery" : ""}${items.heatpump ? ", a heat pump" : ""}${items.wallbox ? ", a wallbox" : ""}`}>
      <div className="house-3d-canvas">
        <Canvas shadows dpr={[1, 2]} camera={{ position: [19, 14, 23], fov: 30 }} gl={{ antialias: true, alpha: true }}>
          <HouseScene roof={roof} cells={cells} panels={panels} items={items} />
          <OrbitControls autoRotate autoRotateSpeed={0.6} enablePan={false} enableZoom={false} minPolarAngle={0.6} maxPolarAngle={1.25} target={[0, 2, 0]} />
        </Canvas>
      </div>
    </figure>
  );
}

