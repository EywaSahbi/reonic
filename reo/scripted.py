"""Scripted mode: rule-based fact extraction and template replies.

Used for chip taps (instant, no LLM) and as the fallback when there is no API key or the LLM fails.
Templates only round and phrase engine numbers (persona rounding rules); they never compute new ones.
"""
import re

STATE_NAMES = [("baden-württemberg|baden-wuerttemberg", "BW"), ("bayern|bavaria|münchen|munich|nürnberg", "BY"),
               ("berlin", "BE"), ("brandenburg|potsdam", "BB"), ("bremen", "HB"), ("hamburg", "HH"), ("hessen|hesse|frankfurt", "HE"),
               ("mecklenburg", "MV"), ("niedersachsen|lower saxony|hannover", "NI"),
               ("nordrhein-westfalen|north rhine|nrw|köln|cologne|düsseldorf", "NW"), ("rheinland-pfalz|mainz", "RP"),
               ("saarland", "SL"), ("sachsen-anhalt|magdeburg", "ST"), ("sachsen|saxony|dresden|leipzig", "SN"),
               ("schleswig-holstein|kiel", "SH"), ("thüringen|thuringia|erfurt", "TH")]

# Exact chip / option texts -> facts (flow.md). Lower-cased.
CHIP_FACTS = {
    "1": {"num_inhabitants": 1}, "2": {"num_inhabitants": 2}, "3": {"num_inhabitants": 3},
    "4": {"num_inhabitants": 4}, "5+": {"num_inhabitants": 5}, "5": {"num_inhabitants": 5},
    "gas": {"heating_type": "gas"}, "oil": {"heating_type": "oil"}, "heatpump": {"heating_type": "heatpump"},
    "heat pump already": {"heating_type": "heatpump"}, "electric": {"heating_type": "electric"},
    "district": {"heating_type": "district"}, "other": {"heating_type": "other"},
    "yes, already": {"has_ev": True}, "planned": {"ev_planned": True}, "no": {"has_ev": False, "ev_planned": False},
    "about 3,000 kwh": {"total_demand_kwh": 3000}, "about 4,500 kwh": {"total_demand_kwh": 4500},
    "about 40 m²": {"roof_area_sqm": 40}, "about 60 m²": {"roof_area_sqm": 60},
    "about 120 m²": {"house_size_sqm": 120}, "about 160 m²": {"house_size_sqm": 160},
    "about 35 ct": {"electricity_price_eur_per_kwh": 0.35}, "about 40 ct": {"electricity_price_eur_per_kwh": 0.40},
    "under €15,000": {"budget_eur": 15000}, "€15,000–25,000": {"budget_eur": 25000},
    **{c.lower(): {"region": c} for c in ["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"]},
    "detached": {"building_type": "detached"}, "semi": {"building_type": "semi"}, "terraced": {"building_type": "terraced"},
}
CHIP_INTENTS = {
    "yes, send it": ("handoff", None), "send to installer": ("handoff", None), "send it": ("handoff", None),
    "not sure": ("skip", None), "no fixed budget": ("skip", None), "not yet": ("other", None),
    "i know my yearly kwh": ("kwh", None),
    "why this size?": ("question", "pv"), "what does it cost?": ("question", "price"),
    "what would make it cheaper?": ("question", "price"), "what if i skip it?": ("question", None),
}


def chip(text: str) -> dict | None:
    """Exact chip tap -> {"facts", "intent", "topic"}, or None if this is free text."""
    t = text.strip().lower()
    if t in CHIP_FACTS:
        return {"facts": dict(CHIP_FACTS[t]), "intent": "facts", "topic": None}
    if t in CHIP_INTENTS:
        intent, topic = CHIP_INTENTS[t]
        return {"facts": {}, "intent": intent, "topic": topic}
    return None


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "")) if re.fullmatch(r"\d{1,3}([.,]\d{3})+", s) else float(s.replace(",", "."))


def extract(text: str, last_field: str | None = None) -> dict:
    """Rule-based extraction for free text (demo phrases in flow.md, German and English)."""
    t = text.lower()
    facts: dict = {}
    if m := re.search(r"(\d[\d.,]*)\s*kwh", t):
        facts["total_demand_kwh"] = _num(m.group(1))  # as stated, incl. EV/heating (engine contract)
    if m := re.search(r"(\d+)\s*(people|persons|person|personen|leute)", t):
        facts["num_inhabitants"] = int(m.group(1))
    if m := re.search(r"(\d[\d.,]*)\s*(m²|m2|qm|square)", t):
        key = "roof_area_sqm" if re.search(r"roof|dach", t) or last_field == "roof_area_sqm" else (
            "house_size_sqm" if re.search(r"living|wohn|house|haus", t) else last_field or "roof_area_sqm")
        if key in ("roof_area_sqm", "house_size_sqm"):
            facts[key] = _num(m.group(1))
    if m := re.search(r"(\d+(?:[.,]\d+)?)\s*(ct|cent)", t):
        facts["electricity_price_eur_per_kwh"] = _num(m.group(1)) / 100
    for word, kind in [("gas", "gas"), ("öl", "oil"), ("oil", "oil"), ("heat pump", "heatpump"), ("wärmepumpe", "heatpump"),
                       ("district", "district"), ("fernwärme", "district")]:
        if re.search(rf"\b{word}", t):
            facts["heating_type"] = kind
            break
    if re.search(r"electric car|e-auto|elektroauto|\bev\b", t):
        planned = re.search(r"buy|next year|plan|getting|kaufen|nächstes jahr|planen|bald", t)
        no_car = re.search(r"\bno\b|kein", t)
        if no_car:
            facts.update(has_ev=False, ev_planned=False)
        else:
            facts["ev_planned" if planned else "has_ev"] = True
    for names, code in STATE_NAMES:
        if re.search(rf"({names})", t):
            facts["region"] = code
            break
    if not facts and last_field and (m := re.fullmatch(r"\s*(\d[\d.,]*)\s*", t)):
        facts[last_field] = _num(m.group(1))
    intent = "facts" if facts else "other"
    topic = None
    if re.search(r"\bwhy\b|warum|wieso|what if|was wäre|how much|wie viel|cost|kosten|teuer|save|spar", t):
        intent = "question" if not facts else intent
        for word, key in [("battery", "battery"), ("batterie", "battery"), ("speicher", "battery"), ("heat pump", "heatpump"),
                          ("wärmepumpe", "heatpump"), ("wallbox", "wallbox"), ("solar", "pv"), ("panel", "pv"),
                          ("cost", "price"), ("kost", "price"), ("teuer", "price"), ("price", "price"),
                          ("save", "savings"), ("spar", "savings")]:
            if word in t:
                topic = key
                break
    if re.search(r"send it|installer|installateur|offer|angebot|call me|anrufen|schick", t):
        intent = "handoff"
    if re.search(r"not sure|don't know|weiß nicht|keine ahnung|skip", t):
        intent = "skip"
    return {"facts": facts, "intent": intent, "topic": topic}


# ---------- phrasing (rounding only) ----------

def eur(x: float) -> str:
    return f"€{round(x / 100) * 100:,.0f}"


def kwp(x: float) -> str:
    return f"{round(x * 2) / 2:g}"


def headline(d: dict) -> str:
    c = d["components"]
    parts = []
    if c["pv"]["recommended"] and c["pv"]["size"]:
        panels = f" (around {c['pv']['quantity']} panels)" if c["pv"].get("quantity") else ""
        parts.append(f"about {kwp(c['pv']['size'])} kWp of solar{panels}")
    if c["battery"]["recommended"] and c["battery"]["size"]:
        parts.append(f"a {round(c['battery']['size'])} kWh battery")
    if c["heatpump"]["recommended"] and c["heatpump"]["size"]:
        parts.append(f"a {round(c['heatpump']['size'])} kW heat pump")
    if c["wallbox"]["recommended"] and c["wallbox"]["size"]:
        parts.append(f"an {round(c['wallbox']['size'])} kW wallbox")
    if not parts:
        return "I don't have a design to suggest yet."
    items = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    lo, hi = d["price"]["range_eur"]
    return f"I'd suggest {items}. That would cost roughly {eur(lo)}–{eur(hi)[1:]} (estimate)."


def changes(before: dict | None, after: dict) -> str | None:
    """What changed between two designs, phrased from engine values; None if nothing visible changed."""
    if not before or before.get("params_version") == "engine-offline":
        return None
    out = []
    for key, name in [("pv", "the solar"), ("battery", "the battery"), ("heatpump", "a heat pump"), ("wallbox", "a wallbox")]:
        b, a = before["components"][key], after["components"][key]
        unit = a["unit"]
        size = (kwp(a["size"]) if key == "pv" else str(round(a["size"]))) if a["size"] else None
        if a["recommended"] and not b["recommended"]:
            out.append(f"added {name.replace('the ', 'a ')}" + (f" ({size} {unit})" if size else ""))
        elif b["recommended"] and not a["recommended"]:
            out.append(f"removed {name.replace('a ', 'the ')}")
        elif a["recommended"] and a["size"] != b["size"] and size:
            out.append(f"{'raised' if (a['size'] or 0) > (b['size'] or 0) else 'lowered'} {name.replace('a ', 'the ')} to about {size} {unit}")
    return ", ".join(out) if out else None


def answer(d: dict, topic: str | None) -> str:
    """Answer a why / cost / savings question from the engine result."""
    c = d["components"]
    if topic in ("pv", "battery", "heatpump", "wallbox"):
        comp = c[topic]
        name = {"pv": "solar size", "battery": "battery", "heatpump": "heat pump", "wallbox": "wallbox"}[topic]
        why = "; ".join(comp["reasons"]) or "no reason recorded"
        return (f"The {name}: {why}." if comp["recommended"] else f"No {name} for now: {why}.")
    if topic == "price":
        top = sorted(d["price"]["items"], key=lambda i: -i["total_eur"])[:2]
        if not top:
            return "I can't break the price down yet."
        parts = " and ".join(f"the {i['label'].lower()} (about {eur(i['total_eur'])})" for i in top)
        return f"Most of the cost is {parts}. All prices are estimates until your planner confirms them."
    if topic == "savings":
        e = d["economics"]
        pb = f"pays for itself in about {round(e['payback_years'])} years" if e["payback_years"] else "doesn't pay back on savings alone"
        return f"You'd save around €{round(e['annual_savings_eur'], -1):,.0f} a year, and it {pb}."
    return f"The solar size: {'; '.join(c['pv']['reasons']) or 'no reason recorded'}."


def summary(plan: dict) -> str:
    """Installer summary paragraph (flow.md 'Plan summary'), from facts, transcript and the engine result."""
    f, d = plan["facts"], plan["design"]
    home = []
    if f.get("num_inhabitants"):
        home.append(f"{f['num_inhabitants']}-person home")
    if kwh := f.get("total_demand_kwh") or f.get("annual_demand_kwh"):
        home.append(f"{kwh:,.0f} kWh/yr")
    if f.get("heating_type"):
        home.append(f"{f['heating_type']} heating")
    if f.get("has_ev"):
        home.append("has an EV")
    elif f.get("ev_planned"):
        home.append("EV planned")
    if f.get("roof_area_sqm"):
        home.append(f"roof {f['roof_area_sqm']:g} m²")
    assumed = [a["field"] for a in d.get("assumptions", [])]
    s = (", ".join(home) or "Few facts given") + (f"; assumed: {', '.join(assumed)}." if assumed else ".")
    asks = sum(1 for m in plan["transcript"] if m["role"] == "customer" and re.search(r"cost|price|kost|teuer|€", m["text"].lower()))
    if asks:
        s += f" Customer asked {asks}x about cost."
    if d.get("params_version") != "engine-offline":
        c = d["components"]
        comps = [f"{kwp(c[k]['size']) if k == 'pv' else round(c[k]['size'])} {c[k]['unit']} {n}"
                 for k, n in [("pv", "PV"), ("battery", "battery"), ("heatpump", "heat pump"), ("wallbox", "wallbox")]
                 if c[k]["recommended"] and c[k]["size"]]
        lo, hi = d["price"]["range_eur"]
        pb = d["economics"]["payback_years"]
        s += f" Proposal: {', '.join(comps) or 'no components'}; {eur(d['price']['total_eur'])} (range {eur(lo)}–{eur(hi)[1:]})"
        s += f", payback ~{round(pb)} yrs." if pb else ", no payback."
    check = [m["field"] for m in d.get("missing_inputs", []) if m["impact"] == "high"] + [fl["text"] for fl in plan.get("flags", [])]
    if check:
        s += f" Check: {'; '.join(check)}."
    return s
