import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { houseDims, WALL_H, type Cell, type ItemKey, type Items, type Roof, type Spot } from "./layout";

// The lot, the house and the components, built from primitives (no downloaded assets). Shared by the customer card and the
// planner's design studio. Draws what it is given; computes no number anyone sees.

const C = {
  grass: "#9ccf7a", grassEdge: "#7fb862", soil: "#b98a5c", path: "#e9dfcc", drive: "#cfcac0",
  wall: "#f6efe3", trim: "#ffffff", roof: "#b5523b", roofDark: "#8f3f2e", glass: "#8fb6d6", door: "#7a5236",
  panel: "#1d2b4f", frame: "#d9dee6", unit: "#f4f5f7", unitDark: "#b9bec7", accent: "#10b981", car: "#f2784b",
  leaf: "#5fa04e", leafDark: "#4b8a3f", trunk: "#8a6142", hedge: "#6aa95a", ghost: "#ffffff", hover: "#f7a35c",
};

let panelTex: THREE.CanvasTexture | null = null;
function panelTexture() {
  if (panelTex) return panelTex;
  const cv = document.createElement("canvas"); cv.width = 64; cv.height = 96;
  const g = cv.getContext("2d")!;
  g.fillStyle = "#1b2a4e"; g.fillRect(0, 0, 64, 96);
  g.strokeStyle = "rgba(170,190,230,.55)"; g.lineWidth = 1;
  for (let i = 1; i < 6; i++) { g.beginPath(); g.moveTo((i * 64) / 6, 0); g.lineTo((i * 64) / 6, 96); g.stroke(); }
  for (let i = 1; i < 10; i++) { g.beginPath(); g.moveTo(0, (i * 96) / 10); g.lineTo(64, (i * 96) / 10); g.stroke(); }
  const sheen = g.createLinearGradient(0, 0, 64, 96); sheen.addColorStop(0, "rgba(255,255,255,.18)"); sheen.addColorStop(.5, "rgba(255,255,255,0)");
  g.fillStyle = sheen; g.fillRect(0, 0, 64, 96);
  panelTex = new THREE.CanvasTexture(cv); panelTex.colorSpace = THREE.SRGBColorSpace;
  return panelTex;
}

export type SceneEvents = {
  mode: "move" | "paint" | "erase";
  hoverCell: string | null;
  selected: ItemKey | null;
  onCellDown: (id: string) => void;
  onCellEnter: (id: string | null) => void;
  onItemDown: (k: ItemKey) => void;
  onGroundMove: (p: Spot) => void;
  onGroundDown: () => void;
};

type Props = { roof: Roof; cells: Cell[]; panels: Set<string>; items: Items; events?: SceneEvents };

export function HouseScene({ roof, cells, panels, items, events }: Props) {
  const { length: L, depth: D, rise } = houseDims(roof);
  const lotX = L + 12, lotZ = D + 12;
  return (
    <group>
      <hemisphereLight args={["#fff6e8", "#7fa36a", 0.9]} />
      <directionalLight position={[10, 18, 12]} intensity={1.6} castShadow shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-20} shadow-camera-right={20} shadow-camera-top={20} shadow-camera-bottom={-20} shadow-bias={-0.0004} shadow-normalBias={0.05} />

      {/* the lot: a grass slab on a soil block, like a game plot */}
      <mesh position={[0, -0.6, 0]} receiveShadow><boxGeometry args={[lotX + 0.2, 1, lotZ + 0.2]} /><meshStandardMaterial color={C.soil} /></mesh>
      <mesh position={[0, -0.05, 0]} receiveShadow
        onPointerMove={events ? (e: ThreeEvent<PointerEvent>) => events.onGroundMove([e.point.x, e.point.z]) : undefined}
        onPointerDown={events ? () => events.onGroundDown() : undefined}>
        <boxGeometry args={[lotX, 0.1, lotZ]} /><meshStandardMaterial color={C.grass} />
      </mesh>
      <mesh position={[0, 0.005, D / 2 + (lotZ / 2 - D / 2) / 2]} receiveShadow><boxGeometry args={[1.4, 0.02, lotZ / 2 - D / 2]} /><meshStandardMaterial color={C.path} /></mesh>
      <mesh position={[L / 2 + 3, 0.006, D / 2 - 1 + (lotZ / 2 - D / 2 + 1) / 2]} receiveShadow><boxGeometry args={[3.2, 0.02, lotZ / 2 - D / 2 + 1]} /><meshStandardMaterial color={C.drive} /></mesh>

      <Trees lotX={lotX} lotZ={lotZ} />
      <HouseBody L={L} D={D} rise={rise} flat={roof.flat} />
      <RoofFaces roof={roof} L={L} D={D} cells={cells} panels={panels} events={events} />

      {items.heatpump && <Placed spot={items.heatpump} k="heatpump" events={events}><HeatPump /></Placed>}
      {items.battery && <Placed spot={items.battery} k="battery" events={events} faceWall={L}><Battery /></Placed>}
      {items.wallbox && <Placed spot={items.wallbox} k="wallbox" events={events} faceWall={L}><Wallbox /></Placed>}
      {items.wallbox && <Car position={[L / 2 + 3, 0, D / 2 + 2.2]} />}
    </group>
  );
}

function HouseBody({ L, D, rise, flat }: { L: number; D: number; rise: number; flat: boolean }) {
  const gable = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(-D / 2, 0); s.lineTo(D / 2, 0); s.lineTo(0, rise); s.closePath();
    return new THREE.ExtrudeGeometry(s, { depth: L - 0.02, bevelEnabled: false });
  }, [L, D, rise]);
  const winY = [1.3, 3.3];
  const nWin = Math.max(2, Math.floor(L / 3));
  const winX = Array.from({ length: nWin }, (_, i) => -L / 2 + ((i + 0.5) * L) / nWin);
  return (
    <group>
      <mesh position={[0, WALL_H / 2, 0]} castShadow receiveShadow><boxGeometry args={[L, WALL_H, D]} /><meshStandardMaterial color={C.wall} /></mesh>
      <mesh position={[0, 0.15, 0]}><boxGeometry args={[L + 0.08, 0.3, D + 0.08]} /><meshStandardMaterial color="#d8cdbb" /></mesh>
      {!flat && <mesh geometry={gable} rotation={[0, Math.PI / 2, 0]} position={[-L / 2 + 0.01, WALL_H, 0]} castShadow><meshStandardMaterial color={C.wall} /></mesh>}
      {flat && <mesh position={[0, WALL_H + 0.15, 0]} castShadow><boxGeometry args={[L + 0.2, 0.3, D + 0.2]} /><meshStandardMaterial color="#9aa0a8" /></mesh>}
      {/* front: door + windows; sides: one window each floor */}
      <mesh position={[0, 1.1, D / 2 + 0.02]}><boxGeometry args={[1.1, 2.2, 0.06]} /><meshStandardMaterial color={C.door} /></mesh>
      <mesh position={[0, 2.35, D / 2 + 0.25]} castShadow><boxGeometry args={[1.8, 0.1, 0.6]} /><meshStandardMaterial color={C.trim} /></mesh>
      {winY.flatMap((y) => winX.filter((x) => y > 2 || Math.abs(x) > 1.2).map((x) => <Window key={`${x}-${y}`} position={[x, y, D / 2 + 0.03]} />))}
      {winY.map((y) => <Window key={`s${y}`} position={[-L / 2 - 0.03, y, 0]} rotation={[0, Math.PI / 2, 0]} />)}
      {winY.map((y) => <Window key={`e${y}`} position={[L / 2 + 0.03, y, -D / 4]} rotation={[0, Math.PI / 2, 0]} />)}
      {!flat && <mesh position={[L / 4, WALL_H + rise * 0.75, -D / 6]} castShadow><boxGeometry args={[0.6, rise * 0.9, 0.6]} /><meshStandardMaterial color={C.roofDark} /></mesh>}
    </group>
  );
}

function Window(p: { position: [number, number, number]; rotation?: [number, number, number] }) {
  return (
    <group {...p}>
      <mesh><boxGeometry args={[1.2, 1.2, 0.06]} /><meshStandardMaterial color={C.trim} /></mesh>
      <mesh position={[0, 0, 0.02]}><boxGeometry args={[1.0, 1.0, 0.06]} /><meshStandardMaterial color={C.glass} roughness={0.2} metalness={0.1} /></mesh>
    </group>
  );
}

/** Roof planes + module cells. Face 0 looks at the camera (front, sunny); face 1 is the same face turned 180°. */
function RoofFaces({ roof, L, D, cells, panels, events }: { roof: Roof; L: number; D: number; cells: Cell[]; panels: Set<string>; events?: SceneEvents }) {
  const t = (roof.tilt * Math.PI) / 180;
  const faces = roof.flat ? [0] : [0, 1];
  return (
    <group>
      {faces.map((face) => (
        <group key={face} rotation={[0, face ? Math.PI : 0, 0]}>
          <group position={roof.flat ? [0, WALL_H + 0.32, D / 2] : [0, WALL_H, D / 2]} rotation={[roof.flat ? -Math.PI / 2 : t - Math.PI / 2, 0, 0]}>
            {!roof.flat && (
              <mesh position={[0, roof.slope / 2, -0.08]} castShadow receiveShadow>
                <boxGeometry args={[L + 0.6, roof.slope + 0.35, 0.16]} /><meshStandardMaterial color={C.roof} />
              </mesh>
            )}
            {cells.filter((c) => c.face === face).map((c) => (
              <CellMesh key={c.id} cell={c} on={panels.has(c.id)} flat={roof.flat} events={events} />
            ))}
          </group>
        </group>
      ))}
    </group>
  );
}

function CellMesh({ cell, on, flat, events }: { cell: Cell; on: boolean; flat: boolean; events?: SceneEvents }) {
  const ref = useRef<THREE.Group>(null);
  const tilt = flat ? 0.26 : 0; // flat roofs: modules on low racks
  useFrame((_, dt) => {
    const g = ref.current; if (!g) return;
    const target = on ? 1 : 0.001;
    g.scale.setScalar(THREE.MathUtils.damp(g.scale.x, target, 10, dt));
  });
  const hover = events && events.hoverCell === cell.id;
  const showGhost = events && !on;
  return (
    <group position={[cell.x, cell.y, 0.03]}>
      {/* hit area + ghost outline (planner only) */}
      {events && (
        <mesh userData={{ cellId: cell.id }}
          onPointerDown={(e) => { e.stopPropagation(); events.onCellDown(cell.id); }}
          onPointerEnter={(e) => { e.stopPropagation(); events.onCellEnter(cell.id); }}
          onPointerLeave={() => events.onCellEnter(null)}>
          <planeGeometry args={[cell.w, cell.h]} />
          <meshBasicMaterial color={hover ? C.hover : C.ghost} transparent opacity={showGhost ? (hover ? 0.7 : events.mode === "move" ? 0.12 : 0.28) : hover && events.mode === "erase" ? 0.5 : 0} depthWrite={false} />
        </mesh>
      )}
      <group ref={ref} scale={on ? 1 : 0.001} rotation={[tilt, 0, 0]}>
        <mesh position={[0, 0, 0.04]} castShadow raycast={() => null}>
          <boxGeometry args={[cell.w, cell.h, 0.05]} />
          <meshStandardMaterial attach="material-0" color={C.frame} />
          <meshStandardMaterial attach="material-1" color={C.frame} />
          <meshStandardMaterial attach="material-2" color={C.frame} />
          <meshStandardMaterial attach="material-3" color={C.frame} />
          <meshStandardMaterial attach="material-4" map={panelTexture()} roughness={0.25} metalness={0.4} />
          <meshStandardMaterial attach="material-5" color={C.panel} />
        </mesh>
      </group>
    </group>
  );
}

/** A component standing on the lot. Selected = soft ring; in the studio it can be grabbed and dragged. */
function Placed({ spot, k, events, faceWall, children }: { spot: Spot; k: ItemKey; events?: SceneEvents; faceWall?: number; children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const appear = useRef(0);
  useFrame((_, dt) => {
    const g = ref.current; if (!g) return;
    g.position.x = THREE.MathUtils.damp(g.position.x, spot[0], 18, dt);
    g.position.z = THREE.MathUtils.damp(g.position.z, spot[1], 18, dt);
    appear.current = THREE.MathUtils.damp(appear.current, 1, 8, dt);
    g.scale.setScalar(appear.current);
  });
  // against the side wall: turn to face outward
  const rotY = faceWall != null && Math.abs(Math.abs(spot[0]) - (faceWall / 2 + 0.25)) < 0.3 ? Math.sign(spot[0]) * Math.PI / 2 : 0;
  const sel = events?.selected === k;
  return (
    <group ref={ref} position={[spot[0], 0, spot[1]]} scale={0.001}
      onPointerDown={events ? (e: ThreeEvent<PointerEvent>) => { if (events.mode !== "move") return; e.stopPropagation(); events.onItemDown(k); } : undefined}>
      <group rotation={[0, rotY, 0]}>{children}</group>
      {events && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]} raycast={() => null}>
        <ringGeometry args={[0.7, 0.85, 40]} /><meshBasicMaterial color={sel ? C.hover : "#ffffff"} transparent opacity={sel ? 0.95 : 0.35} />
      </mesh>}
    </group>
  );
}

function HeatPump() {
  return (
    <group position={[0, 0, 0]}>
      <mesh position={[0, 0.5, 0]} castShadow><boxGeometry args={[1.1, 0.85, 0.45]} /><meshStandardMaterial color={C.unit} /></mesh>
      <mesh position={[-0.15, 0.5, 0.235]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.3, 0.3, 0.02, 32]} /><meshStandardMaterial color={C.unitDark} /></mesh>
      <mesh position={[-0.15, 0.5, 0.25]}><torusGeometry args={[0.3, 0.025, 8, 32]} /><meshStandardMaterial color="#8e949e" /></mesh>
      <Spin position={[-0.15, 0.5, 0.25]} />
      <mesh position={[0.38, 0.5, 0.232]}><boxGeometry args={[0.18, 0.5, 0.02]} /><meshStandardMaterial color={C.unitDark} /></mesh>
      <mesh position={[0, 0.04, 0]}><boxGeometry args={[1.2, 0.08, 0.55]} /><meshStandardMaterial color="#9aa0a8" /></mesh>
    </group>
  );
}

function Spin(p: { position: [number, number, number] }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((_, dt) => { if (ref.current) ref.current.rotation.z += dt * 4; });
  return <mesh ref={ref} {...p}><boxGeometry args={[0.5, 0.06, 0.01]} /><meshStandardMaterial color="#6b717b" /></mesh>;
}

function Battery() {
  return (
    <group>
      <mesh position={[0, 0.75, 0]} castShadow><boxGeometry args={[0.65, 1.3, 0.25]} /><meshStandardMaterial color={C.unit} /></mesh>
      <mesh position={[0, 1.15, 0.13]}><boxGeometry args={[0.4, 0.04, 0.01]} /><meshStandardMaterial color={C.accent} emissive={C.accent} emissiveIntensity={0.8} /></mesh>
      <mesh position={[0, 0.75, 0.13]}><boxGeometry args={[0.5, 0.01, 0.01]} /><meshStandardMaterial color={C.unitDark} /></mesh>
    </group>
  );
}

function Wallbox() {
  return (
    <group>
      <mesh position={[0, 1.25, 0]} castShadow><boxGeometry args={[0.4, 0.55, 0.16]} /><meshStandardMaterial color="#2c3036" /></mesh>
      <mesh position={[0, 1.33, 0.085]}><circleGeometry args={[0.07, 24]} /><meshStandardMaterial color={C.accent} emissive={C.accent} emissiveIntensity={0.9} /></mesh>
      <mesh position={[0.14, 0.95, 0.06]} rotation={[0, 0, 0.3]}><torusGeometry args={[0.18, 0.02, 6, 20, Math.PI]} /><meshStandardMaterial color="#2c3036" /></mesh>
    </group>
  );
}

function Car({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.55, 0]} castShadow><boxGeometry args={[1.8, 0.6, 4.1]} /><meshStandardMaterial color={C.car} /></mesh>
      <mesh position={[0, 1.08, -0.2]} castShadow><boxGeometry args={[1.6, 0.5, 2.2]} /><meshStandardMaterial color={C.car} /></mesh>
      <mesh position={[0, 1.08, -0.2]}><boxGeometry args={[1.62, 0.36, 2.0]} /><meshStandardMaterial color="#2a3442" roughness={0.2} /></mesh>
      {[[-0.9, 1.3], [0.9, 1.3], [-0.9, -1.3], [0.9, -1.3]].map(([x, z]) => (
        <mesh key={`${x}${z}`} position={[x, 0.33, z]} rotation={[0, 0, Math.PI / 2]} castShadow><cylinderGeometry args={[0.33, 0.33, 0.25, 20]} /><meshStandardMaterial color="#26282c" /></mesh>
      ))}
    </group>
  );
}

function Trees({ lotX, lotZ }: { lotX: number; lotZ: number }) {
  const spots: [number, number, number][] = [[-lotX / 2 + 1.6, -lotZ / 2 + 1.8, 1.2], [lotX / 2 - 1.5, -lotZ / 2 + 1.5, 1], [-lotX / 2 + 1.4, lotZ / 2 - 2.2, 0.85]];
  return (
    <group>
      {spots.map(([x, z, s], i) => (
        <group key={i} position={[x, 0, z]} scale={s}>
          <mesh position={[0, 0.8, 0]} castShadow><cylinderGeometry args={[0.15, 0.2, 1.6, 8]} /><meshStandardMaterial color={C.trunk} /></mesh>
          <mesh position={[0, 2.2, 0]} castShadow><icosahedronGeometry args={[1.1, 0]} /><meshStandardMaterial color={i % 2 ? C.leafDark : C.leaf} flatShading /></mesh>
          <mesh position={[0.4, 2.9, 0.2]} castShadow><icosahedronGeometry args={[0.7, 0]} /><meshStandardMaterial color={C.leaf} flatShading /></mesh>
        </group>
      ))}
      {/* hedge along the back */}
      <mesh position={[0, 0.35, -lotZ / 2 + 0.4]} castShadow><boxGeometry args={[lotX - 5, 0.7, 0.6]} /><meshStandardMaterial color={C.hedge} /></mesh>
    </group>
  );
}

/** Lets the studio map a browser drop (clientX/Y) to a roof cell or a ground spot. */
export type Pick = (clientX: number, clientY: number) => { cell: string | null; ground: Spot | null };
export function Picker({ api }: { api: MutableRefObject<Pick | null> }) {
  const { camera, scene, gl, raycaster } = useThree();
  useEffect(() => {
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    api.current = (cx, cy) => {
      const r = gl.domElement.getBoundingClientRect();
      raycaster.setFromCamera(new THREE.Vector2(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1), camera);
      const hit = raycaster.intersectObjects(scene.children, true).find((h) => h.object.userData.cellId);
      const g = new THREE.Vector3();
      const ok = raycaster.ray.intersectPlane(plane, g);
      return { cell: hit ? (hit.object.userData.cellId as string) : null, ground: ok ? [g.x, g.z] : null };
    };
    return () => { api.current = null; };
  }, [api, camera, scene, gl, raycaster]);
  return null;
}
