"""Evidence from real expert designs (data/): flags vs similar homes, and similar real projects.

Flags are aggregate ("larger than 85% of similar homes") and may appear in the customer chat and in LLM context.
Similar projects are individual homes: installer view only, never sent to the customer or to the LLM (hard rule 5).
"""
import bisect
import json
from functools import cache
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "processed"
NAMES = {"pv": "PV", "battery": "Battery", "heatpump": "Heat pump", "wallbox": "Wallbox"}
SIZE_KEY = {"pv": "pv_kwp", "battery": "battery_kwh"}


@cache
def _benchmarks() -> dict | None:
    f = DATA / "benchmarks.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


@cache
def _projects():
    import pandas as pd  # loaded on first use only
    f = DATA / "projects.parquet"
    if not f.exists():
        return None
    p = pd.read_parquet(f).merge(pd.read_csv(DATA / "split.csv"), on="project_id")
    return p[p["split"] == "train"]  # never show val/test homes


def _band(kwh: float | None, bands: list[str]) -> str:
    if kwh is None:
        return "unknown"
    for b in bands:
        lo, _, hi = b.partition("-")
        if kwh >= float(lo.rstrip("+")) and (not hi or kwh < float(hi)):
            return b
    return "unknown"


def _home_key(facts: dict, bands: list[str]) -> dict:
    # shortcut: the dataset's demand is household-only; we use annual_demand_kwh if given, else the customer's total
    kwh = facts.get("annual_demand_kwh") or facts.get("total_demand_kwh")
    return {"demand_band": _band(kwh, bands), "has_ev": bool(facts.get("has_ev") or facts.get("ev_planned")),
            "heating_type": facts.get("heating_type") or "unknown"}


def segment(facts: dict) -> dict | None:
    """Most specific benchmark segment matching the home with n >= min_n (data/CONTRACT.md lookup rule)."""
    b = _benchmarks()
    if not b:
        return None
    home = _home_key(facts, b["demand_bands"])
    fits = [s for s in b["segments"] if s["n"] >= b["min_n"] and all(home.get(k) == v for k, v in s["key"].items())]
    return max(fits, key=lambda s: s["level"], default=None)


def flags(facts: dict, design: dict) -> list[dict]:
    seg = segment(facts)
    if not seg or design.get("params_version") == "engine-offline":
        return []
    out, n = [], seg["n"]
    for key, comp in design["components"].items():
        rate = seg["attach_rate"].get(key)
        if comp["recommended"] and key in SIZE_KEY and comp["size"]:
            values = seg[SIZE_KEY[key]]["values"]
            share = bisect.bisect_left(values, comp["size"]) / len(values)
            p50, unit = seg[SIZE_KEY[key]]["p50"], comp["unit"]
            if share >= 0.85:
                out.append({"component": key, "severity": "warn",
                            "text": f"{NAMES[key]} larger than {share:.0%} of similar homes (median {p50:g} {unit}, n={n})"})
            elif share <= 0.15:
                out.append({"component": key, "severity": "warn",
                            "text": f"{NAMES[key]} smaller than {1 - share:.0%} of similar homes (median {p50:g} {unit}, n={n})"})
        if rate is None:
            continue
        if comp["recommended"] and rate < 0.2:
            out.append({"component": key, "severity": "info", "text": f"Only {rate:.0%} of similar homes got a {NAMES[key].lower()} (n={n})"})
        elif not comp["recommended"] and rate > 0.6:
            out.append({"component": key, "severity": "info", "text": f"{rate:.0%} of similar homes got a {NAMES[key].lower()}; this design has none (n={n})"})
    return out


def similar_projects(facts: dict, k: int = 3) -> list[dict]:
    """The k train projects closest in demand within the same EV group. Installer view only."""
    p = _projects()
    b = _benchmarks()
    if p is None or b is None:
        return []
    kwh = facts.get("annual_demand_kwh") or facts.get("total_demand_kwh")
    ev = bool(facts.get("has_ev") or facts.get("ev_planned"))
    pool = p[p["has_ev"].fillna(False) == ev] if ev else p[p["has_ev"].fillna(False) == False]  # noqa: E712
    if facts.get("heating_type") and (pool["heating_type"] == facts["heating_type"]).sum() >= k:
        pool = pool[pool["heating_type"] == facts["heating_type"]]
    pool = pool[pool["annual_demand_kwh"].notna()]
    if kwh is not None:
        pool = pool.assign(_d=(pool["annual_demand_kwh"] - kwh).abs()).sort_values("_d")
    out = []
    for _, r in pool.head(k).iterrows():
        val = lambda c: None if r[c] != r[c] else r[c]  # NaN -> None
        out.append({
            "project_id": r["project_id"],
            "facts": {f: (bool(val(f)) if f == "has_ev" else val(f)) for f in
                      ("annual_demand_kwh", "num_inhabitants", "heating_type", "has_ev", "house_size_sqm") if val(f) is not None},
            "expert": {"pv": val("pv_kwp") if r["has_pv"] else None, "battery": val("battery_kwh") if r["has_battery"] else None,
                       "heatpump": val("heatpump_kw") if r["has_heatpump"] else None,
                       "wallbox": val("wallbox_kw") if r["has_wallbox"] else None},
        })
    return out
