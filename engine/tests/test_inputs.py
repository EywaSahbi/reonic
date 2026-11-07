import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from inputs import PARAMS, orientation_factor, pv_kwp_for, read_inputs, size_pv  # noqa: E402

LINE = PARAMS["pv_line"]


def test_empty_facts_use_defaults():
    h = read_inputs({})
    assert (h.total_demand_kwh, h.has_ev, h.ev_km_per_year, h.electricity_price_eur_per_kwh) == (4500, False, 0, 0.32)
    assert {"total_demand_kwh", "has_ev", "has_existing_pv", "has_existing_battery", "heating_type", "region",
            "electricity_price_eur_per_kwh"} <= {a["field"] for a in h.assumptions}


def test_total_demand_given():
    h = read_inputs({"total_demand_kwh": 7200})
    assert h.total_demand_kwh == 7200
    assert not any(a["field"] == "total_demand_kwh" for a in h.assumptions)


def test_household_demand_plus_ev_when_no_total():
    h = read_inputs({"annual_demand_kwh": 4500, "has_ev": True, "ev_km_per_year": 15000})
    assert h.total_demand_kwh == pytest.approx(4500 + 15000 * 0.18)
    assert h.ev_kwh == pytest.approx(2700)


def test_demand_from_inhabitants():
    h = read_inputs({"num_inhabitants": 4, "building_type": "terraced"})
    assert h.total_demand_kwh == pytest.approx(4000 * 0.9)


def test_ev_km_from_week_or_day():
    assert read_inputs({"has_ev": True, "ev_km_per_week": 250}).ev_km_per_year == 250 * 52
    assert read_inputs({"has_ev": True, "ev_km_per_day": 40}).ev_km_per_year == 40 * 365
    assert read_inputs({"has_ev": True, "ev_km_per_year": 9000, "ev_km_per_day": 40}).ev_km_per_year == 9000


def test_ev_without_km_gets_average():
    h = read_inputs({"has_ev": True})
    assert h.ev_km_per_year == 13000
    assert any(a["field"] == "ev_km_per_year" for a in h.assumptions)


def test_bad_values_rejected():
    for facts in ({"heating_type": "Gas"}, {"region": "Bayern"}, {"roof_type": "dome"}):
        with pytest.raises(ValueError):
            read_inputs(facts)


def test_pv_follows_expert_line():
    s = size_pv(read_inputs({"total_demand_kwh": 4500}))
    expected = LINE["a_kwp"] + LINE["b_kwp_per_mwh"] * 4.5
    assert s.modules == round(expected * 1000 / 430)
    assert s.area_needed_sqm == pytest.approx(s.modules * PARAMS["module_area_sqm"])


def test_small_homes_get_relatively_more_pv():
    small, big = (size_pv(read_inputs({"total_demand_kwh": d})).kwp for d in (2500, 10000))
    assert small / 2500 > big / 10000 and big > small


def test_region_and_orientation_scale_pv():
    north = size_pv(read_inputs({"total_demand_kwh": 4500, "region": "SH"})).modules
    south = size_pv(read_inputs({"total_demand_kwh": 4500, "region": "BY"})).modules
    east = size_pv(read_inputs({"total_demand_kwh": 4500, "region": "BY", "roof_orientation_deg": 90})).modules
    assert north > south and east > south
    assert orientation_factor(180, 35, None) == 1.0
    assert orientation_factor(90, 35, None) == pytest.approx(orientation_factor(270, 35, None), abs=0.01)
    assert orientation_factor(90, 35, None) == pytest.approx(0.8, abs=0.02)


def test_existing_pv_reduces_new_pv():
    h = read_inputs({"total_demand_kwh": 4500, "has_existing_pv": True, "existing_pv_kwp": 5})
    assert size_pv(h).modules == round((pv_kwp_for(4500, h) - 5) * 1000 / 430)


def test_roof_unknown_is_open_question():
    s = size_pv(read_inputs({"total_demand_kwh": 4500}))
    assert s.roof == "unknown" and [m["field"] for m in s.missing_inputs] == ["roof_area_sqm"]


def test_roof_too_small_uses_usable_share():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 20}))
    assert (s.roof, s.modules_fitting) == ("too_small", int(20 * 0.75 / 1.95))
    assert s.missing_inputs[0]["field"] == "roof_area_sqm" and not s.heatpump_suggested


def test_spare_roof_suggests_heatpump_for_gas():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 100,
                             "heating_type": "gas", "heating_demand_kwh": 15000}))
    assert s.roof == "fits" and s.heatpump_suggested
    assert s.heatpump_electricity_kwh == pytest.approx(5000)
    assert s.heatpump_kw == 7                         # 15,000 kWh / 2,000 h = 7.5 → nearest catalogue size
    assert 0 < s.heatpump_extra_modules <= s.modules_fitting - s.modules


def test_spare_roof_caps_heatpump_pv():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 60, "heating_type": "oil",
                             "heating_demand_kwh": 30000}))
    assert s.heatpump_extra_modules == s.modules_fitting - s.modules


def test_spare_roof_without_heating_demand_asks_for_it():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 100, "heating_type": "gas"}))
    assert s.heatpump_suggested and s.heat_demand_kwh == PARAMS["heating_demand_default_kwh"]
    assert [m["field"] for m in s.missing_inputs] == ["heating_demand_kwh"]


def test_no_heatpump_when_heating_already_electric():
    for heating in ("heatpump", "electric"):
        s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 100, "heating_type": heating}))
        assert not s.heatpump_suggested and s.missing_inputs == []


def test_unknown_heating_with_spare_roof_is_open_question():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 100}))
    assert [m["field"] for m in s.missing_inputs] == ["heating_type"]
