"""Step 0 of METHOD.md: turn HomeFacts (CONTRACT.md) into the home h, size PV and check the roof.

Field names and values follow CONTRACT.md exactly; the contract is the source of truth.
Anything missing gets a default from params.json (listed in `assumptions`) or becomes
an open question (listed in `missing_inputs`).
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

PARAMS = json.loads((Path(__file__).parent / "params.json").read_text())

HEATING_TYPES = {"gas", "oil", "heatpump", "electric", "district", "other"}
ELECTRIC_HEATING = {"heatpump", "electric"}
REGIONS = {
    "BW": "Baden-Württemberg", "BY": "Bayern", "BE": "Berlin", "BB": "Brandenburg", "HB": "Bremen",
    "HH": "Hamburg", "HE": "Hessen", "MV": "Mecklenburg-Vorpommern", "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen", "RP": "Rheinland-Pfalz", "SL": "Saarland", "SN": "Sachsen",
    "ST": "Sachsen-Anhalt", "SH": "Schleswig-Holstein", "TH": "Thüringen",
}
BUILDING_TYPES = {"detached", "semi", "terraced"}
ROOF_TYPES = {"gable", "flat", "mono", "other"}


@dataclass
class Home:
    total_demand_kwh: float             # D: total per year, incl. EV and electric heating
    ev_kwh: float                       # part of D that is EV charging
    heatpump_kwh: float                 # part of D that is an existing heat pump
    has_ev: bool
    ev_planned: bool
    ev_km_per_year: float               # 0 without EV
    has_existing_pv: bool
    existing_pv_kwp: float              # 0 without existing PV
    has_existing_battery: bool
    heating_type: str | None            # one of HEATING_TYPES, None = unknown
    heating_demand_kwh: float | None
    roof_area_sqm: float | None
    region: str | None                  # federal state code, None = unknown
    y_kwh_per_kwp: float                # PV yield: region (else national) × roof orientation / tilt
    orientation_factor: float
    electricity_price_eur_per_kwh: float
    assumptions: list[dict] = field(default_factory=list)
    roof_width_m: float | None = None   # sunny roof face as measured; with roof_length_m it wins over roof_area_sqm
    roof_length_m: float | None = None


@dataclass
class PvSizing:
    kwp: float                          # new PV, snapped to whole modules
    module_w: float
    modules: int
    area_needed_sqm: float
    roof: str                           # "unknown" | "too_small" | "fits"
    modules_fitting: int | None         # modules the usable roof holds, None if roof unknown
    heatpump_suggested: bool
    heatpump_extra_kwp: float           # extra PV on the spare roof for the heat pump
    heatpump_extra_modules: int
    heatpump_electricity_kwh: float | None
    heat_demand_kwh: float | None       # heat the suggested heat pump would deliver
    heatpump_kw: float | None
    missing_inputs: list[dict] = field(default_factory=list)
    capped_from: int | None = None      # modules wanted before the roof cut them (also a lock above the cap)


def orientation_factor(orientation_deg, tilt_deg, roof_type):
    """PVGIS yield of this roof ÷ yield of a south roof at 35° (params pv_yield.orientation_factors)."""
    f = PARAMS["pv_yield"]["orientation_factors"]
    if orientation_deg is None and tilt_deg is None:
        if roof_type == "flat":
            return (f["-90/15"] + f["90/15"]) / 2      # flat roofs: east-west racks at ~15°
        return 1.0
    # contract: 180 = south; PVGIS aspect: 0 = south, -90 = east; north-facing roofs clamp to east / west
    aspect = 0 if orientation_deg is None else max(-90, min(90, orientation_deg - 180))
    tilt = 35 if tilt_deg is None else tilt_deg
    a = min((-90, -45, 0, 45, 90), key=lambda x: abs(x - aspect))
    t = min((15, 25, 35, 45), key=lambda x: abs(x - tilt))
    return f[f"{a}/{t}"]


def read_inputs(facts: dict) -> Home:
    p, d = PARAMS, PARAMS["defaults"]
    assumptions = []

    def given_or_default(name, default, note):
        if facts.get(name) is not None:
            return facts[name]
        assumptions.append({"field": name, "value": default, "note": note})
        return default

    for name, allowed in (("heating_type", HEATING_TYPES), ("region", REGIONS), ("building_type", BUILDING_TYPES),
                          ("roof_type", ROOF_TYPES)):
        if facts.get(name) is not None and facts[name] not in allowed:
            raise ValueError(f"{name} must be one of {sorted(allowed)}")

    for name in ("total_demand_kwh", "annual_demand_kwh", "roof_area_sqm"):
        if facts.get(name) is not None and facts[name] <= 0:
            raise ValueError(f"{name} must be positive")

    ev_planned = bool(facts.get("ev_planned"))
    has_ev = given_or_default("has_ev", False, "no EV today, one is planned" if ev_planned
                              else "no EV unless the customer says so")
    # a planned EV is not in today's stated bill: its charging comes on top (a stated total only includes a present EV)
    planned_only = ev_planned and not has_ev
    km = 0
    if has_ev or planned_only:
        if facts.get("ev_km_per_year") is None and facts.get("ev_km_per_week") is not None:
            km = facts["ev_km_per_week"] * 52
        elif facts.get("ev_km_per_year") is None and facts.get("ev_km_per_day") is not None:
            km = facts["ev_km_per_day"] * 365
        else:
            km = given_or_default("ev_km_per_year", d["ev_km_per_year"], "average yearly driving distance")
    ev_kwh = km * p["k_ev_kwh_per_km"]

    heating = facts.get("heating_type")
    if heating is None:
        assumptions.append({"field": "heating_type", "value": None, "note": "heating type unknown"})
    heat = facts.get("heating_demand_kwh")
    hp_kwh = heat / p["cop"] if heating == "heatpump" and heat else 0.0

    if facts.get("total_demand_kwh") is not None:
        demand = facts["total_demand_kwh"]
        if planned_only:
            demand += ev_kwh
            assumptions.append({"field": "total_demand_kwh", "value": round(demand),
                                "note": f"stated {facts['total_demand_kwh']:,.0f} kWh plus ~{ev_kwh:,.0f} kWh for the planned EV"})
    elif facts.get("annual_demand_kwh") is not None:
        demand = facts["annual_demand_kwh"] + ev_kwh + hp_kwh
        assumptions.append({"field": "total_demand_kwh", "value": round(demand),
                            "note": "household demand plus EV and heat pump, no total given"})
    elif facts.get("num_inhabitants"):
        n = str(min(5, max(1, int(facts["num_inhabitants"]))))
        demand = p["demand_by_inhabitants_kwh"][n] * p["building_type_factor"].get(facts.get("building_type"), 1.0) \
            + ev_kwh + hp_kwh
        assumptions.append({"field": "total_demand_kwh", "value": round(demand),
                            "note": f"typical demand for {facts['num_inhabitants']} inhabitants (Stromspiegel)"})
    else:
        demand = given_or_default("total_demand_kwh", d["total_demand_kwh"], "typical total demand")
    ev_kwh = min(ev_kwh, 0.6 * demand)                 # the EV part cannot exceed the total
    hp_kwh = max(0.0, min(hp_kwh, 0.6 * demand - ev_kwh))

    if facts.get("has_existing_pv") is None and (facts.get("existing_pv_kwp") or 0) > 0:
        facts = {**facts, "has_existing_pv": True}      # a stated size means there is PV
    has_pv = given_or_default("has_existing_pv", False, "no existing PV")
    existing_kwp = 0.0
    if has_pv:
        existing_kwp = given_or_default("existing_pv_kwp", p["existing_pv_default_kwp"], "typical existing PV size")
    has_battery = given_or_default("has_existing_battery", False, "no existing battery")

    region = facts.get("region")
    y = p["pv_yield"]["y_kwh_per_kwp"]
    if region is None:
        assumptions.append({"field": "region", "value": None, "note": f"national PV yield {y:.0f} kWh/kWp"})
    else:
        y = p["pv_yield"]["per_state"][REGIONS[region]]["e_y"]
    of = orientation_factor(facts.get("roof_orientation_deg"), facts.get("roof_tilt_deg"), facts.get("roof_type"))
    if facts.get("roof_orientation_deg") is None:
        assumptions.append({"field": "roof_orientation_deg", "value": 180, "note": "south-facing roof"
                            if facts.get("roof_type") != "flat" else "flat roof, east-west racks"})

    price = given_or_default("electricity_price_eur_per_kwh", d["electricity_price_eur_per_kwh"], "default tariff")

    for name in ("roof_width_m", "roof_length_m"):
        if facts.get(name) is not None and facts[name] <= 0:
            raise ValueError(f"{name} must be positive")

    return Home(float(demand), float(ev_kwh), float(hp_kwh), bool(has_ev), ev_planned, float(km), bool(has_pv),
                float(existing_kwp), bool(has_battery), heating, heat, facts.get("roof_area_sqm"), region,
                float(y * of), float(of), float(price), assumptions, facts.get("roof_width_m"), facts.get("roof_length_m"))


def heat_demand(facts: dict, home: Home):
    """(heat kWh/yr, assumption or None): given, else house size × specific demand by built year, else median."""
    if home.heating_demand_kwh:
        return home.heating_demand_kwh, None
    p = PARAMS
    if facts.get("house_size_sqm"):
        year = facts.get("house_built_year") or 1978
        per_sqm = next(v for k, v in p["heat_demand_kwh_per_sqm_by_built_year"].items()
                       if not k.startswith("_") and year <= int(k))
        q = facts["house_size_sqm"] * per_sqm
        built = f"built {year}" if facts.get("house_built_year") else "of unknown age (assumed before 1979)"
        return q, {"field": "heating_demand_kwh", "value": round(q),
                   "note": f"{facts['house_size_sqm']} m² × {per_sqm} kWh/m² for a house {built}"}
    q = p["heating_demand_default_kwh"]
    return q, {"field": "heating_demand_kwh", "value": q, "note": "median heat demand in the expert projects"}


def profile(installer: str | None) -> dict:
    """The installer's own expert habits (fitted on its train projects), else the all-installer ones."""
    prof = PARAMS.get("installer_profiles", {}).get(installer or "")
    return {"pv_line": prof["pv_line"] if prof else PARAMS["pv_line"],
            "battery_by_pv_band": prof["battery_by_pv_band"] if prof else PARAMS["battery"]["by_pv_band"],
            "pv_packages": prof.get("pv_packages", []) if prof else [],
            "module_w": (prof.get("module_w") if prof else None) or PARAMS["module_w"],
            "installer": installer if prof else None}


def pv_kwp_for(demand_kwh, home: Home, line: dict | None = None):
    """Expert line kWp = a + b × D_MWh, scaled from the national yield to this roof's yield."""
    line = line or PARAMS["pv_line"]
    nat = PARAMS["pv_yield"]["y_kwh_per_kwp"]
    return (line["a_kwp"] + line["b_kwp_per_mwh"] * demand_kwh / 1000) * nat / home.y_kwh_per_kwp


def grid_modules(width_m: float, length_m: float, module_w: float) -> int:
    """Modules that fit a width × length roof face: best grid, portrait or landscape, after the edge margin."""
    p = PARAMS
    scale = math.sqrt(module_w / p["module_w"])        # shortcut: same module shape, area scales with W
    a, b = (d * scale for d in p["module_dims_m"])
    w, l = width_m - 2 * p["roof_edge_margin_m"], length_m - 2 * p["roof_edge_margin_m"]
    if w <= 0 or l <= 0:
        return 0
    return max(math.floor(w / a) * math.floor(l / b), math.floor(w / b) * math.floor(l / a))


def size_pv(home: Home, facts: dict | None = None, pv_kwp_locked: float | None = None,
            line: dict | None = None, packages: list | None = None, module_w: float | None = None) -> PvSizing:
    """PV from the expert line, minus existing PV, snapped to modules; then the roof check (METHOD.md step 0)."""
    p = PARAMS
    w = module_w or p["module_w"]
    area = p["module_area_sqm"] * w / p["module_w"]     # shortcut: same module efficiency, area scales with W
    line = line or p["pv_line"]
    if pv_kwp_locked is not None:
        modules = round(pv_kwp_locked * 1000 / w)
    else:
        need = max(0.0, pv_kwp_for(home.total_demand_kwh, home, line) - home.existing_pv_kwp)
        if packages and need:
            # installers that sell fixed packages: the package they sell most often for this demand (train)
            need = next(kwp for upper, kwp in packages if upper is None or home.total_demand_kwh <= upper)
        modules = round(need * 1000 / w)
    missing = []
    roof, fitting, capped_from = "unknown", None, None
    grid = home.roof_width_m is not None and home.roof_length_m is not None      # measured sides win over the area
    known = grid or home.roof_area_sqm is not None
    hp = {"suggested": False, "kwp": 0.0, "modules": 0, "kwh": None, "heat": None, "kw": None}

    if not known:
        missing.append({"field": "roof_area_sqm", "why": "needed to check the design fits the roof", "impact": "medium"})
    else:
        existing_modules = round(home.existing_pv_kwp * 1000 / w)      # existing panels already use roof
        on_roof = grid_modules(home.roof_width_m, home.roof_length_m, w) if grid \
            else math.floor(home.roof_area_sqm * p["usable_roof_share"] / area)
        fitting = max(0, on_roof - existing_modules)
        if fitting < modules:
            # hard cap: the roof limits the PV, a lock above it is cut too
            roof, capped_from, modules = "too_small", modules, fitting
            if not grid:
                missing.append({"field": "roof_area_sqm",
                                "why": f"usable roof holds only {fitting} of {capped_from} wanted modules, "
                                       f"{(capped_from - fitting) * area:.1f} m² short", "impact": "high"})
        else:
            roof = "fits"
            spare = fitting - modules
            if home.heating_type is None:
                missing.append({"field": "heating_type", "why": "spare roof could power a heat pump", "impact": "high"})
            elif home.heating_type not in ELECTRIC_HEATING and spare > 0:
                heat, _ = heat_demand(facts or {}, home)
                if home.heating_demand_kwh is None:
                    missing.append({"field": "heating_demand_kwh", "why": "sizes the heat pump and its extra PV",
                                    "impact": "high"})
                hp_kwh = heat / p["cop"]
                # marginal expert rate: b kWp per extra MWh, scaled to this roof's yield
                extra = line["b_kwp_per_mwh"] * hp_kwh / 1000 * p["pv_yield"]["y_kwh_per_kwp"] / home.y_kwh_per_kwp
                hp_modules = min(round(extra * 1000 / w), spare)
                kw = min(p["heatpump_catalogue_kw"], key=lambda s: abs(s - heat / p["heatpump_full_load_hours"]))
                hp = {"suggested": True, "kwp": hp_modules * w / 1000, "modules": hp_modules, "kwh": hp_kwh,
                      "heat": heat, "kw": kw}

    return PvSizing(modules * w / 1000, w, modules, modules * area, roof, fitting, hp["suggested"], hp["kwp"],
                    hp["modules"], hp["kwh"], hp["heat"], hp["kw"], missing, capped_from)
