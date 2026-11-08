"""Roof lookup from an address: OpenStreetMap building outline -> estimated sunny roof area.

1. Nominatim geocodes the address (lat/lon, federal state).
2. The OSM map API returns the buildings around that point; we take the building at the address
   (point inside the outline, else matching house number, else the nearest one within 30 m).
3. Outline area (footprint) -> sunny roof face: flat roof = footprint (racks); pitched = footprint / cos(35°) / 2
   (one of two faces); mono-pitch = footprint / cos(35°). An estimate, said so to the customer.

Demo safety (hard rule 6): the demo addresses in addresses.json answer offline; every live result is cached in
roof_cache.json (gitignored). Any failure returns None and reo asks for width x length instead.
OSM usage: identifying user agent, one lookup per customer request, results cached.
"""
import json
import logging
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

import scripted

HERE = Path(__file__).parent
CACHE = HERE / "roof_cache.json"
UA = {"User-Agent": "reo-hackathon-demo/0.1 (Reonic hackathon team project)"}
TILT = 35.0  # assumed pitch of a pitched roof (degrees) when OSM has none
log = logging.getLogger("reo.roof")
SHAPES = {"flat": "flat", "skillion": "mono", "lean_to": "mono", "gabled": "gable", "hipped": "gable",
          "half-hipped": "gable", "gambrel": "gable", "mansard": "gable", "pyramidal": "gable", "saltbox": "gable"}


def _norm(s: str) -> str:
    return s.lower().replace("ß", "ss").replace("strasse", "str").replace(".", "").strip()


def _mock(address: str) -> dict | None:
    for a in json.loads((HERE / "addresses.json").read_text(encoding="utf-8"))["addresses"]:
        if a["match"] in _norm(address):
            return {"label": a["label"], "facts": dict(a["facts"]), "say": a["say"], "source": "demo data"}
    return None


def _cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def area_sqm(coords: list[tuple[float, float]]) -> float:
    """Polygon area in m² from (lat, lon) points: local equirectangular projection + shoelace."""
    lat0 = math.radians(sum(c[0] for c in coords) / len(coords))
    pts = [(math.radians(lon) * 6371000 * math.cos(lat0), math.radians(lat) * 6371000) for lat, lon in coords]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def _inside(lat: float, lon: float, poly: list[tuple[float, float]]) -> bool:
    inside, j = False, len(poly) - 1
    for i in range(len(poly)):
        (yi, xi), (yj, xj) = poly[i], poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def sunny_area(footprint: float, roof_type: str | None) -> float:
    if roof_type == "flat":
        return footprint
    slope = footprint / math.cos(math.radians(TILT))
    return slope if roof_type == "mono" else slope / 2


def _geocode(address: str) -> dict | None:
    """Structured search when the address has a German postcode ("Street 1, 01069 City"), so the postcode is honoured."""
    params = {"format": "jsonv2", "limit": 1, "countrycodes": "de", "addressdetails": 1}
    m = __import__("re").match(r"^\s*(.+?),\s*(\d{5})\s*(.*)$", address)
    params |= {"street": m.group(1), "postalcode": m.group(2), **({"city": m.group(3)} if m.group(3) else {})} if m else {"q": address}
    r = httpx.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=8, params=params)
    r.raise_for_status()
    hits = r.json()
    return hits[0] if hits else None


def _building(lat: float, lon: float, number: str | None) -> dict | None:
    d = 0.0004  # ~45 m around the point
    r = httpx.get("https://api.openstreetmap.org/api/0.6/map", headers=UA, timeout=8,
                  params={"bbox": f"{lon - d},{lat - d},{lon + d},{lat + d}"})
    r.raise_for_status()
    x = ET.fromstring(r.content)
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in x.iter("node")}
    found = []
    for w in x.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        refs = [nd.get("ref") for nd in w.iter("nd")]
        if "building" not in tags or len(refs) < 4 or refs[0] != refs[-1] or not all(r in nodes for r in refs):
            continue
        poly = [nodes[r] for r in refs[:-1]]
        cy, cx = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
        dist = math.hypot((cy - lat) * 111000, (cx - lon) * 111000 * math.cos(math.radians(lat)))
        found.append({"id": w.get("id"), "tags": tags, "poly": poly, "dist": dist,
                      "inside": _inside(lat, lon, poly), "match": bool(number) and tags.get("addr:housenumber") == number})
    found.sort(key=lambda b: (not b["inside"], not b["match"], b["dist"]))
    best = found[0] if found else None
    return best if best and (best["inside"] or best["match"] or best["dist"] <= 30) else None


_SUGGEST: dict[str, list] = {}   # shortcut: in-memory cache of type-ahead answers, fine for one demo process


def suggest(q: str, limit: int = 5) -> list[dict]:
    """Address type-ahead: demo addresses first (offline), then Photon (komoot's OSM search, built for autocomplete;
    Nominatim's usage policy forbids it). [{label, lat?, lon?, housenumber?, state?}]; [] on any failure."""
    nq = _norm(q)
    if len(nq) < 3:
        return []
    demo = [{"label": a["label"]} for a in json.loads((HERE / "addresses.json").read_text(encoding="utf-8"))["addresses"]
            if a["match"] in nq or _norm(a["label"]).startswith(nq)]
    if nq not in _SUGGEST:
        try:
            r = httpx.get("https://photon.komoot.io/api/", headers=UA, timeout=4,
                          params={"q": q, "limit": limit + 3, "lang": "de", "layer": "house", "bbox": "5.87,47.27,15.04,55.06"})
            r.raise_for_status()
            out = []
            for f in r.json().get("features", []):
                p = f["properties"]
                if p.get("countrycode") != "DE" or not p.get("street") or not p.get("housenumber"):
                    continue
                label = f"{p['street']} {p['housenumber']}, {p.get('postcode', '')} {p.get('city', '')}".replace(" ,", ",").strip()
                lon, lat = f["geometry"]["coordinates"]
                if label not in (o["label"] for o in out):
                    out.append({"label": label, "lat": lat, "lon": lon, "housenumber": p["housenumber"],
                                "state": p.get("state") or p.get("city")})   # Berlin / Hamburg / Bremen have no state
            _SUGGEST[nq] = out
        except (httpx.HTTPError, ValueError, KeyError) as e:
            log.warning("address suggest failed: %s", e)
            return demo[:limit]
    return (demo + _SUGGEST[nq])[:limit]


def lookup(address: str, point: dict | None = None) -> dict | None:
    """{label, facts: {roof_area_sqm, roof_type?, region?}, say, source, footprint_sqm?} or None.
    point = a picked suggestion {lat, lon, housenumber?, state?}: skips geocoding, straight to the building."""
    hit = _mock(address)
    if hit:
        return hit
    key = _norm(address)
    cached = _cache().get(key)
    if cached and "lat" in cached:  # older entries lack the location for the satellite view: look up again
        return cached
    try:
        g = ({"lat": point["lat"], "lon": point["lon"], "display_name": address,
              "address": {"house_number": point.get("housenumber"), "state": point.get("state")}}
             if point and point.get("lat") is not None and point.get("lon") is not None else _geocode(address))
        if g is None:
            return None
        addr = g.get("address", {})
        b = _building(float(g["lat"]), float(g["lon"]), addr.get("house_number"))
    except (httpx.HTTPError, ValueError, ET.ParseError) as e:
        log.warning("roof lookup failed: %s", e)
        return None
    if b is None:
        return None
    footprint = area_sqm(b["poly"])
    roof_type = SHAPES.get(b["tags"].get("roof:shape", ""))
    sunny = sunny_area(footprint, roof_type)
    region = next((code for names, code in scripted.STATE_NAMES
                   if __import__("re").search(rf"\b({names})\b", (addr.get("state") or "").lower())), None)
    facts = {"roof_area_sqm": round(sunny), **({"roof_type": roof_type} if roof_type else {}), **({"region": region} if region else {})}
    shape = {"flat": "a flat roof", "mono": "a mono-pitch roof", "gable": "a pitched roof"}.get(roof_type, "a pitched roof (assumed)")
    say = (f"the building outline in OpenStreetMap is about {round(footprint)} m², so with {shape} that is roughly "
           f"{round(sunny)} m² of roof facing the sun (estimate)")
    res = {"label": g.get("display_name", address), "facts": facts, "say": say, "source": "OpenStreetMap",
           "footprint_sqm": round(footprint, 1), "osm_way": b["id"],
           # where the building is, for the satellite view on the customer's plan card (their own address only)
           "lat": float(g["lat"]), "lon": float(g["lon"]), "outline": [[round(la, 7), round(lo, 7)] for la, lo in b["poly"]]}
    c = _cache()
    c[key] = res
    CACHE.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    return res
