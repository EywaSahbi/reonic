"""Contract smoke checks for the engine (:8000), reo (:8001), and data outputs.

Services must already be running. Endpoints for later milestones are skipped
when they return 404/405, so the same check works against M0 stubs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
DEMAND_FACTS = ({}, {"total_demand_kwh": 4500}, FACTS)
REGION_FACTS = ("SH", "BY")  # north and south yield should produce different PV sizes


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


def call_text(base: str, path: str) -> str:
    request = urllib.request.Request(base + path, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"GET {path}: HTTP {exc.code}: {detail}") from exc


def expect_status(base: str, path: str, status: int, body: dict | None = None) -> None:
    try:
        call(base, path, body)
    except AssertionError as exc:
        if f"HTTP {status}" in str(exc):
            return
        raise
    raise AssertionError(f"{path}: expected HTTP {status}, request succeeded")


def check_range(value: object, label: str, nullable: bool = True) -> None:
    if value is None and nullable:
        return
    assert isinstance(value, list) and len(value) == 2, f"{label} must be a two-item array or null"
    assert all(isinstance(x, (int, float)) for x in value), f"{label} entries must be numbers"
    assert value[0] <= value[1], f"{label} lower bound exceeds upper bound"


def check_design(value: object, label: str) -> None:
    assert isinstance(value, dict), f"{label}: expected object"
    for key in ("components", "price", "economics", "bundle", "installer_profile", "assumptions", "missing_inputs", "params_version"):
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
    for key in ("bill_today_eur_per_month", "bill_after_eur_per_month"):
        assert isinstance(economics.get(key), (int, float)), f"{label}.economics.{key} must be numeric"
    assert economics.get("payback_years") is None or isinstance(economics.get("payback_years"), (int, float)), f"{label}.economics.payback_years must be numeric/null"
    assert value.get("bundle") in (None, "S", "M", "L", "XL"), f"{label}.bundle invalid"
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
    plan = check_plan(value["plan"], label + ".plan")
    if plan["design"]["params_version"] == "engine-offline":
        for message in value["messages"]:
            if message["role"] == "reo":
                assert not any("0" <= ch <= "9" for ch in message["text"]), f"{label}: reo invented a number while engine is offline"
    return value


def engine_checks(results: list[str]) -> None:
    health = call(ENGINE, "/health")
    assert isinstance(health, dict) and health.get("ok") is True and isinstance(health.get("params_version"), str), "GET /health shape invalid"
    results.append("PASS engine GET /health")
    installers = call(ENGINE, "/installers")
    assert isinstance(installers, dict) and installers, "GET /installers must return at least one profile"
    for profile in installers.values():
        assert isinstance(profile, dict) and isinstance(profile.get("projects"), int), "GET /installers profile shape invalid"
        line = profile.get("pv_line")
        assert isinstance(line, dict) and all(isinstance(line.get(k), (int, float)) for k in ("a_kwp", "b_kwp_per_mwh")), \
            "installer pv_line must include numeric a_kwp and b_kwp_per_mwh"
        assert isinstance(profile.get("battery_by_pv_band"), list), "installer battery_by_pv_band must be array"
    profile_id = next(iter(installers))
    profiled = call(ENGINE, "/design", {"facts": FACTS, "installer": profile_id})
    check_design(profiled, "engine POST /design with installer profile")
    assert profiled.get("installer_profile") == profile_id, "design must report the selected installer profile"
    results.append("PASS engine GET /installers and installer-profile design")
    prices = call(ENGINE, "/prices")
    assert isinstance(prices, dict), "GET /prices must return a price-list object"
    assert prices and all(isinstance(v, (int, float)) for v in prices.values()), "GET /prices values must be numeric"
    for key in prices:
        if key.endswith("_low"):
            assert key.removesuffix("_low") + "_high" in prices, f"GET /prices missing high bound for {key}"
        if key.endswith("_high"):
            assert key.removesuffix("_high") + "_low" in prices, f"GET /prices missing low bound for {key}"
    results.append("PASS engine GET /prices")
    for design_facts in DEMAND_FACTS:
        design = call(ENGINE, "/design", {"facts": design_facts})
        check_design(design, "engine POST /design")
    results.append("PASS engine /design with no demand, total demand, and household demand")
    for distance_facts in EV_DISTANCE_FACTS:
        distance_design = call(ENGINE, "/design", {"facts": distance_facts})
        check_design(distance_design, "engine POST /design with EV distance")
    results.append("PASS engine /design accepts weekly and daily EV distance facts")
    regional_designs = [
        call(ENGINE, "/design", {"facts": {"total_demand_kwh": 4500, "region": region}})
        for region in REGION_FACTS
    ]
    for design in regional_designs:
        check_design(design, "engine POST /design with region")
    north_pv = regional_designs[0]["components"]["pv"]["size"]
    south_pv = regional_designs[1]["components"]["pv"]["size"]
    assert isinstance(north_pv, (int, float)) and isinstance(south_pv, (int, float)) and north_pv > south_pv, \
        "regional PV sizing should account for the lower northern yield"
    assert not any(item.get("field") == "region" for item in regional_designs[1]["missing_inputs"]), \
        "known region should not remain a missing input"
    results.append("PASS engine /design uses region for PV yield and sizing")
    retrofit = call(ENGINE, "/design", {"facts": {"total_demand_kwh": 4500, "has_existing_pv": True, "existing_pv_kwp": 5}})
    check_design(retrofit, "engine retrofit design")
    assert not retrofit["components"]["pv"]["recommended"], "existing PV retrofit must not recommend new PV by default"
    results.append("PASS engine retrofit design avoids recommending new PV")
    fact_consistent = call(ENGINE, "/design", {"facts": {
        "total_demand_kwh": 4500, "heating_type": "gas", "ev_planned": True, "region": "BY"
    }})
    check_design(fact_consistent, "engine POST /design with gas heating and planned EV")
    hp_reason = " ".join(fact_consistent["components"]["heatpump"]["reasons"]).lower()
    assert "gas" in hp_reason and "already electric" not in hp_reason, \
        "heat-pump explanation must match gas heating"
    ev_notes = [item.get("note") for item in fact_consistent["assumptions"] if item.get("field") == "has_ev"]
    assert ev_notes == ["no EV today, one is planned"], \
        "planned EV assumption must not claim there is no planned EV"
    results.append("PASS engine explanations and assumptions match gas heating and planned EV facts")
    explanation = call(ENGINE, "/explain", {"facts": FACTS, "component": "pv"})
    assert isinstance(explanation, dict) and isinstance(explanation.get("reasons"), list) and isinstance(explanation.get("what_if"), list), "POST /explain response shape invalid"
    assert explanation["what_if"], "POST /explain must return at least one what-if"
    for item in explanation["what_if"]:
        assert isinstance(item.get("locks"), dict) and isinstance(item.get("delta"), dict), "what-if must include locks and deltas"
        for key in ("price_eur", "annual_savings_eur", "payback_years", "autarky_pct", "bill_after_eur_per_month"):
            assert key in item["delta"], f"what-if delta missing {key}"
    results.append("PASS engine POST /explain what-if deltas and locks")


def reo_checks(results: list[str]) -> None:
    health = call(REO, "/health")
    assert isinstance(health, dict) and health.get("ok") is True, "reo GET /health must return ok=true"
    for key in ("llm", "voice", "engine"):
        assert isinstance(health.get(key), bool), f"reo GET /health missing boolean {key}"
    results.append("PASS reo GET /health")
    if health["engine"]:
        prices = call(REO, "/prices")
        assert isinstance(prices, dict), "reo GET /prices must return a price-list object"
        results.append("PASS reo GET /prices")
    else:
        expect_status(REO, "/prices", 503)
        results.append("PASS reo GET /prices returns 503 while engine is offline")

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
        if not isinstance(handoff.get("summary"), str) or not handoff["summary"]:
            raise AssertionError("handed-over Plan must include its installer summary")
        results.append("PASS reo handoff")
    except NotPublished:
        results.append("SKIP handoff: M1 endpoint")
    # Auto-triggered scripted offer preparation must leave a grounded trace and proposed actions only.
    try:
        offer_plan = None
        pack = None
        for _ in range(40):
            offer_plan = check_plan(call(REO, f"/plans/{encoded_id}"), "reo GET /plans/{id} for offer pack")
            pack = offer_plan.get("offer_pack")
            if not isinstance(pack, dict) or pack.get("status") != "preparing":
                break
            time.sleep(0.25)
        if not isinstance(pack, dict) or pack.get("status") != "ready":
            raise AssertionError("handoff offer pack did not reach ready")
        variants = pack.get("variants", [])
        assert [v.get("name") for v in variants] == ["Basic", "Recommended", "Independence"], "offer pack must expose three named variants"
        assert len({v["design"]["price"]["total_eur"] for v in variants}) == 3, "offer variants must have distinct prices"
        assert isinstance(pack.get("run_id"), str) and pack["run_id"], "offer pack must include its run id"
        actions = pack.get("actions", [])
        assert actions and all(a.get("status") == "proposed" for a in actions), "agent actions must remain proposed before approval"
        run = call(REO, f"/runs/{urllib.parse.quote(pack['run_id'], safe='')}")
        assert run.get("status") == "needs_approval", "offer run must wait for planner approval"
        assert any(s.get("tool") == "grounding" and s.get("ok") for s in run.get("steps", [])), "offer pack needs a passed grounding guard"
        assert not any(s.get("effect") == "execute" for s in run.get("steps", [])), "offer agent must not execute actions"
        event_stream = call_text(REO, f"/runs/{urllib.parse.quote(pack['run_id'], safe='')}/events")
        assert event_stream.count("event: step") == len(run.get("steps", [])) and "event: done" in event_stream, \
            "run SSE must replay every step and its done event"
        selected = check_plan(call(REO, f"/plans/{encoded_id}/variant", {"name": "Basic"}), "reo POST /plans/{id}/variant")
        selected_pack = selected.get("offer_pack", {})
        selected_battery = selected["design"]["components"]["battery"]
        selected_draft = selected_pack.get("customer_message_draft", "")
        battery_kwh = round(selected_battery["size"]) if selected_battery.get("recommended") else None
        price_range = selected["design"]["price"]["range_eur"]
        expected_range = f"€{int(round(price_range[0] / 100) * 100):,}–{int(round(price_range[1] / 100) * 100):,}"
        quote_action = next((a for a in selected_pack.get("actions", []) if a.get("kind") == "send_quote"), None)
        assert selected_pack.get("chosen") == "Basic" and selected_pack.get("draft_for") == "Basic", \
            "selecting a variant must mark its refreshed draft for that variant"
        assert (battery_kwh is None or f"{battery_kwh} kWh battery" in selected_draft) and expected_range in selected_draft, \
            "variant draft sizes and price range must match its engine design"
        assert quote_action and quote_action.get("payload", {}).get("message") == selected_draft \
            and quote_action.get("payload", {}).get("variant") == "Basic", \
            "proposed send_quote action must carry the chosen variant and matching draft"
        plan_runs = call(REO, f"/plans/{encoded_id}/runs")
        assert any(r.get("id") == pack["run_id"] for r in plan_runs), "plan run list must contain offer run"
        slots = call(REO, "/calendar/slots")
        assert isinstance(slots.get("slots"), list) and slots["slots"], "calendar slots must be available"
        results.append("PASS reo offer pack, variant-grounded draft, run log/SSE, approval gate, and calendar slots")
    except NotPublished:
        results.append("SKIP offer pack and run trace: phase 2 endpoint not published")
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
    except AssertionError as exc:
        if health["engine"] or "HTTP 503" not in str(exc):
            raise
        results.append("PASS reo installer edit rejects offline engine with HTTP 503")
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
    validation = call(REO, "/validation")
    assert isinstance(validation, dict), "GET /validation must return JSON object"
    if validation.get("available") is False:
        results.append("SKIP reo GET /validation: no score report available")
    else:
        assert "split" in validation and "components" in validation, "GET /validation score shape invalid"
        assert validation.get("file") == "score_test_test.json" and validation.get("split") == "test", \
            "GET /validation default must serve the fixed test report"
        val = call(REO, "/validation?split=val")
        profile_view = call(REO, "/validation?view=profiles")
        assert val.get("file") == "score_val_val.json" and val.get("split") == "val", "GET /validation?split=val must serve the fixed val report"
        assert profile_view.get("file") == "score_val_profiles_val.json", "GET /validation?view=profiles must serve installer-profile results"
        results.append("PASS reo GET /validation fixed test, val, and profile reports")


def data_check() -> str:
    table = ROOT / "data" / "processed" / "projects.parquet"
    splits = ROOT / "data" / "processed" / "split.csv"
    benchmarks = ROOT / "data" / "processed" / "benchmarks.json"
    if not table.exists() or not splits.exists() or not benchmarks.exists():
        return "SKIP data artifacts: projects.parquet, split.csv, or benchmarks.json not published"
    try:
        import pandas as pd
    except ImportError:
        return "SKIP data artifacts: pandas unavailable"
    frame = pd.read_parquet(table)
    required = {
        "project_id", "installer", "option_id", "target_source",
        "annual_demand_kwh", "num_inhabitants", "house_size_sqm", "house_built_year",
        "heating_type", "heating_demand_kwh", "has_ev", "ev_km_per_year",
        "electricity_price_eur_per_kwh", "has_existing_pv", "existing_pv_kwp",
        "has_existing_battery", "existing_battery_kwh", "has_existing_wallbox",
        "existing_heating_electricity_kwh", "has_pv", "pv_kwp", "pv_modules",
        "has_battery", "battery_kwh", "has_heatpump", "heatpump_kw", "has_wallbox", "wallbox_kw",
        "customer_contact_id",
    }
    missing = required - set(frame.columns)
    assert not missing, f"projects.parquet missing columns: {sorted(missing)}"
    assert frame.project_id.notna().all() and frame.project_id.is_unique, "project_id must be non-null and unique"
    split_frame = pd.read_csv(splits)
    assert {"project_id", "split"} <= set(split_frame.columns), "split.csv needs project_id,split"
    assert split_frame.project_id.notna().all() and split_frame.project_id.is_unique, "split project_id must be non-null and unique"
    assert set(split_frame.split) <= {"train", "val", "test"}, "split has unknown labels"
    assert set(frame.project_id) == set(split_frame.project_id), "split must cover exactly the processed projects"
    counts = split_frame.split.value_counts().to_dict()
    assert counts == {"train": 1098, "val": 238, "test": 235}, f"unexpected fixed split counts: {counts}"
    by_customer = frame[["project_id", "customer_contact_id"]].merge(split_frame, on="project_id")
    assert by_customer.customer_contact_id.notna().all(), "customer_contact_id must be populated for leak check"
    assert by_customer.groupby("customer_contact_id").split.nunique().max() == 1, \
        "a customer appears in more than one split"
    with benchmarks.open(encoding="utf-8") as f:
        benchmark_data = json.load(f)
    assert benchmark_data.get("built_from") == "train", "benchmarks must be built from train only"
    assert benchmark_data.get("n_train") == counts["train"], "benchmark n_train differs from fixed train split"
    assert isinstance(benchmark_data.get("segments"), list) and benchmark_data["segments"], \
        "benchmarks must include segments"
    scenario_path = ROOT / "data" / "processed" / "scenarios.json"
    if scenario_path.exists():
        with scenario_path.open(encoding="utf-8") as f:
            scenario_data = json.load(f)
        scenarios = scenario_data.get("scenarios")
        built_from = scenario_data.get("built_from", "").lower()
        assert "val" in built_from and "train" in built_from \
            and ("test" not in built_from or "never test" in built_from) \
            and isinstance(scenarios, list) and len(scenarios) == 9, \
            "scenario set must have nine held-out evaluation cases"
        assert all(item.get("split") != "test" for item in scenarios), "reo scenarios must not include test projects"
    else:
        return f"PASS data artifacts: {len(frame)} projects; fixed split is leak-free; benchmarks built from train; SKIP scenarios"
    return f"PASS data artifacts: {len(frame)} projects; fixed split is leak-free; benchmarks built from train"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-engine", action="store_true", help="check reo and data without requiring :8000")
    parser.add_argument("--skip-reo", action="store_true", help="check engine and data without requiring :8001")
    args = parser.parse_args()
    results = []
    checks = []
    if not args.skip_engine:
        checks.append(("engine", engine_checks))
    else:
        results.append("SKIP engine checks: --skip-engine")
    if not args.skip_reo:
        checks.append(("reo", reo_checks))
    else:
        results.append("SKIP reo checks: --skip-reo")
    for label, check in checks:
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
