"""Reference implementation of the lookups in CONTRACT.md ("Lookups for reo").

reo reads the files itself (no import across folders); this module is the spec in code plus a test target.
Only `train` homes are ever returned or used.
"""

from __future__ import annotations

import bisect
import json
from functools import cache
from pathlib import Path

import pandas as pd

PROC = Path(__file__).resolve().parent / "processed"
SIZE = {"pv": "pv_kwp", "battery": "battery_kwh"}


@cache
def benchmarks() -> dict:
    return json.loads((PROC / "benchmarks.json").read_text(encoding="utf-8"))


@cache
def train() -> pd.DataFrame:
    p = pd.read_parquet(PROC / "projects.parquet").merge(pd.read_csv(PROC / "split.csv"), on="project_id")
    return p[p.split == "train"].reset_index(drop=True)


def demand_band(kwh: float | None) -> str:
    """Household demand (annual_demand_kwh, WITHOUT EV / heat pump) -> band label."""
    if kwh is None or kwh != kwh:
        return "unknown"
    for b in benchmarks()["demand_bands"]:
        lo, _, hi = b.rstrip("+").partition("-")
        if kwh >= float(lo) and (not hi or kwh < float(hi)):
            return b
    return "unknown"


def home_key(home: dict) -> dict:
    return {"demand_band": demand_band(home.get("annual_demand_kwh")),
            "has_ev": bool(home.get("has_ev") or home.get("ev_planned")),
            "heating_type": home.get("heating_type") or "unknown"}


def segment(home: dict) -> dict:
    """Most specific segment whose key matches and n >= min_n. Level 0 (all homes) always matches."""
    b, key = benchmarks(), home_key(home)
    fits = [s for s in b["segments"] if s["n"] >= b["min_n"] and all(key[k] == v for k, v in s["key"].items())]
    return max(fits, key=lambda s: s["level"])


def percentile_of(home: dict, component: str, size: float) -> float:
    """Share of similar homes (with that component) whose expert size is below `size`, 0..1."""
    values = segment(home)[SIZE[component]]["values"]
    return bisect.bisect_left(values, size) / len(values)


def size_at(home: dict, component: str, q: int) -> float:
    """Expert size at percentile q (10, 25, 50, 75, 90) for similar homes."""
    return segment(home)[SIZE[component]][f"p{q}"]


def similar_projects(home: dict, k: int = 3) -> list[dict]:
    """k train homes most like this one: same EV group; same heating type if >= k such homes;
    same existing-PV status; then nearest household demand, ties by installer then project_id."""
    p = train()
    ev = bool(home.get("has_ev") or home.get("ev_planned"))
    pool = p[p.has_ev == ev]
    pool = pool[pool.has_existing_pv == bool(home.get("has_existing_pv"))] if \
        (pool.has_existing_pv == bool(home.get("has_existing_pv"))).sum() >= k else pool
    ht = home.get("heating_type")
    if ht and (pool.heating_type == ht).sum() >= k:
        pool = pool[pool.heating_type == ht]
    kwh = home.get("annual_demand_kwh")
    pool = pool[pool.annual_demand_kwh.notna()].assign(
        _d=(pool.annual_demand_kwh - kwh).abs() if kwh is not None else 0.0)
    pool = pool.sort_values(["_d", "installer", "project_id"]).head(k)
    cols = ["project_id", "installer", "annual_demand_kwh", "has_ev", "heating_type",
            "has_pv", "pv_kwp", "has_battery", "battery_kwh", "has_heatpump", "heatpump_kw", "has_wallbox", "wallbox_kw"]
    return pool[cols].astype(object).where(pool[cols].notna(), None).to_dict("records")
