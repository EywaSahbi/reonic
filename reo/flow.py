"""Which question reo asks next, and when it offers the handoff. Follows experience/flow.md Stage 3 and 5."""

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
    (("house_size_sqm",), {"field": "house_size_sqm", "input": "number",
                           "prompt": "How big is the living space, and roughly when was the house built? That sizes the heat pump."}),
    (("electricity_price_eur_per_kwh",), {"field": "electricity_price_eur_per_kwh", "input": "number",
                                          "prompt": "What do you pay per kWh? I've assumed a typical rate so far."}),
    (("budget_eur",), {"field": "budget_eur", "input": "number",
                       "prompt": "Do you have a budget in mind? Then I can show what fits."}),
]


def _missing(design: dict | None, impact: str) -> set[str]:
    return {m["field"] for m in (design or {}).get("missing_inputs", []) if m.get("impact") == impact}


def _askable(design: dict | None) -> set[str]:
    """Fields the engine knows about. building_type joins only once the engine ships it."""
    return {m["field"] for m in (design or {}).get("missing_inputs", [])} | {
        "heating_type", "has_ev", "roof_area_sqm", "electricity_price_eur_per_kwh", "budget_eur"}


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
        return None
    high = _missing(design, "high")
    if design and not high:
        return None  # flow.md: stop once the engine has no high-impact inputs left
    return next((q for q in open_qs if q["field"] in high), open_qs[0])


def offer_handoff(facts: dict, design: dict | None) -> bool:
    ev_known = facts.get("has_ev") is not None or facts.get("ev_planned") is not None
    return (facts.get("heating_type") is not None and ev_known) or (design is not None and not _missing(design, "high"))
