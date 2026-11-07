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
    loop: bool = True  # False: always the fixed tool sequence (fast, deterministic); the model only phrases elsewhere
    label: Callable[[Ctx], str] | None = None  # model name shown on the run when loop is False


# ---------- offer_prep ----------

def _why(name: str, d: dict) -> str:
    e, c = d["economics"], d["components"]
    bat = f"{scripted.rnd(c['battery']['size'])} kWh battery" if c["battery"]["recommended"] and c["battery"]["size"] else "no battery"
    head = {"Basic": "Lowest price", "Recommended": "Best balance", "Independence": "Most independence"}[name]
    pb = f"payback about {scripted.rnd(e['payback_years'])} years" if e.get("payback_years") else "no payback on savings alone"
    return (f"{head}: {scripted.kwp(c['pv']['size'] or 0)} kWp PV, {bat}, about {scripted.eur(d['price']['total_eur'])}; "
            f"autarky {scripted.rnd(e['autarky_pct'])}%, saves about €{scripted.rnd(e['annual_savings_eur'], 10):,.0f} a year, {pb}.")


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
    return (f"Hello {name},\n\nthank you for planning your solar system with Sonnfeld. Based on your details we suggest "
            f"{suggestion} Before we confirm the final price we would like to see your roof. Would {slot} suit you for a short "
            f"site visit?\n\nBest regards,\nSonnfeld")


def _total(ctx: Ctx, name: str) -> float:
    return ctx.variants[name]["design"]["price"]["total_eur"] if name in ctx.variants else 0


def _make_distinct(ctx: Ctx, call) -> None:
    """If an anchor variant came out like Recommended, use the engine's one-step what-ifs instead (cheaper / dearer)."""
    rec = _total(ctx, "Recommended")
    whatifs = []
    for comp in ("battery", "pv"):
        whatifs += [w for w in call("engine.explain", {"component": comp}).get("what_if", []) if w.get("locks")]
    if _total(ctx, "Basic") >= rec:
        for w in sorted((w for w in whatifs if w["delta"]["price_eur"] < 0), key=lambda w: -w["delta"]["price_eur"]):
            call("plan.propose_variant", {"name": "Basic", "locks": {"heatpump": {"recommended": False}, **w["locks"]}, "why": ""})
            if _total(ctx, "Basic") < rec:
                break
    if _total(ctx, "Independence") <= rec:
        for w in sorted((w for w in whatifs if w["delta"]["price_eur"] > 0), key=lambda w: (w["delta"]["autarky_pct"] <= 0, w["delta"]["price_eur"])):
            call("plan.propose_variant", {"name": "Independence", "locks": w["locks"], "why": ""})
            if _total(ctx, "Independence") > rec:
                break


def offer_scripted(ctx: Ctx, call) -> None:
    call("plan.read", {})
    pct = call("evidence.percentile", {})
    anchors = pct.get("anchors") or {"Basic": {"battery": {"recommended": False}, "heatpump": {"recommended": False}},
                                     "Recommended": {}, "Independence": {}}
    for n in NAMES:
        call("plan.propose_variant", {"name": n, "locks": anchors.get(n, {}), "why": ""})
    if "Recommended" not in ctx.variants:
        return  # engine down: completeness guard reports it
    _make_distinct(ctx, call)
    for n, v in ctx.variants.items():
        v["why"] = _why(n, v["design"])
    base = ctx.variants["Recommended"]["design"]
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
    totals = [v["design"]["price"]["total_eur"] for v in ctx.variants.values()]
    if len(set(totals)) < 3:
        return "the three variants must differ (Basic cheaper, Independence dearer than Recommended)"
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
            "customer_message_draft": ctx.draft, "draft_for": rec, "actions": ctx.actions, "trace": trace, "run_id": run["id"],
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

# ---------- goal_planner: deterministic search over engine variants ----------

GOAL_TEXT = {"budget": "within budget", "independence": "most independence", "lowest_bill": "lowest monthly bill"}


def _score(goal: str, d: dict, budget: float | None):
    e, total = d["economics"], d["total_eur"]
    if goal == "budget":
        fits = budget is None or total <= budget
        return (fits, e["autarky_pct"] if fits else -total, -total)
    if goal == "lowest_bill":
        bill = e.get("bill_after_eur_per_month")
        return (-(bill if bill is not None else -e["annual_savings_eur"] / 12), -total)
    return (e["autarky_pct"], -total)  # independence


def _goal_why(label: str, d: dict) -> str:
    c, e = d["components"], d["economics"]
    parts = [f"{scripted.kwp(c['pv']['size'])} kWp PV" if c["pv"]["recommended"] and c["pv"]["size"] else None,
             f"{scripted.rnd(c['battery']['size'])} kWh battery" if c["battery"]["recommended"] and c["battery"]["size"] else "no battery",
             f"{scripted.rnd(c['heatpump']['size'])} kW heat pump" if c["heatpump"]["recommended"] and c["heatpump"]["size"] else None,
             f"{scripted.rnd(c['wallbox']['size'])} kW wallbox" if c["wallbox"]["recommended"] and c["wallbox"]["size"] else None]
    bill = e.get("bill_after_eur_per_month")
    money = "" if bill is None else (f", monthly bill about €{scripted.rnd(bill)}" if bill >= 0 else f", net feed-in credit about €{scripted.rnd(-bill)} a month")
    return f"{label}: {', '.join(p for p in parts if p)}; about {scripted.eur(d['total_eur'])}, autarky {scripted.rnd(e['autarky_pct'])}%{money}."


def goal_scripted(ctx: Ctx, call) -> None:
    goal, budget = ctx.inputs.get("goal", "independence"), ctx.facts.get("budget_eur")
    options = [{}]
    for comp in ("battery", "pv", "heatpump", "wallbox"):
        options += [w["locks"] for w in call("engine.explain", {"component": comp}).get("what_if", []) if w.get("locks")]
    if ctx.facts.get("has_ev") or ctx.facts.get("ev_planned"):  # an EV home keeps its wallbox
        options = [o for o in options if o.get("wallbox", {}).get("recommended", True)]
    anchors = call("evidence.percentile", {}).get("anchors") or {}
    options += [anchors[k] for k in ("Basic", "Independence") if anchors.get(k)]
    seen, scored = set(), []
    for locks in options:
        key = json.dumps(locks, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        d = call("engine.design", {"locks": locks})
        if "error" not in d:
            scored.append((locks, d))
    if not scored:
        return
    scored.sort(key=lambda x: _score(goal, x[1], budget), reverse=True)
    best, picks, totals = scored[0], [scored[0]], {scored[0][1]["total_eur"]}
    for cand in scored[1:]:
        if cand[1]["total_eur"] not in totals:
            picks.append(cand)
            totals.add(cand[1]["total_eur"])
        if len(picks) == 3:
            break
    ctx.candidates = [d for _, d in scored]
    for i, (locks, d) in enumerate(picks):
        name = "Recommended" if i == 0 else ("Basic" if d["total_eur"] < best[1]["total_eur"] else "Independence")
        if name in ctx.variants:
            name = "Basic" if name == "Independence" else "Independence"
        label = f"Best for {GOAL_TEXT[goal]}" if i == 0 else "Alternative"
        call("plan.propose_variant", {"name": name, "locks": locks, "why": _goal_why(label, d)})
    fits = budget is None or goal != "budget" or best[1]["total_eur"] <= budget
    call("finish", {"recommended": "Recommended",
                    "summary": f"{len(scored)} engine variants compared for {GOAL_TEXT[goal]}" + ("" if fits else "; none fits the budget, cheapest shown")})


def goal_output(ctx: Ctx, run: dict) -> dict:
    rec = ctx.variants.get("Recommended")
    budget = ctx.facts.get("budget_eur")
    return {"goal": ctx.inputs.get("goal"), **({"budget_eur": budget} if budget and ctx.inputs.get("goal") == "budget" else {}),
            "recommendation": rec, "alternatives": [v for n, v in ctx.variants.items() if n != "Recommended"],
            "fits_budget": bool(rec) and (not budget or rec["design"]["price"]["total_eur"] <= budget),
            "trace": [{"step": i + 1, "tool": s.get("tool", s["kind"]), "summary": s["result_summary"]}
                      for i, s in enumerate(x for x in run["steps"] if x["kind"] in ("tool", "guard"))],
            "run_id": run["id"], "summary": (ctx.finish or {}).get("summary", "")}


GOAL_PLANNER = Skill(
    name="goal_planner", model=lambda: llm.AGENT_MODEL,
    tools=["engine.design", "engine.explain", "evidence.percentile", "plan.propose_variant", "finish"],
    max_steps=8, max_seconds=30, effort="low", prompt=lambda: "", context=lambda ctx: "",
    scripted=goal_scripted, texts=lambda ctx: [v["why"] for v in ctx.variants.values()],
    missing=lambda ctx: None if "Recommended" in ctx.variants else "no variant found",
    output=goal_output, loop=False,
)


# ---------- bill_reader: vision reads the bill, facts wait for the customer's confirmation ----------

def bill_scripted(ctx: Ctx, call) -> None:
    got = call("bill.read", {})
    ctx.inputs["read"] = {} if "error" in got else got
    call("finish", {"recommended": "Recommended", "summary": "bill read" if ctx.inputs["read"] else "could not read the bill"})


BILL_READER = Skill(
    name="bill_reader", model=lambda: llm.MODEL, tools=["bill.read", "finish"], max_steps=2, max_seconds=40, effort="low",
    prompt=lambda: "", context=lambda ctx: "", scripted=bill_scripted, texts=lambda ctx: [],
    missing=lambda ctx: None, output=lambda ctx, run: {"read": ctx.inputs.get("read", {}), "run_id": run["id"]},
    loop=False, label=lambda ctx: f"{llm.MODEL} (vision)" if llm.client() else "scripted",
)

# ---------- installer_qa: the planner's "why ...?" / "what if ...?" ----------

def qa_scripted(ctx: Ctx, call) -> None:
    q = ctx.inputs.get("question", "")
    topic = scripted.extract(q)["topic"] or "pv"
    d = call("engine.design", {})
    if "error" in d:
        return
    comp = topic if topic in ("pv", "battery", "heatpump", "wallbox") else "pv"
    ex = call("engine.explain", {"component": comp})
    c = d["components"][comp]
    head = (f"{comp}: {c['size']:g} {c['unit']} because " if c["recommended"] and c["size"] else f"{comp}: not recommended because ") \
        + "; ".join(c["reasons"]) + "."
    whatifs = [f"{w['change']}: {w.get('effect', '')}".rstrip(': ') for w in ex.get('what_if', [])[:2]] if 'error' not in ex else []
    call("finish", {"summary": head + (" What-ifs: " + " | ".join(whatifs) + "." if whatifs else "")})


INSTALLER_QA = Skill(
    name="installer_qa", model=lambda: llm.AGENT_MODEL,
    tools=["plan.read", "engine.design", "engine.explain", "evidence.percentile", "finish"],
    max_steps=6, max_seconds=45, effort="low",
    prompt=lambda: (PROMPTS / "installer_qa.md").read_text(encoding="utf-8"),
    context=lambda ctx: json.dumps({"planner_question": ctx.inputs.get("question"), "plan_id": ctx.plan["id"]}, ensure_ascii=False),
    scripted=qa_scripted, texts=lambda ctx: [(ctx.finish or {}).get("summary", "")],
    missing=lambda ctx: None if (ctx.finish or {}).get("summary") else "no answer",
    output=lambda ctx, run: {"answer": (ctx.finish or {}).get("summary", ""), "run_id": run["id"]},
)

SKILLS = {s.name: s for s in [OFFER_PREP, GOAL_PLANNER, BILL_READER, INSTALLER_QA]}
