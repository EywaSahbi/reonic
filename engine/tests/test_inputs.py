import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from inputs import read_inputs  # noqa: E402


def test_empty_facts_use_defaults():
    h = read_inputs({})
    assert (h.annual_demand_kwh, h.has_ev, h.ev_km_per_year, h.electricity_price_eur_per_kwh) == (4500, False, 0, 0.32)
    assert {a["field"] for a in h.assumptions} == {
        "annual_demand_kwh", "has_ev", "has_existing_pv", "has_existing_battery",
        "heating_type", "electricity_price_eur_per_kwh"}


def test_ev_km_given():
    h = read_inputs({"has_ev": True, "ev_km_per_year": 20000})
    assert h.ev_km_per_year == 20000
    assert not any(a["field"] == "ev_km_per_year" for a in h.assumptions)


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
