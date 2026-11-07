import pandas as pd

from scenarios import ROOT, build


def test_scenarios_cover_hard_cases_and_never_test():
    sc = build()
    ids = {s["id"] for s in sc}
    assert {"retrofit_existing_pv", "ev_planned", "gas_to_heatpump", "tiny_demand", "big_demand", "tight_budget"} <= ids
    assert 6 <= len(sc) <= 10
    split = pd.read_csv(ROOT / "processed" / "split.csv").set_index("project_id").split
    assert all(split[s["project_id"]] != "test" for s in sc)
    by = {s["id"]: s for s in sc}
    assert by["gas_to_heatpump"]["expert"]["heatpump"]["recommended"]
    assert by["retrofit_existing_pv"]["facts"]["has_existing_pv"] and not by["retrofit_existing_pv"]["expert"]["pv"]["recommended"]
    assert by["tight_budget"]["facts"]["budget_eur"] == by["tight_budget"]["added_facts"]["budget_eur"]
