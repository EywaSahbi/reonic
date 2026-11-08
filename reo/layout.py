"""Auto-placement of PV modules on the roof outline (engine/ROOF_LAYOUT.md, phase 3).

Pure geometry, no network, no LLM: the same outline and count always give the same layout. The module COUNT comes from
the engine (design.components.pv.quantity); this file only decides where those modules sit. Planner edits override it.
Coordinates: metres east (x) / north (y) of the frame origin (outline centroid); equirectangular, fine at roof scale.
"""
import math

SETBACK_M = 0.4      # clearance from the roof edge (eaves, ridge, fire-safety), same spirit as the engine's 0.3 m grid margin
GAP_M = 0.02         # space between modules
SHIFTS = 4           # grid offsets tried per axis; the placement with most modules wins
HALF_PITCHED = ("gable", "hip", "complex")   # a footprint of these has one sunny face: the half toward the facing direction
M_PER_DEG = 111_320.0


def _local(outline: list[list[float]]) -> tuple[list[tuple[float, float]], float, float]:
    """[(lat, lon)] -> metres east / north of the vertex centroid, plus that centroid."""
    lat0 = sum(p[0] for p in outline) / len(outline)
    lon0 = sum(p[1] for p in outline) / len(outline)
    k = math.cos(math.radians(lat0)) * M_PER_DEG
    return [((lon - lon0) * k, (lat - lat0) * M_PER_DEG) for lat, lon in outline], lat0, lon0


def _inside(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _edge_dist(x: float, y: float, poly: list[tuple[float, float]]) -> float:
    best = math.inf
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(x - x1 - t * dx, y - y1 - t * dy))
    return best


def _longest_edge_bearing(poly: list[tuple[float, float]]) -> float:
    """Compass bearing (0 = north) of the normal to the longest edge, i.e. the slope direction of a roof along it."""
    (x1, y1), (x2, y2) = max(zip(poly, poly[1:] + poly[:1]), key=lambda e: math.dist(*e))
    return (math.degrees(math.atan2(y2 - y1, x2 - x1)) + 90) % 180      # edge direction + 90, folded to 0..180


def cells(poly: list[tuple[float, float]], facing: float, w: float, h: float, half: bool) -> tuple[list[dict], bool]:
    """Best fitting grid of w x h modules (w across the eave, h along the slope; swapped for landscape) inside the polygon.
    Returns the module cells (x, y = centre in the east / north frame, portrait) and whether the grid is portrait."""
    b = math.radians(facing)
    e, s = (math.cos(b), -math.sin(b)), (math.sin(b), math.cos(b))       # eave direction, slope direction (toward facing)
    uv = [(x * e[0] + y * e[1], x * s[0] + y * s[1]) for x, y in poly]
    us, vs = [p[0] for p in uv], [p[1] for p in uv]
    v_min = (min(vs) + max(vs)) / 2 + 0.1 if half else -math.inf          # ridge: only the facing half takes modules
    best: tuple[int, list[dict], bool] = (0, [], True)
    for portrait in (True, False):
        cw, ch = (w, h) if portrait else (h, w)
        for i in range(SHIFTS):
            for j in range(SHIFTS):
                found = []
                u = min(us) + i * (cw + GAP_M) / SHIFTS
                while u + cw <= max(us):
                    v = min(vs) + j * (ch + GAP_M) / SHIFTS
                    while v + ch <= max(vs):
                        corners = [(u, v), (u + cw, v), (u, v + ch), (u + cw, v + ch), (u + cw / 2, v + ch / 2)]
                        if v >= v_min and all(_inside(a, c, uv) and _edge_dist(a, c, uv) >= SETBACK_M for a, c in corners):
                            cu, cv = u + cw / 2, v + ch / 2
                            found.append({"x": round(cu * e[0] + cv * s[0], 3), "y": round(cu * e[1] + cv * s[1], 3), "portrait": portrait})
                        v += ch + GAP_M
                    u += cw + GAP_M
                if len(found) > best[0]:
                    best = (len(found), found, portrait)
    return best[1], best[2]


def auto_layout(outline: list[list[float]] | None, module: dict, count: int, facts: dict | None = None,
                roof_type: str | None = None, dims: tuple[float, float] | None = None) -> dict | None:
    """roof_layout (source "auto") with `count` modules, or None when there is nothing to draw on.
    outline = [[lat, lon], ...] (roof_location); without one, dims = (width, length) metres give a rectangle with
    frame lat / lon null. `capacity` = modules the outline holds; fewer than `count` -> the layout holds `capacity`
    and says so in `note` (never overlapping to reach the engine's number)."""
    facts = facts or {}
    if outline and len(outline) >= 3:
        poly, lat0, lon0 = _local(outline)
    elif dims:
        (w, l) = dims
        poly, lat0, lon0 = [(-w / 2, -l / 2), (w / 2, -l / 2), (w / 2, l / 2), (-w / 2, l / 2)], None, None
    else:
        return None
    rtype = roof_type or facts.get("roof_type")
    half = rtype in HALF_PITCHED
    facing = facts.get("roof_orientation_deg")
    if facing is None:
        facing = 180.0 if half else _longest_edge_bearing(poly)           # unknown: south for a pitched roof, else along the long edge
    found, portrait = cells(poly, facing, module["w_m"], module["h_m"], half)
    cx = sum(c["x"] for c in found) / len(found) if found else 0
    cy = sum(c["y"] for c in found) / len(found) if found else 0
    chosen = sorted(found, key=lambda c: (math.hypot(c["x"] - cx, c["y"] - cy), c["x"], c["y"]))[:count]
    rot = round(facing % 360, 1)
    layout = {"source": "auto", "module": module, "frame": {"lat": lat0, "lon": lon0, "azimuth_deg": round(facing % 360, 1)},
              "capacity": len(found),
              "modules": sorted(({"x": c["x"], "y": c["y"], "rot_deg": rot, "portrait": c["portrait"]} for c in chosen),
                                key=lambda m: (-m["y"], m["x"]))}
    if len(found) < count:
        layout["note"] = f"the roof outline holds {len(found)} of the {count} modules the design needs"
    return layout


def reconcile(layout: dict, count: int, outline: list[list[float]] | None, facts: dict | None = None,
              dims: tuple[float, float] | None = None) -> dict:
    """Layout after the design's module count changed: drop from the end, or add on free grid cells (planner positions stay)."""
    mods = list(layout["modules"])
    if len(mods) >= count:
        return {**layout, "modules": mods[:count], "note": None} if len(mods) > count else layout
    fresh = auto_layout(outline, layout["module"], 10_000, facts, dims=dims)
    if not fresh:
        return layout
    near = max(layout["module"]["h_m"], layout["module"]["w_m"])
    for c in fresh["modules"]:
        if len(mods) >= count:
            break
        if all(math.hypot(c["x"] - m["x"], c["y"] - m["y"]) >= near for m in mods):
            mods.append(c)
    out = {**layout, "modules": mods, "capacity": fresh["capacity"]}
    out["note"] = f"the roof holds {len(mods)} of the {count} modules the design needs" if len(mods) < count else None
    return out
