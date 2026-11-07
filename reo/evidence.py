"""Evidence from real expert designs (data/benchmarks.json): aggregate flags vs similar homes.

Flags are aggregate ("larger than 85% of similar homes") and may appear in the customer chat and in LLM context.
Individual homes are never served (hard rule 5).
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


def _band(kwh: float | None, bands: list[str]) -> str:
    if kwh is None:
        return "unknown"
    for b in bands:
        lo, _, hi = b.partition("-")
        if kwh >= float(lo.rstrip("+")) and (not hi or kwh < float(hi)):
            return b
    return "unknown"


def _household_kwh(facts: dict) -> float | None:
    """Benchmark bands are household-only (data c0cb87e). A customer's total equals that only without EV and
    electric heating; otherwise we don't band at all (falls back to a coarser segment)."""
    if facts.get("annual_demand_kwh"):
        return facts["annual_demand_kwh"]
    no_extra = not (facts.get("has_ev") or facts.get("ev_planned")) and facts.get("heating_type") not in ("heatpump", "electric")
    return facts.get("total_demand_kwh") if no_extra else None


def _home_key(facts: dict, bands: list[str]) -> dict:
    kwh = _household_kwh(facts)
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


def variant_locks(facts: dict, design: dict) -> dict[str, dict]:
    """Lock sets for the three offer variants (data c0cb87e anchors). Numbers still come from the engine."""
    seg = segment(facts)
    c = design["components"]
    basic, indep = {"heatpump": {"recommended": False}}, {}
    if seg:
        bat, pv = seg["battery_kwh"], seg["pv_kwp"]
        if seg["attach_rate"].get("battery", 1) < 0.5:
            basic["battery"] = {"recommended": False}
        else:
            basic["battery"] = {"recommended": True, "size": min(bat.get("p25", bat["p10"]), c["battery"]["size"] or 99)}
        indep["battery"] = {"recommended": True, "size": max(bat.get("p75", bat["p90"]), c["battery"]["size"] or 0)}
        if not facts.get("has_existing_pv"):
            indep["pv"] = {"recommended": True, "size": max(pv.get("p75", pv["p90"]), c["pv"]["size"] or 0)}
    else:  # no benchmarks: plain lock sets
        basic["battery"] = {"recommended": False}
        if c["battery"]["size"]:
            indep["battery"] = {"recommended": True, "size": round(c["battery"]["size"] * 1.5)}
    return {"Basic": basic, "Recommended": {}, "Independence": indep}
