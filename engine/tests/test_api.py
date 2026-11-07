import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from api import app  # noqa: E402

client = TestClient(app)


def test_health_and_prices():
    assert client.get("/health").json()["ok"] is True
    assert client.get("/prices").json()["pv_eur_per_kwp"] > 0


def test_empty_facts_give_full_design():
    d = client.post("/design", json={"facts": {}}).json()
    assert set(d["components"]) == {"pv", "battery", "heatpump", "wallbox"}
    assert d["components"]["pv"]["recommended"] and d["components"]["pv"]["range"][0] < d["components"]["pv"]["range"][1]
    assert d["price"]["total_eur"] > 0 and d["missing_inputs"][0]["impact"] == "high"
    assert {"total_demand_kwh", "region", "roof_area_sqm"} <= {m["field"] for m in d["missing_inputs"]}


def test_facts_narrow_the_range():
    d = client.post("/design", json={"facts": {"total_demand_kwh": 7200, "region": "BY", "has_ev": True}}).json()
    pv = d["components"]["pv"]
    assert pv["range"][0] == pv["range"][1] == pv["size"]
    assert d["components"]["wallbox"]["recommended"]


def test_lock_battery_off_rederives_price():
    free = client.post("/design", json={"facts": {"total_demand_kwh": 4500}}).json()
    locked = client.post("/design", json={"facts": {"total_demand_kwh": 4500},
                                          "locks": {"battery": {"recommended": False}}}).json()
    assert locked["components"]["battery"] == {**locked["components"]["battery"], "recommended": False, "locked": True}
    assert locked["price"]["total_eur"] < free["price"]["total_eur"]


def test_price_override():
    d = client.post("/design", json={"facts": {"total_demand_kwh": 4500}, "prices": {"pv_eur_per_kwp": 1000}}).json()
    assert d["price"]["items"][0]["unit_price_eur"] == 1000


def test_bad_input_is_422():
    assert client.post("/design", json={"facts": {"region": "Bayern"}}).status_code == 422


def test_fast_enough():
    t = time.perf_counter()
    client.post("/design", json={"facts": {}})
    assert time.perf_counter() - t < 0.1
