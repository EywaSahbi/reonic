"""Installer journey: state consistency and failure recovery (fake engine, scripted mode, no API key)."""
import time

import api
import engine
from harness.runner import RUNS
from test_harness import setup


def _quote(p):
    return next(a for a in p["offer_pack"]["actions"] if a["kind"] == "send_quote")


def _wait(c, pid):
    for _ in range(200):
        p = c.get(f"/plans/{pid}").json()
        if p["offer_pack"]["status"] != "preparing":
            return p
        time.sleep(0.05)
    return p


def test_customer_never_sees_offer_pack_or_planner_working_copy(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    handed = c.get(f"/sessions/{pid}").json()
    assert "offer_pack" not in handed
    c.post(f"/plans/{pid}/edit", json={"locks": {"battery": {"recommended": True, "size": 12}}})
    s = c.get(f"/sessions/{pid}").json()  # planner still working: customer keeps the design they handed over
    assert s["design"]["components"]["battery"]["size"] == handed["design"]["components"]["battery"]["size"]
    c.post(f"/plans/{pid}/actions/{_quote(p)['id']}/approve", json={})
    s = c.get(f"/sessions/{pid}").json()  # once quoted: the confirmed design
    assert s["status"] == "quoted" and s["design"]["components"]["battery"]["size"] == 12


def test_quote_keeps_planner_edits_and_message_matches(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    p = c.post(f"/plans/{pid}/edit", json={"locks": {"battery": {"recommended": True, "size": 12}}}).json()
    assert "12 kWh battery" in p["offer_pack"]["customer_message_draft"]  # draft follows the edit
    assert all(v["stale"] for v in p["offer_pack"]["variants"])
    p = c.post(f"/plans/{pid}/actions/{_quote(p)['id']}/approve", json={}).json()
    assert p["design"]["components"]["battery"]["size"] == 12  # not reset to the proposed Recommended variant
    msg = p["transcript"][-1]["text"]
    assert "12 kWh battery" in msg and f"{p['design']['price']['total_eur']:,.0f}" in msg


def test_quoted_plan_is_frozen(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    c.post(f"/plans/{pid}/finalize", json={})
    assert c.post(f"/plans/{pid}/actions/{_quote(p)['id']}/approve", json={}).status_code == 409  # closed by finalize
    assert c.post(f"/plans/{pid}/finalize", json={}).status_code == 409
    assert c.post(f"/plans/{pid}/edit", json={"facts": {"roof_area_sqm": 30}}).status_code == 409
    assert c.post(f"/plans/{pid}/variant", json={"name": "Basic"}).status_code == 409
    assert c.post(f"/plans/{pid}/prepare", json={}).status_code == 409
    total = c.get(f"/plans/{pid}").json()["design"]["price"]["total_eur"]
    t = c.post(f"/sessions/{pid}/messages", json={"text": "we use about 6,000 kWh a year"}).json()
    assert t["plan"]["facts"]["total_demand_kwh"] == 4500 and t["plan"]["design"]["price"]["total_eur"] == total
    assert "can't change it" in t["messages"][0]["text"] and "ask" not in t
    p = c.post(f"/sessions/{pid}/handoff", json={"name": "Anna"}).json()  # repeated handoff: no reopen
    assert p["status"] == "quoted"
    confirmations = [m for m in p["transcript"] if "confirmed your plan" in m["text"]]
    assert len(confirmations) == 1


def test_booked_slot_reaches_the_quote_message(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    visit = next(a for a in p["offer_pack"]["actions"] if a["kind"] == "book_visit")
    slot = c.get("/calendar/slots").json()["slots"][1]
    p = c.post(f"/plans/{pid}/actions/{visit['id']}/approve", json={"payload": {"slot": slot}}).json()
    draft = p["offer_pack"]["customer_message_draft"]
    assert f"booked for {slot}" in draft and visit["payload"]["slot"] not in draft
    assert _quote(p)["payload"]["message"] == draft


def test_choosing_a_stale_variant_refreshes_it(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    c.post(f"/plans/{pid}/edit", json={"facts": {"ev_planned": True}})
    p = c.post(f"/plans/{pid}/variant", json={"name": "Recommended"}).json()
    v = next(x for x in p["offer_pack"]["variants"] if x["name"] == "Recommended")
    assert not v.get("stale") and v["design"] == p["design"]
    assert p["offer_pack"]["draft_for"] == "Recommended"


def test_edit_during_preparation_marks_variants_stale(tmp_path, monkeypatch):
    c, pid, _ = setup(tmp_path, monkeypatch)
    fast = engine.design
    monkeypatch.setattr(engine, "design", lambda *a, **k: (time.sleep(0.05), fast(*a, **k))[1])
    c.post(f"/plans/{pid}/prepare", json={})
    c.post(f"/plans/{pid}/edit", json={"locks": {"battery": {"recommended": True, "size": 12}}})
    p = _wait(c, pid)
    assert p["offer_pack"]["status"] == "ready" and all(v["stale"] for v in p["offer_pack"]["variants"])
    assert "12 kWh battery" in p["offer_pack"]["customer_message_draft"]


def test_superseded_run_does_not_overwrite_newer_pack(tmp_path, monkeypatch):
    c, pid, _ = setup(tmp_path, monkeypatch)
    started = []
    monkeypatch.setattr(api.threading, "Thread", lambda target, args, daemon: type("T", (), {"start": lambda s: started.append(args)})())
    old = api.start_offer_prep(pid, "prepare")
    new = api.start_offer_prep(pid, "prepare")
    api._finish_offer(*started[1])
    api._finish_offer(*started[0])  # the older run finishes last
    p = c.get(f"/plans/{pid}").json()
    assert p["offer_pack"]["run_id"] == new and p["offer_pack"]["status"] == "ready"
    assert c.get(f"/runs/{old}").json()["status"] != "running"


def test_restart_during_preparation_recovers(tmp_path, monkeypatch):
    c, pid, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(api.threading, "Thread", lambda **k: type("T", (), {"start": lambda s: None})())
    rid = api.start_offer_prep(pid, "prepare")
    RUNS.pop(rid)  # process restarted: the live run is gone
    assert c.get(f"/plans/{pid}").json()["offer_pack"]["status"] == "failed"
    run = c.get(f"/runs/{rid}").json()
    assert run["status"] == "failed" and run["steps"][-1]["args_summary"] == "interrupted"
    assert "event: done" in c.get(f"/runs/{rid}/events").text
    c.post(f"/plans/{pid}/prepare", json={})  # recovery path: prepare again works


def test_non_positive_inputs_never_reach_the_engine(tmp_path, monkeypatch):
    """engine 11f5a6a answers 422 for demand/roof <= 0; reo must not send them (a 422 would read as 'engine down')."""
    c, pid, _ = setup(tmp_path, monkeypatch)
    assert c.post(f"/plans/{pid}/edit", json={"facts": {"roof_area_sqm": 0}}).status_code == 422
    sid = c.post("/sessions", json={}).json()["plan"]["id"]
    t = c.post(f"/sessions/{sid}/facts", json={"facts": {"roof_width_m": 0, "roof_length_m": 6}}).json()
    assert "roof_width_m" not in t["plan"]["facts"] and t["plan"]["design"]["params_version"] != engine.OFFLINE


def test_engine_down_quote_not_sent(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(engine, "design", lambda *a, **k: None)
    r = c.post(f"/plans/{pid}/actions/{_quote(p)['id']}/approve", json={})
    assert r.status_code == 503
    p = c.get(f"/plans/{pid}").json()
    assert p["status"] == "handed_over" and _quote(p)["status"] == "proposed"


def test_delete_plan(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    rid = p["offer_pack"]["run_id"]
    assert c.delete(f"/plans/{pid}").json() == {"deleted": pid}
    assert pid not in [x["id"] for x in c.get("/plans").json()]
    assert c.get(f"/plans/{pid}").status_code == 404 and c.get(f"/sessions/{pid}").status_code == 404
    assert c.get(f"/runs/{rid}").status_code == 404
    assert c.delete(f"/plans/{pid}").status_code == 404
