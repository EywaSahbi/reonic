"""How far expert sizes scatter around the engine's size for similar homes; writes `expert_spread` to params.json.

Run after derive_params.py: `uv run python tools/derive_spread.py --split train`.
For each train project with the component in both designs: ratio = expert size ÷ engine size.
expert_spread[component]["all"] = [lower, upper] quantiles of that ratio for the engine WITHOUT an installer profile
(the customer flow); expert_spread[component][installer] the same with that installer's profile.
Quantile tails (PV 10 / 90%, battery 21 / 79%) are the smallest that give ~80% coverage in 5-fold cross-validation
on train (customer-grouped), not tuned on val: the old "all" row was fitted with profile ratios but applied without a
profile, which left battery coverage at 67% on val.
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


def ratios(df, use_profile=True):
    from design import core
    out = {k: {} for k in COLS}
    for _, r in df.iterrows():
        s = core(facts(r), {}, {}, r.installer if use_profile else None)["sizes"]
        for k, col in COLS.items():
            if s[k] and r[col] > 0:
                out[k].setdefault(r.installer, []).append(r[col] / s[k])
    return out


def coverage(df, use_profile=True):
    from design import design
    hit = {k: [] for k in COLS}
    for _, r in df.iterrows():
        d = design(facts(r), installer=r.installer if use_profile else None)
        for k, col in COLS.items():
            c = d["components"][k]
            if r[col] > 0 and c["recommended"] and c["range"]:
                hit[k].append(c["range"][0] <= r[col] <= c["range"][1])
    return {k: (len(v), round(float(np.mean(v)), 3)) for k, v in hit.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    ap.add_argument("--quantiles", type=float, nargs=2, default=[0.10, 0.90], help="PV")
    ap.add_argument("--battery-quantiles", type=float, nargs=2, default=[0.21, 0.79],
                    help="battery sizes are coarse catalogue steps, so a narrower band already covers ~80%%")
    ap.add_argument("--check", default=None, help="only report coverage on this split")
    args = ap.parse_args()
    if args.check:
        df = expert_designs(split=args.check)
        print(f"coverage on {args.check}, with installer profile:", coverage(df))
        print(f"coverage on {args.check}, no profile (customer flow):", coverage(df, use_profile=False))
        return
    q = {"pv": args.quantiles, "battery": args.battery_quantiles}
    df = expert_designs(split=args.split)
    rs, rs_all = ratios(df), ratios(df, use_profile=False)
    spread = {}
    for k, per in rs.items():
        lo, hi = q[k]
        every = [x for v in rs_all[k].values() for x in v]      # "all" is used without an installer profile
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
