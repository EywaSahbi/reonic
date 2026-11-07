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


@dataclass
class Home:
    total_demand_kwh: float             # D: total per year, incl. EV and electric heating
    has_ev: bool
    ev_km_per_year: float               # 0 without EV
    has_existing_pv: bool
    has_existing_battery: bool
    heating_type: str | None            # one of HEATING_TYPES, None = unknown
    heating_demand_kwh: float | None
    roof_area_sqm: float | None
    region: str | None                  # federal state code, None = unknown
    y_kwh_per_kwp: float                # PV yield of the region, else national
    electricity_price_eur_per_kwh: float
    assumptions: list[dict] = field(default_factory=list)


@dataclass
class PvSizing:
    kwp: float                          # snapped to whole modules
    modules: int
    area_needed_sqm: float
    roof: str                           # "unknown" | "too_small" | "fits"
    modules_fitting: int | None         # modules the roof holds, None if roof unknown
    heatpump_suggested: bool
    heatpump_extra_kwp: float           # extra PV on the spare roof for the heat pump
    heatpump_electricity_kwh: float | None
    missing_inputs: list[dict] = field(default_factory=list)


def read_inputs(facts: dict) -> Home:
    d = PARAMS["defaults"]
    assumptions = []

    def given_or_default(name, default, note):
        if facts.get(name) is not None:
            return facts[name]
        assumptions.append({"field": name, "value": default, "note": note})
        return default

    has_ev = given_or_default("has_ev", False, "no EV unless the customer says so")
    km = 0
    if has_ev:
        if facts.get("ev_km_per_year") is None and facts.get("ev_km_per_week") is not None:
            km = facts["ev_km_per_week"] * 52
        elif facts.get("ev_km_per_year") is None and facts.get("ev_km_per_day") is not None:
            km = facts["ev_km_per_day"] * 365
        else:
            km = given_or_default("ev_km_per_year", d["ev_km_per_year"], "average yearly driving distance")

    if facts.get("total_demand_kwh") is None and facts.get("annual_demand_kwh") is not None:
        # household-only figure given: add the EV as in METHOD.md step 1
        demand = facts["annual_demand_kwh"] + km * PARAMS["k_ev_kwh_per_km"]
        assumptions.append({"field": "total_demand_kwh", "value": demand,
                            "note": "household demand plus EV driving, no total given"})
    else:
        demand = given_or_default("total_demand_kwh", d["total_demand_kwh"], "typical total demand")

    has_pv = given_or_default("has_existing_pv", False, "no existing PV")
    has_battery = given_or_default("has_existing_battery", False, "no existing battery")

    heating = given_or_default("heating_type", None, "heating type unknown")
    if heating is not None and heating not in HEATING_TYPES:
        raise ValueError(f"heating_type must be one of {sorted(HEATING_TYPES)}")

    region = facts.get("region")
    if region is not None and region not in REGIONS:
        raise ValueError(f"region must be one of {sorted(REGIONS)}")
    y = PARAMS["pv_yield"]["y_kwh_per_kwp"]
    if region is None:
        assumptions.append({"field": "region", "value": None, "note": f"national PV yield {y:.0f} kWh/kWp"})
    else:
        y = PARAMS["pv_yield"]["per_state"][REGIONS[region]]["e_y"]

    price = given_or_default("electricity_price_eur_per_kwh", d["electricity_price_eur_per_kwh"], "default tariff")

    return Home(float(demand), bool(has_ev), float(km), bool(has_pv), bool(has_battery), heating,
                facts.get("heating_demand_kwh"), facts.get("roof_area_sqm"), region, float(y), float(price),
                assumptions)


def size_pv(home: Home) -> PvSizing:
    """kWp = D × c / Y, snapped to modules, then the roof check (METHOD.md step 0)."""
    p = PARAMS
    def modules_for(kwh):
        return round(kwh * p["c_coverage"] / home.y_kwh_per_kwp * 1000 / p["module_w"])

    modules = modules_for(home.total_demand_kwh)
    area_needed = modules * p["module_area_sqm"]
    missing = []
    roof, fitting = "unknown", None
    hp_suggested, hp_kwp, hp_kwh = False, 0.0, None

    if home.roof_area_sqm is None:
        missing.append({"field": "roof_area_sqm", "why": "needed to check the design fits the roof", "impact": "medium"})
    else:
        fitting = math.floor(home.roof_area_sqm / p["module_area_sqm"])
        if fitting < modules:
            roof = "too_small"
            missing.append({"field": "roof_area_sqm",
                            "why": f"roof holds {fitting} of {modules} modules, "
                                   f"{area_needed - home.roof_area_sqm:.1f} m² short", "impact": "high"})
        else:
            roof = "fits"
            spare = fitting - modules
            if home.heating_type is None:
                missing.append({"field": "heating_type", "why": "spare roof could power a heat pump", "impact": "high"})
            elif home.heating_type not in ELECTRIC_HEATING and spare > 0:
                hp_suggested = True
                if home.heating_demand_kwh is None:
                    missing.append({"field": "heating_demand_kwh", "why": "sizes the heat pump and its extra PV",
                                    "impact": "high"})
                else:
                    hp_kwh = home.heating_demand_kwh / p["cop"]
                    hp_modules = min(modules_for(hp_kwh), spare)
                    hp_kwp = hp_modules * p["module_w"] / 1000

    return PvSizing(modules * p["module_w"] / 1000, modules, area_needed, roof, fitting,
                    hp_suggested, hp_kwp, hp_kwh, missing)
