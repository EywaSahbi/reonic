import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from inputs import read_inputs, size_pv  # noqa: E402


def test_empty_facts_use_defaults():
    h = read_inputs({})
    assert (h.total_demand_kwh, h.has_ev, h.ev_km_per_year, h.electricity_price_eur_per_kwh) == (4500, False, 0, 0.32)
    assert {a["field"] for a in h.assumptions} == {
        "total_demand_kwh", "has_ev", "has_existing_pv", "has_existing_battery",
        "heating_type", "region", "electricity_price_eur_per_kwh"}


def test_total_demand_given():
    h = read_inputs({"total_demand_kwh": 7200})
    assert h.total_demand_kwh == 7200
    assert not any(a["field"] == "total_demand_kwh" for a in h.assumptions)


def test_household_demand_plus_ev_when_no_total():
    h = read_inputs({"annual_demand_kwh": 4500, "has_ev": True, "ev_km_per_year": 15000})
    assert h.total_demand_kwh == pytest.approx(4500 + 15000 * 0.18)


def test_ev_km_from_week_or_day():
    assert read_inputs({"has_ev": True, "ev_km_per_week": 250}).ev_km_per_year == 250 * 52
    assert read_inputs({"has_ev": True, "ev_km_per_day": 40}).ev_km_per_year == 40 * 365
    assert read_inputs({"has_ev": True, "ev_km_per_year": 9000, "ev_km_per_day": 40}).ev_km_per_year == 9000


def test_ev_without_km_gets_average():
    h = read_inputs({"has_ev": True})
    assert h.ev_km_per_year == 13000
    assert any(a["field"] == "ev_km_per_year" for a in h.assumptions)


def test_no_ev_ignores_km():
    assert read_inputs({"has_ev": False, "ev_km_per_year": 20000}).ev_km_per_year == 0


def test_price_given():
    assert read_inputs({"electricity_price_eur_per_kwh": 0.29}).electricity_price_eur_per_kwh == 0.29


def test_bad_heating_type():
    with pytest.raises(ValueError):
        read_inputs({"heating_type": "Gas"})


def test_pv_size_snaps_to_modules():
    s = size_pv(read_inputs({"total_demand_kwh": 4500}))
    # 4,500 kWh × c 1.93 / Y 1,082 = 8.0 kWp -> 19 modules of 430 W
    assert (s.modules, s.kwp) == (19, pytest.approx(8.17))
    assert s.area_needed_sqm == pytest.approx(19 * 1.95)


def test_roof_unknown_is_open_question():
    s = size_pv(read_inputs({"total_demand_kwh": 4500}))
    assert s.roof == "unknown"
    assert [m["field"] for m in s.missing_inputs] == ["roof_area_sqm"]


def test_roof_too_small():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 20}))
    assert (s.roof, s.modules_fitting) == ("too_small", 10)  # 20 m² / 1.95
    assert s.missing_inputs[0]["field"] == "roof_area_sqm"
    assert not s.heatpump_suggested


def test_spare_roof_suggests_heatpump_for_gas():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 80,
                             "heating_type": "gas", "heating_demand_kwh": 15000}))
    assert s.roof == "fits" and s.heatpump_suggested
    assert s.heatpump_electricity_kwh == 5000
    # 5,000 kWh needs 21 modules, 41 - 19 = 22 spare: all 21 fit
    assert s.heatpump_extra_kwp == pytest.approx(21 * 0.43)


def test_spare_roof_caps_heatpump_pv():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 50,
                             "heating_type": "oil", "heating_demand_kwh": 15000}))
    assert s.heatpump_extra_kwp == pytest.approx((25 - 19) * 0.43)


def test_spare_roof_without_heating_demand_asks_for_it():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 60, "heating_type": "gas"}))
    assert s.heatpump_suggested and s.heatpump_extra_kwp == 0
    assert [m["field"] for m in s.missing_inputs] == ["heating_demand_kwh"]


def test_no_heatpump_when_heating_already_electric():
    for heating in ("heatpump", "electric"):
        s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 60, "heating_type": heating}))
        assert not s.heatpump_suggested and s.missing_inputs == []


def test_unknown_heating_with_spare_roof_is_open_question():
    s = size_pv(read_inputs({"total_demand_kwh": 4500, "roof_area_sqm": 60}))
    assert [m["field"] for m in s.missing_inputs] == ["heating_type"]


def test_region_sets_yield_and_sizing():
    north = read_inputs({"total_demand_kwh": 4500, "region": "SH"})
    south = read_inputs({"total_demand_kwh": 4500, "region": "BY"})
    assert north.y_kwh_per_kwp < read_inputs({}).y_kwh_per_kwp < south.y_kwh_per_kwp
    assert size_pv(north).modules > size_pv(south).modules


def test_bad_region():
    with pytest.raises(ValueError):
        read_inputs({"region": "Bayern"})
