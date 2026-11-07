"""reo's LLM layer: Claude reads what people write and phrases reo's replies.

Numbers never come from here (hard rule 2): extract() turns words into facts, reply() phrases an
engine result. Both return None when there is no API key or the call fails, so the caller falls
back to the scripted mode and the demo never depends on the network.

Check your key:   uv run python llm.py --check
Try one turn:     uv run python llm.py "we use about 4,500 kWh a year"   (needs the engine on :8000)
"""
import json
import logging
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

MODEL = os.getenv("REO_MODEL", "claude-haiku-5-5")  # chat turns + bill photo (EywaSahbi: fast and cheap)
AGENT_MODEL = os.getenv("REO_AGENT_MODEL", "claude-sonnet-5-5")  # offer agent (EywaSahbi)


def fallback_kwargs(model: str) -> dict:
    """Server-side refusal fallback where the model supports it (not on Haiku 5.5)."""
    if "haiku" in model:
        return {}
    return {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
EFFORT = os.getenv("REO_EFFORT", "low")  # chat turns; low keeps replies fast
PERSONA_FILE = HERE.parent / "experience" / "persona.md"  # owned by app, loaded as is
RULES_FILE = HERE / "prompt.md"
log = logging.getLogger("reo.llm")

# HomeFacts field -> type. The model returns facts as a list of {field, value-as-text}; a flat schema
# compiles fast, while one optional property per field is rejected by the API as too complex.
HEATING = ["gas", "oil", "heatpump", "electric", "district", "other"]
FACT_TYPES = {
    "total_demand_kwh": float, "annual_demand_kwh": float, "num_inhabitants": int, "house_size_sqm": float, "house_built_year": int,
    "heating_type": str, "heating_demand_kwh": float, "has_ev": bool, "ev_planned": bool,
    "ev_km_per_year": float, "ev_km_per_week": float, "ev_km_per_day": float,
    "roof_area_sqm": float, "roof_orientation_deg": float, "roof_tilt_deg": float,
    "electricity_price_eur_per_kwh": float, "has_existing_pv": bool, "existing_pv_kwp": float,
    "has_existing_battery": bool, "budget_eur": float, "region": str, "building_type": str, "roof_type": str,
}
ENUMS = {"heating_type": HEATING, "building_type": ["detached", "semi", "terraced"], "roof_type": ["gable", "flat", "mono", "other"]}
REGIONS = ["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"]
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {"type": "array", "items": {
            "type": "object",
            "properties": {"field": {"type": "string", "enum": list(FACT_TYPES)}, "value": {"type": "string"}},
            "required": ["field", "value"], "additionalProperties": False}},
        "intent": {"type": "string", "enum": ["facts", "question", "skip", "handoff", "goal", "other"]},
        "topic": {"type": "string", "enum": ["pv", "battery", "heatpump", "wallbox", "price", "savings", "budget", "independence", "lowest_bill", "none"]},
    },
    "required": ["facts", "intent", "topic"],
    "additionalProperties": False,
}
EXTRACT_SYSTEM = f"""You read one message from a homeowner chatting with a solar installer's assistant and return JSON.
- facts: one {{field, value}} per fact this message states or clearly corrects; nothing else. Never guess or fill defaults.
  value is text: a plain number ("4500", "0.35"), "true"/"false", for heating_type one of {", ".join(HEATING)},
  for building_type one of detached, semi, terraced (Reihenhaus -> terraced, Doppelhaushälfte -> semi, Einfamilienhaus -> detached),
  for roof_type one of gable, flat, mono, other (Satteldach -> gable, Flachdach -> flat, Pultdach -> mono),
  for region the German federal state code ({", ".join(REGIONS)}), e.g. Bavaria/Bayern -> BY, a city -> its state.
  Yearly electricity use as the customer states it (e.g. from the bill) -> total_demand_kwh; annual_demand_kwh only if
  they say it excludes the car and heating.
  Units: kWh per year, m², euros, EUR per kWh (35 ct -> 0.35), degrees with 180 = south.
  "we're buying an electric car" -> ev_planned true; "we have an EV" -> has_ev true; "no car" -> has_ev false and ev_planned false.
  Kilometres: put them in the field matching what was said (per year, per week or per day), no conversion.
  A bare answer like "4" or "yes" answers the question named in last_question.
  "we already have solar / PV on the roof" -> has_existing_pv true (and existing_pv_kwp if a size is given).
- intent: facts (gives information), question (asks why / what if / how much), skip (doesn't know or skips),
  handoff (wants to send the plan, get an offer or be contacted), other (anything else).
- goal: the customer states what to optimise for -> intent goal, topic budget ("keep it under €20,000", also set
  budget_eur), independence ("as independent as possible", "max autarky"), or lowest_bill ("lowest monthly bill").
- topic: what a question or goal is about, else none."""


def _typed_facts(pairs: list[dict]) -> dict:
    """[{field, value: text}] -> HomeFacts with proper types; drops anything that doesn't parse."""
    facts = {}
    for p in pairs:
        field, raw, kind = p["field"], p["value"].strip().lower(), FACT_TYPES.get(p["field"])
        try:
            if kind is bool:
                if raw in ("true", "false"):
                    facts[field] = raw == "true"
            elif field == "region":
                if raw.upper() in REGIONS:
                    facts[field] = raw.upper()
            elif kind is str:
                if raw in ENUMS.get(field, ()):
                    facts[field] = raw
            elif kind is not None:
                facts[field] = kind(float(raw.replace(",", "")))
        except ValueError:
            pass
    return facts


def client() -> anthropic.Anthropic | None:
    # shortcut: gate on the env var so "no key" means scripted mode; profiles via `ant auth login` are ignored
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic(timeout=30.0, max_retries=1)


def _call(system: str, content: str, max_tokens: int, schema: dict | None = None) -> str | None:
    c = client()
    if c is None:
        return None
    output_config = {"effort": EFFORT}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    try:
        r = c.beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            output_config=output_config,
            **fallback_kwargs(MODEL),  # a declined request is re-run on Anthropic's recommended fallback model
        )
    except anthropic.APIConnectionError as e:
        log.warning("LLM unreachable, using scripted fallback: %s", e)
        return None
    except anthropic.APIStatusError as e:
        log.warning("LLM error %s, using scripted fallback: %s", e.status_code, e.message)
        return None
    if r.stop_reason in ("refusal", "max_tokens"):
        log.warning("LLM stopped with %s, using scripted fallback", r.stop_reason)
        return None
    return "".join(b.text for b in r.content if b.type == "text").strip() or None


def extract(text: str, facts: dict, last_question: str | None = None) -> dict | None:
    """Customer message -> {"facts": {only stated fields}, "intent": ..., "topic": ...}, or None."""
    content = json.dumps({"message": text, "known_facts": facts, "last_question": last_question}, ensure_ascii=False)
    out = _call(EXTRACT_SYSTEM, content, max_tokens=4000, schema=EXTRACT_SCHEMA)
    if out is None:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    data["facts"] = _typed_facts(data["facts"])
    data["topic"] = None if data["topic"] == "none" else data["topic"]
    return data


def reply(*, audience: str, latest_message: str, facts: dict, engine_result: dict | None,
          next_question: dict | None = None, offer_handoff: bool = False, changed: str | None = None,
          transcript: list[dict] | None = None, flags: list[dict] | None = None) -> str | None:
    """reo's words for this turn, phrased from the engine result only, or None."""
    system = PERSONA_FILE.read_text(encoding="utf-8") + "\n\n" + RULES_FILE.read_text(encoding="utf-8")
    context = {
        "audience": audience,
        "latest_message": latest_message,
        "facts": facts,
        "engine_result": engine_result,
        "next_question": next_question and next_question["prompt"],
        "offer_handoff": offer_handoff,
        "changed": changed,
        "benchmark_flags": [f["text"] for f in flags or []],
        "recent_transcript": (transcript or [])[-8:],
    }
    return _call(system, json.dumps(context, ensure_ascii=False), max_tokens=8000)



BILL_SCHEMA = {
    "type": "object",
    "properties": {
        "total_demand_kwh": {"type": ["number", "null"], "description": "yearly electricity use in kWh"},
        "electricity_price_eur_per_kwh": {"type": ["number", "null"], "description": "working price per kWh in EUR, e.g. 0.34"},
        "provider": {"type": ["string", "null"]},
        "monthly_payment_eur": {"type": ["number", "null"]},
    },
    "required": ["total_demand_kwh", "electricity_price_eur_per_kwh", "provider", "monthly_payment_eur"],
    "additionalProperties": False,
}


def read_bill(data: bytes, media_type: str) -> dict | None:
    """Claude vision reads an electricity bill photo or PDF. Returns only what is printed on it, or None."""
    c = client()
    if c is None or not data:
        return None
    import base64
    b64 = base64.standard_b64encode(data).decode()
    block = ({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
             if media_type == "application/pdf" else
             {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
    try:
        r = c.messages.create(model=MODEL, max_tokens=4000, output_config={"effort": "low", "format": {"type": "json_schema", "schema": BILL_SCHEMA}},
                              messages=[{"role": "user", "content": [block, {"type": "text", "text":
                                  "This is a German electricity bill. Read the yearly consumption (kWh), the price per kWh "
                                  "(Arbeitspreis, EUR), the provider and the monthly payment (Abschlag). Use null for anything "
                                  "not printed. Never estimate."}]}])
    except anthropic.APIError as e:
        log.warning("bill reading failed: %s", e)
        return None
    if r.stop_reason != "end_turn":
        return None
    try:
        return json.loads(next(b.text for b in r.content if b.type == "text"))
    except (StopIteration, json.JSONDecodeError):
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("No ANTHROPIC_API_KEY: copy reo/.env.example to reo/.env and paste your key there.")
    if sys.argv[1:] == ["--check"]:
        out = _call("Answer with exactly: OK", "Say OK.", max_tokens=2000)
        sys.exit(f"Key works, {MODEL} says: {out}" if out else "Call failed, see the warning above.")

    import engine
    import flow

    message = " ".join(sys.argv[1:]) or "we use about 4,500 kWh a year"
    got = extract(message, {})
    print("extracted:", got)
    facts = (got or {}).get("facts", {})
    design = engine.design(facts)
    if design is None:
        sys.exit(f"Engine not reachable at {engine.ENGINE_URL}; start it to see a full reply.")
    ask = flow.next_question(facts, design)
    print("reo:", reply(audience="customer", latest_message=message, facts=facts, engine_result=design,
                        next_question=ask, offer_handoff=flow.offer_handoff(facts, design)))
