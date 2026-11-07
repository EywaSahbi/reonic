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

MODEL = os.getenv("REO_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("REO_EFFORT", "low")  # chat turns; low keeps replies fast
PERSONA_FILE = HERE.parent / "experience" / "persona.md"  # owned by app, loaded as is
RULES_FILE = HERE / "prompt.md"
log = logging.getLogger("reo.llm")

_NUM, _BOOL = {"type": ["number", "null"]}, {"type": ["boolean", "null"]}
FACT_FIELDS = {
    "annual_demand_kwh": _NUM, "num_inhabitants": _NUM, "house_size_sqm": _NUM, "house_built_year": _NUM,
    "heating_type": {"anyOf": [{"type": "string", "enum": ["gas", "oil", "heatpump", "electric", "district", "other"]},
                               {"type": "null"}]},
    "heating_demand_kwh": _NUM, "has_ev": _BOOL, "ev_planned": _BOOL,
    "ev_km_per_year": _NUM, "ev_km_per_week": _NUM, "ev_km_per_day": _NUM,
    "roof_area_sqm": _NUM, "roof_orientation_deg": _NUM, "roof_tilt_deg": _NUM,
    "electricity_price_eur_per_kwh": _NUM, "has_existing_pv": _BOOL, "existing_pv_kwp": _NUM,
    "has_existing_battery": _BOOL, "budget_eur": _NUM,
}
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {"type": "object", "properties": FACT_FIELDS, "required": list(FACT_FIELDS), "additionalProperties": False},
        "intent": {"type": "string", "enum": ["facts", "question", "skip", "handoff", "other"]},
        "topic": {"anyOf": [{"type": "string", "enum": ["pv", "battery", "heatpump", "wallbox", "price", "savings"]},
                            {"type": "null"}]},
    },
    "required": ["facts", "intent", "topic"],
    "additionalProperties": False,
}
EXTRACT_SYSTEM = """You read one message from a homeowner chatting with a solar installer's assistant and return JSON.
- facts: only what this message states or clearly corrects; null for everything else. Never guess or fill defaults.
  Units: kWh per year, m², euros, EUR per kWh (35 ct -> 0.35), degrees with 180 = south.
  "we're buying an electric car" -> ev_planned true; "we have an EV" -> has_ev true; "no car" -> has_ev false and ev_planned false.
  Kilometres: put them in the field matching what was said (per year, per week or per day), no conversion.
  A bare answer like "4" or "yes" answers the question named in last_question.
- intent: facts (gives information), question (asks why / what if / how much), skip (doesn't know or skips),
  handoff (wants to send the plan, get an offer or be contacted), other (anything else).
- topic: what a question is about, else null."""


def _client() -> anthropic.Anthropic | None:
    # shortcut: gate on the env var so "no key" means scripted mode; profiles via `ant auth login` are ignored
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic(timeout=30.0, max_retries=1)


def _call(system: str, content: str, max_tokens: int, schema: dict | None = None) -> str | None:
    client = _client()
    if client is None:
        return None
    output_config = {"effort": EFFORT}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    try:
        r = client.beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # a declined request is re-run on Anthropic's recommended fallback model
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
    data["facts"] = {k: v for k, v in data["facts"].items() if v is not None}
    return data


def reply(*, audience: str, latest_message: str, facts: dict, engine_result: dict | None,
          next_question: dict | None = None, offer_handoff: bool = False, changed: str | None = None,
          transcript: list[dict] | None = None) -> str | None:
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
        "recent_transcript": (transcript or [])[-8:],
    }
    return _call(system, json.dumps(context, ensure_ascii=False), max_tokens=8000)


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
