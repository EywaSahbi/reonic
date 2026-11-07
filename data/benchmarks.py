"""train -> processed/benchmarks.json: what experts deliver for similar homes (for reo's flags).

    uv run python benchmarks.py

Segments: demand band x EV x heating, plus coarser fallback levels. Built from `train` only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
BANDS = [0, 3000, 4000, 5000, 6000, np.inf]  # kWh/year household demand; 4,500 is the most common value
LEVELS = [["demand_band", "has_ev", "heating_type"], ["demand_band", "has_ev"], ["demand_band"], []]
MIN_N = 15  # reo uses the most specific segment with at least this many homes


def band(kwh: float) -> str:
    if kwh != kwh:
        return "unknown"
    i = int(np.searchsorted(BANDS, kwh, side="right")) - 1
    lo, hi = BANDS[i], BANDS[i + 1]
    return f"{lo:.0f}+" if hi == np.inf else f"{lo:.0f}-{hi:.0f}"


def stats(g: pd.DataFrame) -> dict:
    def pct(s: pd.Series) -> dict | None:
        s = s.dropna()
        if s.empty:
            return None
        return {"p10": round(s.quantile(.1), 1), "p50": round(s.median(), 1), "p90": round(s.quantile(.9), 1),
                "values": sorted(round(float(v), 2) for v in s)}  # full sorted list so reo can say "larger than 85 %"

    def typical(s: pd.Series) -> list:
        return [{"size": float(k), "share": round(v, 2)} for k, v in
                s.dropna().round(1).value_counts(normalize=True).head(3).items()]

    return {
        "n": len(g),
        "pv_kwp": pct(g.pv_kwp), "battery_kwh": pct(g.battery_kwh),
        "battery_kwh_per_kwp": pct((g.battery_kwh / g.pv_kwp).replace([np.inf], np.nan)),
        "attach_rate": {c: round(float(g[f"has_{c}"].mean()), 2) for c in ["pv", "battery", "heatpump", "wallbox"]},
        "typical_sizes": {"battery_kwh": typical(g.battery_kwh), "pv_kwp": typical(g.pv_kwp.round(0))},
    }


def build() -> dict:
    df = pd.read_parquet(ROOT / "processed" / "projects.parquet").merge(pd.read_csv(ROOT / "processed" / "split.csv"))
    t = df[df.split == "train"].copy()
    t["demand_band"] = t.annual_demand_kwh.map(band)
    t["heating_type"] = t.heating_type.fillna("unknown")
    segments = []
    for keys in LEVELS:
        groups = t.groupby(keys) if keys else [((), t)]
        for k, g in groups:
            k = k if isinstance(k, tuple) else (k,)
            key = {name: (bool(v) if name == "has_ev" else v) for name, v in zip(keys, k)}
            segments.append({"level": len(keys), "key": key, **stats(g)})
    return {"built_from": "train", "n_train": len(t), "min_n": MIN_N,
            "demand_bands": [band(b) for b in BANDS[:-1]],
            "lookup": "use the segment with the most key fields that matches the home and has n >= min_n; "
                      "missing fields: demand_band 'unknown', heating_type 'unknown'; level 0 = all homes",
            "segments": segments}


def main() -> None:
    out = ROOT / "processed" / "benchmarks.json"
    b = build()
    out.write_text(json.dumps(b, indent=1))
    usable = [s for s in b["segments"] if s["n"] >= MIN_N]
    print(f"benchmarks.json: {len(b['segments'])} segments, {len(usable)} with n >= {MIN_N}, {out.stat().st_size // 1024} KB")
    for s in usable:
        if s["level"] <= 2:
            pv, bat = s["pv_kwp"] or {}, s["battery_kwh"] or {}
            print(f"  {str(s['key']):45s} n={s['n']:4d} pv p50={pv.get('p50')} bat p50={bat.get('p50')} "
                  f"wallbox={s['attach_rate']['wallbox']}")


if __name__ == "__main__":
    main()
