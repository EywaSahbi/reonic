"""reo API (reo/CONTRACT.md) on :8001. The only API the app calls.

Each customer turn: understand the message (chip table, else Claude, else rules) -> engine /design ->
next question (flow.py) -> reply (Claude from the engine result, else template). The engine is called
every turn, so every number shown is from this turn (hard rule 2).

Run:  uv run uvicorn api:app --reload --port 8001
"""
import base64
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

import engine
import evidence
import flow
import llm
import scripted
import voice
from harness import tools as htools
from harness.runner import RUNS, Runner
from harness.skills import SKILLS

HERE = Path(__file__).parent
STORE = Path(os.getenv("REO_STORE", HERE / "plans.json"))  # shortcut: one JSON file, fine for a demo
REPORTS = HERE.parent / "data" / "reports"  # data/CONTRACT.md: score_<name>_<split>.json
GREETING = ("Hi, I'm reo, the energy advisor at SolarHaus Müller. A few taps and I'll sketch your solar system "
            "with a price estimate. To start: how many people live in your home?")
HANDOFF_OFFER = ("This plan looks solid. Shall I send it to SolarHaus Müller? A planner will check it, usually visit "
                 "to see the roof, and send you a final quote. You're not committing to anything.")
OFFLINE_TEXT = "My calculator isn't reachable right now, so I can't give you numbers yet."

app = FastAPI(title="reo")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
_lock = threading.Lock()


# ---------- store ----------

def _load(store: Path | None = None) -> dict:
    f = store or STORE
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"plans": {}, "state": {}}


def _save(db: dict, store: Path | None = None) -> None:
    (store or STORE).write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(db: dict, pid: str) -> tuple[dict, dict]:
    if pid not in db["plans"]:
        raise HTTPException(404, f"no plan {pid}")
    return db["plans"][pid], db["state"][pid]


def out(plan: dict, installer: bool = False) -> dict:
    """Plan as the app sees it. Customer responses never carry other homes (similar_projects)."""
    if plan["status"] != "drafting":
        plan = {**plan, "summary": scripted.summary(plan)}
    return plan if installer else {**plan, "similar_projects": []}


def attach_evidence(plan: dict) -> None:
    plan["flags"] = evidence.flags(plan["facts"], plan["design"])
    if plan["status"] != "drafting":
        plan["similar_projects"] = evidence.similar_projects(plan["facts"])


def reo_msg(plan: dict, text: str) -> dict:
    m = {"role": "reo", "text": text, "at": now()}
    plan["transcript"].append(m)
    return m


def _design(plan: dict, st: dict) -> tuple[dict, bool]:
    d = engine.design(plan["facts"], st.get("locks"), st.get("prices"))
    return (d, True) if d else (engine.offline_design(), False)


# ---------- customer turn ----------

def customer_turn(db: dict, pid: str, parsed: dict, text: str, free_text: bool) -> dict:
    plan, st = _get(db, pid)
    intent, topic, new = parsed["intent"], parsed.get("topic"), parsed["facts"]

    if intent == "kwh":
        st["last_ask"] = "total_demand_kwh"
        m = reo_msg(plan, "Great, that's the most precise. What does your bill say per year?")
        return {"messages": [m], "plan": out(plan), "suggestions": ["About 3,000 kWh", "About 4,500 kWh"], "ask": flow.KWH_ASK}
    if intent == "handoff":
        m = reo_msg(plan, "Great, just add your name (and email if you like) below.")
        return {"messages": [m], "plan": out(plan), "suggestions": []}
    if intent == "skip" and st.get("last_ask"):
        st["skipped"] = sorted(set(st["skipped"]) | {st["last_ask"]})

    before = plan["design"]
    had_numbers = before.get("params_version") != engine.OFFLINE and any(h["trigger"] != "start" for h in plan["history"])
    plan["facts"].update(new)
    d, ok = _design(plan, st)
    plan["design"] = d
    attach_evidence(plan)
    if new:
        plan["history"].append({"at": now(), "trigger": text, "total_eur": d["price"]["total_eur"]})
    changed = scripted.changes(before, d) if new and had_numbers else None

    ask = flow.next_question(plan["facts"], d if ok else None, set(st["skipped"]))
    offer = ok and not st["offered"] and flow.offer_handoff(plan["facts"], d, set(st["skipped"]))
    if offer:
        st["offered"], ask = True, None
    st["last_ask"] = ask["field"] if ask else None

    reply = None
    if not ok:
        reply = OFFLINE_TEXT + (" " + ask["prompt"] if ask else "")
    elif free_text:
        reply = llm.reply(audience="customer", latest_message=text, facts=plan["facts"], engine_result=d,
                          next_question=ask, offer_handoff=offer, changed=changed, transcript=plan["transcript"],
                          flags=plan["flags"])
    if reply is None:
        reply = template(d, intent, topic, new, changed, had_numbers, ask, offer)
    m = reo_msg(plan, reply)
    plan["updated_at"] = now()

    if offer:
        suggestions = ["Yes, send it", "Not yet"]
    elif ask:
        suggestions = flow.CHIPS.get(ask["field"], []) + (["Send to installer"] if st["offered"] else [])
    else:
        suggestions = flow.STANDING_CHIPS
    turn = {"messages": [m], "plan": out(plan), "suggestions": suggestions}
    if ask:
        turn["ask"] = flow.ui_ask(ask)
    return turn


def template(d, intent, topic, new, changed, had_numbers, ask, offer) -> str:
    lo, hi = d["price"]["range_eur"]
    est = f"roughly {scripted.eur(lo)}–{scripted.eur(hi)[1:]} (estimate)"
    parts = []
    if new and not had_numbers:
        parts.append("For your home, " + scripted.headline(d))
    elif changed:
        parts.append(f"Got it, so I've {changed}. The new estimate is {est}.")
    elif new:
        parts.append(f"Thanks, noted. The estimate is {est}.")
    if intent == "question":
        parts.append(scripted.answer(d, topic))
    elif intent == "skip":
        parts.append("No problem, I'll work with a typical value for now.")
    elif intent == "other" and not new:
        parts.append("I'm only here to help with your home's energy plan. Shall we continue with that?")
    if ask:
        parts.append(ask["prompt"])
    elif offer:
        parts.append(HANDOFF_OFFER)
    return " ".join(parts) or "Anything else you'd like to know about your plan?"


# ---------- customer endpoints ----------

class Text(BaseModel):
    text: str


class Facts(BaseModel):
    facts: dict


class Address(BaseModel):
    address: str


class Handoff(BaseModel):
    name: str
    email: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "llm": bool(os.getenv("ANTHROPIC_API_KEY")), "voice": voice.enabled(), "engine": engine.healthy()}


@app.post("/sessions")
def start_session(_: dict | None = None):
    with _lock:
        db = _load()
        pid = uuid.uuid4().hex[:10]
        design = engine.design({}) or engine.offline_design()  # zero-fact design once the engine allows facts: {}
        plan = {"id": pid, "status": "drafting", "customer": {}, "facts": {}, "design": design, "transcript": [],
                "flags": [], "similar_projects": [], "installer_edits": [],
                "history": [{"at": now(), "trigger": "start", "total_eur": design["price"]["total_eur"]}], "updated_at": now()}
        db["plans"][pid] = plan
        db["state"][pid] = {"skipped": [], "offered": False, "last_ask": "num_inhabitants", "locks": {}, "prices": {}}
        m = reo_msg(plan, GREETING)
        _save(db)
        return {"messages": [m], "plan": out(plan), "suggestions": ["I know my yearly kWh"], "ask": flow.OPENING_ASK}


@app.post("/sessions/{pid}/messages")
def send_message(pid: str, body: Text):
    with _lock:
        db = _load()
        turn = message_turn(db, pid, body.text)
        _save(db)
        return turn


def message_turn(db: dict, pid: str, text: str) -> dict:
    plan, st = _get(db, pid)
    plan["transcript"].append({"role": "customer", "text": text, "at": now()})
    parsed = scripted.chip(text)  # chip taps answer instantly, no LLM (flow.md)
    free = parsed is None
    if free:
        q = next((a["prompt"] for _, a in flow.QUESTIONS if a["field"] == st.get("last_ask")), st.get("last_ask"))
        parsed = llm.extract(text, plan["facts"], q) or scripted.extract(text, st.get("last_ask"))
    return customer_turn(db, pid, parsed, text, free)


@app.post("/sessions/{pid}/voice")
def send_voice(pid: str, audio: UploadFile = File(...)):
    """Spoken turn (VOICE.md): speech-to-text -> the normal message turn -> text-to-speech of reo's reply."""
    data = audio.file.read()
    heard = voice.transcribe(data, audio.filename or "audio.webm", audio.content_type or "audio/webm")
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        if heard is None:
            m = reo_msg(plan, "Sorry, I didn't catch that. Could you say it again, or type it?")
            _save(db)
            turn = {"messages": [m], "plan": out(plan), "suggestions": flow.CHIPS.get(st.get("last_ask") or "", [])}
            return {**turn, "heard": "", "audio": None}
        turn = message_turn(db, pid, heard)
        _save(db)
    mp3 = voice.speak(" ".join(m["text"] for m in turn["messages"]))
    return {**turn, "heard": heard, "audio": base64.b64encode(mp3).decode() if mp3 else None}


@app.post("/tts")
def tts(body: Text):
    """Read any reo message aloud (greeting, chip turns)."""
    mp3 = voice.speak(body.text)
    if mp3 is None:
        return JSONResponse({"error": "voice not available"}, status_code=503)
    return Response(mp3, media_type="audio/mpeg")


@app.post("/sessions/{pid}/facts")
def send_facts(pid: str, body: Facts):
    with _lock:
        db = _load()
        facts = {k: v for k, v in body.facts.items() if v is not None}
        turn = customer_turn(db, pid, {"facts": facts, "intent": "facts", "topic": None}, "facts", free_text=False)
        _save(db)
        return turn


@app.post("/sessions/{pid}/address")
def send_address(pid: str, body: Address):
    # shortcut: address lookup mock lands in M2; until then ask for the roof size directly
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        st["last_ask"] = "roof_area_sqm"
        m = reo_msg(plan, "I can't look up that address yet. Could you tell me roughly how big the sunny side of your roof is, in m²?")
        _save(db)
        return {"messages": [m], "plan": out(plan), "suggestions": ["About 40 m²", "About 60 m²"],
                "ask": {"field": "roof_area_sqm", "prompt": "Roof area (m²)", "input": "number"}}


@app.post("/sessions/{pid}/handoff")
def handoff(pid: str, body: Handoff):
    with _lock:
        db = _load()
        plan, _ = _get(db, pid)
        plan["status"] = "handed_over"
        plan["customer"] = {"name": body.name, **({"email": body.email} if body.email else {})}
        attach_evidence(plan)
        reo_msg(plan, f"Done. Your plan is with SolarHaus Müller, {body.name}. "
                      "You'll see the final quote here once your planner has confirmed it.")
        plan["updated_at"] = now()
        _save(db)
    start_offer_prep(pid, "handoff")  # trigger: handoff -> offer_prep (runs in the background)
    return out(_get(_load(), pid)[0])


@app.get("/sessions/{pid}")
def get_session(pid: str):
    return out(_get(_load(), pid)[0])


# ---------- installer endpoints ----------

class Edit(BaseModel):
    locks: dict | None = None
    facts: dict | None = None
    prices: dict | None = None


class Ask(BaseModel):
    text: str


class Finalize(BaseModel):
    note: str | None = None


@app.get("/plans")
def list_plans(status: str | None = None):
    plans = [p for p in _load()["plans"].values() if not status or p["status"] == status]  # installer inbox
    plans.sort(key=lambda p: p["updated_at"], reverse=True)
    return [{"id": p["id"], "customer": p["customer"], "total_eur": p["design"]["price"]["total_eur"],
             "status": p["status"], "updated_at": p["updated_at"]} for p in plans]


@app.get("/plans/{pid}")
def get_plan(pid: str):
    return out(_get(_load(), pid)[0], installer=True)


@app.post("/plans/{pid}/edit")
def edit_plan(pid: str, body: Edit):
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        st["locks"].update(body.locks or {})  # locks persist across edits, merged per component
        st["prices"].update(body.prices or {})
        facts = {**plan["facts"], **(body.facts or {})}
        d = engine.design(facts, st["locks"], st["prices"])
        if d is None:
            raise HTTPException(503, "engine not reachable, edit not applied")
        before = plan["design"]["price"]["total_eur"]
        plan["facts"], plan["design"] = facts, d
        what = [f"{k} {'set to ' + str(v.get('size', 'recommended')) if v.get('recommended') else 'removed'}"
                for k, v in (body.locks or {}).items()]
        what += [f"{k} = {v}" for k, v in (body.facts or {}).items()]
        what += ["prices edited"] if body.prices else []
        plan["installer_edits"].append({"at": now(), "change": ", ".join(what) or "no change",
                                        "before": before, "after": d["price"]["total_eur"]})
        plan["history"].append({"at": now(), "trigger": "installer edit", "total_eur": d["price"]["total_eur"]})
        attach_evidence(plan)
        for v in (plan.get("offer_pack") or {}).get("variants", []):
            v["stale"] = True  # trigger: installer edit -> variants no longer match the facts / locks / prices
        plan["updated_at"] = now()
        _save(db)
        return out(plan, installer=True)


@app.post("/plans/{pid}/ask")
def ask_plan(pid: str, body: Ask):
    plan, st = _get(_load(), pid)
    d = engine.design(plan["facts"], st["locks"], st["prices"])  # fresh engine call for this answer
    if d is None:
        return {"answer": "The calculation isn't reachable right now, so I can't explain the numbers yet."}
    answer = llm.reply(audience="installer", latest_message=body.text, facts=plan["facts"], engine_result=d,
                       transcript=plan["transcript"], flags=evidence.flags(plan["facts"], d))  # aggregate only, no other homes
    return {"answer": answer or scripted.answer(d, scripted.extract(body.text)["topic"])}


@app.post("/plans/{pid}/finalize")
def finalize(pid: str, body: Finalize):
    with _lock:
        db = _load()
        plan, _ = _get(db, pid)
        _finalize(plan, body.note)
        _save(db)
        return out(plan, installer=True)


def _finalize(plan: dict, note: str | None) -> None:
    plan["status"] = "quoted"
    total = scripted.eur(plan["design"]["price"]["total_eur"])
    design = scripted.headline(plan["design"]).split(". That would")[0].removeprefix("I'd suggest ")
    reo_msg(plan, f"Your planner has confirmed your plan: {design}, total {total} (confirmed by SolarHaus Müller)."
                  + (f" {note}" if note else ""))
    plan["updated_at"] = now()


@app.get("/prices")
def prices():
    p = engine.prices()
    if p is None:
        return JSONResponse({"error": "engine not reachable"}, status_code=503)
    return p


@app.get("/validation")
def validation(split: str = "test"):
    """data's latest score JSON for the split (test, else val), as published; reo never edits the numbers."""
    for sp in dict.fromkeys([split, "test", "val"]):
        files = sorted(REPORTS.glob(f"score_*_{sp}.json"), key=lambda f: f.stat().st_mtime)
        if files:
            return {"available": True, "file": files[-1].name, **json.loads(files[-1].read_text(encoding="utf-8"))}
    return {"available": False, "note": "validation numbers arrive from data/score.py"}


# ---------- agent harness: offer pack, runs, approvals ----------

PREPARING = {"status": "preparing", "variants": [], "recommended": "Recommended", "flags": [], "site_visit_checklist": [],
             "open_questions": [], "customer_message_draft": "", "actions": [], "trace": [], "duration_s": 0, "model": "",
             "prepared_at": None, "run_id": None}


def start_offer_prep(pid: str, trigger: str) -> str:
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        ctx = htools.Ctx(json.loads(json.dumps(plan)), json.loads(json.dumps(st)), list(db.get("calendar", [])))
        runner = Runner(SKILLS["offer_prep"], ctx, trigger)
        plan["offer_pack"] = {**PREPARING, "run_id": runner.run["id"]}
        _save(db)
    threading.Thread(target=_finish_offer, args=(pid, runner, STORE), daemon=True).start()
    return runner.run["id"]


def _finish_offer(pid: str, runner: Runner, store: Path) -> None:
    run = runner.go()
    with _lock:
        db = _load(store)  # the store the run started on, even if STORE changed meanwhile
        plan = db["plans"].get(pid)
        if plan is None:
            return
        pack = run["output"] or {**PREPARING, "status": "failed", "run_id": run["id"]}
        if pack.get("status") == "preparing":
            pack["status"] = "failed"
        plan["offer_pack"] = {**pack, "duration_s": run["duration_s"], "prepared_at": now()}
        db.setdefault("runs", {})[run["id"]] = run
        _save(db, store)


def _run(rid: str) -> dict:
    run = RUNS.get(rid) or _load().get("runs", {}).get(rid)
    if run is None:
        raise HTTPException(404, f"no run {rid}")
    return run


class Payload(BaseModel):
    payload: dict | None = None


class Reason(BaseModel):
    reason: str | None = None


class VariantName(BaseModel):
    name: str


@app.post("/plans/{pid}/prepare")
def prepare(pid: str, _: dict | None = None):
    _get(_load(), pid)
    start_offer_prep(pid, "prepare")
    return out(_get(_load(), pid)[0], installer=True)


@app.post("/plans/{pid}/variant")
def choose_variant(pid: str, body: VariantName):
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        pack = plan.get("offer_pack") or {}
        v = next((x for x in pack.get("variants", []) if x["name"] == body.name), None)
        if v is None:
            raise HTTPException(404, f"no variant {body.name}")
        d = engine.design(plan["facts"], v["locks"], st["prices"])
        if d is None:
            raise HTTPException(503, "engine not reachable, variant not applied")
        before = plan["design"]["price"]["total_eur"]
        st["locks"] = dict(v["locks"])
        plan["design"] = d
        pack["chosen"] = body.name
        for act in pack.get("actions", []):
            if act["kind"] == "send_quote" and act["status"] == "proposed":
                act["label"], act["payload"]["variant"] = f"Send quote ({body.name} variant)", body.name
        plan["installer_edits"].append({"at": now(), "change": f"variant {body.name} chosen", "before": before,
                                        "after": d["price"]["total_eur"]})
        plan["history"].append({"at": now(), "trigger": f"variant {body.name}", "total_eur": d["price"]["total_eur"]})
        attach_evidence(plan)
        plan["updated_at"] = now()
        _save(db)
        return out(plan, installer=True)


def _action(plan: dict, aid: str) -> dict:
    a = next((x for x in (plan.get("offer_pack") or {}).get("actions", []) if x["id"] == aid), None)
    if a is None:
        raise HTTPException(404, f"no action {aid}")
    if a["status"] != "proposed":
        raise HTTPException(409, f"action {aid} is already {a['status']}")
    return a


def _log_step(db: dict, plan: dict, step: dict) -> None:
    run = db.get("runs", {}).get((plan.get("offer_pack") or {}).get("run_id"))
    if run:
        run["steps"].append({"n": len(run["steps"]) + 1, "ms": 0, **step})
        if not any(a["status"] == "proposed" for a in plan["offer_pack"]["actions"]):
            run["status"] = "done"
        RUNS.pop(run["id"], None)  # the stored copy is now the truth


@app.post("/plans/{pid}/actions/{aid}/approve")
def approve(pid: str, aid: str, body: Payload | None = None):
    """The only way an execute tool runs: a planner's click."""
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        a = _action(plan, aid)
        override = (body.payload if body else None) or {}
        payload = {**a["payload"], **override}
        if a["kind"] == "book_visit" and payload.get("slot") in db.get("calendar", []):
            raise HTTPException(409, f"slot {payload['slot']} is already booked")
        result = htools.execute(a["kind"], payload, db)
        if a["kind"] == "send_quote":
            # the quote is the plan as the planner left it: a chosen variant (plus later edits) wins over the proposal
            pack = plan["offer_pack"]
            want = override.get("variant") or (None if pack.get("chosen") else payload.get("variant"))
            payload["variant"] = want or pack.get("chosen") or payload.get("variant")
            v = next((x for x in pack["variants"] if x["name"] == want), None)
            if v and pack.get("chosen") != v["name"]:
                d = engine.design(plan["facts"], v["locks"], st["prices"])
                if d:
                    st["locks"], plan["design"], pack["chosen"] = dict(v["locks"]), d, v["name"]
            _finalize(plan, payload.get("message"))
        elif a["kind"] == "book_visit":
            reo_msg(plan, f"Your site visit with SolarHaus Müller is booked for {payload['slot']}.")
        elif a["kind"] == "request_document":
            reo_msg(plan, f"Your planner would like a few documents: {', '.join(payload.get('documents', []))}. "
                          "You can send them by email or bring them to the site visit.")
        a.update(status="done", payload=payload, result=result, at=now())
        _log_step(db, plan, {"kind": "tool", "tool": htools.EXECUTE_TOOL[a["kind"]], "effect": "execute",
                             "args_summary": f"approved by planner: {a['label']}", "result_summary": result})
        plan["updated_at"] = now()
        _save(db)
        return out(plan, installer=True)


@app.post("/plans/{pid}/actions/{aid}/reject")
def reject(pid: str, aid: str, body: Reason | None = None):
    with _lock:
        db = _load()
        plan, _ = _get(db, pid)
        a = _action(plan, aid)
        a.update(status="rejected", result=(body.reason if body else None) or "rejected by planner", at=now())
        _log_step(db, plan, {"kind": "guard", "tool": "approval", "ok": True,
                             "args_summary": a["label"], "result_summary": "rejected by planner, nothing executed"})
        plan["updated_at"] = now()
        _save(db)
        return out(plan, installer=True)


@app.get("/calendar/slots")
def calendar_slots():
    return {"slots": htools.free_slots(_load().get("calendar", []))}


@app.get("/runs/{rid}")
def get_run(rid: str):
    return _run(rid)


@app.get("/plans/{pid}/runs")
def plan_runs(pid: str):
    stored = _load().get("runs", {})
    runs = {**stored, **{k: v for k, v in RUNS.items() if k not in stored}}
    mine = [{k: v for k, v in r.items() if k != "output"} for r in runs.values() if r["plan_id"] == pid]
    return sorted(mine, key=lambda r: r["started_at"], reverse=True)


@app.get("/runs/{rid}/events")
def run_events(rid: str):
    """Server-Sent Events: past steps first, then live ones, then 'done'."""
    _run(rid)

    def stream():
        sent = 0
        while True:
            run = _run(rid)
            for st in run["steps"][sent:]:
                yield f"event: step\ndata: {json.dumps(st, ensure_ascii=False)}\n\n"
            sent = len(run["steps"])
            if run["status"] != "running":
                yield f"event: done\ndata: {json.dumps({'status': run['status'], 'duration_s': run['duration_s']})}\n\n"
                return
            time.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream")
