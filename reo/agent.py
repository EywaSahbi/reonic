"""Offer agent: prepares the planner's offer pack after handoff (docs/plan.md Phase 2).

Guardrails: tools are deterministic (engine, benchmarks, mock calendar); every number in a variant comes from an
engine design of this run; actions are only *proposed* (the planner approves); every step lands in the trace;
without an API key the scripted path builds the same pack.

Flow: code runs the fixed steps (designs for three lock sets, explain, flags, slots), then Claude (agent model)
may try other lock sets with the same tools and writes the words via `submit_pack`. Variant designs are always
re-run by code from the final locks, so Claude never supplies a number.
"""
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import anthropic

import engine
import evidence
import llm
import scripted

log = logging.getLogger("reo.agent")
NAMES = ["Basic", "Recommended", "Independence"]
MAX_TURNS = 6


def slots(booked: list[str], n: int = 4) -> list[str]:
    """Mock calendar: weekday site-visit slots from tomorrow, 09:00 and 14:00, minus booked ones."""
    out, day = [], datetime.now().date() + timedelta(days=1)
    while len(out) < n:
        if day.weekday() < 5:
            out += [f"{day.isoformat()} {h}" for h in ("09:00", "14:00") if f"{day.isoformat()} {h}" not in booked]
        day += timedelta(days=1)
    return out[:n]


def _short(d: dict) -> dict:
    """The numbers of a design the agent needs, nothing else."""
    c = d["components"]
    return {"components": {k: {"recommended": v["recommended"], "size": v["size"], "unit": v["unit"], "reasons": v["reasons"]}
                           for k, v in c.items()},
            "total_eur": d["price"]["total_eur"], "range_eur": d["price"]["range_eur"], "economics": d["economics"],
            "bundle": d.get("bundle")}


class Run:
    def __init__(self, plan: dict, st: dict, booked: list[str]):
        self.facts, self.plan, self.st = plan["facts"], plan, st
        self.base_locks = st.get("locks") or {}
        self.prices = st.get("prices") or None
        self.trace: list[dict] = []
        self.locks: dict[str, dict] = {}
        self.designs: dict[str, dict] = {}
        self.booked = booked

    def step(self, tool: str, summary: str) -> None:
        self.trace.append({"step": len(self.trace) + 1, "tool": tool, "summary": summary})

    def design(self, name: str, locks: dict) -> dict | None:
        merged = {**locks, **self.base_locks}  # the planner's own locks always win
        d = engine.design(self.facts, merged, self.prices)
        if d:
            self.locks[name], self.designs[name] = merged, d
            c = d["components"]
            parts = [f"{k} {c[k]['size']:g} {c[k]['unit']}" for k in ("pv", "battery", "heatpump", "wallbox")
                     if c[k]["recommended"] and c[k]["size"]]
            self.step("engine.design", f"{name}: {', '.join(parts) or 'no components'}, €{d['price']['total_eur']:,.0f}, "
                                       f"autarky {d['economics']['autarky_pct']:.0f}%")
        else:
            self.step("engine.design", f"{name}: engine not reachable")
        return d


def _fixed_steps(run: Run) -> bool:
    base = run.design("Recommended", {})
    if base is None:
        return False
    anchors = evidence.variant_locks(run.facts, base)
    seg = evidence.segment(run.facts)
    run.step("benchmarks", f"segment {seg['key'] if seg else 'none'} (n={seg['n'] if seg else 0}): variant anchors "
                           + "; ".join(f"{k} {v}" for k, v in anchors.items() if v))
    for name in ("Basic", "Independence"):
        run.design(name, anchors[name])
    for comp in ("battery", "pv"):
        ex = engine.explain(run.facts, comp, run.base_locks, run.prices)
        if ex and ex.get("what_if"):
            run.step("engine.explain", f"{comp}: " + "; ".join(f"{w['change']} → {w['effect']}" for w in ex["what_if"][:2]))
    run.flags = evidence.flags(run.facts, base)
    run.step("benchmarks", f"{len(run.flags)} flag(s) vs similar homes" + (": " + run.flags[0]["text"] if run.flags else ""))
    run.slots = slots(run.booked)
    run.step("calendar", f"next free site-visit slots: {', '.join(run.slots[:2])}")
    return True


# ---------- words: scripted ----------

def _why_scripted(name: str, d: dict, base: dict) -> str:
    e, c = d["economics"], d["components"]
    bat = f"{round(c['battery']['size'])} kWh battery" if c["battery"]["recommended"] and c["battery"]["size"] else "no battery"
    head = {"Basic": "Lowest price", "Recommended": "Best balance", "Independence": "Most independence"}[name]
    pb = f"payback ~{round(e['payback_years'])} yrs" if e.get("payback_years") else "no payback"
    return (f"{head}: {scripted.kwp(c['pv']['size'] or 0)} kWp PV, {bat}, {scripted.eur(d['price']['total_eur'])}; "
            f"autarky {round(e['autarky_pct'])}%, saves €{round(e['annual_savings_eur'], -1):,.0f}/yr, {pb}.")


def _checklist(facts: dict, design: dict) -> list[str]:
    items = ["Check roof condition, shading and usable area", "Check meter cabinet and space for inverter and battery"]
    if not facts.get("roof_area_sqm"):
        items.insert(0, "Measure the roof: area was not given (engine assumed a typical roof)")
    if facts.get("has_existing_pv"):
        items.append("Inspect the existing PV system (size, inverter, age) for integration")
    if design["components"]["wallbox"]["recommended"]:
        items.append("Plan the wallbox location and cable route to the parking spot")
    if design["components"]["heatpump"]["recommended"] or facts.get("heating_type") in ("gas", "oil"):
        items.append("Look at the current heating system and the space for a heat pump")
    return items


def _open_questions(design: dict) -> list[str]:
    names = {"roof_area_sqm": "roof area", "region": "federal state", "electricity_price_eur_per_kwh": "electricity price",
             "heating_demand_kwh": "heating demand", "house_size_sqm": "living space", "budget_eur": "budget",
             "roof_type": "roof shape", "building_type": "type of house"}
    qs = [f"{names.get(m['field'], m['field'].replace('_', ' '))}: {m['why']}" for m in design.get("missing_inputs", [])
          if m.get("impact") in ("high", "medium")]
    qs += [f"Assumed {a['field'].replace('_', ' ')}: {a['note']}" for a in design.get("assumptions", [])[:3]]
    return qs


def _draft_scripted(plan: dict, d: dict, slot: str) -> str:
    name = plan["customer"].get("name", "")
    return (f"Hello {name},\n\nthank you for planning your solar system with us. Based on your details we suggest "
            f"{scripted.headline(d).removeprefix('I would suggest ').removeprefix('I' + chr(39) + 'd suggest ')} "
            f"Before we confirm the final price we'd like to see your roof. Would {slot} suit you for a short site visit?\n\n"
            f"Best regards,\nSolarHaus Müller").replace("(estimate).", "(estimate).")


# ---------- words: Claude tool loop ----------

TOOLS = [
    {"name": "design_variant", "description": "Run the engine for one offer variant with the given component locks. "
     "Returns the design numbers. Use it to try a better lock set for a variant; the last call per name is kept.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string", "enum": NAMES},
         "locks": {"type": "object", "description": "e.g. {\"battery\": {\"recommended\": true, \"size\": 10}, \"heatpump\": {\"recommended\": false}}"}},
         "required": ["name", "locks"]}},
    {"name": "explain", "description": "Engine reasons and what-ifs for one component of the recommended design.",
     "input_schema": {"type": "object", "properties": {"component": {"type": "string", "enum": ["pv", "battery", "heatpump", "wallbox"]}},
                      "required": ["component"]}},
    {"name": "submit_pack", "description": "Finish: the words of the offer pack. Every number you write must appear in a design returned in this run.",
     "input_schema": {"type": "object", "properties": {
         "why": {"type": "object", "properties": {n: {"type": "string"} for n in NAMES}, "required": NAMES,
                 "description": "one or two sentences per variant for the planner: who it suits, the trade-off"},
         "recommended": {"type": "string", "enum": NAMES},
         "site_visit_checklist": {"type": "array", "items": {"type": "string"}},
         "open_questions": {"type": "array", "items": {"type": "string"}},
         "customer_message_draft": {"type": "string", "description": "short message from the planner to the customer, in the customer's language, proposing the site visit slot; prices only as estimates"}},
         "required": ["why", "recommended", "site_visit_checklist", "open_questions", "customer_message_draft"]}},
]

SYSTEM = """You are reo's offer agent at SolarHaus Müller. A customer handed over their plan; you prepare the offer pack for the planner.
You already have three engine designs (Basic, Recommended, Independence). You may call design_variant to try a better lock set
for a variant (at most twice) or explain for details, then you must call submit_pack.
Rules: every number you write (sizes, prices, savings, percentages, payback) must appear in an engine design from this run,
rounded at most. Prices to the customer are estimates. Never promise subsidies, dates other than the given slot, or savings.
The planner decides; actions are proposed only. Be concise and concrete."""


def _claude_words(run: Run, persona: str) -> dict | None:
    c = llm.client()
    if c is None:
        return None
    context = {"facts": run.facts, "customer_name": run.plan["customer"].get("name"),
               "designs": {n: _short(d) for n, d in run.designs.items()}, "flags": [f["text"] for f in run.flags],
               "missing_inputs": run.designs["Recommended"].get("missing_inputs", []),
               "assumptions": run.designs["Recommended"].get("assumptions", []),
               "proposed_site_visit_slot": run.slots[0],
               "customer_transcript": [m["text"] for m in run.plan["transcript"] if m["role"] == "customer"][-10:]}
    messages = [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
    system = SYSTEM + "\n\nCustomer-facing voice (for the draft message only):\n" + persona
    for _ in range(MAX_TURNS):
        try:
            r = c.beta.messages.create(model=llm.AGENT_MODEL, max_tokens=16000, system=system, tools=TOOLS, messages=messages,
                                       output_config={"effort": "medium"}, betas=["server-side-fallback-2026-07-01"],
                                       fallbacks="default")
        except anthropic.APIError as e:
            log.warning("offer agent LLM failed: %s", e)
            run.step("llm", f"Claude unavailable ({type(e).__name__}), scripted words")
            return None
        if r.stop_reason in ("refusal", "max_tokens"):
            run.step("llm", f"Claude stopped ({r.stop_reason}), scripted words")
            return None
        messages.append({"role": "assistant", "content": r.content})
        results = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            if b.name == "submit_pack":
                run.step("llm", "Claude wrote variant notes, checklist, open questions and the draft message")
                return b.input
            if b.name == "design_variant" and b.input.get("name") in NAMES and isinstance(b.input.get("locks"), dict):
                d = run.design(b.input["name"], b.input["locks"])
                out = _short(d) if d else {"error": "engine not reachable"}
            elif b.name == "explain":
                out = engine.explain(run.facts, b.input.get("component", "battery"), run.base_locks, run.prices) or {"error": "not available"}
                run.step("engine.explain", f"{b.input.get('component')}: requested by Claude")
            else:
                out = {"error": "invalid tool input"}
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, ensure_ascii=False)})
        if not results:
            run.step("llm", "Claude ended without submit_pack, scripted words")
            return None
        messages.append({"role": "user", "content": results})
    run.step("llm", "Claude used too many steps, scripted words")
    return None


def _euros_ok(text: str, designs: dict) -> bool:
    """Hard rule 2 check on Claude's text: every € amount must match a design total or price item (to the nearest 100)."""
    allowed = set()
    for d in designs.values():
        vals = [d["price"]["total_eur"], *d["price"]["range_eur"], d["economics"]["annual_savings_eur"],
                *(i["total_eur"] for i in d["price"]["items"])]
        allowed |= {round(v / 100) for v in vals} | {round(v / 10) * 10 for v in vals}
    for m in re.findall(r"€\s?(\d[\d.,]*)|(\d[\d.,]*)\s?€", text):
        n = float((m[0] or m[1]).replace(".", "").replace(",", "")) if re.search(r"\d[.,]\d{3}", m[0] or m[1]) else float((m[0] or m[1]).replace(",", "."))
        if round(n / 100) not in allowed and n not in allowed:
            return False
    return True


# ---------- the pack ----------

def prepare(plan: dict, st: dict, booked: list[str], persona: str) -> dict:
    t0 = time.time()
    run = Run(plan, st, booked)
    if not _fixed_steps(run):
        return {"status": "failed", "variants": [], "recommended": "Recommended", "flags": [], "site_visit_checklist": [],
                "open_questions": [], "customer_message_draft": "", "actions": [], "trace": run.trace,
                "duration_s": round(time.time() - t0, 1), "model": "none", "prepared_at": _now()}
    words = _claude_words(run, persona)
    model = llm.AGENT_MODEL
    if words and not all(_euros_ok(t, run.designs) for t in [words["customer_message_draft"], *words["why"].values()]):
        run.step("llm", "a € amount in Claude's text did not match any engine design, scripted words instead")
        words = None
    base = run.designs["Recommended"]
    if not words:
        model = "scripted"
        words = {"why": {n: _why_scripted(n, d, base) for n, d in run.designs.items()}, "recommended": "Recommended",
                 "site_visit_checklist": _checklist(run.facts, base), "open_questions": _open_questions(base),
                 "customer_message_draft": _draft_scripted(plan, base, run.slots[0])}
    rec = words["recommended"] if words["recommended"] in run.designs else "Recommended"
    variants = [{"name": n, "locks": run.locks[n], "design": run.designs[n], "why": words["why"].get(n, "")}
                for n in NAMES if n in run.designs]
    name = plan["customer"].get("name") or "the customer"
    actions = [
        {"id": "a1", "kind": "book_visit", "label": f"Book site visit {run.slots[0]}", "payload": {"slot": run.slots[0]}, "status": "proposed"},
        {"id": "a2", "kind": "send_quote", "label": f"Send quote ({rec} variant)",
         "payload": {"variant": rec, "message": words["customer_message_draft"]}, "status": "proposed"},
        {"id": "a3", "kind": "create_crm_task", "label": f"Follow up with {name} in 3 days",
         "payload": {"task": f"Follow up with {name}", "due_in_days": 3}, "status": "proposed"},
    ]
    docs = (["roof photos"] if not run.facts.get("roof_area_sqm") else []) + (["offer or datasheet of the existing PV"] if run.facts.get("has_existing_pv") else [])
    if docs:
        actions.append({"id": "a4", "kind": "request_document", "label": f"Ask {name} for {' and '.join(docs)}",
                        "payload": {"documents": docs}, "status": "proposed"})
    run.step("actions", f"{len(actions)} actions proposed, none executed (planner approves)")
    return {"status": "ready", "variants": variants, "recommended": rec, "flags": run.flags,
            "site_visit_checklist": words["site_visit_checklist"], "open_questions": words["open_questions"],
            "customer_message_draft": words["customer_message_draft"], "actions": actions, "trace": run.trace,
            "duration_s": round(time.time() - t0, 1), "model": model, "prepared_at": _now()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
