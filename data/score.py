"""Score engine predictions against the expert designs.

    uv run python score.py <predictions.csv> --split val|test|train|all

Prints a summary and writes reports/score_<name>_<split>.json (format in CONTRACT.md).
Always scores a naive baseline built from `train` next to the predictions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
COMPONENTS = {"pv": "pv_kwp", "battery": "battery_kwh", "heatpump": "heatpump_kw", "wallbox": "wallbox_kw"}
TOL = {"pv": 0.20, "battery": 0.20, "heatpump": 0.20, "wallbox": 0.05}  # relative size tolerance


def load(split: str) -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "processed" / "projects.parquet")
    sp = pd.read_csv(ROOT / "processed" / "split.csv")
    df = df.merge(sp, on="project_id")
    return df if split == "all" else df[df.split == split]


def normalise(pred: pd.DataFrame) -> pd.DataFrame:
    """has_* from the flag if given, else from size > 0; sizes 0/empty when absent."""
    out = pred[["project_id"]].copy()
    for c, size in COMPONENTS.items():
        s = pd.to_numeric(pred.get(size), errors="coerce").fillna(0.0)
        flag = pred[f"has_{c}"].astype(str).str.lower().isin(["true", "1"]) if f"has_{c}" in pred else s > 0
        out[f"has_{c}"] = flag.values
        out[size] = np.where(flag, s, 0.0)
    return out


def metrics(truth: pd.DataFrame, pred: pd.DataFrame) -> dict:
    m = truth.merge(pred, on="project_id", suffixes=("_t", "_p"))
    res = {}
    for c, size in COMPONENTS.items():
        t, p = m[f"has_{c}_t"].astype(bool).values, m[f"has_{c}_p"].astype(bool).values
        tp, fp, fn = int((t & p).sum()), int((~t & p).sum()), int((t & ~p).sum())
        both = t & p & m[f"{size}_t"].notna().values & (m[f"{size}_p"].values > 0)
        st, sp_ = m[f"{size}_t"].values[both], m[f"{size}_p"].values[both]
        err = np.abs(sp_ - st)
        res[c] = {
            "n_expert": int(t.sum()),
            "presence_acc": round(float((t == p).mean()), 3),
            "f1": round(2 * tp / (2 * tp + fp + fn), 3) if tp + fp + fn else None,
            "size_n": int(both.sum()),
            "size_mae": round(float(err.mean()), 2) if both.any() else None,
            "size_mdape": round(float(np.median(err / st)), 3) if both.any() else None,
            "within_tol": round(float((err <= TOL[c] * st).mean()), 3) if both.any() else None,
        }
    presence = np.all([m[f"has_{c}_t"].astype(bool) == m[f"has_{c}_p"].astype(bool) for c in COMPONENTS], axis=0)
    return {"n": len(m), "components": res, "bundle_match": round(float(presence.mean()), 3)}


def baseline(truth: pd.DataFrame) -> pd.DataFrame:
    """Naive design from train: PV and battery always at the train median, no heat pump, wallbox iff EV."""
    train = load("train")
    b = truth[["project_id"]].copy()
    b["has_pv"], b["pv_kwp"] = True, train.pv_kwp.median()
    b["has_battery"], b["battery_kwh"] = True, train.battery_kwh.median()
    b["has_heatpump"], b["heatpump_kw"] = False, 0.0
    b["has_wallbox"] = truth.has_ev.values
    b["wallbox_kw"] = np.where(b.has_wallbox, train.wallbox_kw.median(), 0.0)
    return b


def run(pred_path: Path, split: str) -> dict:
    truth = load(split)
    pred = normalise(pd.read_csv(pred_path))
    missing = set(truth.project_id) - set(pred.project_id)
    name = pred_path.stem.removeprefix("predictions_")
    report = {"split": split, "model": name, **metrics(truth, pred),
              "missing_predictions": len(missing),
              "by_installer": {inst: metrics(g, pred) for inst, g in truth.groupby("installer")},
              "baseline": metrics(truth, baseline(truth)),
              "baseline_by_installer": {inst: metrics(g, baseline(g)) for inst, g in truth.groupby("installer")},
              "tolerance": TOL}
    out = ROOT / "reports" / f"score_{name}_{split}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    return report


def show(r: dict) -> None:
    print(f"split={r['split']} model={r['model']} n={r['n']} missing={r['missing_predictions']}")
    print(f"{'':10s}{'presence':>9s}{'f1':>7s}{'MAE':>7s}{'MdAPE':>7s}{'in_tol':>7s}   | baseline presence / in_tol")
    for c, v in r["components"].items():
        b = r["baseline"]["components"][c]
        f = lambda x, p=3: "-" if x is None else f"{x:.{p}f}" if isinstance(x, float) else str(x)
        print(f"{c:10s}{f(v['presence_acc']):>9s}{f(v['f1']):>7s}{f(v['size_mae'], 2):>7s}"
              f"{f(v['size_mdape']):>7s}{f(v['within_tol']):>7s}   | {f(b['presence_acc'])} / {f(b['within_tol'])}")
    print(f"bundle_match {r['bundle_match']:.3f}   (baseline {r['baseline']['bundle_match']:.3f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--split", default="val", choices=["train", "val", "test", "all"])
    a = ap.parse_args()
    if a.split == "test":
        print("note: test split. Report these numbers as they come out; do not tune on them.")
    show(run(a.predictions, a.split))


if __name__ == "__main__":
    main()
