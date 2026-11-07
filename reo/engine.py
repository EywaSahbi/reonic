"""Thin client for the engine API (engine/CONTRACT.md). Every number reo shows comes through here."""
import os

import httpx

ENGINE_URL = os.getenv("ENGINE_URL", "http://localhost:8000")


def design(facts: dict, locks: dict | None = None, prices: dict | None = None) -> dict | None:
    """POST /design. Returns the Design, or None if the engine is unreachable or errors."""
    body = {"facts": facts}
    if locks:
        body["locks"] = locks
    if prices:
        body["prices"] = prices
    try:
        r = httpx.post(f"{ENGINE_URL}/design", json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return None
