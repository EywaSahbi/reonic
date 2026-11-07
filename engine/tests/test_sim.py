import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from sim import simulate  # noqa: E402


def test_energy_balance():
    r = simulate(4500, 2000, 3000, 9, 1082, 10, calibrated=False)
    assert r["load"] == 9500
    assert r["self_used"] + r["import"] == pytest.approx(r["load"], rel=1e-6)
    assert r["self_used"] + r["export"] <= r["generation"] + 1e-6      # battery losses only reduce the total


def test_battery_raises_autarky_with_diminishing_returns():
    a = [simulate(4500, 0, 0, 9, 1082, b, calibrated=False)["self_used"] for b in (0, 5, 10, 15)]
    assert a[0] < a[1] < a[2] < a[3]
    assert a[1] - a[0] > a[2] - a[1] > a[3] - a[2]


def test_no_pv_imports_everything():
    r = simulate(4500, 0, 0, 0, 1082, 0)
    assert r["import"] == pytest.approx(4500) and r["export"] == 0


def test_calibration_lowers_self_use_to_measured_homes():
    raw = simulate(4500, 0, 0, 9, 1082, 9, calibrated=False)
    cal = simulate(4500, 0, 0, 9, 1082, 9)
    assert 0.8 * raw["self_used"] < cal["self_used"] < raw["self_used"]
    assert cal["self_used"] + cal["import"] == pytest.approx(cal["load"], rel=1e-6)
