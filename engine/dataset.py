"""Expert designs from data's `data/processed/projects.parquet` (+ `split.csv`): the home's facts and what the expert offered.

Used offline only (tools/derive_params.py, predict.py); the API never reads the dataset. Reading data's file
means engine fits and scores on exactly the targets data's score.py checks.
"""
from pathlib import Path

import pandas as pd

PROCESSED = Path(__file__).parent.parent / "data" / "processed"
FACTS = ["total_demand_kwh", "has_ev", "ev_km_per_year", "heating_type", "heating_demand_kwh", "has_existing_pv",
         "existing_pv_kwp", "has_existing_battery", "electricity_price_eur_per_kwh"]


def expert_designs(k_ev=0.18, cop=3.0, split=None):
    """One row per project: facts (contract names, total demand rebuilt as in METHOD.md step 1) + expert targets.

    split: None = all projects, else "train" / "val" / "test" from data's split.csv.
    """
    df = pd.read_parquet(PROCESSED / "projects.parquet")
    if split:
        ids = pd.read_csv(PROCESSED / "split.csv")
        df = df[df.project_id.isin(ids.project_id[ids.split == split])]
    df = df.copy()
    km = df.ev_km_per_year.where(df.has_ev, 0).fillna(0)
    hp = df.existing_heating_electricity_kwh.where(df.heating_type == "heatpump")
    hp = hp.fillna((df.heating_demand_kwh / cop).where(df.heating_type == "heatpump")).fillna(0)
    df["total_demand_kwh"] = df.annual_demand_kwh + km * k_ev + hp
    for col in ("pv_kwp", "battery_kwh", "heatpump_kw", "wallbox_kw"):
        df[col] = df[col].fillna(0.0)
    return df.reset_index(drop=True)


def facts(row):
    """HomeFacts (CONTRACT.md) for one dataset project; missing values are left out."""
    out = {}
    for k in FACTS:
        v = row[k]
        if v is None or (isinstance(v, float) and v != v):
            continue
        out[k] = v.item() if hasattr(v, "item") else v
    return out
