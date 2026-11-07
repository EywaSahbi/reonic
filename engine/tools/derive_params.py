"""Derive the expert-habit parameters from all projects in `Project Data/` and write them into params.json.

Run once after derive_y.py: `uv run python tools/derive_params.py --split train` (fit on data's train split only;
without --split all projects are used, which makes any evaluation in-sample).

- PV line  kWp = a + b × D_MWh   fitted through the medians of demand bands (robust to odd projects)
- c        median of kWp × Y / D (kept to explain the size: "produces ~c× your demand")
- r_B      median battery kWh per PV kWp; battery catalogue = sizes offered at least 20 times
- battery bands: the experts' most common battery size per PV size band (sizes battery like experts do)
- installer_profiles: the PV line and battery bands per installer, from that installer's projects only; for installers
  that sell fixed packages (top 5 PV sizes ≥ 50% of their designs) the PV sizes they sold at least 5 times
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
PV_BANDS = [6, 8, 10, 12, 15]          # upper kWp bounds; above the last = last band


def pv_line(pv):
    """(a, b, median abs error) of kWp = a + b × D_MWh through the medians of ten demand bands."""
    pv = pv.copy()
    pv["band"] = pd.qcut(pv.total_demand_kwh, 10, duplicates="drop")
    bands = pv.groupby("band", observed=True).agg(d=("total_demand_kwh", "median"), kwp=("pv_kwp", "median"),
                                                  n=("pv_kwp", "size"))
    b, a = np.polyfit(bands.d / 1000, bands.kwp, 1, w=np.sqrt(bands.n))
    err = float((pv.pv_kwp - (a + b * pv.total_demand_kwh / 1000)).abs().median())
    return float(a), float(b), err


PACKAGE_BANDS = 6                      # demand bands for package sellers (chosen on val: 4 / 5 / 6 / 8 tried)


def pv_packages(df):
    """For installers that sell fixed packages (top 5 PV sizes ≥ 50% of designs): the package they sell most often
    per demand band, as [[upper total_demand_kwh or null, kWp], ...]; [] for installers that design freely."""
    g = df[(df.pv_kwp > 0) & ~df.has_existing_pv.astype(bool)]
    sizes = g.pv_kwp.round(2).value_counts()
    if not len(sizes) or sizes.head(5).sum() / sizes.sum() < 0.5:
        return []
    edges = sorted(set(float(e) for e in np.quantile(g.total_demand_kwh, np.linspace(0, 1, PACKAGE_BANDS + 1))[1:-1]))
    modes, lo = [], -1.0
    for hi in edges + [None]:
        band = g[(g.total_demand_kwh > lo) & ((g.total_demand_kwh <= hi) if hi else True)]
        modes.append(float(band.pv_kwp.round(2).mode().iloc[0]))
        lo = hi
    # bands hold ~40 projects each, so their modes are noisy: make the package grow with demand (smallest package
    # in the lowest band, then never smaller than the band before); better on val (65% vs 61% within ±20%)
    mono = [min(modes)]
    for m in modes[1:]:
        mono.append(max(mono[-1], m))
    return [[hi, m] for hi, m in zip(edges + [None], mono)]


def module_w(df):
    """The installer's typical module power (W): median kWp per module over its designs with a module count.
    Used only for package sellers, so packages come out exact (10.8 kWp = 24 × 450 W); free designers keep the
    engine's finer 430 W steps (closer to the experts on val)."""
    g = df[(df.pv_kwp > 0) & (df.pv_modules > 0)]
    return round(float((g.pv_kwp * 1000 / g.pv_modules).median())) if len(g) else None


def battery_bands(df):
    """[[upper PV kWp or null, most common expert battery kWh], ...] over projects with PV and a battery."""
    t = df[(df.pv_kwp > 0) & (df.battery_kwh > 0)]
    out, lo = [], 0
    for hi in PV_BANDS + [None]:
        g = t[(t.pv_kwp > lo) & ((t.pv_kwp <= hi) if hi else True)]
        out.append([hi, float(g.battery_kwh.round(0).mode().iloc[0])])
        lo = hi
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "val", "test"], default=None)
    split = ap.parse_args().split
    params = json.loads(PARAMS_PATH.read_text())
    y = params["pv_yield"]["y_kwh_per_kwp"]
    df = expert_designs(params["k_ev_kwh_per_km"], params["cop"], split)
    pv = df[(df.pv_kwp > 0) & ~df.has_existing_pv.astype(bool) & (df.heatpump_kw == 0)
            & df.annual_demand_kwh.between(1000, 20000) & (df.pv_kwp <= 40)].copy()

    a, b, line_err = pv_line(pv)
    c = float((pv.pv_kwp * y / pv.total_demand_kwh).median())
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
    params["battery"] = {"share_with_pv": round(share, 3), "r_b_kwh_per_kwp": round(r_b, 3), "catalogue_kwh": catalogue,
                         "by_pv_band": battery_bands(df)}
    profiles = {}
    for inst, g in df.groupby("installer"):
        ga, gb, gerr = pv_line(pv[pv.installer == inst])
        profiles[inst] = {"pv_line": {"a_kwp": round(ga, 3), "b_kwp_per_mwh": round(gb, 3),
                                      "median_abs_error_kwp": round(gerr, 2)},
                          "battery_by_pv_band": battery_bands(g), "pv_packages": pv_packages(g),
                          "module_w": module_w(g) if pv_packages(g) else None, "projects": len(g)}
        print(f"  {inst}: kWp = {ga:.2f} + {gb:.3f} × D_MWh, battery bands {profiles[inst]['battery_by_pv_band']}, "
              f"packages {profiles[inst]['pv_packages']}")
    params["installer_profiles"] = profiles
    params["heatpump_catalogue_kw"] = hp_sizes
    params["derived_from_dataset"] = {"on": date.today().isoformat(), "script": "engine/tools/derive_params.py",
                                      "projects": len(df), "split": split or "all"}
    params.pop("c_derivation", None)
    PARAMS_PATH.write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
