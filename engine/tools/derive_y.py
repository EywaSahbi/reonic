"""Derive Y (specific PV yield, kWh per kWp per year) from real data and store it in params.json.

Run once, offline from the engine's point of view: `uv run python tools/derive_y.py`.
1. PVGIS (EU JRC, satellite irradiance 2005-2023) gives the yield of 1 kWp per federal state
   (one point per state: its capital), south-facing, 35° tilt, 14% system losses.
2. The Marktstammdatenregister (Bundesnetzagentur) gives the number of small PV systems
   (> 2 and < 30 kWp, in operation) per state: where residential roofs are.
3. Y = yield per state, weighted by those counts.
4. Orientation / tilt factors from PVGIS at the centre of Germany, relative to south 35°.
Only generic coordinates and public filters are sent; no customer or project data.
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

PARAMS_PATH = Path(__file__).parent.parent / "params.json"
PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
MASTR = "https://www.marktstammdatenregister.de/MaStR/Einheit/EinheitJson/GetErweiterteOeffentlicheEinheitStromerzeugung"
LOSS, ANGLE, ASPECT = 14, 35, 0
CENTRE = (51.31, 9.48)  # Kassel, near the geographic centre of Germany

# state: (MaStR Bundesland id, capital lat, lon)
STATES = {
    "Baden-Württemberg": (1402, 48.78, 9.18), "Bayern": (1403, 48.14, 11.58),
    "Berlin": (1401, 52.52, 13.40), "Brandenburg": (1400, 52.40, 13.07),
    "Bremen": (1404, 53.08, 8.80), "Hamburg": (1406, 53.55, 10.00),
    "Hessen": (1405, 50.08, 8.24), "Mecklenburg-Vorpommern": (1407, 53.63, 11.41),
    "Niedersachsen": (1408, 52.37, 9.73), "Nordrhein-Westfalen": (1409, 51.23, 6.78),
    "Rheinland-Pfalz": (1410, 50.00, 8.27), "Saarland": (1412, 49.24, 6.99),
    "Sachsen": (1413, 51.05, 13.74), "Sachsen-Anhalt": (1414, 52.13, 11.63),
    "Schleswig-Holstein": (1411, 54.32, 10.14), "Thüringen": (1415, 50.98, 11.03),
}


def get_json(url, params):
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=60) as r:
        return json.load(r)


def pvgis_yield(lat, lon, angle=ANGLE, aspect=ASPECT):
    """(E_y, SD_y) for 1 kWp in kWh/yr."""
    d = get_json(PVGIS, {"lat": lat, "lon": lon, "peakpower": 1, "loss": LOSS,
                         "angle": angle, "aspect": aspect, "outputformat": "json"})
    t = d["outputs"]["totals"]["fixed"]
    return t["E_y"], t["SD_y"]


def small_pv_count(state_id):
    """Solar units (Energieträger 2495) in operation (status 35), > 2 and < 30 kWp, in one state."""
    f = (f"Energieträger~eq~'2495'~and~Bundesland~eq~'{state_id}'~and~Betriebs-Status~eq~'35'"
         "~and~Bruttoleistung der Einheit~lt~'30'~and~Bruttoleistung der Einheit~gt~'2'")
    total = get_json(MASTR, {"page": 1, "pageSize": 1, "filter": f}).get("Total")
    if total is None:
        raise RuntimeError(f"MaStR returned no total for state {state_id}")
    return total


def main():
    per_state = {}
    for name, (sid, lat, lon) in STATES.items():
        e_y, sd_y = pvgis_yield(lat, lon)
        per_state[name] = {"e_y": e_y, "sd_y": sd_y, "small_pv_count": small_pv_count(sid)}
        print(f"{name:24} Y={e_y:7.1f}  sd={sd_y:5.1f}  systems={per_state[name]['small_pv_count']:>9,}")
        time.sleep(0.5)  # be polite to both services

    n = sum(s["small_pv_count"] for s in per_state.values())
    y = sum(s["e_y"] * s["small_pv_count"] for s in per_state.values()) / n
    sd = sum(s["sd_y"] * s["small_pv_count"] for s in per_state.values()) / n

    ref, _ = pvgis_yield(*CENTRE)
    factors = {}
    for aspect in (-90, -45, 0, 45, 90):
        for angle in (15, 25, 35, 45):
            factors[f"{aspect}/{angle}"] = round(pvgis_yield(*CENTRE, angle, aspect)[0] / ref, 3)

    params = json.loads(PARAMS_PATH.read_text())
    params["pv_yield"] = {
        "y_kwh_per_kwp": round(y, 1),
        "sd_kwh_per_kwp": round(sd, 1),
        "reference": f"south (aspect {ASPECT}), tilt {ANGLE}°, losses {LOSS}%",
        "orientation_factors": {"_key": "aspect/tilt, aspect 0 = south, -90 = east, 90 = west", **factors},
        "per_state": per_state,
        "source": "PVGIS v5.3 PVcalc (SARAH-3, 2005-2023) at state capitals, weighted by MaStR "
                  "solar units in operation, 2-30 kWp",
        "derived_on": date.today().isoformat(),
        "script": "engine/tools/derive_y.py",
    }
    PARAMS_PATH.write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n")
    print(f"\nY = {y:.1f} kWh/kWp/yr (± {sd:.1f} year to year), {n:,} systems -> params.json")


if __name__ == "__main__":
    main()
