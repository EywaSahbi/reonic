"""Contract smoke checks for the engine (:8000), reo (:8001), and data outputs.

Services must already be running. Endpoints for later milestones are skipped
when they return 404/405, so the same check works against M0 stubs.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = os.environ.get("ENGINE_URL", "http://localhost:8000").rstrip("/")
REO = os.environ.get("REO_URL", "http://localhost:8001").rstrip("/")
COMPONENTS = ("pv", "battery", "heatpump", "wallbox")
FACTS = {"annual_demand_kwh": 4500}
EV_DISTANCE_FACTS = (
    {"annual_demand_kwh": 4500, "has_ev": True, "ev_km_per_week": 250},
    {"annual_demand_kwh": 4500, "has_ev": True, "ev_km_per_day": 35},
)


class NotPublished(Exception):
    pass


def call(base: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 405):
            raise NotPublished(f"HTTP {exc.code}") from exc
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"{request.method} {path}: HTTP {exc.code}: {detail}") from exc


def check_range(value: object, label: str, nullable: bool = True) -> None:
    if value is None and nullable:
        return
    assert isinstance(value, list) and len(value) == 2, f"{label} must be a two-item array or null"
    assert all(isinstance(x, (int, float)) for x in value), f"{label} entries must be numbers"
    assert value[0] <= value[1], f"{label} lower bound exceeds upper bound"


def check_design(value: object, label: str) -> None:
    assert isinstance(value, dict), f"{label}: expected object"
    for key in ("components", "price", "economics", "assumptions", "missing_inputs", "params_version"):
        assert key in value, f"{label}: missing {key}"
    components = value["components"]
    assert isinstance(components, dict), f"{label}.components must be object"
    for name in COMPONENTS:
        item = components.get(name)
        assert isinstance(item, dict), f"{label}: missing component {name}"
        for key in ("recommended", "size", "unit", "range", "confidence", "locked", "reasons"):
            assert key in item, f"{label}.{name}: missing {key}"
        assert isinstance(item["recommended"], bool), f"{label}.{name}.recommended must be bool"
        assert item["size"] is None or isinstance(item["size"], (int, float)), f"{label}.{name}.size must be number/null"
        assert item["unit"] in ("kWp", "kWh", "kW"), f"{label}.{name}.unit is invalid"
        check_range(item["range"], f"{label}.{name}.range")
        assert item["confidence"] in ("low", "medium", "high"), f"{label}.{name}.confidence is invalid"
        assert isinstance(item["locked"], bool), f"{label}.{name}.locked must be bool"
        assert isinstance(item["reasons"], list) and all(isinstance(x, str) for x in item["reasons"]), f"{label}.{name}.reasons must be string array"
    price = value["price"]
    assert isinstance(price, dict) and isinstance(price.get("items"), list), f"{label}.price shape invalid"
    for key in ("total_eur",):
        assert isinstance(price.get(key), (int, float)), f"{label}.price.{key} must be numeric"
    check_range(price.get("range_eur"), f"{label}.price.range_eur", nullable=False)
    economics = value["economics"]
    assert isinstance(economics, dict), f"{label}.economics must be object"
    for key in ("total_demand_kwh", "self_consumption_pct", "autarky_pct", "annual_savings_eur"):
        assert isinstance(economics.get(key), (int, float)), f"{label}.economics.{key} must be numeric"
    assert economics.get("payback_years") is None or isinstance(economics.get("payback_years"), (int, float)), f"{label}.economics.payback_years must be numeric/null"
    assert isinstance(value["assumptions"], list), f"{label}.assumptions must be array"
    assert isinstance(value["missing_inputs"], list), f"{label}.missing_inputs must be array"
    assert isinstance(value["params_version"], str), f"{label}.params_version must be string"


def check_plan(value: object, label: str) -> dict:
    assert isinstance(value, dict), f"{label}: expected Plan object"
    for key in ("id", "status", "customer", "facts", "design", "transcript", "flags", "similar_projects", "installer_edits", "history", "updated_at"):
        assert key in value, f"{label}: missing {key}"
    assert isinstance(value["id"], str) and value["id"], f"{label}.id must be nonempty string"
    assert value["status"] in ("drafting", "handed_over", "quoted"), f"{label}.status invalid"
    assert isinstance(value["customer"], dict) and isinstance(value["facts"], dict), f"{label}.customer/facts invalid"
    check_design(value["design"], label + ".design")
    for key in ("transcript", "flags", "similar_projects", "installer_edits", "history"):
        assert isinstance(value[key], list), f"{label}.{key} must be array"
    return value


def check_turn(value: object, label: str) -> dict:
    assert isinstance(value, dict), f"{label}: expected Turn object"
    for key in ("messages", "plan", "suggestions"):
        assert key in value, f"{label}: missing {key}"
    assert isinstance(value["messages"], list), f"{label}.messages must be array"
    for message in value["messages"]:
        assert isinstance(message, dict) and message.get("role") in ("reo", "customer", "installer") and isinstance(message.get("text"), str) and isinstance(message.get("at"), str), f"{label}: invalid Message"
    assert isinstance(value["suggestions"], list) and all(isinstance(x, str) for x in value["suggestions"]), f"{label}.suggestions must be string array"
    check_plan(value["plan"], label + ".plan")
    return value


def engine_checks(results: list[str]) -> None:
    health = call(ENGINE, "/health")
    assert isinstance(health, dict) and health.get("ok") is True and isinstance(health.get("params_version"), str), "GET /health shape invalid"
    results.append("PASS engine GET /health")
    prices = call(ENGINE, "/prices")
    assert isinstance(prices, dict), "GET /prices must return a price-list object"
    results.append("PASS engine GET /prices")
    design = call(ENGINE, "/design", {"facts": FACTS})
    check_design(design, "engine POST /design")
    results.append("PASS engine POST /design")
    for distance_facts in EV_DISTANCE_FACTS:
        distance_design = call(ENGINE, "/design", {"facts": distance_facts})
        check_design(distance_design, "engine POST /design with EV distance")
    results.append("PASS engine /design accepts weekly and daily EV distance facts")
    try:
        explanation = call(ENGINE, "/explain", {"facts": FACTS, "component": "pv"})
    except NotPublished:
        results.append("SKIP engine POST /explain: later milestone")
    else:
        assert isinstance(explanation, dict) and isinstance(explanation.get("reasons"), list) and isinstance(explanation.get("what_if"), list), "POST /explain response shape invalid"
        results.append("PASS engine POST /explain")


def reo_checks(results: list[str]) -> None:
    turn = check_turn(call(REO, "/sessions", {}), "reo POST /sessions")
    plan_id = turn["plan"]["id"]
    encoded_id = urllib.parse.quote(plan_id, safe="")
    results.append("PASS reo POST /sessions")
    try:
        messages = call(REO, f"/sessions/{encoded_id}/messages", {"text": "We use about 4,500 kWh a year."})
    except NotPublished:
        results.append("SKIP customer messages: endpoint not published")
    else:
        turn = check_turn(messages, "reo POST /sessions/{id}/messages")
        results.append("PASS reo customer messages")
    try:
        turn = check_turn(call(REO, f"/sessions/{encoded_id}/facts", {"facts": FACTS}), "reo POST /sessions/{id}/facts")
        results.append("PASS reo customer facts")
    except NotPublished:
        results.append("SKIP customer facts: M1 endpoint")
    try:
        turn = check_turn(call(REO, f"/sessions/{encoded_id}/address", {"address": "Hackathonstrasse 1, Munich"}), "reo POST /sessions/{id}/address")
        results.append("PASS reo mocked address lookup")
    except NotPublished:
        results.append("SKIP address lookup: M2 endpoint")
    try:
        handoff = check_plan(call(REO, f"/sessions/{encoded_id}/handoff", {"name": "QA smoke"}), "reo POST /sessions/{id}/handoff")
        if handoff["status"] != "handed_over":
            raise AssertionError("handoff must set plan.status to handed_over")
        results.append("PASS reo handoff")
    except NotPublished:
        results.append("SKIP handoff: M1 endpoint")
    try:
        check_plan(call(REO, f"/sessions/{encoded_id}"), "reo GET /sessions/{id}")
        results.append("PASS reo customer plan retrieval")
    except NotPublished:
        results.append("SKIP customer plan retrieval: not published")
    try:
        plans = call(REO, "/plans?status=handed_over")
        assert isinstance(plans, list), "GET /plans must return array"
        for plan in plans:
            assert isinstance(plan, dict) and all(k in plan for k in ("id", "customer", "total_eur", "status", "updated_at")), "GET /plans row shape invalid"
        results.append("PASS reo installer plan list")
    except NotPublished:
        results.append("SKIP installer plan list: M1 endpoint")
    try:
        plan = check_plan(call(REO, f"/plans/{encoded_id}"), "reo GET /plans/{id}")
        results.append("PASS reo installer plan detail")
    except NotPublished:
        results.append("SKIP installer plan detail: M1 endpoint")
    try:
        edited = check_plan(call(REO, f"/plans/{encoded_id}/edit", {"facts": {"has_ev": True}}), "reo POST /plans/{id}/edit")
        results.append("PASS reo installer edit")
    except NotPublished:
        results.append("SKIP installer edit: M1 endpoint")
    try:
        answer = call(REO, f"/plans/{encoded_id}/ask", {"text": "Why this battery size?"})
        assert isinstance(answer, dict) and isinstance(answer.get("answer"), str), "POST /plans/{id}/ask response shape invalid"
        results.append("PASS reo installer ask")
    except NotPublished:
        results.append("SKIP installer ask: M2 endpoint")
    try:
        final_plan = check_plan(call(REO, f"/plans/{encoded_id}/finalize", {}), "reo POST /plans/{id}/finalize")
        if final_plan["status"] != "quoted":
            raise AssertionError("finalize must set plan.status to quoted")
        results.append("PASS reo finalize")
    except NotPublished:
        results.append("SKIP finalize: M1 endpoint")
    try:
        validation = call(REO, "/validation")
        assert isinstance(validation, dict) and "split" in validation and "components" in validation, "GET /validation score shape invalid"
        results.append("PASS reo GET /validation")
    except NotPublished:
        results.append("SKIP validation: M2 endpoint")


def data_check() -> str:
    table = ROOT / "data" / "processed" / "projects.parquet"
    splits = ROOT / "data" / "processed" / "split.csv"
    if not table.exists() or not splits.exists():
        return "SKIP data artifacts: projects.parquet or split.csv not published"
    try:
        import pandas as pd
    except ImportError:
        return "SKIP data artifacts: pandas unavailable"
    frame = pd.read_parquet(table)
    required = {"project_id", "annual_demand_kwh", "has_pv", "pv_kwp", "has_battery", "battery_kwh", "has_heatpump", "heatpump_kw", "has_wallbox", "wallbox_kw"}
    missing = required - set(frame.columns)
    assert not missing, f"projects.parquet missing columns: {sorted(missing)}"
    assert frame.project_id.notna().all() and frame.project_id.is_unique, "project_id must be non-null and unique"
    split_frame = pd.read_csv(splits)
    assert {"project_id", "split"} <= set(split_frame.columns), "split.csv needs project_id,split"
    assert split_frame.project_id.notna().all() and split_frame.project_id.is_unique, "split project_id must be non-null and unique"
    assert set(split_frame.split) <= {"train", "val", "test"}, "split has unknown labels"
    assert set(frame.project_id) == set(split_frame.project_id), "split must cover exactly the processed projects"
    return f"PASS data artifacts: {len(frame)} unique projects; split covers all projects"


def main() -> int:
    results = []
    for label, check in (("engine", engine_checks), ("reo", reo_checks)):
        try:
            check(results)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, NotPublished, AssertionError) as exc:
            print(f"FAIL {label} contract: {exc}")
            return 1
    try:
        results.append(data_check())
    except (AssertionError, ValueError, ImportError) as exc:
        print(f"FAIL data contract: {exc}")
        return 1
    print("\n".join(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
