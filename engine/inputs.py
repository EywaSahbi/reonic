"""Step 0 of METHOD.md: turn HomeFacts (CONTRACT.md) into the home h.

Field names and values follow CONTRACT.md exactly; the contract is the source of truth.
Anything missing gets a default from params.json and is listed in `assumptions`.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

PARAMS = json.loads((Path(__file__).parent / "params.json").read_text())

HEATING_TYPES = {"gas", "oil", "heatpump", "electric", "district", "other"}


@dataclass
class Home:
    annual_demand_kwh: float            # household demand per year, without EV and heat pump
    has_ev: bool
    ev_km_per_year: float               # 0 without EV
    has_existing_pv: bool
    has_existing_battery: bool
    heating_type: str | None            # one of HEATING_TYPES, None = unknown
    electricity_price_eur_per_kwh: float
    assumptions: list[dict] = field(default_factory=list)


def read_inputs(facts: dict) -> Home:
    d = PARAMS["defaults"]
    assumptions = []

    def given_or_default(name, default, note):
        if facts.get(name) is not None:
            return facts[name]
        assumptions.append({"field": name, "value": default, "note": note})
        return default

    demand = given_or_default("annual_demand_kwh", d["annual_demand_kwh"], "typical household demand")
    has_ev = given_or_default("has_ev", False, "no EV unless the customer says so")
    km = 0
    if has_ev:
        if facts.get("ev_km_per_year") is None and facts.get("ev_km_per_week") is not None:
            km = facts["ev_km_per_week"] * 52
        elif facts.get("ev_km_per_year") is None and facts.get("ev_km_per_day") is not None:
            km = facts["ev_km_per_day"] * 365
        else:
            km = given_or_default("ev_km_per_year", d["ev_km_per_year"], "average yearly driving distance")
    has_pv = given_or_default("has_existing_pv", False, "no existing PV")
    has_battery = given_or_default("has_existing_battery", False, "no existing battery")

    heating = given_or_default("heating_type", None, "heating type unknown")
    if heating is not None and heating not in HEATING_TYPES:
        raise ValueError(f"heating_type must be one of {sorted(HEATING_TYPES)}")

    price = given_or_default("electricity_price_eur_per_kwh", d["electricity_price_eur_per_kwh"], "default tariff")

    return Home(float(demand), bool(has_ev), float(km), bool(has_pv), bool(has_battery),
                heating, float(price), assumptions)
