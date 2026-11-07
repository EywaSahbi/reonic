"""Skills = prompt + allowed tools + budget + output. The same runner executes them with Claude or scripted."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import llm
import scripted
from harness.tools import Ctx

PROMPTS = Path(__file__).parent / "skills"
NAMES = ["Basic", "Recommended", "Independence"]


@dataclass
class Skill:
    name: str
    model: Callable[[], str]
    tools: list[str]
    max_steps: int
    max_seconds: int
    effort: str
    prompt: Callable[[], str]
    context: Callable[[Ctx], str]
    scripted: Callable[[Ctx, Callable], None]
    texts: Callable[[Ctx], list[str]]
    missing: Callable[[Ctx], str | None]
    output: Callable[[Ctx, dict], dict]


# ---------- offer_prep ----------

def _why(name: str, d: dict) -> str:
    e, c = d["economics"], d["components"]
    bat = f"{round(c['battery']['size'])} kWh battery" if c["battery"]["recommended"] and c["battery"]["size"] else "no battery"
    head = {"Basic": "Lowest price", "Recommended": "Best balance", "Independence": "Most independence"}[name]
    pb = f"payback about {round(e['payback_years'])} years" if e.get("payback_years") else "no payback on savings alone"
    return (f"{head}: {scripted.kwp(c['pv']['size'] or 0)} kWp PV, {bat}, about {scripted.eur(d['price']['total_eur'])}; "
            f"autarky {round(e['autarky_pct'])}%, saves about €{round(e['annual_savings_eur'], -1):,.0f} a year, {pb}.")


def _checklist(facts: dict, d: dict) -> list[str]:
    items = ["Check roof condition, shading and usable area", "Check meter cabinet and space for inverter and battery"]
    if not facts.get("roof_area_sqm"):
        items.insert(0, "Measure the roof: no area given, the engine assumed a typical roof")
    if facts.get("has_existing_pv"):
        items.append("Inspect the existing PV system (size, inverter, age) for integration")
    if d["components"]["wallbox"]["recommended"]:
        items.append("Plan the wallbox location and cable route to the parking spot")
    if d["components"]["heatpump"]["recommended"] or facts.get("heating_type") in ("gas", "oil"):
        items.append("Look at the current heating system and the space for a heat pump")
    return items


def _questions(d: dict) -> list[str]:
    names = {"roof_area_sqm": "Roof area", "region": "Federal state", "electricity_price_eur_per_kwh": "Electricity price",
             "heating_demand_kwh": "Heating demand", "house_size_sqm": "Living space", "budget_eur": "Budget",
             "roof_type": "Roof shape", "building_type": "Type of house"}
    qs = [f"{names.get(m['field'], m['field'].replace('_', ' ').capitalize())} unknown: {m['why']}"
          for m in d.get("missing_inputs", []) if m.get("impact") in ("high", "medium")]
    return qs + [f"Assumed: {a['note']}" for a in d.get("assumptions", [])[:3] if a.get("note")]


def _draft(name: str, d: dict, slot: str) -> str:
    suggestion = scripted.headline(d).removeprefix("I'd suggest ")
    return (f"Hello {name},\n\nthank you for planning your solar system with SolarHaus Müller. Based on your details we suggest "
            f"{suggestion} Before we confirm the final price we would like to see your roof. Would {slot} suit you for a short "
            f"site visit?\n\nBest regards,\nSolarHaus Müller")


def offer_scripted(ctx: Ctx, call) -> None:
    call("plan.read", {})
    pct = call("evidence.percentile", {})
    anchors = pct.get("anchors") or {"Basic": {"battery": {"recommended": False}, "heatpump": {"recommended": False}},
                                     "Recommended": {}, "Independence": {}}
    for n in NAMES:
        r = call("plan.propose_variant", {"name": n, "locks": anchors.get(n, {}), "why": ""})
        if "error" not in r:
            ctx.variants[n]["why"] = _why(n, ctx.variants[n]["design"])
    if "Recommended" not in ctx.variants:
        return  # engine down: completeness guard reports it
    base = ctx.variants["Recommended"]["design"]
    call("engine.explain", {"component": "battery"})
    slot = call("calendar.slots", {})["slots"][0]
    name = ctx.plan["customer"].get("name") or "the customer"
    call("plan.propose_action", {"kind": "book_visit", "label": f"Book site visit {slot}", "payload": {"slot": slot}})
    call("plan.propose_action", {"kind": "send_quote", "label": "Send quote (Recommended variant)", "payload": {"variant": "Recommended"}})
    call("plan.propose_action", {"kind": "create_crm_task", "label": f"Follow up with {name} in 3 days",
                                 "payload": {"task": f"Follow up with {name}", "due_in_days": 3}})
    docs = (["roof photos"] if not ctx.facts.get("roof_area_sqm") else []) + \
           (["offer or datasheet of the existing PV"] if ctx.facts.get("has_existing_pv") else [])
    if docs:
        call("plan.propose_action", {"kind": "request_document", "label": f"Ask {name} for {' and '.join(docs)}",
                                     "payload": {"documents": docs}})
    for q in _questions(base):
        call("plan.add_question", {"text": q})
    for item in _checklist(ctx.facts, base):
        call("plan.add_question", {"text": item, "kind": "site_visit"})
    call("plan.draft_message", {"text": _draft(ctx.plan["customer"].get("name", ""), base, slot)})
    call("finish", {"recommended": "Recommended", "summary": "Three variants from the engine, actions proposed for your approval."})


def offer_texts(ctx: Ctx) -> list[str]:
    return [v["why"] for v in ctx.variants.values()] + [ctx.draft] + ctx.questions + ctx.checklist + \
           [(ctx.finish or {}).get("summary", "")]


def offer_missing(ctx: Ctx) -> str | None:
    gaps = [n for n in NAMES if n not in ctx.variants]
    if gaps:
        return f"missing variants: {', '.join(gaps)}"
    if not ctx.draft:
        return "no draft message"
    if not any(a["kind"] == "send_quote" for a in ctx.actions):
        return "no send_quote action"
    return None


def offer_output(ctx: Ctx, run: dict) -> dict:
    rec = (ctx.finish or {}).get("recommended") if (ctx.finish or {}).get("recommended") in ctx.variants else "Recommended"
    for a in ctx.actions:
        if a["kind"] == "send_quote":
            a["payload"] = {"variant": a["payload"].get("variant", rec), "message": ctx.draft}
    trace = [{"step": i + 1, "tool": s.get("tool", s["kind"]), "summary": s["result_summary"]}
             for i, s in enumerate(x for x in run["steps"] if x["kind"] in ("tool", "guard"))]
    ready = offer_missing(ctx) is None
    return {"status": "ready" if ready else "failed", "variants": [ctx.variants[n] for n in NAMES if n in ctx.variants],
            "recommended": rec, "flags": ctx.flags, "site_visit_checklist": ctx.checklist, "open_questions": ctx.questions,
            "customer_message_draft": ctx.draft, "actions": ctx.actions, "trace": trace, "run_id": run["id"],
            "model": run["model"], "summary": (ctx.finish or {}).get("summary", "")}


OFFER_PREP = Skill(
    name="offer_prep", model=lambda: llm.AGENT_MODEL,
    tools=["plan.read", "evidence.percentile", "engine.design", "engine.explain", "calendar.slots", "plan.propose_variant",
           "plan.propose_action", "plan.add_question", "plan.draft_message", "finish"],
    max_steps=14, max_seconds=150, effort="medium",
    prompt=lambda: (PROMPTS / "offer_prep.md").read_text(encoding="utf-8") + "\n\nCustomer-facing voice (draft message only):\n"
                   + llm.PERSONA_FILE.read_text(encoding="utf-8"),
    context=lambda ctx: json.dumps({"task": "prepare the offer pack", "plan_id": ctx.plan["id"],
                                    "customer_name": ctx.plan["customer"].get("name")}, ensure_ascii=False),
    scripted=offer_scripted, texts=offer_texts, missing=offer_missing, output=offer_output,
)

SKILLS = {s.name: s for s in [OFFER_PREP]}
