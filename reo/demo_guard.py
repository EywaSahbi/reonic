"""Single-process admission control for the laptop demo; enabled only with REO_DEMO_PIN.

Caps reject work rather than queueing it. State is bounded, in memory, and resets on restart.
Keep one uvicorn worker; this is not a distributed limiter.
"""
import hmac
import os
import re
import threading
import time
from collections import deque

from fastapi import HTTPException
from starlette.responses import JSONResponse

clock = time.monotonic
_lock = threading.Lock()
_sessions: dict[str, float] = {}
_requests = deque()
_failures = deque()
_inflight = 0
_mutations = 0
_runs = 0


def enabled():
    return bool(os.getenv("REO_DEMO_PIN", ""))


def setting(name, default):
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def limits():
    return {"max_active_sessions": setting("REO_MAX_ACTIVE_SESSIONS", 5),
            "session_idle_seconds": setting("REO_SESSION_IDLE_SECONDS", 900),
            "max_concurrent_runs": setting("REO_MAX_CONCURRENT_RUNS", 2),
            "max_inflight_requests": setting("REO_MAX_INFLIGHT_REQUESTS", 12),
            "max_concurrent_mutations": setting("REO_MAX_CONCURRENT_MUTATIONS", 2),
            "max_requests_per_minute": setting("REO_MAX_REQUESTS_PER_MINUTE", 240),
            "max_body_bytes": setting("REO_MAX_BODY_BYTES", 8 * 1024 * 1024)}


def busy(message="demo capacity reached", retry=5):
    return HTTPException(429, message, headers={"Retry-After": str(retry)})


def admit_session(pid):
    if not enabled():
        return False
    now = clock()
    cfg = limits()
    with _lock:
        for key, touched in list(_sessions.items()):
            if now - touched >= cfg["session_idle_seconds"]:
                del _sessions[key]
        new = pid not in _sessions
        if new and len(_sessions) >= cfg["max_active_sessions"]:
            raise busy("demo active-session limit reached", 30)
        _sessions[pid] = now
        return new


def release_session(pid):
    with _lock:
        _sessions.pop(pid, None)


class RunLease:
    def __init__(self, active):
        self.active = active

    def release(self):
        global _runs
        with _lock:
            if self.active:
                self.active = False
                _runs -= 1


def reserve_run():
    global _runs
    if not enabled():
        return RunLease(False)
    with _lock:
        if _runs >= limits()["max_concurrent_runs"]:
            raise busy("demo agent-job limit reached")
        _runs += 1
        return RunLease(True)


def reset():
    """For isolated regression tests; not an HTTP endpoint."""
    global _inflight, _mutations, _runs
    with _lock:
        _sessions.clear()
        _requests.clear()
        _failures.clear()
        _inflight = _mutations = _runs = 0


class DemoGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        global _inflight, _mutations
        if scope["type"] != "http" or not enabled() or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        path, method = scope["path"], scope["method"]
        client = (scope.get("client") or ("unknown",))[0]
        now, cfg = clock(), limits()
        admitted = mutation = False
        pid, new_session = None, False
        status = 500
        try:
            # Throttle all requests, including public health and invalid-PIN attempts.
            with _lock:
                while _requests and now - _requests[0] >= 60:
                    _requests.popleft()
                if len(_requests) >= cfg["max_requests_per_minute"]:
                    raise busy("demo request-rate limit reached", 60)
                _requests.append(now)
            if path != "/health":
                pin = os.getenv("REO_DEMO_PIN", "")
                sent = headers.get("x-demo-pin", "")
                if not hmac.compare_digest(sent.encode(), pin.encode()):
                    with _lock:
                        while _failures and now - _failures[0][0] >= 60:
                            _failures.popleft()
                        if len(_failures) >= 12 or sum(ip == client for _, ip in _failures) >= 5:
                            raise busy("too many demo PIN attempts", 60)
                        _failures.append((now, client))
                    raise HTTPException(401, "demo PIN required")
            with _lock:
                if _inflight >= cfg["max_inflight_requests"]:
                    raise busy()
                if method not in ("GET", "HEAD") and _mutations >= cfg["max_concurrent_mutations"]:
                    raise busy("demo busy processing other requests")
                _inflight += 1
                admitted = True
                if method not in ("GET", "HEAD"):
                    _mutations += 1
                    mutation = True
            max_body = cfg["max_body_bytes"] if "multipart/form-data" in headers.get("content-type", "") else min(cfg["max_body_bytes"], 65536)
            try:
                content_length = int(headers.get("content-length", "0"))
            except ValueError:
                raise HTTPException(400, "invalid content length")
            if content_length < 0 or content_length > max_body:
                raise HTTPException(413, "request body too large")
            match = re.match(r"^/sessions/([^/]+)(?:/|$)", path)
            if match:
                pid = match[1]
                new_session = admit_session(pid)
            consumed = 0
            async def bounded_receive():
                nonlocal consumed
                message = await receive()
                if message["type"] == "http.request":
                    consumed += len(message.get("body", b""))
                    if consumed > max_body:
                        raise HTTPException(413, "request body too large")
                return message
            buffered_body = bytearray()
            if mutation:
                while True:
                    message = await bounded_receive()
                    if message["type"] == "http.disconnect":
                        break
                    buffered_body.extend(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
            replayed = False
            async def replay_receive():
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": bytes(buffered_body), "more_body": False}
                return await receive()
            async def tracked_send(message):
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                await send(message)
            await self.app(scope, replay_receive if mutation else bounded_receive, tracked_send)
        except HTTPException as exc:
            status = exc.status_code
            await JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)(scope, receive, send)
        finally:
            if pid and new_session and status >= 400:
                release_session(pid)
            if admitted:
                with _lock:
                    _inflight -= 1
                    if mutation:
                        _mutations -= 1
