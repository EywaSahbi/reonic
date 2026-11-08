import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { Design, HomeFacts } from "../types";
import { HouseScene } from "./HouseScene";
import { defaultItems, enginePanels, fitRoof, frontCells } from "./layout";

// Customer plan card: the house builds itself from the engine's design (module count, battery, heat pump, wallbox).
// Read-only; drag to look around. Lazy-loaded from PlanCard so the website's first paint stays light.
export default function House3D({ design, facts }: { design: Design; facts: HomeFacts }) {
  const pv = design.components.pv;
  const need = pv.recommended ? pv.quantity ?? 0 : 0;
  const roof = useMemo(() => fitRoof(facts, need), [facts.roof_width_m, facts.roof_length_m, facts.roof_area_sqm, facts.roof_tilt_deg, need]); // eslint-disable-line react-hooks/exhaustive-deps
  const cells = useMemo(() => frontCells(roof, pv.max_modules, need), [roof, pv.max_modules, need]); // front face only
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

