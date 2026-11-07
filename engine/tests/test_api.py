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
    assert p["pv_eur_per_kwp_low"] < p["pv_eur_per_kwp"] < p["pv_eur_per_kwp_high"]


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
    assert n[1] - n[0] < w[1] - w[0] and n[0] == n[1]
    assert narrow["components"]["pv"]["confidence"] == "high"
    assert len(narrow["missing_inputs"]) < len(wide["missing_inputs"])


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
    d = post({"total_demand_kwh": 4500}, prices={"pv_eur_per_kwp": 1000})
    assert d["price"]["items"][0]["unit_price_eur"] == 1000


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
