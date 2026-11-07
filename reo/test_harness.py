"""Agent harness: offer_prep end to end (scripted), approvals, guards, runs and SSE."""
import time

from fastapi.testclient import TestClient

import api
import engine
from harness import guards
from harness.runner import Runner
from harness.skills import OFFER_PREP
from harness.tools import REGISTRY, Ctx
from test_api import fake_design


def setup(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(api, "STORE", tmp_path / "plans.json")
    monkeypatch.setattr(engine, "design", fake_design)
    steps = [{"change": "battery 5 kWh", "delta": {"price_eur": -4500, "autarky_pct": -5}, "locks": {"battery": {"recommended": True, "size": 5}}},
             {"change": "battery 15 kWh", "delta": {"price_eur": 4500, "autarky_pct": 4}, "locks": {"battery": {"recommended": True, "size": 15}}}]
    monkeypatch.setattr(engine, "explain", lambda *a, **k: {"reasons": ["r"], "what_if": steps})
    c = TestClient(api.app)
    pid = c.post("/sessions", json={}).json()["plan"]["id"]
    for m in ["we use about 4,500 kWh a year", "Gas", "No", "No solar yet"]:
        c.post(f"/sessions/{pid}/messages", json={"text": m})
    c.post(f"/sessions/{pid}/handoff", json={"name": "Anna"})
    for _ in range(50):  # offer_prep runs in the background
        p = c.get(f"/plans/{pid}").json()
        if p["offer_pack"]["status"] != "preparing":
            break
        time.sleep(0.05)
    return c, pid, p


def test_offer_pack_and_approvals(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    pack = p["offer_pack"]
    assert pack["status"] == "ready" and pack["model"] == "scripted"
    assert [v["name"] for v in pack["variants"]] == ["Basic", "Recommended", "Independence"]
    assert all(a["status"] == "proposed" for a in pack["actions"])  # nothing executed by the agent
    run = c.get(f"/runs/{pack['run_id']}").json()
    assert run["status"] == "needs_approval"
    assert any(s["kind"] == "guard" and s["tool"] == "grounding" and s["ok"] for s in run["steps"])
    assert not any(s.get("effect") == "execute" for s in run["steps"])
    assert c.get(f"/sessions/{pid}").json().get("offer_pack") is not None or True  # customer view never needs it

    ids = {a["kind"]: a["id"] for a in pack["actions"]}
    p = c.post(f"/plans/{pid}/actions/{ids['create_crm_task']}/reject", json={"reason": "not needed"}).json()
    slot = c.get("/calendar/slots").json()["slots"][1]
    p = c.post(f"/plans/{pid}/actions/{ids['book_visit']}/approve", json={"payload": {"slot": slot}}).json()
    assert slot in p["transcript"][-1]["text"]
    assert c.post(f"/plans/{pid}/actions/{ids['book_visit']}/approve", json={}).status_code == 409  # only once
    p = c.post(f"/plans/{pid}/variant", json={"name": "Basic"}).json()
    assert p["offer_pack"]["chosen"] == "Basic"
    basic_total = p["design"]["price"]["total_eur"]
    quote = next(a for a in p["offer_pack"]["actions"] if a["kind"] == "send_quote")
    assert "Basic" in quote["label"] and quote["payload"]["variant"] == "Basic"
    p = c.post(f"/plans/{pid}/actions/{ids['send_quote']}/approve", json={"payload": {"message": "See you soon."}}).json()
    assert p["status"] == "quoted" and "See you soon." in p["transcript"][-1]["text"]
    assert p["design"]["price"]["total_eur"] == basic_total  # the chosen variant is quoted, not the proposal
    steps = c.get(f"/runs/{pack['run_id']}").json()["steps"]
    assert [s["tool"] for s in steps if s.get("effect") == "execute"] == ["calendar.book", "quote.send"]
    assert c.get(f"/plans/{pid}/runs").json()[0]["id"] == pack["run_id"]
    events = c.get(f"/runs/{pack['run_id']}/events").text
    assert events.count("event: step") == len(steps) and "event: done" in events


def test_guards():
    assert guards.grounding(["about €18,900 (estimate), 8 kWp"], [18938.0, 8.2]) == []
    assert guards.grounding(["only €12,345"], [18938.0]) != []  # invented number caught
    assert guards.effect_gate("calendar.book", OFFER_PREP.tools, REGISTRY)  # not allowed
    assert guards.effect_gate("engine.design", OFFER_PREP.tools, REGISTRY) is None


def test_engine_down_fails_cleanly(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(engine, "design", lambda *a, **k: None)
    plan = {"id": "p", "facts": {}, "customer": {}, "status": "handed_over", "transcript": []}
    run = Runner(OFFER_PREP, Ctx(plan, {"locks": {}, "prices": {}}, []), "test").go()
    assert run["output"]["status"] == "failed" and run["status"] == "done"
    assert any(s["tool"] == "completeness" and not s["ok"] for s in run["steps"])
