"""How far expert sizes scatter around the engine's size for similar homes; writes `expert_spread` to params.json.

Run after derive_params.py: `uv run python tools/derive_spread.py --split train`.
For each train project with the component in both designs: ratio = expert size ÷ engine size (installer profile used).
expert_spread[component][installer or "all"] = [lower, upper] quantiles of that ratio (PV 15 / 85%, battery 20 / 80%,
chosen on val for ~80% coverage).
design.py widens each PV and battery `range` to size × [lower, upper], so the range answers
"what would comparable expert designs choose", not only "what could the missing inputs change".
Coverage (expert size inside the range) is checked on val with `--check val`.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dataset import expert_designs, facts  # noqa: E402

PARAMS_PATH = ROOT / "params.json"
COLS = {"pv": "pv_kwp", "battery": "battery_kwh"}


def ratios(df):
    from design import core
    out = {k: {} for k in COLS}
    for _, r in df.iterrows():
        s = core(facts(r), {}, {}, r.installer)["sizes"]
        for k, col in COLS.items():
            if s[k] and r[col] > 0:
                out[k].setdefault(r.installer, []).append(r[col] / s[k])
    return out


def coverage(df):
    from design import design
    hit = {k: [] for k in COLS}
    for _, r in df.iterrows():
        d = design(facts(r), installer=r.installer)
        for k, col in COLS.items():
            c = d["components"][k]
            if r[col] > 0 and c["recommended"] and c["range"]:
                hit[k].append(c["range"][0] <= r[col] <= c["range"][1])
    return {k: (len(v), round(float(np.mean(v)), 3)) for k, v in hit.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    ap.add_argument("--quantiles", type=float, nargs=2, default=[0.15, 0.85], help="PV")
    ap.add_argument("--battery-quantiles", type=float, nargs=2, default=[0.20, 0.80],
                    help="battery sizes are coarse catalogue steps, so a narrower band already covers ~80%%")
    ap.add_argument("--check", default=None, help="only report coverage on this split")
    args = ap.parse_args()
    if args.check:
        print(f"coverage on {args.check}:", coverage(expert_designs(split=args.check)))
        return
    q = {"pv": args.quantiles, "battery": args.battery_quantiles}
    rs = ratios(expert_designs(split=args.split))
    spread = {}
    for k, per in rs.items():
        lo, hi = q[k]
        every = [x for v in per.values() for x in v]
        spread[k] = {"all": [round(float(np.quantile(every, lo)), 3), round(float(np.quantile(every, hi)), 3)]}
        for inst, v in per.items():
            spread[k][inst] = [round(float(np.quantile(v, lo)), 3), round(float(np.quantile(v, hi)), 3)]
        print(k, spread[k])
    params = json.loads(PARAMS_PATH.read_text())
    params["expert_spread"] = {**spread, "quantiles": q, "split": args.split,
                               "script": "engine/tools/derive_spread.py"}
    PARAMS_PATH.write_text(json.dumps(params, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
