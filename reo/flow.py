"""Which question reo asks next, and when it offers the handoff. Follows experience/flow.md Stage 3 and 5."""

REGIONS = ["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"]  # engine HomeFacts.region
ALWAYS_ASK = {"heating_type", "has_ev"}  # flow.md: the two facts that change the design most; engine only assumes them

# (fields that count as "known", ask) in the order of flow.md Stage 3.
QUESTIONS = [
    (("building_type",), {"field": "building_type", "input": "choice", "options": ["detached", "semi", "terraced"],
                          "prompt": "What kind of house is it? That tells me roughly how much roof and heating you have."}),
    (("heating_type",), {"field": "heating_type", "input": "choice",
                         "options": ["gas", "oil", "heatpump", "electric", "district", "other"],
                         "prompt": "How do you heat today? That decides whether a heat pump makes sense."}),
    (("has_ev", "ev_planned"), {"field": "has_ev", "input": "choice", "options": ["Yes, already", "Planned", "No"],
                                "prompt": "Do you have an electric car, or plan to get one? It changes the solar size and adds a wallbox."}),
    (("roof_area_sqm",), {"field": "roof_area_sqm", "input": "address",
                          "prompt": "How big is the roof area that faces the sun? Or give me your address and I'll look it up."}),
    (("region",), {"field": "region", "input": "choice", "options": REGIONS,
                   "prompt": "Which federal state do you live in? That sets how much sun your panels get."}),
    (("house_size_sqm",), {"field": "house_size_sqm", "input": "number",
                           "prompt": "How big is the living space, and roughly when was the house built? That sizes the heat pump."}),
    (("electricity_price_eur_per_kwh",), {"field": "electricity_price_eur_per_kwh", "input": "number",
                                          "prompt": "What do you pay per kWh? I've assumed a typical rate so far."}),
    (("budget_eur",), {"field": "budget_eur", "input": "number",
                       "prompt": "Do you have a budget in mind? Then I can show what fits."}),
]


# Chips shown with each ask (flow.md Stage 3 table).
CHIPS = {
    "building_type": [],
    "heating_type": ["Gas", "Oil", "Heat pump already", "Other"],
    "has_ev": ["Yes, already", "Planned", "No"],
    "roof_area_sqm": ["About 40 m²", "About 60 m²", "Not sure"],
    "region": [],
    "house_size_sqm": ["About 120 m²", "About 160 m²"],
    "electricity_price_eur_per_kwh": ["About 35 ct", "About 40 ct", "Not sure"],
    "budget_eur": ["Under €15,000", "€15,000–25,000", "No fixed budget"],
}
STANDING_CHIPS = ["Why this size?", "What does it cost?", "Send to installer"]
OPENING_ASK = {"field": "num_inhabitants", "prompt": "People in your home", "input": "choice", "options": ["1", "2", "3", "4", "5+"]}
KWH_ASK = {"field": "total_demand_kwh", "prompt": "Yearly electricity use (kWh, from your bill)", "input": "number"}


def ui_ask(ask: dict) -> dict:
    """The Turn.ask shape for the app: short prompt label, no explanation sentence."""
    label = {"building_type": "Type of house", "heating_type": "How do you heat today?", "has_ev": "Electric car?",
             "roof_area_sqm": "Roof area facing the sun (m²) or your address", "region": "Federal state", "house_size_sqm": "Living space (m²)",
             "electricity_price_eur_per_kwh": "Price per kWh (€)", "budget_eur": "Budget (€)"}
    out = {k: v for k, v in ask.items() if k != "prompt"}
    out["prompt"] = label.get(ask["field"], ask["prompt"])
    return out


def _missing(design: dict | None, impact: str) -> set[str]:
    return {m["field"] for m in (design or {}).get("missing_inputs", []) if m.get("impact") == impact}


def _askable(design: dict | None) -> set[str]:
    """Worth asking: heating and EV always, otherwise what the engine lists as high or medium impact.
    Without an engine result, fall back to flow.md's main rows."""
    if design is None:
        return ALWAYS_ASK | {"roof_area_sqm"}
    return ALWAYS_ASK | {m["field"] for m in design.get("missing_inputs", []) if m.get("impact") in ("high", "medium")}


def next_question(facts: dict, design: dict | None, skipped: set[str] = frozenset()) -> dict | None:
    """The one ask for this turn, or None when nothing important is left."""
    open_qs = []
    for known, ask in QUESTIONS:
        if any(facts.get(f) is not None for f in known) or ask["field"] in skipped:
            continue
        if ask["field"] not in _askable(design):
            continue
        if ask["field"] == "house_size_sqm" and not (design or {}).get("components", {}).get("heatpump", {}).get("recommended"):
            continue  # only size the heat pump when it is in play
        open_qs.append(ask)
    if not open_qs:
        return None  # nothing worth asking left (flow.md stop rule)
    high = _missing(design, "high")
    return next((q for q in open_qs if q["field"] in high), open_qs[0])


def offer_handoff(facts: dict, design: dict | None, skipped: set[str] = frozenset()) -> bool:
    """flow.md Stage 5: heating and EV known, or nothing worth asking is left."""
    ev_known = facts.get("has_ev") is not None or facts.get("ev_planned") is not None
    return (facts.get("heating_type") is not None and ev_known) or next_question(facts, design, skipped) is None
