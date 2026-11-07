"""Per-installer comparison: engine with vs without installer_profile, against the naive baseline.

    uv run python installers.py ../engine/out/predictions_val.csv ../engine/out/predictions_val_profiles.csv --split val

Writes reports/installer_style_<split>.md. Uses score.py's metrics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from score import ROOT, load, normalise, run


def pv_bias(truth: pd.DataFrame, pred_path: Path) -> pd.Series:
    """Median signed PV error (engine - expert, kWp) per installer, homes where both have PV."""
    m = truth.merge(normalise(pd.read_csv(pred_path)), on="project_id", suffixes=("", "_p"))
    m = m[m.has_pv & m.has_pv_p & m.pv_kwp.notna()]
    return (m.pv_kwp_p - m.pv_kwp).groupby(m.installer).median()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("without", type=Path)
    ap.add_argument("with_profiles", type=Path)
    ap.add_argument("--split", default="val", choices=["val", "test"])
    a = ap.parse_args()
    truth = load(a.split)
    r0, r1 = run(a.without, a.split), run(a.with_profiles, a.split)
    b0, b1 = pv_bias(truth, a.without), pv_bias(truth, a.with_profiles)
    pct = lambda v: "-" if v is None else f"{v:.0%}"
    rows = []
    for inst in sorted(r0["by_installer"]):
        e0, e1, bl = r0["by_installer"][inst], r1["by_installer"][inst], r0["baseline_by_installer"][inst]
        for comp, label in (("pv", "PV size within ±20 %"), ("battery", "Battery size within ±20 %")):
            rows.append(f"| {inst} (n={e0['n']}) | {label} | {pct(bl['components'][comp]['within_tol'])} | "
                        f"{pct(e0['components'][comp]['within_tol'])} | {pct(e1['components'][comp]['within_tol'])} |")
        rows.append(f"| {inst} | PV size MAE (kWp) | {bl['components']['pv']['size_mae']} | "
                    f"{e0['components']['pv']['size_mae']} | {e1['components']['pv']['size_mae']} |")
        rows.append(f"| {inst} | PV median bias (kWp, engine − expert) | | {b0.get(inst, np.nan):+.2f} | {b1.get(inst, np.nan):+.2f} |")
    md = f"""# Installer style: engine with vs without installer_profile ({a.split})

Same `{a.split}` homes, engine parameters from `train` only. "With profile" fits the PV line and battery bands
on each installer's own `train` projects. Baseline: train medians, wallbox iff EV.

| Installer | Metric | Baseline | Engine, all installers | Engine, installer profile |
|---|---|---|---|---|
""" + "\n".join(rows) + f"""

Overall: PV within ±20 % {pct(r0['components']['pv']['within_tol'])} → {pct(r1['components']['pv']['within_tol'])}, \
battery {pct(r0['components']['battery']['within_tol'])} → {pct(r1['components']['battery']['within_tol'])}, \
bundle match {pct(r0['bundle_match'])} → {pct(r1['bundle_match'])} (baseline {pct(r0['baseline']['bundle_match'])}).
"""
    out = ROOT / "reports" / f"installer_style_{a.split}.md"
    out.write_text(md, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console is cp1252
    print(md)


if __name__ == "__main__":
    main()
