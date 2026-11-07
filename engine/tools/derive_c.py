"""Derive c (coverage: expert PV yearly generation / total yearly demand) from the expert designs.

Run once: `uv run python tools/derive_c.py` (after derive_y.py, it needs Y). Writes `c_coverage` into params.json.
Uses all projects in `Project Data/` (decision by the engine owner; see STATUS.md).

Per project h:
    D_h  = energy_demand_wh / 1,000 + EV km × k_EV + existing heat-pump electricity   (METHOD.md step 1)
    kWp_h = expert PV size, rebuilt from the parts list (below)
    c_h  = kWp_h × Y / D_h
c = median over projects. Projects with an existing PV system, a heat pump in the offer (its demand is
unknown), zero or extreme demand, or no PV in any option are left out.
"""
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / "Project Data"
PARAMS_PATH = ROOT / "params.json"

MOUNT = re.compile(r"^(DC Install|Roof Mounting|Substructure)", re.I)
NOT_COUNT = re.compile(r"Surcharge|Ballast|Scaffolding|End Caps", re.I)


def module_watts(parts):
    """Module power in W per installer: from 'PV Module 463W' names, else module_watt_peak."""
    m = parts[parts.component_type == "Module"]
    named = m.component_name.str.extract(r"(\d{3})\s*W", expand=False).astype(float)
    return float(named.fillna(m.module_watt_peak).median())


def option_kwp(rows, watt):
    """Expert PV kWp of one offer option, or None if the option has no PV."""
    mod = rows[rows.component_type == "Module"]
    if len(mod):
        w = mod.component_name.str.extract(r"(\d{3})\s*W", expand=False).astype(float).fillna(mod.module_watt_peak)
        return float((mod.quantity * w.fillna(watt)).sum() / 1000)
    pkg = rows.component_name.str.extract(r"(\d+(?:[.,]\d+)?)\s*kWp\s*\+", expand=False).dropna()
    if len(pkg):
        return float(pkg.str.replace(",", ".").astype(float).max())
    mount = rows[rows.component_name.fillna("").str.match(MOUNT)
                 & ~rows.component_name.fillna("").str.contains(NOT_COUNT)
                 & (rows.quantity_units.fillna("Item") == "Item") & (rows.quantity >= 3)]
    if len(mount):
        # shortcut: the mounting / DC-install quantity is the module count, wattage is the installer's median
        return float(mount.quantity.max() * watt / 1000)
    return None


def projects(installer, y, k_ev, cop):
    folder = DATA / installer
    homes = pd.read_csv(folder / "projects_status_quo.csv")
    parts = pd.read_csv(folder / "project_options_parts.csv")
    watt = module_watts(parts)

    sells_hp = set(parts.loc[parts.technology == "heatpump", "project_id"])
    kwp = {}
    for pid, rows in parts.groupby("project_id"):
        sizes = [s for _, o in rows.groupby("option_id") if (s := option_kwp(o, watt))]
        if sizes:
            # shortcut: no flag says which option was delivered, so take the median over options
            kwp[pid] = float(pd.Series(sizes).median())

    out = []
    for h in homes.itertuples():
        if h.project_id not in kwp or h.project_id in sells_hp or h.has_solar is True:
            continue
        e_house = h.energy_demand_wh / 1000
        if not 1000 <= e_house <= 20000:
            continue
        ev = h.ev_annual_drive_distance_km * k_ev if h.has_ev is True and pd.notna(h.ev_annual_drive_distance_km) else 0
        hp = 0.0
        if h.heating_existing_type == "Heatpump":
            if pd.notna(h.heating_existing_electricity_demand_kwh):
                hp = h.heating_existing_electricity_demand_kwh
            elif pd.notna(h.heating_existing_heating_demand_wh) and h.heating_existing_heating_demand_wh > 0:
                hp = h.heating_existing_heating_demand_wh / 1000 / cop
        d = e_house + ev + hp
        out.append({"installer": installer, "kwp": kwp[h.project_id], "d": d, "e_house": e_house,
                    "c": kwp[h.project_id] * y / d})
    return out, watt


def main():
    params = json.loads(PARAMS_PATH.read_text())
    y = params["pv_yield"]["y_kwh_per_kwp"]
    rows, watts = [], {}
    for inst in sorted(p.name for p in DATA.iterdir() if p.is_dir()):
        r, watts[inst] = projects(inst, y, params["k_ev_kwh_per_km"], params["cop"])
        rows += r
    df = pd.DataFrame(rows)

    c = float(df.c.median())
    q1, q3 = df.c.quantile([0.25, 0.75])
    print(f"projects used: {len(df)}  (module W per installer: {watts})")
    print(f"c = {c:.3f}  (IQR {q1:.2f}-{q3:.2f})  -> {c / y * 1000:.3f} kWp per MWh at Y = {y}")
    for inst, g in df.groupby("installer"):
        print(f"  {inst}: c = {g.c.median():.3f}  n = {len(g)}")

    # does total demand explain the expert size better than household demand alone?
    for col in ("d", "e_house"):
        r = (df.kwp / df[col]).median()
        mae = (df.kwp - r * df[col]).abs().median()
        print(f"  kWp = {r * 1000:.3f} × {col} MWh: median abs error {mae:.2f} kWp")
    b, a = pd.Series(df.kwp).pipe(lambda k: __import__("numpy").polyfit(df.d / 1000, k, 1))
    print(f"  straight line check: kWp = {a:.2f} + {b:.3f} × D_MWh")

    params["c_coverage"] = round(c, 3)
    params["c_derivation"] = {
        "projects": len(df), "iqr": [round(q1, 3), round(q3, 3)],
        "per_installer": {i: round(float(g.c.median()), 3) for i, g in df.groupby("installer")},
        "source": "median of expert kWp × Y / D over all projects in Project Data/",
        "derived_on": date.today().isoformat(), "script": "engine/tools/derive_c.py",
    }
    params["_placeholders"] = "k_ev and cop are hand-set until taken from published measurements"
    PARAMS_PATH.write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
