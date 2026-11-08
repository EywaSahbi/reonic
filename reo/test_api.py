"""End-to-end through the API with a fake engine and no API key (scripted mode)."""
from fastapi.testclient import TestClient

import api
import engine
import evidence


def fake_design(facts, locks=None, prices=None):
    """Test double for the engine; numbers here are fixtures, not real sizing."""
    ev = facts.get("has_ev") or facts.get("ev_planned")
    pv = 10.5 if ev else 8.2
    locks = locks or {}
    bat = locks.get("battery", {}).get("size", 10)
    hp = (locks.get("heatpump") or {}).get("recommended", False)
    comp = lambda rec, size, unit, why: {"recommended": rec, "size": size if rec else None, "unit": unit, "range": None,
                                         "confidence": "medium", "locked": False, "reasons": [why]}
    total = 18900 + (3000 if ev else 0) + (bat - 10) * 900 + (20000 if hp else 0)
    return {"components": {"pv": comp(True, pv, "kWp", "demand"), "battery": comp(True, bat, "kWh", "evening use"),
                           "heatpump": comp(hp, 8, "kW", "heating unknown"), "wallbox": comp(bool(ev), 11, "kW", "EV")},
            "price": {"items": [{"label": "PV modules", "qty": 20, "unit": "pc", "unit_price_eur": 300, "total_eur": 6000}],
                      "total_eur": total, "range_eur": [total - 1800, total + 1900]},
            "economics": {"total_demand_kwh": 4500, "self_consumption_pct": 60, "autarky_pct": 70,
                          "annual_savings_eur": 1243, "payback_years": 11},
            "heating_comparison": {"fuel": "gas", "energy_factor": 3.7, "cost_now_eur_per_year": 3004, "cost_heatpump_eur_per_year": 2182,
                                   "cost_factor": 1.38, "heatpump_cheaper": True, "co2_now_kg_per_year": 5025,
                                   "co2_heatpump_kg_per_year": 2345, "co2_reduction_pct": 53.3, "note": None}
            if facts.get("heating_type") == "gas" else None,
            "assumptions": [], "missing_inputs": [{"field": "heating_type", "why": "", "impact": "high"}]
            if not facts.get("heating_type") else [], "params_version": "test"}


def fake_explain(facts, component, locks=None, prices=None):
    return {"reasons": [], "what_if": [{"change": "add heat pump", "effect": "", "locks": {},
                                         "delta": {"price_eur": 20000, "annual_savings_eur": 300, "payback_years": 1, "autarky_pct": 0,
                                                   "bill_after_eur_per_month": 0}}]}


def client(tmp_path, monkeypatch, engine_up=True):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(api, "STORE", tmp_path / "plans.json")
    monkeypatch.setattr(engine, "explain", fake_explain)
    monkeypatch.setattr(engine, "design", fake_design if engine_up else (lambda *a, **k: None))
    return TestClient(api.app)


def test_demo_flow(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    t = c.post("/sessions", json={}).json()
    pid = t["plan"]["id"]
    assert t["ask"]["field"] == "total_demand_kwh" and "Skip" in t["suggestions"]

    t = c.post(f"/sessions/{pid}/messages", json={"text": "we use about 4,500 kWh a year"}).json()
    assert t["plan"]["facts"]["total_demand_kwh"] == 4500
    assert "8 kWp" in t["messages"][0]["text"] and "estimate" in t["messages"][0]["text"]
    assert "For your home, I'd suggest" in t["messages"][0]["text"]
    assert t["ask"]["field"] == "roof_area_sqm" and t["ask"]["input"] == "address"  # location right after kWh

    t = c.post(f"/sessions/{pid}/messages", json={"text": "Skip"}).json()
    assert t["ask"]["field"] == "region"
    t = c.post(f"/sessions/{pid}/messages", json={"text": "BY"}).json()  # state given: no dimensions
    assert t["plan"]["facts"]["region"] == "BY" and t["ask"]["field"] == "has_ev"

    t = c.post(f"/sessions/{pid}/messages", json={"text": "we're buying an electric car next year"}).json()
    assert t["plan"]["facts"]["ev_planned"] is True
    assert "added a wallbox" in t["messages"][0]["text"]
    assert t["ask"]["field"] == "heating_type"

    t = c.post(f"/sessions/{pid}/messages", json={"text": "Gas"}).json()  # chip
    assert t["plan"]["facts"]["heating_type"] == "gas"
    assert "heat pump" in t["messages"][0]["text"] and "€2,180" in t["messages"][0]["text"]  # engine's heating_comparison
    assert "still stands" in t["messages"][0]["text"] and "€20,000 more" in t["messages"][0]["text"]
    assert t["ask"]["field"] == "heatpump_option" and not t["plan"]["design"]["components"]["heatpump"]["recommended"]
    assert t["heatpump_option"]["with"]["components"]["heatpump"]["recommended"] and "heatpump_option" not in t["plan"]["facts"]

    t = c.post(f"/sessions/{pid}/messages", json={"text": "No, keep my plan"}).json()   # chip
    assert "without a heat pump" in t["messages"][0]["text"] and not t["plan"]["design"]["components"]["heatpump"]["recommended"]
    assert t["ask"]["field"] == "has_existing_pv" and "heatpump_option" not in t

    t = c.post(f"/sessions/{pid}/messages", json={"text": "No solar yet"}).json()  # chip
    assert t["plan"]["facts"]["has_existing_pv"] is False
    assert t["suggestions"][0] == "Yes, send it"  # heating + EV + existing solar known -> offer the handoff once

    t = c.post(f"/sessions/{pid}/messages", json={"text": "Not yet"}).json()
    assert "only here to help" not in t["messages"][0]["text"]

    t = c.post(f"/sessions/{pid}/messages", json={"text": "why a battery?"}).json()
    assert "evening use" in t["messages"][0]["text"]

    p = c.post(f"/sessions/{pid}/handoff", json={"name": "Anna"}).json()
    assert p["status"] == "handed_over" and "summary" in p
    assert [x["id"] for x in c.get("/plans?status=handed_over").json()] == [pid]
    assert "similar_projects" not in c.get(f"/plans/{pid}").json()  # individual homes are never served

    p = c.post(f"/plans/{pid}/edit", json={"locks": {"battery": {"recommended": True, "size": 12}}}).json()
    assert p["design"]["components"]["battery"]["size"] == 12
    p = c.post(f"/plans/{pid}/edit", json={"facts": {"roof_area_sqm": 50}}).json()
    assert p["design"]["components"]["battery"]["size"] == 12  # lock persisted
    assert len(p["installer_edits"]) == 2

    p = c.post(f"/plans/{pid}/finalize", json={"note": "See you Tuesday."}).json()
    assert p["status"] == "quoted" and "confirmed by Sonnfeld" in p["transcript"][-1]["text"]


def test_engine_down_never_invents_numbers(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, engine_up=False)
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{pid}/messages", json={"text": "we use about 4,500 kWh a year"}).json()
    assert "can't give you numbers" in t["messages"][0]["text"]
    assert t["plan"]["design"]["params_version"] == engine.OFFLINE
    assert c.post(f"/plans/{pid}/edit", json={"facts": {"roof_area_sqm": 50}}).status_code == 503


def test_voice_turn(tmp_path, monkeypatch):
    import voice
    c = client(tmp_path, monkeypatch)
    monkeypatch.setattr(voice, "transcribe", lambda audio, *a: "we use about 4,500 kWh a year" if audio else None)
    monkeypatch.setattr(voice, "speak", lambda text: b"mp3")
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{pid}/voice", files={"audio": ("a.webm", b"xx", "audio/webm")}).json()
    assert t["heard"].startswith("we use") and t["plan"]["facts"]["total_demand_kwh"] == 4500 and t["audio"] == "bXAz"
    t = c.post(f"/sessions/{pid}/voice", files={"audio": ("a.webm", b"", "audio/webm")}).json()
    assert t["heard"] == "" and "didn't catch" in t["messages"][0]["text"]


def test_articles():
    import scripted
    assert [scripted.a_n(n) for n in ["8", "11", "18", "80", "10", "12", "1"]] == ["an", "an", "an", "an", "a", "a", "a"]


def test_address_lookup(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{pid}/address", json={"address": "Musterstraße 12, München"}).json()
    assert t["plan"]["facts"]["roof_area_sqm"] == 48 and t["plan"]["facts"]["region"] == "BY"
    assert t["messages"][0]["text"].startswith("I looked up your address")
    t = c.post(f"/sessions/{pid}/address", json={"address": "Irgendwo 1"}).json()
    assert t["ask"]["field"] == "roof_dims"


def test_address_typed_or_spoken_in_the_chat(tmp_path, monkeypatch):
    import voice
    c = client(tmp_path, monkeypatch)
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{pid}/messages", json={"text": "4500"}).json()
    assert t["ask"]["input"] == "address"
    t = c.post(f"/sessions/{pid}/messages", json={"text": "Musterstraße 12, 80331 München"}).json()  # no address box
    assert t["plan"]["facts"]["roof_area_sqm"] == 48 and t["roof"]["source"] == "demo data"
    assert t["messages"][0]["text"].startswith("I looked up your address")
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    c.post(f"/sessions/{pid}/messages", json={"text": "4500"})
    monkeypatch.setattr(voice, "transcribe", lambda *a: "Musterstraße 12 in München")
    monkeypatch.setattr(voice, "speak", lambda text: None)
    t = c.post(f"/sessions/{pid}/voice", files={"audio": ("a.webm", b"xx", "audio/webm")}).json()
    assert t["plan"]["facts"]["roof_area_sqm"] == 48 and t["heard"].startswith("Musterstraße")


def test_looks_like_address():
    import scripted
    yes = ["Musterstraße 12, 80331 München", "Platz der Republik 1, Berlin", "Hauptstr. 5", "10557 Berlin",
           "Am Lindenhof 3, Dresden"]
    no = ["4500", "Skip", "15000 kWh", "the roof is 10 x 5.5 m", "about 50 m²", "why a battery?", "we have 4 people"]
    assert all(scripted.looks_like_address(s) for s in yes) and not any(scripted.looks_like_address(s) for s in no)


def test_roof_by_dimensions_and_skip(tmp_path, monkeypatch):
    import roof
    c = client(tmp_path, monkeypatch)
    monkeypatch.setattr(roof, "lookup", lambda a: None)  # building not on the map
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{pid}/address", json={"address": "Unbekannt 1"}).json()
    assert t["ask"]["input"] == "dimensions" and t["suggestions"] == ["Skip"]
    t = c.post(f"/sessions/{pid}/facts", json={"facts": {"roof_width_m": 8, "roof_length_m": 6}}).json()
    assert t["plan"]["facts"]["roof_area_sqm"] == 48  # width x length, the engine fits modules from the sides
    t = c.post(f"/sessions/{pid}/messages", json={"text": "the roof is 10 x 5.5 m"}).json()
    assert t["plan"]["facts"]["roof_area_sqm"] == 55
    pid2 = c.post("/sessions", json={}).json()["plan"]["id"]
    c.post(f"/sessions/{pid2}/address", json={"address": "Unbekannt 1"})
    t = c.post(f"/sessions/{pid2}/messages", json={"text": "Skip"}).json()
    assert "roof_area_sqm" not in t["plan"]["facts"] and (t.get("ask") or {}).get("field") not in ("roof_area_sqm", "roof_dims")


def test_roof_geometry():
    import roof
    assert abs(roof.area_sqm([(0, 0), (0, 0.0001), (0.0001, 0.0001), (0.0001, 0)]) - 123.6) < 1
    assert roof.sunny_area(100, "flat") == 100 and round(roof.sunny_area(100, "gable")) == 61 and round(roof.sunny_area(100, "mono")) == 122


def test_kwh_skip_goes_through_people_then_state_then_dimensions(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    say = lambda text: c.post(f"/sessions/{pid}/messages", json={"text": text}).json()
    assert say("Skip")["ask"]["field"] == "num_inhabitants"
    t = say("3")
    assert t["plan"]["facts"]["num_inhabitants"] == 3 and t["ask"]["field"] == "roof_area_sqm"
    assert say("Skip")["ask"]["field"] == "region"
    t = say("Skip")
    assert t["ask"]["field"] == "roof_dims" and t["ask"]["input"] == "dimensions"
    t = say("Skip")
    assert t["ask"]["field"] == "has_ev"                                       # nothing known about the roof: assumed, on to EV
    assert say("No")["ask"]["field"] == "heating_type"
    t = say("electric")
    assert "heat pump would be worth" not in t["messages"][0]["text"] and t["ask"]["field"] == "has_existing_pv"


def test_address_sets_roof_location_for_the_satellite_view(tmp_path, monkeypatch):
    import roof
    c = client(tmp_path, monkeypatch)
    hit = {"label": "Teststraße 1, 01069 Dresden", "facts": {"roof_area_sqm": 40}, "say": "about 40 m²", "source": "OpenStreetMap",
           "footprint_sqm": 65.0, "lat": 51.05, "lon": 13.74, "outline": [[51.05, 13.74], [51.0501, 13.74], [51.0501, 13.7402]]}
    monkeypatch.setattr(roof, "lookup", lambda a: hit if a.startswith("Test") else None)
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{pid}/address", json={"address": "Teststraße 1, 01069 Dresden"}).json()
    assert t["plan"]["roof_location"] == {"label": hit["label"], "lat": 51.05, "lon": 13.74, "outline": hit["outline"]}
    t = c.post(f"/sessions/{pid}/address", json={"address": "Nirgendwo 9"}).json()
    assert "roof_location" not in t["plan"]  # a new address without a building: back to the drawn house


def test_plan_builds_up_with_the_answers():
    from api import reveal_locks
    off = {"recommended": False}
    assert reveal_locks({}, set()) == {"pv": off, "battery": off, "wallbox": off, "heatpump": off}
    assert reveal_locks({"total_demand_kwh": 4500}, set()) == {"wallbox": off, "heatpump": off}
    assert reveal_locks({}, {"total_demand_kwh", "num_inhabitants"}) == {"wallbox": off, "heatpump": off}  # both skipped
    assert reveal_locks({"num_inhabitants": 3, "ev_planned": True, "heating_type": "gas"}, set()) == {}


def test_customer_engine_calls_carry_the_reveal_locks(tmp_path, monkeypatch):
    seen = []
    c = client(tmp_path, monkeypatch)
    monkeypatch.setattr(engine, "design", lambda f, locks=None, prices=None: seen.append(dict(locks or {})) or fake_design(f, locks, prices))
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    assert set(seen[-1]) == {"pv", "battery", "wallbox", "heatpump"}  # empty house, no price
    first = c.get(f"/sessions/{pid}").json()["design"]["components"]
    assert "electricity use" in first["pv"]["reasons"][0] and "installer" not in first["wallbox"]["reasons"][0]
    c.post(f"/sessions/{pid}/messages", json={"text": "we use about 4,500 kWh a year"})
    assert set(seen[-1]) == {"wallbox", "heatpump"}


def test_heatpump_option_yes_by_typing_and_by_tap(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    for answer in (lambda pid: c.post(f"/sessions/{pid}/messages", json={"text": "yes please"}).json(),
                   lambda pid: c.post(f"/sessions/{pid}/facts", json={"facts": {"heatpump_option": True}}).json()):
        pid = c.post("/sessions", json={}).json()["plan"]["id"]
        c.post(f"/sessions/{pid}/facts", json={"facts": {"total_demand_kwh": 4500, "roof_area_sqm": 50, "has_ev": False, "heating_type": "gas"}})
        t = c.post(f"/sessions/{pid}/messages", json={"text": "hi"}).json()
        assert t["ask"]["field"] == "heatpump_option"
        t = answer(pid)
        assert t["plan"]["design"]["components"]["heatpump"]["recommended"] and "now includes the heat pump" in t["messages"][0]["text"]
        assert "heatpump_option" not in t["plan"]["facts"] and t["ask"]["field"] == "has_existing_pv"


def test_electric_heating_has_no_heatpump_step(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{pid}/facts", json={"facts": {"total_demand_kwh": 4500, "roof_area_sqm": 50, "has_ev": False, "heating_type": "electric"}}).json()
    assert t["ask"]["field"] == "has_existing_pv" and "heatpump_option" not in t
