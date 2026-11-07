"""Engine HTTP API per CONTRACT.md: `uv run uvicorn api:app --port 8000`.

Stub (PLAN.md #15): PV, roof check and heat-pump suggestion are the real Step 0 (`inputs.py`);
battery, wallbox, price and economics are simple placeholder rules until PLAN.md #5-#10 replace them.
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from inputs import PARAMS, Home, read_inputs, size_pv

PRICES = {k: v for k, v in json.loads((Path(__file__).parent / "prices.json").read_text()).items()
          if not k.startswith("_")}
VERSION = f"{PARAMS['version']}-stub"
BATTERY_SIZES = [5, 8, 10, 15]          # shortcut: catalogue sizes, upgrade to the dataset catalogue (PLAN #8)
HEATPUMP_SIZES = [5, 7, 9, 12]
AUTARKY = {False: 0.35, True: 0.70}  # shortcut: share of demand covered by PV, upgrade to simulation (PLAN #7)
IMPACT_ORDER = {"high": 0, "medium": 1, "low": 2}

app = FastAPI(title="reo engine")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:8001"],
                   allow_methods=["*"], allow_headers=["*"])


class DesignRequest(BaseModel):
    facts: dict = {}
    locks: dict = {}
    prices: dict = {}


def nearest(sizes, x):
    return min(sizes, key=lambda s: abs(s - x))


def component(recommended, size, unit, reasons, rng=None, quantity=None, confidence="medium"):
    c = {"recommended": recommended, "size": size if recommended else None, "unit": unit,
         "range": rng if recommended else None, "confidence": confidence, "locked": False, "reasons": reasons}
    if quantity is not None and recommended:
        c["quantity"] = quantity
    return c


def pv_range(facts, home):
    """kWp at the low / high plausible value of the unknown inputs (PLAN #11, first cut)."""
    runs = []
    demands = [3000, 7000] if facts.get("total_demand_kwh") is None and facts.get("annual_demand_kwh") is None \
        else [home.total_demand_kwh]
    ys = [home.y_kwh_per_kwp] if home.region else \
        [min(s["e_y"] for s in PARAMS["pv_yield"]["per_state"].values()),
         max(s["e_y"] for s in PARAMS["pv_yield"]["per_state"].values())]
    for d in demands:
        for y in ys:
            h = Home(**{**home.__dict__, "total_demand_kwh": d, "y_kwh_per_kwp": y, "assumptions": []})
            runs.append(size_pv(h).kwp)
    return [round(min(runs), 2), round(max(runs), 2)]


def confidence(size, rng):
    if not size or not rng:
        return "low"
    spread = (rng[1] - rng[0]) / size
    return "high" if spread < 0.1 else "medium" if spread < 0.3 else "low"


def design(facts: dict, locks: dict, price_overrides: dict) -> dict:
    home = read_inputs(facts)
    pv = size_pv(home)
    prices = {**PRICES, **price_overrides}
    d = home.total_demand_kwh

    rng = pv_range(facts, home)
    pv_reasons = [f"{d:,.0f} kWh/yr total demand, sized like expert designs (≈{PARAMS['c_coverage']:.1f}× your demand)",
                  f"{pv.modules} modules of {PARAMS['module_w']} W need {pv.area_needed_sqm:.0f} m² of roof"]
    if pv.roof == "too_small":
        pv_reasons.append(f"your roof holds only {pv.modules_fitting} modules")
    comps = {"pv": component(pv.kwp > 0 and not home.has_existing_pv, round(pv.kwp, 2), "kWp", pv_reasons, rng,
                             pv.modules, confidence(pv.kwp, rng))}

    def apply_lock(key):
        lock = locks.get(key)
        if lock:
            c = comps[key]
            c["recommended"] = lock["recommended"]
            c["size"] = lock.get("size", c["size"]) if lock["recommended"] else None
            c["locked"] = True
            if not lock["recommended"]:
                c["range"] = None
                c.pop("quantity", None)

    apply_lock("pv")
    pv_kwp = comps["pv"]["size"] or 0

    batt = nearest(BATTERY_SIZES, pv_kwp)
    comps["battery"] = component(pv_kwp > 0 and not home.has_existing_battery, batt, "kWh",
                                 [f"about 1 kWh per kWp of PV stores the midday surplus for the evening ({pv_kwp:.1f} kWp)"])
    apply_lock("battery")

    wants_wallbox = home.has_ev or bool(facts.get("ev_planned"))
    comps["wallbox"] = component(wants_wallbox, 11, "kW", ["you have or plan an EV; 11 kW is the standard home charger"]
                                 if wants_wallbox else ["no EV now or planned"], [11, 11], confidence="high")
    apply_lock("wallbox")

    hp_kw = nearest(HEATPUMP_SIZES, home.heating_demand_kwh / 2000) if home.heating_demand_kwh else None
    if pv.heatpump_suggested:
        hp_reasons = [f"your {home.heating_type} heating could run on the spare roof's solar power"
                      + (f" (+{pv.heatpump_extra_kwp:.1f} kWp)" if pv.heatpump_extra_kwp else "")]
    elif home.heating_type in ("heatpump", "electric"):
        hp_reasons = [f"your heating is already electric ({home.heating_type}), no heat pump needed"]
    elif home.heating_type is None:
        hp_reasons = ["heating type unknown, so no heat-pump decision yet"]
    elif pv.roof == "unknown":
        hp_reasons = [f"{home.heating_type} heating could switch to a heat pump; roof area needed to check it fits"]
    else:
        hp_reasons = ["the roof is fully used by the PV for your electricity demand"]
    comps["heatpump"] = component(pv.heatpump_suggested, hp_kw, "kW", hp_reasons, confidence="low")
    apply_lock("heatpump")

    items = []

    def item(label, qty, unit, unit_price):
        items.append({"label": label, "qty": qty, "unit": unit, "unit_price_eur": unit_price,
                      "total_eur": round(qty * unit_price, 2)})

    c = comps
    if c["pv"]["recommended"]:
        item("PV system", c["pv"]["size"], "kWp", prices["pv_eur_per_kwp"])
    if c["battery"]["recommended"]:
        item("Battery", c["battery"]["size"], "kWh", prices["battery_eur_per_kwh"])
    if c["wallbox"]["recommended"]:
        item("Wallbox", 1, "piece", prices["wallbox_eur"])
    if c["heatpump"]["recommended"] and c["heatpump"]["size"]:
        item("Heat pump", c["heatpump"]["size"], "kW", prices["heatpump_eur_per_kw"])
    if items:
        item("Planning, scaffolding, grid registration", 1, "flat", prices["fixed_fees_eur"])
    total = round(sum(i["total_eur"] for i in items), 2)
    spread = 0.15 + (0.15 if c["pv"]["confidence"] == "low" else 0)
    price = {"items": items, "total_eur": total, "range_eur": [round(total * (1 - spread)), round(total * (1 + spread))]}

    gen = pv_kwp * home.y_kwh_per_kwp
    used = min(d * AUTARKY[bool(c["battery"]["recommended"])], gen)
    savings = used * home.electricity_price_eur_per_kwh + (gen - used) * prices["feed_in_eur_per_kwh"]
    economics = {"total_demand_kwh": round(d), "self_consumption_pct": round(100 * used / gen, 1) if gen else 0,
                 "autarky_pct": round(100 * used / d, 1) if d else 0, "annual_savings_eur": round(savings),
                 "payback_years": round(total / savings, 1) if savings > 0 else None}

    missing = list(pv.missing_inputs)
    if facts.get("total_demand_kwh") is None and facts.get("annual_demand_kwh") is None:
        missing.append({"field": "total_demand_kwh", "why": "sets the PV and battery size", "impact": "high"})
    if home.region is None:
        missing.append({"field": "region", "why": "sun differs ~15% between north and south", "impact": "medium"})
    if facts.get("electricity_price_eur_per_kwh") is None:
        missing.append({"field": "electricity_price_eur_per_kwh", "why": "sets savings and payback", "impact": "low"})
    missing.sort(key=lambda m: IMPACT_ORDER[m["impact"]])

    return {"components": comps, "price": price, "economics": economics, "assumptions": home.assumptions,
            "missing_inputs": missing, "params_version": VERSION}


@app.get("/health")
def health():
    return {"ok": True, "params_version": VERSION}


@app.get("/prices")
def prices():
    return PRICES


@app.post("/design")
def post_design(req: DesignRequest):
    try:
        return design(req.facts, req.locks, req.prices)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))
