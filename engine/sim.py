"""One year, hour by hour (METHOD.md step 4): where every kWh goes for a given design.

Load = H0 household profile + EV charging in the evening + heat pump by outdoor temperature.
PV = PVGIS hourly output of 1 kWp × kWp, scaled to the home's yield Y.
Each hour: PV serves the load, surplus charges the battery, the rest is exported;
a shortfall is covered by the battery, the rest is imported.
"""
import json
from pathlib import Path

P = json.loads((Path(__file__).parent / "profiles.json").read_text())
_H0_SUM, _PV_SUM = sum(P["h0_kwh_per_1000"]), sum(P["pv_kwh_per_1000"])
H0 = [x / _H0_SUM for x in P["h0_kwh_per_1000"]]                     # shares of the year, sum 1
PV = [x / _PV_SUM for x in P["pv_kwh_per_1000"]]
_HEAT = [max(0.0, 15.0 - t) for t in P["t2m_c"]]                     # heating degree hours, base 15 °C
_HEAT_SUM = sum(_HEAT)
HEAT = [0.85 * h / _HEAT_SUM + 0.15 / 8760 for h in _HEAT]            # + 15% hot water, flat over the year
EV_HOURS = (18, 19, 20, 21)                                          # charging after work
ETA = 0.95                                                           # battery efficiency each way
C_RATE = 0.5                                                         # max charge / discharge per hour, × capacity


def simulate(house_kwh, ev_kwh, heatpump_kwh, kwp, y, battery_kwh):
    """Yearly sums in kWh: generation, self_used, export, import, load."""
    ev_per_hour = ev_kwh / 365 / len(EV_HOURS)
    gen_scale = kwp * y
    max_p = battery_kwh * C_RATE
    soc = 0.0
    used = export = imp = 0.0
    for t in range(8760):
        load = house_kwh * H0[t] + heatpump_kwh * HEAT[t] + (ev_per_hour if t % 24 in EV_HOURS else 0.0)
        g = gen_scale * PV[t]
        if g >= load:
            used += load
            surplus = g - load
            charge = min(surplus, max_p, (battery_kwh - soc) / ETA)
            soc += charge * ETA
            export += surplus - charge
        else:
            used += g
            need = load - g
            give = min(need, max_p, soc * ETA)
            soc -= give / ETA
            used += give
            imp += need - give
    load_total = house_kwh + ev_kwh + heatpump_kwh
    return {"generation": gen_scale, "self_used": used, "export": export, "import": imp, "load": load_total}
