import flow
import llm


def fields(facts, skipped=()):
    q = flow.next_question(facts, None, set(skipped))
    return q["field"] if q else None


def test_question_order_kwh_known():
    assert fields({}) == "total_demand_kwh"
    f = {"total_demand_kwh": 4500}
    assert fields(f) == "roof_area_sqm"                                    # location right after kWh, no people count
    f["roof_area_sqm"] = 48                                                 # address found -> EV, no state / dimensions
    assert fields(f) == "has_ev"
    f["ev_planned"] = True
    assert fields(f) == "heating_type"
    f["heating_type"] = "gas"
    assert fields(f) == "has_existing_pv"                                   # retrofit handling stays (app ACK)
    f["has_existing_pv"] = True
    assert fields(f) == "existing_pv_kwp"
    f["existing_pv_kwp"] = 5
    assert fields(f) is None and flow.offer_handoff(f)


def test_kwh_skipped_asks_people_then_location():
    assert fields({}, {"total_demand_kwh"}) == "num_inhabitants"
    assert fields({"num_inhabitants": 3}, {"total_demand_kwh"}) == "roof_area_sqm"
    assert fields({}, {"total_demand_kwh", "num_inhabitants"}) == "roof_area_sqm"   # people skipped too: still go on


def test_location_fallbacks():
    base = {"total_demand_kwh": 4500}
    assert fields(base, {"roof_area_sqm"}) == "region"                      # address skipped -> federal state
    assert fields({**base, "region": "BY"}, {"roof_area_sqm"}) == "has_ev"  # state given -> EV
    assert fields(base, {"roof_area_sqm", "region"}) == "roof_dims"         # state skipped -> roof width x length
    assert flow.ASK["roof_dims"]["input"] == "dimensions"
    assert fields({**base, "roof_width_m": 8, "roof_length_m": 6}, {"roof_area_sqm", "region"}) == "has_ev"
    assert fields(base, {"roof_area_sqm", "region", "roof_dims"}) == "has_ev"        # dimensions skipped -> EV anyway
    assert fields(base, {"roof_dims"}) == "region"                          # address not found, dimensions skipped -> state


def test_ev_and_heating_are_always_asked_in_that_order():
    base = {"total_demand_kwh": 4500, "roof_area_sqm": 40}
    assert fields(base) == "has_ev" and fields({**base, "has_ev": False}) == "heating_type"
    assert fields({**base, "has_ev": False, "heating_type": "electric", "has_existing_pv": False}) is None


def test_no_key_means_fallback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.extract("we use 4500 kWh", {}) is None
    assert llm.reply(audience="customer", latest_message="hi", facts={}, engine_result=None) is None


def test_scripted_states_and_house():
    import scripted
    got = scripted.extract("Wir wohnen in einem Reihenhaus mit Flachdach in Hamburg")["facts"]
    assert got == {"building_type": "terraced", "roof_type": "flat", "region": "HH"}
    assert scripted.extract("wir wohnen in Niedersachsen")["facts"] == {"region": "NI"}


def test_rounding_matches_app():
    import scripted
    assert scripted.eur(63650) == "€63,700"  # half up, like the plan card (qa BLOCKED 20:17)
    assert scripted.eur(13190) == "€13,200" and scripted.kwp(8.25) == "8.5" and scripted.rnd(10.5) == 11


def test_heating_advice_only_claims_what_the_engine_shows():
    import scripted
    hc = {"fuel": "gas", "energy_factor": 3.7, "cost_now_eur_per_year": 3004, "cost_heatpump_eur_per_year": 2182, "cost_factor": 1.38,
          "heatpump_cheaper": True, "co2_now_kg_per_year": 5025, "co2_heatpump_kg_per_year": 2345, "co2_reduction_pct": 53.3, "note": None}
    text = scripted.heating_advice({"heating_comparison": hc})
    assert "heat pump" in text and "3.7 times less energy" in text and "€2,180" in text and "€3,000" in text and "53%" in text
    dearer = scripted.heating_advice({"heating_comparison": {**hc, "heatpump_cheaper": False, "cost_factor": 0.8,
                                                             "co2_reduction_pct": None}})
    assert "instead of" not in dearer and "own solar" in dearer and "CO₂" not in dearer
    assert scripted.heating_advice({"heating_comparison": None}) is None and scripted.heating_advice({}) is None
