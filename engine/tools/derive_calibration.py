"""Correct the simulation's H0 optimism with 74 measured household load profiles; writes `sim_calibration` to params.json.

The BDEW H0 profile is the average of many homes, so it has no real peaks: one home's kettle or oven at 19:00 draws
far more than the panels or battery can give in that minute. The hourly H0 simulation therefore overstates how
much solar power a home uses itself. This tool measures by how much:

1. HTW Berlin profiles (Tjaden, Bergner, Weniger, Quaschning: "Representative electrical load profiles of residential
   buildings in Germany with a temporal resolution of one second", HTW Berlin, CC BY-NC 4.0): 74 single-family homes,
   one year, 1-minute active power. Download (public share, password `profile`, linked from
   https://solar.htw-berlin.de/elektrische-lastprofile-fuer-wohngebaeude/) `CSV_74_Loadprofiles_1min_W_var.zip` and unzip
   PL1.csv, PL2.csv, PL3.csv into one folder. The raw data stays outside the repo; only the factor table is committed.
2. Each home is scaled to 1 MWh/yr and simulated minute by minute with the same battery rules as sim.py, for a grid of
   PV generation per kWh of demand × battery kWh per MWh of demand. PV = the engine's hourly PVGIS profile, spread
   evenly over each hour.
3. factor = mean self-used share over the 74 homes ÷ the hourly H0 simulation's self-used share, per grid point.
sim.py multiplies its self-used energy by the bilinearly interpolated factor.

    uv run python tools/derive_calibration.py /path/to/htw_folder
"""
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from sim import C_RATE, ETA, PV, simulate  # noqa: E402

PARAMS_PATH = ROOT / "params.json"
GEN = [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]       # yearly PV generation ÷ yearly demand
BAT = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]             # battery kWh per MWh of yearly demand


def measured_self_use(folder: Path) -> np.ndarray:
    """[len(GEN), len(BAT)] mean self-used share of demand over the 74 homes, 1-minute simulation."""
    watts = sum(pd.read_csv(folder / f"PL{i}.csv", header=None, dtype=np.float32).to_numpy() for i in (1, 2, 3))
    kwh = watts / 60_000                                       # W per minute → kWh per minute
    load = kwh / kwh.sum(axis=0) * 1000                        # every home scaled to 1,000 kWh/yr
    n_min, n_homes = load.shape
    pv_min = np.repeat(np.array(PV, dtype=np.float32) / 60, 60)[:n_min] * 1000   # kWh per minute for 1,000 kWh/yr
    g = np.repeat(np.array(GEN, dtype=np.float32), len(BAT))   # combos: (gen, bat)
    b = np.tile(np.array(BAT, dtype=np.float32), len(GEN))
    gen_c = np.repeat(g, n_homes)                              # combos × homes, flattened
    cap = np.repeat(b, n_homes)
    max_p = cap * C_RATE / 60                                  # kWh per minute
    soc = np.zeros_like(cap)
    used = np.zeros_like(cap)
    for t in range(n_min):
        lt = np.tile(load[t], len(g))
        gt = gen_c * pv_min[t]
        direct = np.minimum(gt, lt)
        surplus = gt - direct
        need = lt - direct
        charge = np.minimum(np.minimum(surplus, max_p), (cap - soc) / ETA)
        soc += charge * ETA
        give = np.minimum(np.minimum(need, max_p), soc * ETA)
        soc -= give / ETA
        used += direct + give
        if t % 100_000 == 0:
            print(f"  minute {t:,} of {n_min:,}")
    return (used / 1000).reshape(len(GEN), len(BAT), n_homes).mean(axis=2)


def main():
    folder = Path(sys.argv[1])
    real = measured_self_use(folder)
    h0 = np.array([[simulate(1000, 0, 0, gr, 1000, ba, calibrated=False)["self_used"] / 1000 for ba in BAT] for gr in GEN])
    factor = real / h0
    for gr, row_r, row_h, row_f in zip(GEN, real, h0, factor):
        print(f"gen {gr:4}: measured {np.round(row_r * 100).astype(int)}  H0 {np.round(row_h * 100).astype(int)}  "
              f"factor {np.round(row_f, 2)}")
    params = json.loads(PARAMS_PATH.read_text())
    params["sim_calibration"] = {
        "gen_ratio": GEN, "battery_kwh_per_mwh": BAT, "factor": np.round(factor, 4).tolist(),
        "measured_self_use": np.round(real, 4).tolist(),
        "source": "HTW Berlin, 74 measured single-family load profiles, 1-minute (Tjaden et al., CC BY-NC 4.0), "
                  "vs the engine's hourly H0 simulation",
        "derived_on": date.today().isoformat(), "script": "engine/tools/derive_calibration.py",
    }
    PARAMS_PATH.write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
