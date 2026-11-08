"""Harness evals on data's scenarios (data/processed/scenarios.json). Needs the engine on :8000.

    uv run python -m evals            # scripted planner (no API calls)
    uv run python -m evals --llm      # the skills' models (costs API calls)

Per scenario, offer_prep must: ground every number, execute nothing, return exactly one quotation (the engine's design),
respect the budget (time, and budget_eur if given), and leave a trace. Exit code 1 if any check fails.
"""
import json
import os
import sys
from pathlib import Path

import engine
from harness.runner import Runner
from harness.skills import OFFER_PREP
from harness.tools import Ctx

SCENARIOS = Path(__file__).parent.parent.parent / "data" / "processed" / "scenarios.json"


def checks(sc: dict, run: dict) -> dict[str, bool]:
    out = run["output"] or {}
    variants = out.get("variants", [])
    budget = sc["facts"].get("budget_eur")
    rec = next((v for v in variants if v["name"] == out.get("recommended")), None)
    guard = [s for s in run["steps"] if s.get("tool") == "grounding"]
    return {
        "grounded": bool(guard) and guard[-1].get("ok", False),
        "no_execute": not any(s.get("effect") == "execute" for s in run["steps"])
                      and all(a["status"] == "proposed" for a in out.get("actions", [])),
        "one_offer": [v["name"] for v in variants] == ["Recommended"],
        "budget": run["duration_s"] <= OFFER_PREP.max_seconds and (not budget or (rec and rec["design"]["price"]["total_eur"] <= budget * 1.05)),
        "trace": len(out.get("trace", [])) >= 5,
    }


def main() -> int:
    if "--llm" not in sys.argv:
        os.environ["ANTHROPIC_API_KEY"] = ""  # scripted planner only
    if not engine.healthy():
        print(f"engine not reachable at {engine.ENGINE_URL}: start it first (cd engine && uv run uvicorn api:app --port 8000)")
        return 1
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]
    rows, failed = [], 0
    for sc in scenarios:
        plan = {"id": f"eval-{sc['id']}", "facts": dict(sc["facts"]), "customer": {"name": "Test"}, "status": "handed_over",
                "transcript": []}
        run = Runner(OFFER_PREP, Ctx(plan, {"locks": {}, "prices": {}}, []), "eval").go()
        c = checks(sc, run)
        failed += not all(c.values())
        out = run["output"] or {}
        rec = next((v for v in out.get("variants", []) if v["name"] == out.get("recommended")), None)
        comp = (rec or {}).get("design", {}).get("components", {})
        reo = "/".join(f"{comp[k]['size']:g}" if comp.get(k, {}).get("recommended") and comp[k]["size"] else "-"
                       for k in ("pv", "battery", "wallbox"))
        exp = "/".join(f"{sc['expert'][k]['size']:g}" if sc["expert"][k]["recommended"] and sc["expert"][k]["size"] else "-"
                       for k in ("pv", "battery", "wallbox"))
        rows.append([sc["id"], run["model"], f"{run['duration_s']}s", *("ok" if v else "FAIL" for v in c.values()), reo, exp])
    head = ["scenario", "model", "time", "grounded", "no_execute", "one_offer", "budget", "trace", "reo pv/bat/wb", "expert pv/bat/wb"]
    widths = [max(len(str(r[i])) for r in [head, *rows]) for i in range(len(head))]
    for r in [head, *rows]:
        print("  ".join(str(x).ljust(w) for x, w in zip(r, widths)))
    print(f"\n{len(rows) - failed}/{len(rows)} scenarios pass all checks")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
