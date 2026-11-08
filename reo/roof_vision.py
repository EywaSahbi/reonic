"""Roof check on the satellite photo (EywaSahbi, 2026-11-08): Claude Opus 5.5 looks at the customer's own building and
returns a corrected roof outline, the roof type, the ridge direction and an estimated pitch.

Claude only returns geometry (pixel points, angles); every area is computed here in code (roof.area_sqm, sunny_area),
and the engine sizes from those facts. The answer is accepted only when it stays close to the OpenStreetMap outline
(area 0.6-1.8x, centre within 8 m), otherwise the OSM estimate stands. Hard rule 5: only this one home's photo is sent.
"""
import base64
import io
import json
import logging
import math

import anthropic
import httpx
from PIL import Image

import llm
import roof

MODEL = "claude-opus-5-5"
TILE, Z_MAX, SIZE = 256, 19, 768   # Esri World Imagery has real imagery up to zoom 19 in Germany
TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
log = logging.getLogger("reo.roof_vision")

SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "outline": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
        "roof_type": {"type": "string", "enum": ["flat", "gable", "hip", "mono", "complex"]},
        "ridge_bearing_deg": {"type": ["number", "null"]},
        "pitch_deg": {"type": ["number", "null"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["found", "outline", "roof_type", "ridge_bearing_deg", "pitch_deg", "confidence"],
    "additionalProperties": False,
}

PROMPT = """This is a top-down satellite photo ({w} x {h} px, north up) of one house in Germany. The hint below is the
building outline from OpenStreetMap in pixel coordinates (x right, y down); it may be shifted or rough.

OSM outline: {hint}

Find the roof of the building that this outline marks (the one nearest the image centre) and return:
- found: false if you cannot see that roof clearly.
- outline: the roof's outer edge as pixel points [x, y] in order around the roof (4-30 points, no repeat of the first).
- roof_type: flat, gable (two faces), hip (four faces), mono (one sloped face) or complex.
- ridge_bearing_deg: compass direction of the main ridge line (0 = north-south, 90 = east-west), null for flat roofs.
- pitch_deg: your estimate of the roof pitch in degrees from shading, shadows and roof style (typical German roofs
  are 30-45; flat roofs 0), null if you cannot tell.
- confidence: how sure you are of the outline."""


def _px(lat: float, lon: float, z: int) -> tuple[float, float]:
    n, r = TILE * 2 ** z, math.radians(lat)
    return (lon + 180) / 360 * n, (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n


def _latlon(x: float, y: float, z: int) -> tuple[float, float]:
    n = TILE * 2 ** z
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))), x / n * 360 - 180


def _photo(outline: list[list[float]]) -> tuple[bytes, int, float, float, float]:
    """(PNG, zoom, left, top, scale): a square crop centred on the building, the building about 30 % of its width, at
    the sharpest zoom; small houses are enlarged to SIZE px so the roof edges are big enough to point at."""
    z = Z_MAX
    while z > 16:
        p = [_px(la, lo, z) for la, lo in outline]
        if max(max(q[0] for q in p) - min(q[0] for q in p), max(q[1] for q in p) - min(q[1] for q in p)) <= 0.45 * SIZE:
            break
        z -= 1
    p = [_px(la, lo, z) for la, lo in outline]
    span = max(max(q[0] for q in p) - min(q[0] for q in p), max(q[1] for q in p) - min(q[1] for q in p))
    side = min(SIZE, max(256.0, span / 0.3))             # crop size in map pixels at zoom z (at most 3x enlarged)
    left = (max(q[0] for q in p) + min(q[0] for q in p)) / 2 - side / 2
    top = (max(q[1] for q in p) + min(q[1] for q in p)) / 2 - side / 2
    x0, y0 = int(left // TILE), int(top // TILE)
    x1, y1 = int((left + side) // TILE), int((top + side) // TILE)
    mosaic = Image.new("RGB", ((x1 - x0 + 1) * TILE, (y1 - y0 + 1) * TILE))
    with httpx.Client(headers=roof.UA, timeout=8) as c:
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                r = c.get(TILES.format(z=z, x=tx, y=ty))
                r.raise_for_status()
                mosaic.paste(Image.open(io.BytesIO(r.content)).convert("RGB"), ((tx - x0) * TILE, (ty - y0) * TILE))
    ox, oy = left - x0 * TILE, top - y0 * TILE
    img = mosaic.crop((round(ox), round(oy), round(ox + side), round(oy + side))).resize((SIZE, SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), z, left, top, SIZE / side


def facing(ridge_bearing: float | None, roof_type: str) -> float | None:
    """Azimuth (0 = north, 180 = south) of the sunniest roof face: perpendicular to the ridge, the side nearest south."""
    if ridge_bearing is None or roof_type not in ("gable", "hip", "complex"):
        return None
    a, b = (ridge_bearing + 90) % 360, (ridge_bearing + 270) % 360
    return round(min((a, b), key=lambda f: abs(f - 180)))


def measure(lat: float, lon: float, outline: list[list[float]]) -> dict | None:
    """{outline, footprint_sqm, facts: {roof_area_sqm, roof_type, roof_tilt_deg?, roof_orientation_deg?}, confidence}
    or None (no key, no photo, unsure or too far from the OSM outline)."""
    c = llm.client()
    if c is None or len(outline) < 3:
        return None
    try:
        png, z, left, top, scale = _photo(outline)
    except (httpx.HTTPError, OSError) as e:
        log.warning("satellite photo failed: %s", e)
        return None
    hint = [[round((x - left) * scale), round((y - top) * scale)] for x, y in (_px(la, lo, z) for la, lo in outline)]
    try:
        r = c.beta.messages.create(
            model=MODEL, max_tokens=16000,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode()}},
                {"type": "text", "text": PROMPT.format(w=SIZE, h=SIZE, hint=json.dumps(hint))}]}],
            **llm.fallback_kwargs(MODEL))
    except anthropic.APIError as e:
        log.warning("roof vision failed: %s", e)
        return None
    if r.stop_reason != "end_turn":
        log.warning("roof vision stopped: %s", r.stop_reason)
        return None
    try:
        out = json.loads(next(b.text for b in r.content if b.type == "text"))
    except (StopIteration, json.JSONDecodeError):
        return None
    log.info("roof vision answer: %s", out)
    pts = [p for p in out.get("outline", []) if len(p) == 2]
    if not out.get("found") or out.get("confidence") == "low" or len(pts) < 3:
        log.warning("roof vision unsure (found=%s, confidence=%s)", out.get("found"), out.get("confidence"))
        return None
    poly = [_latlon(x / scale + left, y / scale + top, z) for x, y in pts]
    footprint, osm = roof.area_sqm(poly), roof.area_sqm([tuple(p) for p in outline])
    cy, cx = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
    oy, ox = sum(p[0] for p in outline) / len(outline), sum(p[1] for p in outline) / len(outline)
    shift = math.hypot((cy - oy) * 111000, (cx - ox) * 111000 * math.cos(math.radians(oy)))
    if not (0.6 <= footprint / osm <= 1.8) or shift > 8:       # guard: stay close to the OSM building (OSM outlines are often too small)
        log.warning("roof vision rejected: area x%.2f, shift %.1f m", footprint / osm, shift)
        return None
    kind = {"hip": "gable", "complex": "gable"}.get(out["roof_type"], out["roof_type"])
    pitch = out.get("pitch_deg")
    tilt = 0.0 if kind == "flat" else min(55.0, max(15.0, pitch)) if pitch is not None else None
    facts = {"roof_area_sqm": round(roof.sunny_area(footprint, kind, tilt)), "roof_type": kind,
             **({"roof_tilt_deg": round(tilt)} if tilt is not None else {}),
             **({"roof_orientation_deg": o} if (o := facing(out.get("ridge_bearing_deg"), out["roof_type"])) is not None else {})}
    return {"outline": [[round(la, 7), round(lo, 7)] for la, lo in poly], "footprint_sqm": round(footprint, 1),
            "facts": facts, "confidence": out["confidence"]}
