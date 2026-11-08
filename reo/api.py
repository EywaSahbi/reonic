"""reo API (reo/CONTRACT.md) on :8001. The only API the app calls.

Each customer turn: understand the message (chip table, else Claude, else rules) -> engine /design ->
next question (flow.py) -> reply (Claude from the engine result, else template). The engine is called
every turn, so every number shown is from this turn (hard rule 2).

Run:  uv run uvicorn api:app --reload --port 8001
"""
import base64
import hmac
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
import demo_guard
import evidence
import flow
import llm
import roof
import scripted
import voice
from harness import tools as htools
from harness.runner import RUNS, Runner
from harness import skills as hskills
from harness.skills import SKILLS

HERE = Path(__file__).parent
STORE = Path(os.getenv("REO_STORE", HERE / "plans.json"))  # shortcut: one JSON file, fine for a demo
GREETING = ("Hi, I'm the energy advisor at Sonnfeld. A few taps and I'll sketch your solar system "
            "with a price estimate. To start: roughly how many kWh of electricity do you use per year? It's on your bill.")
HANDOFF_OFFER = ("This plan looks solid. Shall I send it to Sonnfeld? A planner will check it, usually visit "
                 "to see the roof, and send you a final quote. You're not committing to anything.")
OFFLINE_TEXT = "My calculator isn't reachable right now, so I can't give you numbers yet."

app = FastAPI(title="reo")
INSTALLER_ROUTES = ("/plans", "/runs", "/calendar", "/prices")  # planner-only: plans, offer packs, runs, approvals


@app.middleware("http")
async def installer_auth(request, call_next):
    """Deployment guard: with REO_INSTALLER_TOKEN set (reo/.env on the laptop), installer routes need
    `Authorization: Bearer <token>`; customer routes stay open (the session id is the customer's key).
    Unset (local dev, tests): no check. Registered before CORS, so CORS wraps it and 401s carry CORS headers."""
    token = os.getenv("REO_INSTALLER_TOKEN", "")
    path = request.url.path
    if token and request.method != "OPTIONS" and any(path == r or path.startswith(r + "/") for r in INSTALLER_ROUTES):
        sent = request.headers.get("authorization", "")
        if not hmac.compare_digest(sent.encode(), f"Bearer {token}".encode()):
            return JSONResponse({"error": "planner token required"}, status_code=401)
    return await call_next(request)


app.add_middleware(demo_guard.DemoGuard)

ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"] + \
          [o.strip().rstrip("/") for o in os.getenv("REO_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"], expose_headers=["Retry-After"])
_lock = threading.Lock()


# ---------- store ----------

def _load(store: Path | None = None) -> dict:
    f = store or STORE
    if f.exists():
        return _recover(json.loads(f.read_text(encoding="utf-8")))
    return {"plans": {}, "state": {}}


def _recover(db: dict) -> dict:
    """A run stored as 'running' that this process does not know was cut off by a restart: show it as failed
    (and its offer pack), so the UI can offer 'Prepare again' instead of waiting forever."""
    for run in db.get("runs", {}).values():
        if run["status"] == "running" and run["id"] not in RUNS:
            run["status"] = "failed"
            run["steps"].append({"n": len(run["steps"]) + 1, "kind": "guard", "tool": "error", "ok": False, "ms": 0,
                                 "args_summary": "interrupted", "result_summary": "reo restarted during this run; prepare again"})
    for plan in db["plans"].values():
        pack = plan.get("offer_pack")
        if pack and pack["status"] == "preparing" and pack.get("run_id") not in RUNS:
            pack["status"] = "failed"
    return db


def _read() -> dict:
    """Read-only snapshot for endpoints that do not write: under the lock, so a concurrent _save (e.g. the
    background offer run) is never seen half-written."""
    with _lock:
        return _load()


def _save(db: dict, store: Path | None = None) -> None:
    (store or STORE).write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(db: dict, pid: str) -> tuple[dict, dict]:
    if pid not in db["plans"]:
        raise HTTPException(404, f"no plan {pid}")
    return db["plans"][pid], db["state"][pid]


def out(plan: dict, installer: bool = False) -> dict:
    """Plan as the app sees it. Customer responses never carry the installer's offer pack, and until the quote is confirmed they show the design the customer handed over, not the planner's
    working copy (which may carry installer prices such as the grant line)."""
    shown = {k: v for k, v in plan.items() if k not in ("customer_design", "offer_pack", "similar_projects")}
    if not installer:
        shown["design"] = customer_design(plan)
    elif "offer_pack" in plan:
        shown["offer_pack"] = plan["offer_pack"]
    if plan["status"] != "drafting":
        shown["summary"] = scripted.summary(shown)
    return shown


def customer_design(plan: dict) -> dict:
    """What the customer may see: the handed-over design while the planner works, the plan itself otherwise."""
    if plan["status"] == "handed_over":
        return plan.get("customer_design") or plan["design"]
    return plan["design"]


def attach_evidence(plan: dict) -> None:
    plan["flags"] = evidence.flags(plan["facts"], plan["design"])


def reo_msg(plan: dict, text: str) -> dict:
    m = {"role": "reo", "text": text, "at": now()}
    plan["transcript"].append(m)
    return m


# Customer-side designs leave out the heat-pump grant: persona.md says reo never names a funding amount or a
# post-grant price to the customer (app FYI 20:27, until Raneem decides). The planner's view keeps the grant line.
CUSTOMER_PRICES = {"heatpump_subsidy_share": 0}


def customer_prices(st: dict) -> dict:
    return {**CUSTOMER_PRICES, **(st.get("prices") or {})}


def _design(plan: dict, st: dict) -> tuple[dict, bool]:
    d = engine.design(plan["facts"], st.get("locks"), customer_prices(st))
    return (d, True) if d else (engine.offline_design(), False)


# ---------- customer turn ----------

def customer_turn(db: dict, pid: str, parsed: dict, text: str, free_text: bool) -> dict:
    plan, st = _get(db, pid)
    intent, topic, new = parsed["intent"], parsed.get("topic"), parsed["facts"]
    if plan["status"] != "drafting":
        return after_handoff_turn(plan, intent, topic)
    new = {k: v for k, v in new.items() if k not in non_positive(new)}  # "0 m²" is not an answer: ask again

    if intent == "bill_yes":  # confirm what bill_reader read
        new = st.pop("bill_pending", None) or {}
        intent = "facts" if new else "continue"
    if intent == "bill_no":
        st.pop("bill_pending", None)
        st["last_ask"] = "total_demand_kwh"
        m = reo_msg(plan, "No problem. What does your bill say per year?")
        return {"messages": [m], "plan": out(plan), "suggestions": ["About 3,000 kWh", "About 4,500 kWh"], "ask": flow.KWH_ASK}
    if intent == "goal" and topic in GOALS:
        return goal_turn(db, plan, st, new, topic)
    if intent == "dims":
        st["last_ask"] = "roof_dims"
        m = reo_msg(plan, "Sure. How wide and how long is the roof face that gets the sun, in metres? For example \"8 x 6 m\".")
        return {"messages": [m], "plan": out(plan), "suggestions": ["Skip"], "ask": flow.DIMS_ASK}
    if new.get("roof_width_m") and new.get("roof_length_m"):
        # customer's own measurement: the area is their fact (width x length); the engine fits modules from the sides
        new = {**new, "roof_area_sqm": round(new["roof_width_m"] * new["roof_length_m"], 1)}
    elif "roof_area_sqm" in new:  # a new roof area (address lookup, "about 50 m²") replaces earlier measured sides
        plan["facts"].pop("roof_width_m", None)
        plan["facts"].pop("roof_length_m", None)
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


POSITIVE = ("total_demand_kwh", "annual_demand_kwh", "roof_area_sqm", "roof_width_m", "roof_length_m")


def non_positive(facts: dict) -> list[str]:
    """Fields the engine rejects with 422 when <= 0 (engine 11f5a6a); reo never sends them, so a 422 is never
    mistaken for 'engine down'."""
    return [k for k in POSITIVE if isinstance(facts.get(k), (int, float)) and facts[k] <= 0]


def after_handoff_turn(plan: dict, intent: str, topic: str | None) -> dict:
    """Once handed over the plan is the planner's (flow.md: no more questions). A customer message is kept in the
    transcript for the planner but changes no facts or design; questions are answered from what the customer sees."""
    d = customer_design(plan)
    who = "Your planner has confirmed your quote" if plan["status"] == "quoted" else "Your plan is with Sonnfeld now"
    if intent == "question" and d.get("params_version") != engine.OFFLINE:
        text = scripted.answer(d, topic)
    else:
        text = f"{who}, so I can't change it here. I've kept your message so your planner sees it."
    m = reo_msg(plan, text)
    plan["updated_at"] = now()
    return {"messages": [m], "plan": out(plan), "suggestions": []}


GOALS = {"budget": "your budget", "independence": "as much independence as possible", "lowest_bill": "the lowest monthly bill"}
GOAL_CHIPS = ["Keep it under €20,000", "As independent as possible", "Lowest monthly bill"]


def run_skill(db: dict, skill: str, plan: dict, st: dict, trigger: str, inputs: dict | None = None) -> dict:
    """Run a harness skill synchronously on a copy of this plan; the run is stored with the plan store."""
    ctx = htools.Ctx(json.loads(json.dumps(plan)), json.loads(json.dumps(st)), list(db.get("calendar", [])))
    ctx.inputs = inputs or {}
    run = Runner(SKILLS[skill], ctx, trigger).go()
    db.setdefault("runs", {})[run["id"]] = run
    RUNS.pop(run["id"], None)
    return run


def run_skill_unlocked(pid: str, skill: str, trigger: str, inputs: dict) -> dict:
    """Like run_skill, but the (possibly slow) model loop runs outside the store lock."""
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        ctx = htools.Ctx(json.loads(json.dumps(plan)), json.loads(json.dumps(st)), list(db.get("calendar", [])))
    ctx.inputs = inputs
    run = Runner(SKILLS[skill], ctx, trigger).go()
    with _lock:
        db = _load()
        db.setdefault("runs", {})[run["id"]] = run
        RUNS.pop(run["id"], None)
        _save(db)
    return run


def goal_turn(db: dict, plan: dict, st: dict, new: dict, goal: str) -> dict:
    """Trigger: goal message -> goal_planner. The best variant becomes the plan (customer's choice), two alternatives shown."""
    plan["facts"].update(new)
    run = run_skill(db, "goal_planner", plan, {**st, "prices": customer_prices(st)}, "goal message", {"goal": goal})
    res = run["output"] or {}
    rec = res.get("recommendation")
    if not rec:
        m = reo_msg(plan, OFFLINE_TEXT)
        return {"messages": [m], "plan": out(plan), "suggestions": flow.STANDING_CHIPS}
    st["locks"] = {k: v for k, v in rec["locks"].items()}
    plan["design"] = rec["design"]
    plan["history"].append({"at": now(), "trigger": f"goal: {goal}", "total_eur": rec["design"]["price"]["total_eur"]})
    attach_evidence(plan)
    lead = f"For {GOALS[goal]}, " + scripted.headline(rec["design"])
    if goal == "budget" and not res.get("fits_budget"):
        lead = "Nothing I can design fits that budget, so here is the lowest-priced option. " + scripted.headline(rec["design"])
    alts = [f"{a['why'].split(': ', 1)[1].split(';')[0]} for about {scripted.eur(a['design']['price']['total_eur'])}"
            for a in res.get("alternatives", [])]
    text = lead + (f" Alternatives: {' or '.join(alts)} (estimates)." if alts else "")
    m = reo_msg(plan, text)
    plan["updated_at"] = now()
    return {"messages": [m], "plan": out(plan), "suggestions": ["Send to installer", "Why this size?"]
            + [c for c in GOAL_CHIPS if c.lower().split()[0] not in goal], "goal_result": res}


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
    roof_limit = next((r for r in d["components"]["pv"]["reasons"] if "roof is the limit" in r), None)
    if roof_limit and (new.get("roof_area_sqm") or new.get("roof_width_m")):
        parts.append(roof_limit[0].upper() + roof_limit[1:] + ".")  # engine's own words: the roof caps the modules
    if intent == "question":
        parts.append(scripted.answer(d, topic))
    elif intent == "skip":
        parts.append("No problem, I'll work with a typical value for now.")
    elif intent == "other" and not new:
        parts.append("I'm only here to help with your home's energy plan. Shall we continue with that?")
    if "heating_type" in new and (advice := scripted.heating_advice(d)):
        parts.append(advice)
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
    return {"ok": True, "llm": bool(os.getenv("ANTHROPIC_API_KEY")), "voice": voice.enabled(), "engine": engine.healthy(),
            "demo_auth_required": demo_guard.enabled(), "demo_limits": demo_guard.limits() if demo_guard.enabled() else None}


@app.get("/demo/access")
def demo_access():
    return {"ok": True}


@app.post("/sessions")
def start_session(_: dict | None = None):
    with _lock:
        db = _load()
        pid = uuid.uuid4().hex[:10]
        demo_guard.admit_session(pid)
        try:
            design = engine.design({}, None, CUSTOMER_PRICES) or engine.offline_design()  # zero-fact first design
            plan = {"id": pid, "status": "drafting", "customer": {}, "facts": {}, "design": design, "transcript": [],
                    "flags": [], "installer_edits": [],
                    "history": [{"at": now(), "trigger": "start", "total_eur": design["price"]["total_eur"]}], "updated_at": now()}
            db["plans"][pid] = plan
            db["state"][pid] = {"skipped": [], "offered": False, "last_ask": "total_demand_kwh", "locks": {}, "prices": {}}
            m = reo_msg(plan, GREETING)
            _save(db)
            return {"messages": [m], "plan": out(plan), "suggestions": flow.CHIPS["total_demand_kwh"], "ask": flow.ui_ask(flow.OPENING_ASK)}
        except BaseException:
            demo_guard.release_session(pid)
            raise


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


@app.post("/sessions/{pid}/bill")
def send_bill(pid: str, image: UploadFile = File(...)):
    """Trigger: bill upload -> bill_reader. Facts wait for the customer's 'Yes, that's right'."""
    data, media = image.file.read(), image.content_type or "image/jpeg"
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        snap_plan, snap_st, booked = json.loads(json.dumps(plan)), json.loads(json.dumps(st)), list(db.get("calendar", []))
    ctx = htools.Ctx(snap_plan, snap_st, booked)
    ctx.inputs = {"bill": data, "media_type": media}
    run = Runner(SKILLS["bill_reader"], ctx, "bill upload").go()  # vision call outside the lock
    read = (run["output"] or {}).get("read", {})
    facts = {k: read[k] for k in ("total_demand_kwh", "electricity_price_eur_per_kwh") if read.get(k)}
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        db.setdefault("runs", {})[run["id"]] = run
        RUNS.pop(run["id"], None)
        plan["transcript"].append({"role": "customer", "text": "(photo of my electricity bill)", "at": now()})
        if facts:
            st["bill_pending"] = facts
            bits = ([f"about {facts['total_demand_kwh']:,.0f} kWh a year"] if "total_demand_kwh" in facts else []) + \
                   ([f"{facts['electricity_price_eur_per_kwh'] * 100:.1f} ct per kWh"] if "electricity_price_eur_per_kwh" in facts else [])
            who = f" from {read['provider']}" if read.get("provider") else ""
            m = reo_msg(plan, f"I read this from your bill{who}: {' and '.join(bits)}. Is that right?")
            turn = {"messages": [m], "plan": out(plan), "suggestions": ["Yes, that's right", "Not quite"],
                    "bill": {"read": {**facts, **({"provider": read["provider"]} if read.get("provider") else {})}, "confirmed": False}}
        else:
            st["last_ask"] = "total_demand_kwh"
            m = reo_msg(plan, "I couldn't read that bill. Could you type your yearly electricity use instead?")
            turn = {"messages": [m], "plan": out(plan), "suggestions": ["About 3,000 kWh", "About 4,500 kWh"], "ask": flow.KWH_ASK}
        _save(db)
        return turn


@app.post("/sessions/{pid}/address")
def send_address(pid: str, body: Address):
    """Roof from the address: demo addresses offline, else OpenStreetMap building outline (roof.py).
    Not found -> offer width x length or skip."""
    hit = roof.lookup(body.address)  # network call outside the lock
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        plan["transcript"].append({"role": "customer", "text": body.address, "at": now()})
        if hit is None:
            st["last_ask"] = "roof_dims"
            m = reo_msg(plan, "I couldn't find that building on the map. You can enter the roof's width and length instead, or skip it.")
            _save(db)
            return {"messages": [m], "plan": out(plan), "suggestions": ["Skip"], "ask": flow.DIMS_ASK}
        turn = customer_turn(db, pid, {"facts": dict(hit["facts"]), "intent": "facts", "topic": None}, f"address: {hit['label']}", False)
        turn["messages"][0]["text"] = f"I looked up your address: {hit['say']}. " + turn["messages"][0]["text"]
        turn["roof"] = {"source": hit["source"], "label": hit["label"], **({"footprint_sqm": hit["footprint_sqm"]} if "footprint_sqm" in hit else {})}
        _save(db)
        return turn


@app.post("/sessions/{pid}/handoff")
def handoff(pid: str, body: Handoff):
    with _lock:
        db = _load()
        plan, _ = _get(db, pid)
        if plan["status"] != "drafting":  # a repeated handoff (double click, retry) must not reopen the plan or restart prep
            return out(plan)
        lease = demo_guard.reserve_run()
        try:
            plan["status"] = "handed_over"
            plan["customer_design"] = plan["design"]  # what the customer agreed to; the planner edits plan["design"]
            plan["customer"] = {"name": body.name, **({"email": body.email} if body.email else {})}
            attach_evidence(plan)
            reo_msg(plan, f"Done. Your plan is with Sonnfeld, {body.name}. "
                          "You'll see the final quote here once your planner has confirmed it.")
            plan["updated_at"] = now()
            _save(db)
        except BaseException:
            lease.release()
            raise
    start_offer_prep(pid, "handoff", lease)  # trigger: handoff -> offer_prep (runs in the background)
    return out(_get(_read(), pid)[0])


@app.get("/sessions/{pid}")
def get_session(pid: str):
    return out(_get(_read(), pid)[0])


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
    plans = [p for p in _read()["plans"].values() if not status or p["status"] == status]  # installer inbox
    plans.sort(key=lambda p: p["updated_at"], reverse=True)
    return [{"id": p["id"], "customer": p["customer"], "total_eur": p["design"]["price"]["total_eur"],
             "status": p["status"], "updated_at": p["updated_at"]} for p in plans]


@app.get("/plans/{pid}")
def get_plan(pid: str):
    return out(_get(_read(), pid)[0], installer=True)


@app.delete("/plans/{pid}")
def delete_plan(pid: str):
    """Planner removes an inbox entry: the plan, its state and its runs. A running offer prep finds no plan and
    drops its result (_finish_offer). Booked calendar slots stay booked."""
    with _lock:
        db = _load()
        _get(db, pid)
        del db["plans"][pid]
        db["state"].pop(pid, None)
        for rid in [r for r, run in db.get("runs", {}).items() if run["plan_id"] == pid]:
            del db["runs"][rid]
            RUNS.pop(rid, None)
        _save(db)
    demo_guard.release_session(pid)
    return {"deleted": pid}


@app.post("/plans/{pid}/edit")
def edit_plan(pid: str, body: Edit):
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        _not_quoted(plan)
        if bad := non_positive(body.facts or {}):
            raise HTTPException(422, f"must be greater than 0: {', '.join(bad)}")
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
        _refresh_draft(db, plan)  # the draft and the pending quote describe the plan as edited
        plan["updated_at"] = now()
        _save(db)
        return out(plan, installer=True)


def _not_quoted(plan: dict) -> None:
    """The customer already holds a confirmed quote: changing the design now would contradict it."""
    if plan["status"] == "quoted":
        raise HTTPException(409, "plan is already quoted; the confirmed quote can't be changed")


def _visit(db: dict, plan: dict) -> tuple[str, bool]:
    """The site-visit slot the customer message should name: the booked one, else the proposed one if still free."""
    acts = [a for a in (plan.get("offer_pack") or {}).get("actions", []) if a["kind"] == "book_visit"]
    done = next((a["payload"]["slot"] for a in acts if a["status"] == "done"), None)
    if done:
        return done, True
    booked = db.get("calendar", [])
    slot = next((a["payload"].get("slot") for a in acts if a["status"] == "proposed" and a["payload"].get("slot") not in booked), None)
    return slot or htools.free_slots(booked)[0], False


def _refresh_draft(db: dict, plan: dict) -> None:
    """Regenerate the customer message from the plan's current design (template, grounded by construction) and
    put it on the pending send_quote, so the sent message always matches the quoted design."""
    pack = plan.get("offer_pack")
    if not pack or pack.get("status") != "ready" or plan["design"].get("params_version") == engine.OFFLINE:
        return
    slot, booked = _visit(db, plan)
    pack["customer_message_draft"] = hskills._draft(plan["customer"].get("name", ""), plan["design"], slot, booked)
    pack["draft_for"] = pack.get("chosen") or pack.get("recommended")
    for act in pack.get("actions", []):
        if act["kind"] == "send_quote" and act["status"] == "proposed":
            act["payload"]["message"] = pack["customer_message_draft"]


@app.post("/plans/{pid}/ask")
def ask_plan(pid: str, body: Ask):
    plan, st = _get(_read(), pid)
    d = engine.design(plan["facts"], st["locks"], st["prices"])  # fresh engine call for this answer
    if d is None:
        return {"answer": "The calculation isn't reachable right now, so I can't explain the numbers yet."}
    parsed = scripted.extract(body.text)
    if parsed["intent"] == "goal" and parsed["topic"] in GOALS:  # planner asks for a goal: goal_planner, nothing applied
        with _lock:
            db = _load()
            plan, st = _get(db, pid)
            plan = {**plan, "facts": {**plan["facts"], **parsed["facts"]}}
            run = run_skill(db, "goal_planner", plan, st, "installer goal question", {"goal": parsed["topic"]})
            _save(db)
        res = run["output"] or {}
        lines = [res["recommendation"]["why"]] + [a["why"] for a in res.get("alternatives", [])] if res.get("recommendation") else []
        return {"answer": " ".join(lines) or "No variant found.", "goal_result": res}
    run = run_skill_unlocked(pid, "installer_qa", "installer question", {"question": body.text})  # traced, grounded
    res = run["output"] or {}
    return {"answer": res.get("answer") or scripted.answer(d, scripted.extract(body.text)["topic"]), "run_id": run["id"]}


@app.post("/plans/{pid}/finalize")
def finalize(pid: str, body: Finalize):
    with _lock:
        db = _load()
        plan, _ = _get(db, pid)
        _not_quoted(plan)  # a second finalize would send the customer a second confirmation
        _finalize(plan, body.note)
        for a in (plan.get("offer_pack") or {}).get("actions", []):  # the quote is out: close the pending send_quote
            if a["kind"] == "send_quote" and a["status"] == "proposed":
                a.update(status="done", result="quote sent with Finalize", at=now())
                _log_step(db, plan, {"kind": "tool", "tool": "quote.send", "effect": "execute",
                                     "args_summary": "finalized by planner", "result_summary": "quote sent to the customer"})
        _save(db)
        return out(plan, installer=True)


def _finalize(plan: dict, note: str | None) -> None:
    plan["status"] = "quoted"
    total = scripted.eur(plan["design"]["price"]["total_eur"])
    design = scripted.headline(plan["design"]).split(". That would")[0].removeprefix("I'd suggest ")
    reo_msg(plan, f"Your planner has confirmed your plan: {design}, total {total} (confirmed by Sonnfeld)."
                  + (f" {note}" if note else ""))
    plan["updated_at"] = now()


@app.get("/prices")
def prices():
    p = engine.prices()
    if p is None:
        return JSONResponse({"error": "engine not reachable"}, status_code=503)
    return p


# ---------- agent harness: offer pack, runs, approvals ----------

PREPARING = {"status": "preparing", "variants": [], "recommended": "Recommended", "flags": [], "site_visit_checklist": [],
             "open_questions": [], "customer_message_draft": "", "actions": [], "trace": [], "duration_s": 0, "model": "",
             "prepared_at": None, "run_id": None}


def start_offer_prep(pid: str, trigger: str, lease=None) -> str:
    lease = lease or demo_guard.reserve_run()
    try:
        with _lock:
            db = _load()
            plan, st = _get(db, pid)
            ctx = htools.Ctx(json.loads(json.dumps(plan)), json.loads(json.dumps(st)), list(db.get("calendar", [])))
            runner = Runner(SKILLS["offer_prep"], ctx, trigger, lease=lease)
            plan["offer_pack"] = {**PREPARING, "run_id": runner.run["id"]}
            db.setdefault("runs", {})[runner.run["id"]] = json.loads(json.dumps(runner.run))
            _save(db)
        threading.Thread(target=_finish_offer, args=(pid, runner, STORE), daemon=True).start()
        return runner.run["id"]
    except BaseException:
        lease.release()
        raise


def _finish_offer(pid: str, runner: Runner, store: Path) -> None:
    run = runner.go()
    try:
        with _lock:
            db = _load(store)  # the store the run started on, even if STORE changed meanwhile
            plan = db["plans"].get(pid)
            if plan is None:
                return
            db.setdefault("runs", {})[run["id"]] = run
            if (plan.get("offer_pack") or {}).get("run_id") != run["id"]:  # a newer prepare replaced this run
                _save(db, store)
                return
            pack = run["output"] or {**PREPARING, "status": "failed", "run_id": run["id"]}
            if pack.get("status") == "preparing":
                pack["status"] = "failed"
            plan["offer_pack"] = {**pack, "duration_s": run["duration_s"], "prepared_at": now()}
            st = db["state"][pid]
            basis = (runner.ctx.facts, runner.ctx.st.get("locks") or {}, runner.ctx.st.get("prices") or {})
            if basis != (plan["facts"], st.get("locks") or {}, st.get("prices") or {}):  # planner edited while reo prepared
                for v in plan["offer_pack"]["variants"]:
                    v["stale"] = True
                _refresh_draft(db, plan)
            _save(db, store)
    finally:
        RUNS.pop(run["id"], None)


def _run(rid: str) -> dict:
    run = RUNS.get(rid) or _read().get("runs", {}).get(rid)
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
    _not_quoted(_get(_read(), pid)[0])
    start_offer_prep(pid, "prepare")
    return out(_get(_read(), pid)[0], installer=True)


@app.post("/plans/{pid}/variant")
def choose_variant(pid: str, body: VariantName):
    with _lock:
        db = _load()
        plan, st = _get(db, pid)
        _not_quoted(plan)
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
        if v.pop("stale", False):  # an outdated card is re-run on today's facts: card, plan and draft agree again
            v["design"], v["why"] = d, hskills._why(v["name"], d)
        for act in pack.get("actions", []):
            if act["kind"] == "send_quote" and act["status"] == "proposed":
                act["label"], act["payload"]["variant"] = f"Send quote ({body.name} variant)", body.name
        _refresh_draft(db, plan)  # the draft must describe the chosen variant
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
        if a["kind"] == "send_quote":
            # the quote is the plan as the planner left it: an explicit variant, else a chosen variant or later edits;
            # the proposed variant only while the plan is still exactly as reo prepared it
            _not_quoted(plan)
            pack = plan["offer_pack"]
            edited = any(v.get("stale") for v in pack["variants"])
            want = override.get("variant") or (None if pack.get("chosen") or edited else payload.get("variant"))
            v = next((x for x in pack["variants"] if x["name"] == want), None)
            if v and pack.get("chosen") != v["name"]:
                d = engine.design(plan["facts"], v["locks"], st["prices"])
                if d is None:
                    raise HTTPException(503, "engine not reachable, quote not sent")
                st["locks"], plan["design"], pack["chosen"] = dict(v["locks"]), d, v["name"]
                if pack.get("draft_for") != v["name"]:
                    _refresh_draft(db, plan)
                    payload["message"] = override.get("message") or pack["customer_message_draft"]
            payload["variant"] = pack.get("chosen") or (None if edited else payload.get("variant"))
        result = htools.execute(a["kind"], payload, db)  # after every check: nothing half-done on a refusal
        if a["kind"] == "send_quote":
            _finalize(plan, payload.get("message"))
        elif a["kind"] == "book_visit":
            reo_msg(plan, f"Your site visit with Sonnfeld is booked for {payload['slot']}.")
        elif a["kind"] == "request_document":
            reo_msg(plan, f"Your planner would like a few documents: {', '.join(payload.get('documents', []))}. "
                          "You can send them by email or bring them to the site visit.")
        a.update(status="done", payload=payload, result=result, at=now())
        if a["kind"] == "book_visit" and plan["status"] != "quoted":
            _refresh_draft(db, plan)  # the message now names the booked slot
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
    return {"slots": htools.free_slots(_read().get("calendar", []))}


@app.get("/runs/{rid}")
def get_run(rid: str):
    return _run(rid)


@app.get("/plans/{pid}/runs")
def plan_runs(pid: str):
    stored = _read().get("runs", {})
    runs = {**stored, **RUNS}  # a live run's in-memory copy is newer than its stored start record
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
