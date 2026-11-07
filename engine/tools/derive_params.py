"""Derive the expert-habit parameters from all projects in `Project Data/` and write them into params.json.

Run once after derive_y.py: `uv run python tools/derive_params.py --split train` (fit on data's train split only;
without --split all projects are used, which makes any evaluation in-sample).

- PV line  kWp = a + b × D_MWh   fitted through the medians of demand bands (robust to odd projects)
- c        median of kWp × Y / D (kept to explain the size: "produces ~c× your demand")
- r_B      median battery kWh per PV kWp; battery catalogue = sizes offered at least 20 times
- heat-pump and wallbox sizes offered
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dataset import expert_designs  # noqa: E402

PARAMS_PATH = ROOT / "params.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "val", "test"], default=None)
    split = ap.parse_args().split
    params = json.loads(PARAMS_PATH.read_text())
    y = params["pv_yield"]["y_kwh_per_kwp"]
    df = expert_designs(params["k_ev_kwh_per_km"], params["cop"], split)
    pv = df[(df.pv_kwp > 0) & ~df.has_existing_pv.astype(bool) & (df.heatpump_kw == 0)
            & df.annual_demand_kwh.between(1000, 20000) & (df.pv_kwp <= 40)].copy()

    pv["band"] = pd.qcut(pv.total_demand_kwh, 10, duplicates="drop")
    bands = pv.groupby("band", observed=True).agg(d=("total_demand_kwh", "median"), kwp=("pv_kwp", "median"),
                                                  n=("pv_kwp", "size"))
    b, a = np.polyfit(bands.d / 1000, bands.kwp, 1, w=np.sqrt(bands.n))
    c = float((pv.pv_kwp * y / pv.total_demand_kwh).median())
    line_err = float((pv.pv_kwp - (a + b * pv.total_demand_kwh / 1000)).abs().median())
    c_err = float((pv.pv_kwp - c / y * pv.total_demand_kwh).abs().median())

    bat = df[(df.pv_kwp > 0) & (df.battery_kwh > 0)]
    r_b = float((bat.battery_kwh / bat.pv_kwp).median())
    sizes = df[df.battery_kwh > 0].battery_kwh.round(1).value_counts()
    catalogue = sorted(float(s) for s, n in sizes.items() if n >= 20)
    share = float((df[df.pv_kwp > 0].battery_kwh > 0).mean())
    hp_sizes = sorted({round(float(s)) for s in df[df.heatpump_kw > 0].heatpump_kw})

    print(f"PV projects {len(pv)}: kWp = {a:.2f} + {b:.3f} × D_MWh (median abs error {line_err:.2f} kWp); "
          f"fixed c = {c:.2f} would give {c_err:.2f}")
    print(f"battery with PV {share:.0%}, r_B = {r_b:.2f} kWh/kWp, catalogue {catalogue}; heat pumps {hp_sizes}")

    params["pv_line"] = {"a_kwp": round(float(a), 3), "b_kwp_per_mwh": round(float(b), 3),
                         "median_abs_error_kwp": round(line_err, 2), "projects": len(pv)}
    params["c_coverage"] = round(c, 3)
    params["battery"] = {"share_with_pv": round(share, 3), "r_b_kwh_per_kwp": round(r_b, 3), "catalogue_kwh": catalogue}
    params["heatpump_catalogue_kw"] = hp_sizes
    params["derived_from_dataset"] = {"on": date.today().isoformat(), "script": "engine/tools/derive_params.py",
                                      "projects": len(df), "split": split or "all"}
    params.pop("c_derivation", None)
    PARAMS_PATH.write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
