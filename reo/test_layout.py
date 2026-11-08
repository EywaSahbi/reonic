"""Auto-placement of PV modules (layout.py) and the planner's first-open layout."""
import math

import layout
from test_installer import _module_engine, setup

MOD = {"id": "m", "wp": 430, "w_m": 1.134, "h_m": 1.722}


def rect(w, l, lat=51.0, lon=13.0):
    """Outline [[lat, lon]] of a w x l metre rectangle."""
    dy, dx = l / 2 / 111_320.0, w / 2 / (111_320.0 * math.cos(math.radians(lat)))
    return [[lat - dy, lon - dx], [lat - dy, lon + dx], [lat + dy, lon + dx], [lat + dy, lon - dx]]


def overlap(a, b, m=MOD):
    """Axis-aligned check (layouts at 0 / 90 / 180 / 270 degrees): centres closer than a module in both axes."""
    def size(k):   # modules rotated 90 / 270 degrees swap their east / north extent
        w, h = (m["w_m"], m["h_m"]) if k["portrait"] else (m["h_m"], m["w_m"])
        return (h, w) if round(k["rot_deg"]) % 180 == 90 else (w, h)
    (wa, ha), (wb, hb) = size(a), size(b)
    return abs(a["x"] - b["x"]) < (wa + wb) / 2 - 1e-6 and abs(a["y"] - b["y"]) < (ha + hb) / 2 - 1e-6


def test_flat_roof_fills_to_count_inside_the_setback():
    lay = layout.auto_layout(rect(10, 8), MOD, 20, {"roof_type": "flat", "roof_orientation_deg": 180})
    assert lay["source"] == "auto" and len(lay["modules"]) == 20 and lay["capacity"] >= 20
    assert not any(overlap(a, b) for i, a in enumerate(lay["modules"]) for b in lay["modules"][i + 1:])
    assert all(abs(m["x"]) + 0.567 <= 5 - layout.SETBACK_M + 1e-6 for m in lay["modules"] if m["portrait"])
    assert lay == layout.auto_layout(rect(10, 8), MOD, 20, {"roof_type": "flat", "roof_orientation_deg": 180})  # deterministic
    assert lay["frame"]["azimuth_deg"] == 180 and abs(lay["frame"]["lat"] - 51.0) < 1e-6


def test_gable_footprint_uses_only_the_facing_half():
    lay = layout.auto_layout(rect(12, 10), MOD, 100, {"roof_type": "gable", "roof_orientation_deg": 180})
    assert lay["modules"] and all(m["y"] < 0 for m in lay["modules"])   # south face = lower half of the footprint
    assert len(lay["modules"]) == lay["capacity"] and "holds" in lay["note"]   # fewer than asked: said, never overlapped
    north = layout.auto_layout(rect(12, 10), MOD, 100, {"roof_type": "gable", "roof_orientation_deg": 0})
    assert all(m["y"] > 0 for m in north["modules"])


def test_no_outline_uses_dims_or_gives_nothing():
    assert layout.auto_layout(None, MOD, 5) is None
    lay = layout.auto_layout(None, MOD, 6, {"roof_type": "flat"}, dims=(8, 6))
    assert len(lay["modules"]) == 6 and lay["frame"]["lat"] is None


def test_reconcile_keeps_positions_drops_from_the_end_and_adds_on_free_cells():
    lay = layout.auto_layout(rect(10, 8), MOD, 8, {"roof_type": "flat"})
    less = layout.reconcile(lay, 5, rect(10, 8), {"roof_type": "flat"})
    assert less["modules"] == lay["modules"][:5]
    more = layout.reconcile(lay, 12, rect(10, 8), {"roof_type": "flat"})
    assert more["modules"][:8] == lay["modules"] and len(more["modules"]) == 12
    assert not any(overlap(a, b) for i, a in enumerate(more["modules"]) for b in more["modules"][i + 1:])


def test_plan_opens_with_modules_placed_and_follows_the_design(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    _module_engine(monkeypatch, cap=40)
    c.post(f"/plans/{pid}/edit", json={"locks": {"pv": {"recommended": True, "size": 20 * 0.43}}})
    import api
    with api._lock:
        db = api._load()
        db["plans"][pid]["roof_location"] = {"label": "x", "lat": 51.0, "lon": 13.0, "outline": rect(14, 10)}
        db["plans"][pid]["facts"].update(roof_type="flat", roof_orientation_deg=180)
        api._save(db)
    a = c.get(f"/plans/{pid}").json()
    assert a["roof_layout"]["source"] == "auto" and len(a["roof_layout"]["modules"]) == 20
    assert c.get(f"/plans/{pid}").json()["roof_layout"] == a["roof_layout"]      # stable, no churn
    b = c.post(f"/plans/{pid}/edit", json={"locks": {"pv": {"recommended": True, "size": 12 * 0.43}}}).json()
    assert len(c.get(f"/plans/{pid}").json()["roof_layout"]["modules"]) == 12     # auto layout follows the count
    assert "roof_layout" not in c.get(f"/sessions/{pid}").json()
    # a planner layout keeps its positions when the design count changes
    mods = [{"x": float(i), "y": 0.0, "rot_deg": 180, "portrait": True} for i in range(4)]
    c.put(f"/plans/{pid}/layout", json={"modules": mods})
    c.post(f"/plans/{pid}/edit", json={"locks": {"pv": {"recommended": True, "size": 3 * 0.43}}})
    got = c.get(f"/plans/{pid}").json()["roof_layout"]
    assert got["source"] == "planner" and got["modules"] == mods[:3]


def test_reset_layout_goes_back_to_auto(tmp_path, monkeypatch):
    import api
    c, pid, p = setup(tmp_path, monkeypatch)
    _module_engine(monkeypatch, cap=40)
    c.post(f"/plans/{pid}/edit", json={"locks": {"pv": {"recommended": True, "size": 6 * 0.43}}})
    with api._lock:
        db = api._load()
        db["plans"][pid]["roof_location"] = {"label": "x", "lat": 51.0, "lon": 13.0, "outline": rect(14, 10)}
        api._save(db)
    c.put(f"/plans/{pid}/layout", json={"modules": [{"x": float(i), "y": 0.0, "rot_deg": 0, "portrait": True} for i in range(6)]})
    r = c.delete(f"/plans/{pid}/layout").json()
    assert r["roof_layout"]["source"] == "auto" and len(r["roof_layout"]["modules"]) == 6
