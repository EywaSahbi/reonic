"""Deployment guard: planner token on installer routes, customer routes open, CORS on 401s."""
from test_harness import setup

ORIGIN = "http://localhost:5173"


def test_installer_routes_need_the_planner_token(tmp_path, monkeypatch):
    c, pid, p = setup(tmp_path, monkeypatch)
    monkeypatch.setenv("REO_INSTALLER_TOKEN", "s3cret")
    ok = {"Authorization": "Bearer s3cret", "Origin": ORIGIN}
    for path in ["/plans", f"/plans/{pid}", f"/runs/{p['offer_pack']['run_id']}", f"/plans/{pid}/runs", "/calendar/slots"]:
        r = c.get(path, headers={"Origin": ORIGIN})
        assert r.status_code == 401 and r.headers.get("access-control-allow-origin") == ORIGIN, path  # app can read the 401
        assert c.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401, path
        assert c.get(path, headers=ok).status_code == 200, path
    assert c.post(f"/plans/{pid}/finalize", json={}).status_code == 401  # nothing runs without the token
    sse = c.get(f"/runs/{p['offer_pack']['run_id']}/events", headers=ok)
    assert sse.status_code == 200 and "event: done" in sse.text
    pre = c.options("/plans", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET",
                                       "Access-Control-Request-Headers": "authorization"})
    assert pre.status_code == 200  # CORS preflight carries no token
    assert c.get(f"/sessions/{pid}").status_code == 200 and c.get("/health").status_code == 200  # customer side open
    assert c.get("/plansXYZ").status_code == 404  # prefix match is per path segment


def test_no_token_configured_means_no_check(tmp_path, monkeypatch):
    c, pid, _ = setup(tmp_path, monkeypatch)
    monkeypatch.delenv("REO_INSTALLER_TOKEN", raising=False)
    assert c.get(f"/plans/{pid}").status_code == 200
