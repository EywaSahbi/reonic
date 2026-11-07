"""Contract smoke checks for the running Reonic stack.

The engine must already be running on localhost:8000. Checks for unpublished
M1/M2 artifacts are skipped so this script is useful throughout the build.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_CONTRACT = ROOT / "engine" / "CONTRACT.md"
DATA_CONTRACT = ROOT / "data" / "CONTRACT.md"
BASE = os.environ.get("ENGINE_URL", "http://localhost:8000").rstrip("/")
COMPONENTS = ("pv", "battery", "heatpump", "wallbox")


def request(path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.status, json.loads(response.read())


def check_design(value: object, label: str) -> None:
    assert isinstance(value, dict), f"{label}: expected JSON object"
    for key in ("components", "summary", "assumptions", "model_version"):
        assert key in value, f"{label}: missing {key}"
    assert isinstance(value["components"], dict), f"{label}: components must be object"
    for name in COMPONENTS:
        component = value["components"].get(name)
        assert isinstance(component, dict), f"{label}: missing component {name}"
        for key in ("recommended", "size", "unit", "confidence", "alternatives", "locked", "reasons"):
            assert key in component, f"{label}.{name}: missing {key}"
        assert isinstance(component["recommended"], bool), f"{label}.{name}.recommended must be bool"
        assert component["size"] is None or isinstance(component["size"], (int, float)), f"{label}.{name}.size must be number/null"
        assert isinstance(component["confidence"], (int, float)) and 0 <= component["confidence"] <= 1, f"{label}.{name}.confidence outside 0..1"
        assert isinstance(component["alternatives"], list), f"{label}.{name}.alternatives must be array"
        assert isinstance(component["reasons"], list), f"{label}.{name}.reasons must be array"
    assert isinstance(value["summary"], str)
    assert isinstance(value["assumptions"], list)
    assert isinstance(value["model_version"], str)


def optional_data_check() -> str:
    table = ROOT / "data" / "processed" / "projects.parquet"
    splits = ROOT / "data" / "processed" / "split.csv"
    if not table.exists() or not splits.exists():
        return "SKIP data artifacts: processed table or split.csv not published"
    try:
        import pandas as pd
    except ImportError:
        return "SKIP data artifacts: pandas unavailable for parquet inspection"
    frame = pd.read_parquet(table)
    required = {"project_id", "energy_demand_kwh", "has_pv", "pv_kwp", "has_battery", "battery_kwh", "has_heatpump", "heatpump_kw", "has_wallbox", "wallbox_kw"}
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
    if not ENGINE_CONTRACT.exists() or not DATA_CONTRACT.exists():
        print("FAIL contract file missing")
        return 1
    results = []
    try:
        status, health = request("/health")
        assert status == 200 and health.get("ok") is True, "/health must return {ok: true, ...}"
        assert isinstance(health.get("model_version"), str), "/health missing model_version"
        results.append("PASS GET /health")
        home = {"energy_demand_kwh": 4500}
        _, design = request("/design", home)
        check_design(design, "POST /design")
        results.append("PASS POST /design")
        try:
            _, refined = request("/refine", {"home": home})
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                results.append("SKIP POST /refine: M1 endpoint not published")
            else:
                raise
        else:
            check_design(refined, "POST /refine")
            results.append("PASS POST /refine")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, AssertionError, urllib.error.HTTPError) as exc:
        print(f"FAIL engine smoke at {BASE}: {exc}")
        return 1
    try:
        results.append(optional_data_check())
    except (AssertionError, ImportError, ValueError) as exc:
        print(f"FAIL data contract: {exc}")
        return 1
    print("\n".join(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
