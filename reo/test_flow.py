import flow
import llm


def test_question_order_and_stop():
    design = {"missing_inputs": [{"field": "heating_type", "impact": "high"}, {"field": "roof_area_sqm", "impact": "high"}],
              "components": {"heatpump": {"recommended": False}}}
    assert flow.next_question({"annual_demand_kwh": 4500}, design)["field"] == "heating_type"
    assert flow.next_question({"heating_type": "gas"}, design)["field"] == "roof_area_sqm"  # high impact jumps the EV question
    assert flow.next_question({"heating_type": "gas", "ev_planned": True}, {"missing_inputs": [], "components": {}}) is None
    assert flow.offer_handoff({"heating_type": "gas", "has_ev": False}, design)


def test_no_key_means_fallback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.extract("we use 4500 kWh", {}) is None
    assert llm.reply(audience="customer", latest_message="hi", facts={}, engine_result=None) is None


def test_scripted_states_and_house():
    import scripted
    got = scripted.extract("Wir wohnen in einem Reihenhaus mit Flachdach in Hamburg")["facts"]
    assert got == {"building_type": "terraced", "roof_type": "flat", "region": "HH"}
    assert scripted.extract("wir wohnen in Niedersachsen")["facts"] == {"region": "NI"}
