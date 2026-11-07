"""Expert designs from `Project Data/`: one row per project with the home's facts and what the expert offered.

Used offline only (tools/derive_params.py, predict.py); the API never reads the dataset.
Quirks handled (docs/dataset_explanation.md): swapped battery / inverter columns, W and Wh units,
PV size rebuilt from module rows, package names or the mounting quantity (= module count).
"""
import re
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent.parent / "Project Data"
MOUNT = re.compile(r"^(DC Install|Roof Mounting|Substructure)", re.I)
NOT_COUNT = re.compile(r"Surcharge|Ballast|Scaffolding|End Caps", re.I)
HEATING = {"Heatpump": "heatpump", "Gas": "gas", "Oil": "oil", "OtherRenewable": "other", "OtherNonRenewable": "other"}


def _watts(names, fallback):
    return names.str.extract(r"(\d{3})\s*W", expand=False).astype(float).fillna(fallback)


def module_watts(parts):
    m = parts[parts.component_type == "Module"]
    return float(_watts(m.component_name, m.module_watt_peak).median())


def option_design(rows, watt):
    """(pv_kwp, battery_kwh, wallbox_kw, heatpump_kw) of one offer option; 0 = not offered."""
    names = rows.component_name.fillna("")
    mod = rows[rows.component_type == "Module"]
    pkg_pv = names.str.extract(r"(\d+(?:[.,]\d+)?)\s*kWp\s*\+", expand=False).dropna()
    mount = rows[names.str.match(MOUNT) & ~names.str.contains(NOT_COUNT)
                 & (rows.quantity_units.fillna("Item") == "Item") & (rows.quantity >= 3)]
    if len(mod):
        pv = float((mod.quantity * _watts(mod.component_name, mod.module_watt_peak).fillna(watt)).sum() / 1000)
    elif len(pkg_pv):
        pv = float(pkg_pv.str.replace(",", ".").astype(float).max())
    elif len(mount):
        # shortcut: the mounting / DC-install quantity is the module count, wattage is the installer's median
        pv = float(mount.quantity.max() * watt / 1000)
    else:
        pv = 0.0

    bat = rows[rows.component_type == "BatteryStorage"]
    pkg_bat = names.str.extract(r"\+\s*(\d+(?:[.,]\d+)?)\s*kWh", expand=False).dropna()
    if len(bat) and bat.inverter_power_kw.notna().any():
        battery = float((bat.quantity * bat.inverter_power_kw).sum() / 1000)   # swapped column, Wh
    elif len(pkg_bat):
        battery = float(pkg_bat.str.replace(",", ".").astype(float).max())
    else:
        battery = 0.0

    wb = rows[rows.component_type == "Wallbox"]
    wallbox = float(wb.wb_charging_speed_kw.max() / 1000) if len(wb) and wb.wb_charging_speed_kw.notna().any() \
        else (11.0 if len(wb) else 0.0)
    hp = rows[rows.component_type == "Heatpump"]
    heatpump = float(hp.heatpump_nominal_power_kw.max() / 1000) if len(hp) and hp.heatpump_nominal_power_kw.notna().any() \
        else 0.0
    return pv, battery, wallbox, heatpump


def expert_designs(k_ev=0.18, cop=3.0):
    """One row per project with parts: facts (contract names) + expert targets."""
    out = []
    for folder in sorted(p for p in DATA.iterdir() if p.is_dir()):
        homes = pd.read_csv(folder / "projects_status_quo.csv")
        parts = pd.read_csv(folder / "project_options_parts.csv")
        watt = module_watts(parts)
        first = {}
        for pid, rows in parts.groupby("project_id"):
            # shortcut: no flag says which option was delivered; use the first option
            opt = rows[rows.option_number == rows.option_number.min()]
            first[pid] = option_design(opt, watt)
        for h in homes.itertuples():
            if h.project_id not in first:
                continue
            e_house = h.energy_demand_wh / 1000
            km = h.ev_annual_drive_distance_km if h.has_ev is True and pd.notna(h.ev_annual_drive_distance_km) else 0
            hp_el = 0.0
            if h.heating_existing_type == "Heatpump":
                if pd.notna(h.heating_existing_electricity_demand_kwh):
                    hp_el = h.heating_existing_electricity_demand_kwh
                elif pd.notna(h.heating_existing_heating_demand_wh) and h.heating_existing_heating_demand_wh > 0:
                    hp_el = h.heating_existing_heating_demand_wh / 1000 / cop
            heat = h.heating_existing_heating_demand_wh / 1000 \
                if pd.notna(h.heating_existing_heating_demand_wh) and h.heating_existing_heating_demand_wh > 0 else None
            pv, battery, wallbox, heatpump = first[h.project_id]
            out.append({
                "project_id": h.project_id, "installer": folder.name,
                "total_demand_kwh": e_house + km * k_ev + hp_el, "annual_demand_kwh": e_house,
                "has_ev": h.has_ev is True, "ev_km_per_year": km or None,
                "heating_type": HEATING.get(h.heating_existing_type), "heating_demand_kwh": heat,
                "has_existing_pv": h.has_solar is True,
                "existing_pv_kwp": h.solar_size_kwp / 1000 if pd.notna(h.solar_size_kwp) else None,
                "has_existing_battery": h.has_storage is True,
                "electricity_price_eur_per_kwh": h.energy_price_per_wh * 1000
                if pd.notna(h.energy_price_per_wh) and 0.0001 < h.energy_price_per_wh < 0.001 else None,
                "pv_kwp": pv, "battery_kwh": battery, "wallbox_kw": wallbox, "heatpump_kw": heatpump,
            })
    return pd.DataFrame(out)


def facts(row):
    """HomeFacts (CONTRACT.md) for one dataset project."""
    keys = ["total_demand_kwh", "has_ev", "ev_km_per_year", "heating_type", "heating_demand_kwh", "has_existing_pv",
            "existing_pv_kwp", "has_existing_battery", "electricity_price_eur_per_kwh"]
    return {k: (None if pd.isna(row[k]) else row[k]) for k in keys if not (row[k] is None or (row[k] != row[k]))}
