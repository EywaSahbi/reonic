"""PIN and real admission rejections, with fake engine and no paid model calls."""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api
import demo_guard as guard
import engine
from test_api import fake_design

PIN = {"X-Demo-Pin": "test-demo"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    guard.reset()
    monkeypatch.setenv("REO_DEMO_PIN", "test-demo")
    monkeypatch.delenv("REO_INSTALLER_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(api, "STORE", tmp_path / "plans.json")
    monkeypatch.setattr(engine, "design", fake_design)
    monkeypatch.setattr(engine, "healthy", lambda: True)
    with TestClient(api.app) as c:
        yield c
    guard.reset()


def test_pin_and_attempt_throttle(client):
    assert client.get("/health").json()["demo_auth_required"] is True
    for _ in range(5):
        assert client.get("/demo/access").status_code == 401
    rejected = client.get("/demo/access", headers={"X-Demo-Pin": "wrong"})
    assert rejected.status_code == 429 and rejected.headers["retry-after"] == "60"
    assert client.get("/demo/access", headers=PIN).status_code == 200
    assert client.post("/sessions", json={}).status_code == 429


def test_pin_and_planner_token_are_independent(client, monkeypatch):
    monkeypatch.setenv("REO_INSTALLER_TOKEN", "planner-secret")
    assert client.get("/plans", headers=PIN).status_code == 401
    assert client.get("/plans", headers={"Authorization": "Bearer planner-secret"}).status_code == 401
    assert client.get("/plans", headers={**PIN, "Authorization": "Bearer planner-secret"}).status_code == 200
    r = client.get("/demo/access", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 401 and r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "Retry-After" in r.headers["access-control-expose-headers"]
    assert client.options("/sessions", headers={"Origin":"http://localhost:5173", "Access-Control-Request-Method":"POST", "Access-Control-Request-Headers":"x-demo-pin"}).status_code == 200


def test_active_sessions_and_idle_expiry(client, monkeypatch):
    monkeypatch.setenv("REO_MAX_ACTIVE_SESSIONS", "2")
    monkeypatch.setenv("REO_SESSION_IDLE_SECONDS", "10")
    clock = [100.0]
    monkeypatch.setattr(guard, "clock", lambda: clock[0])
    first = client.post("/sessions", json={}, headers=PIN).json()["plan"]["id"]
    assert client.post("/sessions", json={}, headers=PIN).status_code == 200
    blocked = client.post("/sessions", json={}, headers=PIN)
    assert blocked.status_code == 429 and blocked.headers["retry-after"] == "30"
    assert client.get(f"/sessions/{first}", headers=PIN).status_code == 200
    clock[0] += 11
    assert client.post("/sessions", json={}, headers=PIN).status_code == 200
    assert len(guard._sessions) == 1


def test_invalid_session_and_failed_creation_release_slot(client, monkeypatch):
    monkeypatch.setenv("REO_MAX_ACTIVE_SESSIONS", "1")
    assert client.get("/sessions/not-real", headers=PIN).status_code == 404
    assert not guard._sessions
    def fail(*a, **k):
        raise RuntimeError("simulated engine failure")
    monkeypatch.setattr(engine, "design", fail)
    with pytest.raises(RuntimeError):
        client.post("/sessions", json={}, headers=PIN)
    assert not guard._sessions
    monkeypatch.setattr(engine, "design", fake_design)
    assert client.post("/sessions", json={}, headers=PIN).status_code == 200


def test_mutation_limit_rejects_instead_of_queueing(client, monkeypatch):
    monkeypatch.setenv("REO_MAX_CONCURRENT_MUTATIONS", "1")
    entered, release = threading.Event(), threading.Event()
    def blocked(*a, **k):
        entered.set()
        assert release.wait(5)
        return fake_design(*a, **k)
    monkeypatch.setattr(engine, "design", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        work = pool.submit(lambda: client.post("/sessions", json={}, headers=PIN))
        try:
            assert entered.wait(3)
            assert client.post("/sessions", json={}, headers=PIN).status_code == 429
        finally:
            release.set()
        assert work.result().status_code == 200
    assert guard._mutations == guard._inflight == 0


def test_agent_run_budget_and_release(client, monkeypatch):
    monkeypatch.setenv("REO_MAX_CONCURRENT_RUNS", "2")
    leases = [guard.reserve_run(), guard.reserve_run()]
    with pytest.raises(HTTPException) as exc:
        guard.reserve_run()
    assert exc.value.status_code == 429
    leases[0].release()
    next_lease = guard.reserve_run()
    next_lease.release()
    for lease in leases:
        lease.release()
    assert guard._runs == 0


def test_request_and_body_bounds(client, monkeypatch):
    monkeypatch.setenv("REO_MAX_BODY_BYTES", "128")
    assert client.post("/sessions", content=b"x"*129, headers={**PIN,"Content-Type":"application/json"}).status_code == 413
    def chunks():
        yield b"x"*80
        yield b"x"*80
    assert client.post("/sessions", content=chunks(), headers={**PIN,"Content-Type":"application/json"}).status_code == 413
    monkeypatch.setenv("REO_MAX_REQUESTS_PER_MINUTE", "1")
    guard.reset()
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 429


def test_busy_handoff_does_not_change_customer_plan(client):
    pid = client.post("/sessions", json={}, headers=PIN).json()["plan"]["id"]
    leases = [guard.reserve_run(), guard.reserve_run()]
    try:
        response = client.post(f"/sessions/{pid}/handoff", json={"name":"Capacity test"}, headers=PIN)
        assert response.status_code == 429
        assert client.get(f"/sessions/{pid}", headers=PIN).json()["status"] == "drafting"
    finally:
        for lease in leases:
            lease.release()


def test_runner_exception_releases_capacity(client, monkeypatch):
    from harness.runner import Runner, RUNS
    from harness.skills import OFFER_PREP
    from harness.tools import Ctx
    runner = Runner(OFFER_PREP, Ctx({"id":"capacity-failure", "facts":{}}, {"locks":{}, "prices":{}}, []), "test")
    def fail():
        raise RuntimeError("simulated runner failure")
    monkeypatch.setattr(runner, "_go", fail)
    with pytest.raises(RuntimeError):
        runner.go()
    assert guard._runs == 0
    RUNS.pop(runner.run["id"], None)


def test_total_inflight_limit(client, monkeypatch):
    monkeypatch.setenv("REO_MAX_INFLIGHT_REQUESTS", "1")
    entered, release = threading.Event(), threading.Event()
    def blocked_health():
        entered.set()
        assert release.wait(5)
        return True
    monkeypatch.setattr(engine, "healthy", blocked_health)
    with ThreadPoolExecutor(max_workers=1) as pool:
        work = pool.submit(lambda: client.get("/health"))
        try:
            assert entered.wait(3)
            assert client.get("/demo/access", headers=PIN).status_code == 429
        finally:
            release.set()
        assert work.result().status_code == 200
    assert guard._inflight == 0
