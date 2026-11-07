"""Thin client for the engine API (engine/CONTRACT.md). Every number reo shows comes through here."""
import os

import httpx

ENGINE_URL = os.getenv("ENGINE_URL", "http://localhost:8000")
OFFLINE = "engine-offline"  # params_version of the placeholder design below


def _post(path: str, body: dict) -> dict | None:
    try:
        r = httpx.post(f"{ENGINE_URL}{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def design(facts: dict, locks: dict | None = None, prices: dict | None = None) -> dict | None:
    """POST /design. Returns the Design, or None if the engine is unreachable or errors."""
    body = {"facts": facts}
    if locks:
        body["locks"] = locks
    if prices:
        body["prices"] = prices
    return _post("/design", body)


def prices() -> dict | None:
    try:
        r = httpx.get(f"{ENGINE_URL}/prices", timeout=5)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def healthy() -> bool:
    try:
        return httpx.get(f"{ENGINE_URL}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def offline_design() -> dict:
    """Contract-shaped design with no numbers, used only while the engine is down (hard rule 2: never invent)."""
    comp = lambda unit: {"recommended": False, "size": None, "unit": unit, "range": None, "confidence": "low",
                         "locked": False, "reasons": ["calculation not available right now"]}
    return {
        "components": {"pv": comp("kWp"), "battery": comp("kWh"), "heatpump": comp("kW"), "wallbox": comp("kW")},
        "price": {"items": [], "total_eur": 0, "range_eur": [0, 0]},
        "economics": {"total_demand_kwh": 0, "self_consumption_pct": 0, "autarky_pct": 0,
                      "annual_savings_eur": 0, "payback_years": None},
        "assumptions": [], "missing_inputs": [], "params_version": OFFLINE,
    }
