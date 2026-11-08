import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from api import app  # noqa: E402
from design import battery_for, sim  # noqa: E402
from inputs import PARAMS  # noqa: E402

client = TestClient(app)
GAS_HOME = {"total_demand_kwh": 4500, "heating_type": "gas", "roof_area_sqm": 100, "region": "NW",
            "heating_demand_kwh": 15000}


def post(facts, **kw):  # noqa: D103
    r = client.post("/design", json={"facts": facts, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_health_and_prices():
    assert client.get("/health").json()["ok"] is True
    p = client.get("/prices").json()
    assert 0 < p["heatpump_subsidy_share"] < 1 and p["feed_in_eur_per_kwh"] > 0   # equipment prices live in catalog.json


def test_empty_facts_give_full_design():
    d = post({})
    assert set(d["components"]) == {"pv", "battery", "heatpump", "wallbox"}
    pv = d["components"]["pv"]
    assert pv["recommended"] and pv["range"][0] < pv["range"][1] and pv["quantity"] > 0
    assert d["components"]["battery"]["recommended"]
    assert d["price"]["range_eur"][0] < d["price"]["total_eur"] < d["price"]["range_eur"][1]
    top = [m["field"] for m in d["missing_inputs"][:2]]
    assert {"has_existing_pv", "total_demand_kwh"} == set(top) and d["missing_inputs"][0]["impact"] == "high"
    assert d["bundle"] in {"S", "M", "L", "XL"}
    for k in ("bill_today_eur_per_month", "bill_after_eur_per_month", "autarky_pct", "payback_years"):
        assert d["economics"][k] is not None


def test_each_fact_narrows_the_design():
    wide = post({})
    narrow = post({"total_demand_kwh": 4500, "region": "BY", "roof_orientation_deg": 180, "has_ev": False,
                   "roof_area_sqm": 60, "heating_type": "heatpump", "electricity_price_eur_per_kwh": 0.3})
    w, n = wide["components"]["pv"]["range"], narrow["components"]["pv"]["range"]
    assert n[1] - n[0] < w[1] - w[0]
    assert narrow["components"]["pv"]["confidence"] == "high"      # nothing left that would change the size
    assert len(narrow["missing_inputs"]) < len(wide["missing_inputs"])


def test_range_keeps_expert_spread_around_size():
    pv = post({"total_demand_kwh": 4500, "region": "BY", "roof_orientation_deg": 180, "has_existing_pv": False})["components"]["pv"]
    lo_r, hi_r = PARAMS["expert_spread"]["pv"]["all"]
    assert pv["range"] == [round(pv["size"] * lo_r, 2), round(pv["size"] * hi_r, 2)]


def test_ev_adds_wallbox_and_evening_load():
    d = post({"total_demand_kwh": 7200, "has_ev": True, "ev_km_per_day": 40})
    assert d["components"]["wallbox"] == {**d["components"]["wallbox"], "recommended": True, "size": 11}


def test_gas_home_with_spare_roof_gets_heatpump_priced_and_saved():
    d = post(GAS_HOME)
    hp = d["components"]["heatpump"]
    assert hp["recommended"] and hp["size"] in PARAMS["heatpump_catalogue_kw"] and "gas" in hp["reasons"][0]
    assert any("heat pump" in i["label"].lower() for i in d["price"]["items"])
    assert d["economics"]["total_demand_kwh"] == round(4500 + 15000 / PARAMS["cop"])
    grant = [i for i in d["price"]["items"] if i["label"].startswith("KfW")]
    assert grant and grant[0]["total_eur"] < 0
    assert d["economics"]["bill_today_eur_per_month"] > d["economics"]["bill_after_eur_per_month"]


def test_battery_lock_rederives_price_and_autarky():
    free = post({"total_demand_kwh": 4500})
    off = post({"total_demand_kwh": 4500}, locks={"battery": {"recommended": False}})
    assert off["components"]["battery"]["locked"] and not off["components"]["battery"]["recommended"]
    assert off["price"]["total_eur"] < free["price"]["total_eur"]
    assert off["economics"]["autarky_pct"] < free["economics"]["autarky_pct"]


def test_pv_lock_rederives_battery():
    d = post({"total_demand_kwh": 4500}, locks={"pv": {"recommended": True, "size": 15}})
    assert d["components"]["pv"]["size"] == 15 and d["components"]["pv"]["range"] == [15, 15]
    assert d["components"]["battery"]["size"] == battery_for(15, PARAMS["battery"]["by_pv_band"])


def test_price_override_is_exact():
    a = post({"total_demand_kwh": 4500}, prices={"module_eur": 100})
    b = post({"total_demand_kwh": 4500}, prices={"module_eur": 120})
    n = a["components"]["pv"]["quantity"]
    assert abs((b["price"]["total_eur"] - a["price"]["total_eur"]) - 20 * n) < 0.05
    assert a["price"]["items"][0]["unit_price_eur"] == 100


def test_price_lines_split_and_add_up():
    d = post({"total_demand_kwh": 4500, "ev_planned": True})
    labels = [i["label"] for i in d["price"]["items"]]
    assert labels[0].startswith("JA Solar") and "Scaffolding" in labels and "Wallbox installation and registration" in labels
    assert any(l.startswith("Huawei SUN2000") for l in labels) and any(l.startswith("go-e") for l in labels)
    modules = d["price"]["items"][0]
    assert modules["qty"] == d["components"]["pv"]["quantity"] and modules["unit"] == "pc"
    assert abs(sum(i["total_eur"] for i in d["price"]["items"]) - d["price"]["total_eur"]) < 0.01


def test_reasons_match_facts():
    d = post({"total_demand_kwh": 4500, "heating_type": "gas", "ev_planned": True, "region": "BY"})
    assert "gas" in d["components"]["heatpump"]["reasons"][0]
    assert [a["note"] for a in d["assumptions"] if a["field"] == "has_ev"] == ["no EV today, one is planned"]
    assert "plan an EV" in d["components"]["wallbox"]["reasons"][0]


def test_explain_battery_what_ifs():
    r = client.post("/explain", json={"facts": {"total_demand_kwh": 4500}, "component": "battery"}).json()
    changes = [w["change"] for w in r["what_if"]]
    assert changes[0] == "no battery" and len(changes) == 3          # off, one step down, one step up
    off = r["what_if"][0]["delta"]
    assert off["price_eur"] < 0 and off["autarky_pct"] < 0 and r["what_if"][0]["locks"]["battery"] == {"recommended": False}


def test_explain_adds_missing_component():
    r = client.post("/explain", json={"facts": {"total_demand_kwh": 4500, "has_ev": False}, "component": "wallbox"}).json()
    assert r["what_if"][0]["change"] == "add wallbox" and r["what_if"][0]["delta"]["price_eur"] > 0


def test_bad_input_is_422():
    assert client.post("/design", json={"facts": {"region": "Bayern"}}).status_code == 422


def test_fast_enough():
    sim.cache_clear()
    t = time.perf_counter()
    post(GAS_HOME)
    assert time.perf_counter() - t < 0.1


def test_budget_shrinks_battery_then_pv():
    full = post({"total_demand_kwh": 4500})
    budget = full["price"]["total_eur"] - 3000
    d = post({"total_demand_kwh": 4500, "budget_eur": budget})
    assert d["price"]["total_eur"] <= budget
    assert not d["components"]["battery"]["locked"]
    assert any("budget" in r for c in d["components"].values() for r in c["reasons"])


def test_more_facts_do_not_widen_price_range():
    a = post({"num_inhabitants": 4})["price"]["range_eur"]
    b = post({"num_inhabitants": 4, "ev_planned": True, "heating_type": "gas"})["price"]["range_eur"]
    assert b[1] / b[0] <= a[1] / a[0] * 1.1        # a wallbox adds a little, a possible heat pump adds nothing


def test_existing_pv_is_a_retrofit():
    d = post({"total_demand_kwh": 6000, "has_existing_pv": True, "existing_pv_kwp": 5})
    assert not d["components"]["pv"]["recommended"] and "already have 5 kWp" in d["components"]["pv"]["reasons"][0]
    assert d["components"]["battery"]["recommended"]          # storage for the existing panels
    assert d["bundle"] is None


def test_existing_pv_lock_still_allows_more_panels():
    d = post({"total_demand_kwh": 6000, "has_existing_pv": True, "existing_pv_kwp": 5},
             locks={"pv": {"recommended": True, "size": 4}})
    assert d["components"]["pv"]["size"] == 4


def test_installer_profile_changes_style():
    a = post({"total_demand_kwh": 4500}, installer="23c108b7")
    b = post({"total_demand_kwh": 4500}, installer="2a8ba8e2")
    assert a["installer_profile"] == "23c108b7" and a["components"]["pv"]["size"] != b["components"]["pv"]["size"]
    assert post({"total_demand_kwh": 4500}, installer="unknown")["installer_profile"] is None
    assert set(client.get("/installers").json()) == {"23c108b7", "2a8ba8e2"}


def test_subsidy_share_zero_hides_grant_line():
    d = post(GAS_HOME, prices={"heatpump_subsidy_share": 0})
    assert not any(i["label"].startswith("KfW") for i in d["price"]["items"])
    assert d["price"]["total_eur"] > post(GAS_HOME)["price"]["total_eur"]


def test_roof_is_a_hard_cap_end_to_end():
    d = post({"total_demand_kwh": 9000, "roof_area_sqm": 20})
    pv = d["components"]["pv"]
    assert pv["max_modules"] == 7 and pv["quantity"] == 7 and pv["size"] == 3.01
    assert pv["range"][1] <= 3.01 and any("roof is the limit" in r for r in pv["reasons"])


def test_roof_sides_and_locked_pv_above_the_cap():
    facts = {"total_demand_kwh": 9000, "roof_width_m": 6.0, "roof_length_m": 3.0, "roof_area_sqm": 500}
    d = post(facts, locks={"pv": {"recommended": True, "size": 12.0}})
    pv = d["components"]["pv"]
    assert pv["max_modules"] == 6 and pv["quantity"] == 6 and pv["size"] == 2.58 and pv["locked"]
    assert "cut to" in pv["reasons"][0]
    assert post({"total_demand_kwh": 9000})["components"]["pv"].get("max_modules") is None


def test_roof_without_room_says_so():
    d = post({"total_demand_kwh": 4500, "roof_width_m": 1, "roof_length_m": 1})
    pv = d["components"]["pv"]
    assert pv["size"] is None and pv["max_modules"] == 0 and "no new PV fits" in pv["reasons"][0]
    assert "existing" not in pv["reasons"][0]


def test_planned_ev_grows_pv_and_adds_wallbox():
    base, ev = post({"total_demand_kwh": 4500}), post({"total_demand_kwh": 4500, "ev_planned": True})
    assert ev["components"]["wallbox"]["recommended"] and ev["components"]["pv"]["size"] > base["components"]["pv"]["size"]
    assert ev["economics"]["total_demand_kwh"] > 4500


def test_existing_pv_size_not_asked_again():
    d = post({"total_demand_kwh": 4500, "existing_pv_kwp": 8})
    assert "has_existing_pv" not in [m["field"] for m in d["missing_inputs"]]
    assert d["components"]["pv"]["size"] is None


def test_invalid_demand_is_422():
    assert client.post("/design", json={"facts": {"total_demand_kwh": -5}}).status_code == 422


def test_heating_comparison_gas_and_electric():
    hc = post({"total_demand_kwh": 4500, "heating_type": "gas", "heating_demand_kwh": 18000})["heating_comparison"]
    assert hc["heat_kwh"] == 18000 and hc["energy_factor"] == round(3.3 / 0.9, 1)
    assert hc["cost_now_eur_per_year"] == 2400 and abs(hc["cost_factor"] - 2400 / hc["cost_heatpump_eur_per_year"]) < 0.02
    assert hc["co2_now_kg_per_year"] == round(18000 / 0.9 * 0.201) and 0 < hc["co2_reduction_pct"] < 100
    assert post({"total_demand_kwh": 4500, "heating_type": "electric"})["heating_comparison"] is None
    assert post({"total_demand_kwh": 4500})["heating_comparison"] is None


def test_heating_comparison_without_official_co2_factor():
    hc = post({"total_demand_kwh": 4500, "heating_type": "district", "heating_demand_kwh": 18000})["heating_comparison"]
    assert hc["cost_factor"] > 1 and hc["co2_reduction_pct"] is None


def test_heatpump_cheaper_flag_follows_prices():
    f = {"total_demand_kwh": 4500, "heating_type": "gas", "heating_demand_kwh": 18000}
    assert post(f)["heating_comparison"]["heatpump_cheaper"] is True
    hc = post({**f, "electricity_price_eur_per_kwh": 0.60})["heating_comparison"]
    assert hc["heatpump_cheaper"] is False and hc["cost_factor"] < 1


def test_price_range_uses_typical_band_not_extremes():
    d = post({"total_demand_kwh": 4500, "region": "BY", "roof_orientation_deg": 180, "heating_type": "electric",
              "electricity_price_eur_per_kwh": 0.32, "has_existing_pv": False, "has_ev": False, "roof_area_sqm": 80})
    lo, hi = d["price"]["range_eur"]
    assert lo < d["price"]["total_eur"] < hi and hi / lo < 1.35        # only the price-list spread is left: half of the sourced min-max
    assert post({"total_demand_kwh": 4500})["price"]["range_eur"][1] / post({"total_demand_kwh": 4500})["price"]["range_eur"][0] < 1.6
    fixed = post({"total_demand_kwh": 4500}, prices={"module_eur": 93})["price"]["range_eur"]
    assert fixed[0] < fixed[1]
