"""Run the engine on every dataset project and compare with what the experts offered (PLAN.md #16).

    uv run python predict.py          → out/predictions_all.csv (data/CONTRACT.md format) + scores printed

The whole dataset is used (owner's decision); the PV line, r_B and catalogues were derived from the same
projects, so these scores are in-sample for those few parameters. data's score.py stays the official scorer.
"""
import json
from pathlib import Path

import pandas as pd

from dataset import expert_designs, facts
from design import VERSION, core
from inputs import PARAMS

OUT = Path(__file__).parent / "out"
TOL = {"pv": 0.2, "battery": 0.2, "heatpump": 0.2, "wallbox": 0.0}   # size within ±20% (wallbox exact)


def predict(df):
    rows = []
    for _, r in df.iterrows():
        s = core(facts(r), {}, {})["sizes"]
        rows.append({"project_id": r.project_id,
                     **{f"has_{k}": bool(s[k]) for k in ("pv", "battery", "heatpump", "wallbox")},
                     "pv_kwp": s["pv"] or 0, "battery_kwh": s["battery"] or 0,
                     "heatpump_kw": s["heatpump"] or 0, "wallbox_kw": s["wallbox"] or 0})
    return pd.DataFrame(rows)


def score(truth, pred):
    out = {}
    for k, col in (("pv", "pv_kwp"), ("battery", "battery_kwh"), ("heatpump", "heatpump_kw"), ("wallbox", "wallbox_kw")):
        t, p = truth[col].values > 0, pred[col].values > 0
        both = t & p
        err = abs(pred[col].values[both] - truth[col].values[both])
        tp, fp, fn = (t & p).sum(), (~t & p).sum(), (t & ~p).sum()
        out[k] = {"presence_acc": round(float((t == p).mean()), 3),
                  "f1": round(float(2 * tp / (2 * tp + fp + fn)), 3) if tp + fp + fn else None,
                  "size_mae": round(float(err.mean()), 2) if both.any() else None,
                  "size_median_ae": round(float(pd.Series(err).median()), 2) if both.any() else None,
                  "within_tol": round(float((err <= TOL[k] * truth[col].values[both]).mean()), 3) if both.any() else None,
                  "n_expert": int(t.sum())}
    return out


def baseline(truth):
    """Simple rules to beat: PV and battery always at the experts' median size, wallbox iff EV."""
    b = truth[["project_id"]].copy()
    b["pv_kwp"] = truth.pv_kwp[truth.pv_kwp > 0].median()
    b["battery_kwh"] = truth.battery_kwh[truth.battery_kwh > 0].median()
    b["heatpump_kw"] = 0.0
    b["wallbox_kw"] = truth.has_ev.map({True: 11.0, False: 0.0})
    return b


def main():
    truth = expert_designs(PARAMS["k_ev_kwh_per_km"], PARAMS["cop"])
    pred = predict(truth)
    OUT.mkdir(exist_ok=True)
    pred.to_csv(OUT / "predictions_all.csv", index=False)

    report = {"split": "all", "n": len(truth), "model": VERSION, "components": score(truth, pred),
              "baseline": score(truth, baseline(truth)),
              "per_installer": {i: score(truth[truth.installer == i], pred[truth.installer == i])
                                for i in sorted(truth.installer.unique())}}
    (OUT / "score_all.json").write_text(json.dumps(report, indent=2))
    print(f"{len(truth)} projects, model {VERSION}")
    for k in report["components"]:
        e, b = report["components"][k], report["baseline"][k]
        print(f"  {k:9} presence {e['presence_acc']:.0%} (baseline {b['presence_acc']:.0%})  "
              f"size MAE {e['size_mae']} (baseline {b['size_mae']})  within tol {e['within_tol']} (baseline {b['within_tol']})")


if __name__ == "__main__":
    main()
