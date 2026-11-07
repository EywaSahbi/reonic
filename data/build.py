"""Raw CSVs -> processed/projects.parquet + processed/split.csv (idempotent).

One row per project: inputs under the engine's HomeFacts names + the expert design
derived from one offer option. Rules are documented in NOTES.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT.parent / "Project Data"
OUT = ROOT / "processed"
INSTALLERS = ["23c108b7", "2a8ba8e2"]
SEED = 42
SPLIT_SHARES = {"train": 0.70, "val": 0.15, "test": 0.15}
DEFAULT_MODULE_WP = 460.0  # shortcut: typical module when an installer has no Module rows; median of observed Wp is 455-480

HARDWARE = {"Module", "BatteryStorage", "Wallbox", "Heatpump", "Inverter", "ModuleFrameConstruction"}
MOUNT = re.compile(r"substructure|roof mounting|dc install", re.I)
NOT_MOUNT = re.compile(r"surcharge|scaffold", re.I)
KWP = re.compile(r"(\d+(?:[.,]\d+)?)\s*kWp", re.I)
KWH = re.compile(r"(\d+(?:[.,]\d+)?)\s*kWh", re.I)
KW = re.compile(r"(\d+(?:[.,]\d+)?)\s*kW(?![hp])", re.I)
HEATING = {"Heatpump": "heatpump", "Gas": "gas", "Oil": "oil", "OtherRenewable": "other", "OtherNonRenewable": "other"}


def num(rx: re.Pattern, text: str) -> float | None:
    m = rx.search(text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def pick_option(parts: pd.DataFrame) -> pd.DataFrame:
    """Expert design = highest option_number that contains hardware (default until Reonic confirms)."""
    hw = parts[parts.component_type.isin(HARDWARE) | parts.component_name.str.contains("Complete Package", na=False)]
    best = hw.groupby("project_id").option_number.max().rename("best").reset_index()
    pairs = parts.merge(best, on="project_id")
    pairs = pairs[pairs.option_number == pairs.best]
    first_id = pairs.groupby("project_id").option_id.first()  # tie on option_number: take one id
    return parts[parts.option_id.isin(first_id)]


def design(opt: pd.DataFrame, module_wp: float) -> dict:
    """Turn one option's line items into the expert targets."""
    names = opt.component_name.fillna("")
    packages = names[names.str.contains("Complete Package", case=False)]
    pkg_kwp = next((v for v in map(lambda s: num(KWP, s), packages) if v), None)
    pkg_kwh = next((v for v in map(lambda s: num(KWH, s), packages) if v), None)

    # PV: package name ("10.8kWp") > module count x Wp. Module count = max(Module rows, mounting rows),
    # because some options list only a few extra Module rows next to mounting for the full array.
    mods = opt[(opt.component_type == "Module") & opt.module_watt_peak.notna()]
    mount = opt[names.str.contains(MOUNT) & ~names.str.contains(NOT_MOUNT)
                & ~opt.quantity_units.isin(["SquareMeter", "LinearMeter"])]
    n_mods = float(mods.quantity.sum()) if len(mods) else 0.0
    n_mount = float(mount.quantity.max()) if len(mount) else 0.0
    n_mount = n_mount if n_mount > 1 else 0.0  # quantity 1 is a flat-rate line, not a module count
    wp = float(mods.module_watt_peak.mean()) if len(mods) else module_wp
    n = max(n_mods, n_mount)
    if pkg_kwp:
        pv, src = pkg_kwp, "package_name"
    elif n:
        pv, src = n * wp / 1000, "module_rows" if n_mods >= n_mount else "mount_count"
    else:
        pv, src = np.nan, "none"
    has_pv = bool(pv == pv) or (opt.technology == "solar").any() and len(mount) > 0
    if has_pv and pv != pv:
        src = "pv_size_unknown"

    # Battery: capacity sits in inverter_power_kw on BatteryStorage rows (swapped column, Wh)
    bat = opt[opt.component_type == "BatteryStorage"]
    bat_kwh = float((bat.inverter_power_kw * bat.quantity).sum() / 1000) if bat.inverter_power_kw.notna().any() else None
    bat_kwh = bat_kwh or pkg_kwh

    # Heat pump: name ("Heat Pump 12.5kW") is more precise than the rounded spec column
    hp = opt[opt.component_type == "Heatpump"]
    hp_kw = None
    if len(hp):
        hp_kw = num(KW, hp.component_name.iloc[0]) or float(hp.heatpump_nominal_power_kw.max() / 1000)

    wb = opt[opt.component_type == "Wallbox"]
    wb_kw = None
    if len(wb):
        wb_kw = float(wb.wb_charging_speed_kw.max() / 1000) if wb.wb_charging_speed_kw.notna().any() \
            else num(KW, wb.component_name.iloc[0])

    return {
        "option_id": opt.option_id.iloc[0],
        "has_pv": has_pv, "pv_kwp": round(pv, 2) if pv == pv else np.nan,
        "pv_modules": n if n else np.nan,
        "has_battery": bat_kwh is not None, "battery_kwh": bat_kwh if bat_kwh else np.nan,
        "has_heatpump": hp_kw is not None, "heatpump_kw": hp_kw if hp_kw else np.nan,
        "has_wallbox": wb_kw is not None, "wallbox_kw": wb_kw if wb_kw else np.nan,
        "target_source": src,
    }


def inputs(s: pd.DataFrame) -> pd.DataFrame:
    """Status-quo columns -> HomeFacts names (engine/CONTRACT.md), units fixed."""
    price = s.energy_price_per_wh * 1000
    price = price.where((price > 0.05) & (price < 2))  # 0 and the one per-kWh-in-per-Wh entry -> unknown
    demand = (s.energy_demand_wh / 1000).where(s.energy_demand_wh > 0)
    return pd.DataFrame({
        "project_id": s.project_id,
        "annual_demand_kwh": demand,
        "num_inhabitants": s.num_inhabitants,
        "house_size_sqm": s.house_size_sqm,
        "house_built_year": s.house_built_year,
        "heating_type": s.heating_existing_type.map(HEATING),
        "heating_demand_kwh": (s.heating_existing_heating_demand_wh / 1000).where(s.heating_existing_heating_demand_wh > 0),
        "has_ev": s.has_ev.astype(bool),
        "ev_km_per_year": s.ev_annual_drive_distance_km,
        "electricity_price_eur_per_kwh": price,
        "has_existing_pv": s.has_solar.astype(bool),
        "existing_pv_kwp": s.solar_size_kwp / 1000,
        "has_existing_battery": s.has_storage.astype(bool),
        # extra context, not HomeFacts
        "existing_battery_kwh": s.storage_size_kwh / 1000,
        "has_existing_wallbox": s.has_wallbox.astype(bool),
        "existing_heating_electricity_kwh": s.heating_existing_electricity_demand_kwh.where(
            s.heating_existing_electricity_demand_kwh > 0),
        "flexible_price_eur_per_kwh": s.energy_price_with_flexible_tariff * 1000,
        "load_profile": s.load_profile,
        "country": s.country,
        "customer_contact_id": s.customer_contact_id,
        "offer_created_at": pd.to_datetime(s.offer_created_at, format="mixed"),
    })


def split(df: pd.DataFrame) -> pd.DataFrame:
    """train/val/test by customer (no customer in two splits), stratified by installer, fixed seed."""
    rng = np.random.default_rng(SEED)
    out = []
    for inst, g in df.groupby("installer"):
        customers = np.sort(g.customer_contact_id.unique())
        rng.shuffle(customers)
        n = len(customers)
        cut1, cut2 = round(n * SPLIT_SHARES["train"]), round(n * (SPLIT_SHARES["train"] + SPLIT_SHARES["val"]))
        label = {c: "train" if i < cut1 else "val" if i < cut2 else "test" for i, c in enumerate(customers)}
        out.append(pd.DataFrame({"project_id": g.project_id, "split": g.customer_contact_id.map(label)}))
    return pd.concat(out).sort_values("project_id").reset_index(drop=True)


def build() -> pd.DataFrame:
    rows = []
    for inst in INSTALLERS:
        s = pd.read_csv(RAW / inst / "projects_status_quo.csv")
        p = pd.read_csv(RAW / inst / "project_options_parts.csv")
        wp = p.loc[p.component_type == "Module", "module_watt_peak"].median()
        wp = wp if wp == wp else DEFAULT_MODULE_WP
        chosen = pick_option(p)
        targets = pd.DataFrame([{"project_id": pid, **design(opt, wp)} for pid, opt in chosen.groupby("project_id")])
        df = inputs(s).merge(targets, on="project_id", how="inner")  # projects without parts are dropped
        df.insert(1, "installer", inst)
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df = build()
    sp = split(df)
    df.to_parquet(OUT / "projects.parquet", index=False)
    sp.to_csv(OUT / "split.csv", index=False)
    print(f"projects.parquet: {len(df)} rows, {df.shape[1]} columns")
    print(sp.merge(df[["project_id", "installer"]]).groupby(["installer", "split"]).size().unstack())
    print("target_source:", df.target_source.value_counts().to_dict())
    for c in ["pv", "battery", "heatpump", "wallbox"]:
        size = {"pv": "pv_kwp", "battery": "battery_kwh", "heatpump": "heatpump_kw", "wallbox": "wallbox_kw"}[c]
        print(f"{c:9s} share={df[f'has_{c}'].mean():.2f}  median={df[size].median():.1f}  missing_size={(df[f'has_{c}'] & df[size].isna()).sum()}")


if __name__ == "__main__":
    main()
