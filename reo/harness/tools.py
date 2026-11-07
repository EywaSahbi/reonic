"""Tool registry. Every tool declares an effect class:
read     no side effects (engine, evidence, plan, calendar slots)
propose  writes only a proposal into the run context (variants, actions, draft, questions); the planner decides
execute  real side effect (calendar booking, CRM, sending the quote). Never in a skill's tool list: only the
         approve endpoint runs these, after a human click.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import engine
import evidence


@dataclass
class Tool:
    name: str
    effect: str  # read | propose | execute
    description: str
    schema: dict
    handler: Callable[["Ctx", dict], dict]


@dataclass
class Ctx:
    """What one run may see and change: its own plan only (scope guard, hard rule 5)."""
    plan: dict
    st: dict
    booked: list[str]
    variants: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    draft: str = ""
    questions: list = field(default_factory=list)
    checklist: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    slots: list = field(default_factory=list)
    finish: dict | None = None
    inputs: dict = field(default_factory=dict)  # per-run inputs: bill image, goal
    candidates: list = field(default_factory=list)  # goal planner: designs evaluated

    def reset(self) -> None:
        """Drop the model's proposals before the scripted planner starts over."""
        self.variants, self.actions, self.draft, self.questions, self.checklist, self.finish = {}, [], "", [], [], None

    @property
    def facts(self) -> dict:
        return self.plan["facts"]

    def locks(self, extra: dict | None = None) -> dict:
        return {**(extra or {}), **(self.st.get("locks") or {})}  # the planner's own locks always win


def short(d: dict | None) -> dict:
    """The numbers of a design a model needs."""
    if not d:
        return {"error": "engine not reachable"}
    c = d["components"]
    return {"components": {k: {"recommended": v["recommended"], "size": v["size"], "unit": v["unit"], "reasons": v["reasons"]}
                           for k, v in c.items()},
            "total_eur": d["price"]["total_eur"], "range_eur": d["price"]["range_eur"],
            "price_items": [{"label": i["label"], "total_eur": i["total_eur"]} for i in d["price"]["items"]],
            "economics": d["economics"], "bundle": d.get("bundle"),
            "missing_inputs": d.get("missing_inputs", []), "assumptions": d.get("assumptions", [])}


def free_slots(booked: list[str], n: int = 4) -> list[str]:
    """Mock calendar: weekday site-visit slots from tomorrow, 09:00 and 14:00, minus booked ones."""
    out, day = [], datetime.now().date() + timedelta(days=1)
    while len(out) < n:
        if day.weekday() < 5:
            out += [f"{day.isoformat()} {h}" for h in ("09:00", "14:00") if f"{day.isoformat()} {h}" not in booked]
        day += timedelta(days=1)
    return out[:n]


# ---------- read ----------

def _design(ctx: Ctx, a: dict) -> dict:
    return short(engine.design(ctx.facts, ctx.locks(a.get("locks")), ctx.st.get("prices") or None))


def _explain(ctx: Ctx, a: dict) -> dict:
    return engine.explain(ctx.facts, a["component"], ctx.locks(), ctx.st.get("prices") or None) or {"error": "not available"}


def _percentile(ctx: Ctx, a: dict) -> dict:
    """Aggregate comparison with similar real homes (no individual projects: hard rule 5)."""
    seg = evidence.segment(ctx.facts)
    if not seg:
        return {"error": "no benchmarks"}
    d = engine.design(ctx.facts, ctx.locks(), ctx.st.get("prices") or None)
    ctx.flags = evidence.flags(ctx.facts, d) if d else []
    pick = lambda k: {q: seg[k].get(q) for q in ("p10", "p25", "p50", "p75", "p90")}
    return {"segment": seg["key"], "n": seg["n"], "pv_kwp": pick("pv_kwp"), "battery_kwh": pick("battery_kwh"),
            "attach_rate": seg["attach_rate"], "flags": [f["text"] for f in ctx.flags],
            "anchors": evidence.variant_locks(ctx.facts, d) if d else {}}


def _bill_read(ctx: Ctx, a: dict) -> dict:
    """Vision: read the uploaded bill (only printed values, nulls dropped)."""
    import llm
    got = llm.read_bill(ctx.inputs.get("bill", b""), ctx.inputs.get("media_type", "image/jpeg"))
    if got is None:
        return {"error": "could not read the bill"}
    return {k: v for k, v in got.items() if v is not None}


def _plan_read(ctx: Ctx, a: dict) -> dict:
    p = ctx.plan
    return {"facts": p["facts"], "customer_name": p["customer"].get("name"), "status": p["status"],
            "customer_said": [m["text"] for m in p["transcript"] if m["role"] == "customer"][-10:]}


def _slots(ctx: Ctx, a: dict) -> dict:
    ctx.slots = free_slots(ctx.booked)
    return {"slots": ctx.slots}


# ---------- propose ----------

def _propose_variant(ctx: Ctx, a: dict) -> dict:
    d = engine.design(ctx.facts, ctx.locks(a.get("locks")), ctx.st.get("prices") or None)
    if d is None:
        return {"error": "engine not reachable"}
    ctx.variants[a["name"]] = {"name": a["name"], "locks": ctx.locks(a.get("locks")), "design": d, "why": a.get("why", "")}
    return {"proposed": a["name"], **short(d)}


def _propose_action(ctx: Ctx, a: dict) -> dict:
    if a["kind"] not in ("book_visit", "send_quote", "create_crm_task", "request_document"):
        return {"error": "unknown action kind"}
    act = {"id": f"a{len(ctx.actions) + 1}", "kind": a["kind"], "label": a["label"], "payload": a.get("payload") or {},
           "status": "proposed"}
    ctx.actions.append(act)
    return {"proposed_action": act["id"], "status": "proposed (waits for the planner)"}


def _draft(ctx: Ctx, a: dict) -> dict:
    ctx.draft = a["text"]
    return {"draft_saved": True}


def _question(ctx: Ctx, a: dict) -> dict:
    (ctx.checklist if a.get("kind") == "site_visit" else ctx.questions).append(a["text"])
    return {"added": a.get("kind", "open_question")}


def _finish(ctx: Ctx, a: dict) -> dict:
    ctx.finish = a
    return {"finished": True}


_LOCKS = {"type": "object", "description": "component locks, e.g. {\"battery\": {\"recommended\": true, \"size\": 10}, \"heatpump\": {\"recommended\": false}}"}
_COMP = {"type": "string", "enum": ["pv", "battery", "heatpump", "wallbox"]}

REGISTRY: dict[str, Tool] = {t.name: t for t in [
    Tool("engine.design", "read", "Run the engine with optional extra component locks; returns sizes, prices, economics.",
         {"type": "object", "properties": {"locks": _LOCKS}}, _design),
    Tool("engine.explain", "read", "Engine reasons and what-ifs for one component.",
         {"type": "object", "properties": {"component": _COMP}, "required": ["component"]}, _explain),
    Tool("evidence.percentile", "read", "How the design compares with similar real homes (aggregate percentiles, flags, variant anchors).",
         {"type": "object", "properties": {}}, _percentile),
    Tool("bill.read", "read", "Read the uploaded electricity bill (vision): yearly kWh, price per kWh, provider.",
         {"type": "object", "properties": {}}, _bill_read),
    Tool("plan.read", "read", "This plan's facts, customer name and what the customer said.", {"type": "object", "properties": {}}, _plan_read),
    Tool("calendar.slots", "read", "Next free site-visit slots.", {"type": "object", "properties": {}}, _slots),
    Tool("plan.propose_variant", "propose", "Propose an offer variant: the engine designs it from the locks; you add a one-sentence why.",
         {"type": "object", "properties": {"name": {"type": "string", "enum": ["Basic", "Recommended", "Independence"]},
                                           "locks": _LOCKS, "why": {"type": "string"}}, "required": ["name", "why"]}, _propose_variant),
    Tool("plan.propose_action", "propose", "Propose an action for the planner to approve (nothing runs until approved).",
         {"type": "object", "properties": {"kind": {"type": "string", "enum": ["book_visit", "send_quote", "create_crm_task", "request_document"]},
                                           "label": {"type": "string"}, "payload": {"type": "object"}},
          "required": ["kind", "label"]}, _propose_action),
    Tool("plan.draft_message", "propose", "Save the draft message from the planner to the customer.",
         {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}, _draft),
    Tool("plan.add_question", "propose", "Add an open question for the planner, or a site-visit checklist item (kind site_visit).",
         {"type": "object", "properties": {"text": {"type": "string"}, "kind": {"type": "string", "enum": ["open_question", "site_visit"]}},
          "required": ["text"]}, _question),
    Tool("finish", "propose", "Finish the run: a one-line summary (or your answer) for the planner, and for offer packs the variant you recommend.",
         {"type": "object", "properties": {"recommended": {"type": "string", "enum": ["Basic", "Recommended", "Independence"]},
                                           "summary": {"type": "string"}}, "required": ["summary"]}, _finish),
]}


# ---------- execute (approve endpoint only) ----------

def execute(kind: str, payload: dict, db: dict) -> str:
    """Run an approved action's side effect on the mocks; returns a one-line result."""
    if kind == "book_visit":
        db.setdefault("calendar", []).append(payload["slot"])
        return f"site visit booked for {payload['slot']}"
    if kind in ("create_crm_task", "request_document"):
        db.setdefault("crm", []).append({"kind": kind, **payload, "at": datetime.now().isoformat(timespec="seconds")})
        return f"CRM: {payload.get('task') or 'document request: ' + ', '.join(payload.get('documents', []))}"
    if kind == "send_quote":
        return "quote sent to the customer"
    raise ValueError(kind)


EXECUTE_TOOL = {"book_visit": "calendar.book", "create_crm_task": "crm.create_task", "request_document": "crm.create_task",
                "send_quote": "quote.send"}
