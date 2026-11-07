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
    comp = lambda rec, size, unit, why: {"recommended": rec, "size": size if rec else None, "unit": unit, "range": None,
                                         "confidence": "medium", "locked": False, "reasons": [why]}
    total = 18900 + (3000 if ev else 0) + (bat - 10) * 900
    return {"components": {"pv": comp(True, pv, "kWp", "demand"), "battery": comp(True, bat, "kWh", "evening use"),
                           "heatpump": comp(False, None, "kW", "heating unknown"), "wallbox": comp(bool(ev), 11, "kW", "EV")},
            "price": {"items": [{"label": "PV modules", "qty": 20, "unit": "pc", "unit_price_eur": 300, "total_eur": 6000}],
                      "total_eur": total, "range_eur": [total - 1800, total + 1900]},
            "economics": {"total_demand_kwh": 4500, "self_consumption_pct": 60, "autarky_pct": 70,
                          "annual_savings_eur": 1243, "payback_years": 11},
            "assumptions": [], "missing_inputs": [{"field": "heating_type", "why": "", "impact": "high"}]
            if not facts.get("heating_type") else [], "params_version": "test"}


def client(tmp_path, monkeypatch, engine_up=True):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(api, "STORE", tmp_path / "plans.json")
    monkeypatch.setattr(engine, "design", fake_design if engine_up else (lambda *a, **k: None))
    return TestClient(api.app)


def test_demo_flow(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    t = c.post("/sessions", json={}).json()
    pid = t["plan"]["id"]
    assert t["ask"]["field"] == "num_inhabitants"

    t = c.post(f"/sessions/{pid}/messages", json={"text": "we use about 4,500 kWh a year"}).json()
    assert t["plan"]["facts"]["total_demand_kwh"] == 4500
    assert "8 kWp" in t["messages"][0]["text"] and "estimate" in t["messages"][0]["text"]
    assert "For your home, I'd suggest" in t["messages"][0]["text"]
    assert t["ask"]["field"] == "heating_type"

    t = c.post(f"/sessions/{pid}/messages", json={"text": "Gas"}).json()  # chip
    assert t["plan"]["facts"]["heating_type"] == "gas"
    assert t["ask"]["field"] == "has_ev"  # EV is always asked, the engine only assumes it

    t = c.post(f"/sessions/{pid}/messages", json={"text": "we're buying an electric car next year"}).json()
    assert t["plan"]["facts"]["ev_planned"] is True
    assert "added a wallbox" in t["messages"][0]["text"]
    assert t["ask"]["field"] == "has_existing_pv"

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
    if evidence.DATA.joinpath("benchmarks.json").exists():  # data published: evidence for the installer only
        assert len(c.get(f"/plans/{pid}").json()["similar_projects"]) == 3
        assert c.get(f"/sessions/{pid}").json()["similar_projects"] == []

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
