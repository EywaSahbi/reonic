"""Which question reo asks next, and when it offers the handoff. Follows experience/flow.md Stage 3 and 5."""

REGIONS = ["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"]  # engine HomeFacts.region

FOSSIL = {"gas", "oil", "district", "other"}   # heating that a heat pump could replace: the heat pump is offered as an option

# Prompts per field. The order is fixed by next_question() below (customer-backend flow of 2026-11-08).
QUESTIONS = [
    (("total_demand_kwh", "annual_demand_kwh"), {"field": "total_demand_kwh", "input": "number",
                                                  "prompt": "Roughly how many kWh of electricity do you use per year? It's on your bill."}),
    (("num_inhabitants",), {"field": "num_inhabitants", "input": "choice", "options": ["1", "2", "3", "4", "5+"],
                            "prompt": "No problem. How many people live in your home? I can estimate from that."}),
    (("roof_area_sqm", "roof_width_m"), {"field": "roof_area_sqm", "input": "address",
                          "prompt": "What's your address? I'll measure the roof from the map, or you can skip."}),
    (("region",), {"field": "region", "input": "choice", "options": REGIONS,
                   "prompt": "Which federal state? It sets how much sun your panels get."}),
    (("roof_dims",), {"field": "roof_dims", "input": "dimensions",
                      "prompt": "Sunny roof face: width × length (m)"}),
    (("has_ev", "ev_planned"), {"field": "has_ev", "input": "choice", "options": ["Yes, already", "Planned", "No"],
                                "prompt": "Do you have an electric car, or plan one? It changes the solar size."}),
    (("heating_type",), {"field": "heating_type", "input": "choice",
                         "options": ["gas", "oil", "heatpump", "electric", "district", "other"],
                         "prompt": "How do you heat today? It decides whether a heat pump fits."}),
    (("heatpump_option",), {"field": "heatpump_option", "input": "choice",
                            "options": ["Yes, show me the heat pump option", "No, keep my plan"],
                            "prompt": "Would you like to consider the heat pump option?"}),
    (("has_existing_pv",), {"field": "has_existing_pv", "input": "choice", "options": ["Yes, I have solar", "No solar yet"],
                            "prompt": "Do you already have solar on the roof?"}),
    (("existing_pv_kwp",), {"field": "existing_pv_kwp", "input": "number",
                            "prompt": "Roughly how big is it, in kWp? It's on the old offer or inverter."}),
]
ASK = {a["field"]: a for _, a in QUESTIONS}


# Chips shown with each ask (flow.md Stage 3 table).
CHIPS = {
    "total_demand_kwh": ["About 3,000 kWh", "About 4,500 kWh", "Skip"],
    "num_inhabitants": ["Skip"],
    "building_type": [],
    "heating_type": ["Gas", "Oil", "Heat pump already", "Other"],
    "has_ev": ["Yes, already", "Planned", "No"],
    "roof_area_sqm": ["Enter width × length", "Skip"],
    "region": ["Skip"],
    "roof_dims": ["Skip"],
    "has_existing_pv": ["Yes, I have solar", "No solar yet"],
    "existing_pv_kwp": ["About 5 kWp", "About 10 kWp", "Not sure"],
    "roof_type": [],
    "house_size_sqm": ["About 120 m²", "About 160 m²"],
    "electricity_price_eur_per_kwh": ["About 35 ct", "About 40 ct", "Not sure"],
    "budget_eur": ["Under €15,000", "€15,000–25,000", "No fixed budget"],
}
STANDING_CHIPS = ["Why this size?", "What does it cost?", "Send to installer"]
PEOPLE_ASK = {"field": "num_inhabitants", "prompt": "People in your home", "input": "choice", "options": ["1", "2", "3", "4", "5+"]}
DIMS_ASK = {"field": "roof_dims", "prompt": "Sunny roof face: width × length (m)", "input": "dimensions"}  # app sends /facts {roof_width_m, roof_length_m}
KWH_ASK = {"field": "total_demand_kwh", "prompt": "Yearly electricity use (kWh, from your bill)", "input": "number"}
OPENING_ASK = KWH_ASK


def ui_ask(ask: dict) -> dict:
    """The Turn.ask shape for the app: short prompt label, no explanation sentence."""
    label = {"num_inhabitants": "People in your home", "total_demand_kwh": "Yearly electricity use (kWh)", "roof_dims": "Roof width × length (m)", "building_type": "Type of house", "heating_type": "How do you heat today?", "has_ev": "Electric car?",
             "roof_area_sqm": "Your address (we measure the roof from the map)", "region": "Federal state", "has_existing_pv": "Solar already on the roof?", "heatpump_option": "Heat pump option", "existing_pv_kwp": "Existing solar (kWp)", "roof_type": "Roof shape", "house_size_sqm": "Living space (m²)",
             "electricity_price_eur_per_kwh": "Price per kWh (€)", "budget_eur": "Budget (€)"}
    out = {k: v for k, v in ask.items() if k != "prompt"}
    out["prompt"] = label.get(ask["field"], ask["prompt"])
    return out


def next_question(facts: dict, design: dict | None = None, skipped: set[str] = frozenset()) -> dict | None:
    """The one ask for this turn, or None when the flow is done. Fixed order, skips branch:
    kWh (skipped: people) -> address (skipped: roof width x length) -> EV -> heating (-> heat pump option).
    No federal-state and no existing-solar questions (EywaSahbi, 2026-11-08); volunteered facts still count."""
    def known(*names):
        return any(facts.get(n) is not None for n in names)
    roof = known("roof_area_sqm", "roof_width_m")
    if not known("total_demand_kwh", "annual_demand_kwh"):
        if "total_demand_kwh" not in skipped:
            return ASK["total_demand_kwh"]
        if not known("num_inhabitants") and "num_inhabitants" not in skipped:
            return ASK["num_inhabitants"]
    if not roof:
        if "roof_area_sqm" not in skipped and "roof_dims" not in skipped:
            return ASK["roof_area_sqm"]
        if "roof_dims" not in skipped:
            return ASK["roof_dims"]
    for field in ("has_ev", "heating_type"):
        if not known(*next(k for k, a in QUESTIONS if a["field"] == field)) and field not in skipped:
            return ASK[field]
    if facts.get("heating_type") in FOSSIL and "heatpump_option" not in skipped:   # "skipped" also holds closed asks
        return ASK["heatpump_option"]
    return None


def offer_handoff(facts: dict, design: dict | None = None, skipped: set[str] = frozenset()) -> bool:
    """The flow is done: offer the handoff."""
    return next_question(facts, design, skipped) is None
