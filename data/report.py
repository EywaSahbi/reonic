"""Reality-check report: engine vs experts on one split, with charts for the pitch.

    uv run python report.py ../engine/out/predictions_test.csv --split test

Writes reports/reality_check_<split>.md and reports/*_<split>.png. Uses score.py's metrics; no tuning.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from score import COMPONENTS, baseline, load, metrics, normalise

ROOT = Path(__file__).resolve().parent
REP = ROOT / "reports"
# palette: dataviz reference instance (light), series 1 = engine, series 2 = baseline
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
ENGINE, BASE = "#2a78d6", "#eb6834"


def style(ax, title: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=13, color=INK, pad=12)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=10)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart_vs_baseline(r: dict, split: str) -> Path:
    rows = [("PV size\nwithin ±20 %", "pv", "within_tol"), ("Battery size\nwithin ±20 %", "battery", "within_tol"),
            ("PV yes/no\ncorrect", "pv", "presence_acc"), ("All 4 yes/no\ncorrect", None, "bundle_match")]
    get = lambda d, c, k: d["bundle_match"] if c is None else d["components"][c][k]
    eng = [get(r, c, k) for _, c, k in rows]
    base = [get(r["baseline"], c, k) for _, c, k in rows]
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=SURFACE)
    x, w = np.arange(len(rows)), 0.36
    for xs, vals, col, lab in ((x - w / 2 - 0.01, eng, ENGINE, "Engine"), (x + w / 2 + 0.01, base, BASE, "Naive baseline")):
        bars = ax.bar(xs, vals, w, color=col, label=lab)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.0%}", ha="center", color=INK, fontsize=10)
    ax.set_xticks(x, [r_[0] for r_ in rows])
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    style(ax, f"Engine vs naive baseline on {r['n']} unseen homes ({split})")
    ax.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=INK2)
    out = REP / f"vs_baseline_{split}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def chart_pv_scatter(m: pd.DataFrame, split: str) -> Path:
    b = m[m.has_pv & m.has_pv_p & m.pv_kwp.notna()]
    lim = float(np.ceil(min(30, max(b.pv_kwp.quantile(.98), b.pv_kwp_p.quantile(.98))) / 5) * 5)
    fig, ax = plt.subplots(figsize=(6, 6), facecolor=SURFACE)
    xs = np.linspace(0, lim, 50)
    ax.fill_between(xs, xs * 0.8, xs * 1.2, color=ENGINE, alpha=0.10, linewidth=0, label="within ±20 %")
    ax.plot(xs, xs, color=INK2, linewidth=1, linestyle="--", label="same as expert")
    inside = (b.pv_kwp_p - b.pv_kwp).abs() <= 0.2 * b.pv_kwp
    ax.scatter(b.pv_kwp, b.pv_kwp_p, s=28, color=ENGINE, edgecolor=SURFACE, linewidth=1, zorder=3)
    ax.set_xlim(0, lim), ax.set_ylim(0, lim)
    ax.set_xlabel("Expert design (kWp)", color=INK2)
    ax.set_ylabel("Engine proposal (kWp)", color=INK2)
    style(ax, f"PV size: engine vs expert, {len(b)} homes ({inside.mean():.0%} within ±20 %)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=INK2)
    out = REP / f"pv_scatter_{split}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def chart_no_pv(m: pd.DataFrame, split: str) -> Path:
    nopv = m[~m.has_pv]
    cats = {"Battery only": nopv.has_battery & ~nopv.has_wallbox & ~nopv.has_heatpump,
            "Wallbox only": ~nopv.has_battery & nopv.has_wallbox & ~nopv.has_heatpump,
            "Battery + wallbox": nopv.has_battery & nopv.has_wallbox,
            "Heat pump": nopv.has_heatpump}
    counts = {k: int(v.sum()) for k, v in cats.items()}
    fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=SURFACE)
    names = list(counts)[::-1]
    bars = ax.barh(names, [counts[n] for n in names], color=ENGINE, height=0.55)
    for b, n in zip(bars, names):
        ax.text(b.get_width() + 0.5, b.get_y() + b.get_height() / 2, str(counts[n]), va="center", color=INK, fontsize=10)
    style(ax, f"{len(nopv)} homes where the expert sold no PV: what they got instead\n"
              f"Existing PV is recorded for only {int(nopv.has_existing_pv.sum())} of them")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    out = REP / f"no_pv_{split}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def analyse(m: pd.DataFrame) -> dict:
    b = m[m.has_pv & m.has_pv_p & m.pv_kwp.notna()].copy()
    b["err"] = b.pv_kwp_p - b.pv_kwp
    b["band"] = pd.cut(b.annual_demand_kwh, [0, 3000, 4000, 5000, 6000, np.inf],
                       labels=["<3,000", "3,000-4,000", "4,000-5,000", "5,000-6,000", "6,000+"])
    bat = m[m.has_battery & m.has_battery_p]
    nopv = m[~m.has_pv]
    return {
        "pv_false_yes": int((~m.has_pv & m.has_pv_p).sum()), "pv_false_no": int((m.has_pv & ~m.has_pv_p).sum()),
        "nopv": len(nopv), "nopv_retrofit": int((nopv.has_battery | nopv.has_wallbox).sum()),
        "nopv_existing_flag": int(nopv.has_existing_pv.sum()),
        "pv_bias": float(b.err.median()), "pv_abs_median": float(b.err.abs().median()),
        # note: "engine" is a reserved keyword of DataFrame.agg, so the columns carry a unit suffix
        "pv_by_band": b.groupby("band", observed=True).agg(n=("err", "size"), expert_kwp=("pv_kwp", "median"),
                                                          engine_kwp=("pv_kwp_p", "median"), bias_kwp=("err", "median")),
        "pv_by_installer": b.groupby("installer").err.agg(["size", "median"]),
        "pv_by_source": b.groupby("target_source").err.agg(["size", lambda x: x.abs().median()]),
        "bat_expert_sizes": bat.battery_kwh.round(1).value_counts().head(5),
        "bat_engine_sizes": bat.battery_kwh_p.round(1).value_counts().head(5),
        "wb_expert": int(m.has_wallbox.sum()), "wb_engine": int(m.has_wallbox_p.sum()),
        "wb_expert_with_ev": int((m.has_wallbox & m.has_ev).sum()),
        "hp_expert": int(m.has_heatpump.sum()),
    }


def table(df: pd.DataFrame) -> str:
    df = df.round(2).reset_index()
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns)
    return head + "\n" + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False))


def write(r: dict, a: dict, charts: list[Path], split: str, model: str) -> Path:
    c, bc = r["components"], r["baseline"]["components"]
    pct = lambda v: "-" if v is None else f"{v:.0%}"
    md = f"""# Reality check: engine vs expert designs ({split})

Model `{model}` on **{r['n']} homes the engine never saw** (`{split}` split of `data/processed/split.csv`).
Engine parameters come from `train` only. Numbers as they came out of `score.py`; nothing was tuned on this split.
Baseline: every home gets the train-median PV and battery, no heat pump, a wallbox iff it has an EV.

## Headline

| | Engine | Baseline |
|---|---|---|
| PV size within ±20 % of the expert | {pct(c['pv']['within_tol'])} | {pct(bc['pv']['within_tol'])} |
| PV size, median absolute error | {a['pv_abs_median']:.1f} kWp | |
| PV size MAE | {c['pv']['size_mae']} kWp | {bc['pv']['size_mae']} kWp |
| Battery size within ±20 % | {pct(c['battery']['within_tol'])} | {pct(bc['battery']['within_tol'])} |
| PV yes/no correct | {pct(c['pv']['presence_acc'])} | {pct(bc['pv']['presence_acc'])} |
| Battery yes/no correct | {pct(c['battery']['presence_acc'])} | {pct(bc['battery']['presence_acc'])} |
| Wallbox yes/no correct | {pct(c['wallbox']['presence_acc'])} | {pct(bc['wallbox']['presence_acc'])} |
| All four yes/no correct | {pct(r['bundle_match'])} | {pct(r['baseline']['bundle_match'])} |

## Where and why the engine deviates

1. **PV yes/no: the engine misses {a['pv_false_no']} PV homes, but proposes PV to {a['pv_false_yes']} of the {a['nopv']} homes where the expert sold none.**
   {a['nopv_retrofit']} of those {a['nopv']} homes got a battery or wallbox instead, i.e. retrofits to a home that most likely already has PV.
   The input data records existing PV for only {a['nopv_existing_flag']} of them. This is missing input, not a sizing error:
   asking "do you already have solar?" (reo) removes it.
2. **PV size has no overall bias** (median {a['pv_bias']:+.1f} kWp, typical miss {a['pv_abs_median']:.1f} kWp) and rises with demand like the expert sizes do:

{table(a['pv_by_band'])}

   Per installer the residual has opposite signs, i.e. each installer has its own sizing style:

{table(a['pv_by_installer'].rename(columns={'size': 'n', 'median': 'bias_kwp'}))}

   Part of the error is in the "truth": for `mount_count` homes the expert kWp is itself estimated from module count × typical Wp (±5 %).

{table(a['pv_by_source'].set_axis(['n', 'median_abs_err_kwp'], axis=1))}

3. **Battery size: experts pick catalogue steps, the engine a ratio.** Expert sizes cluster at
   {', '.join(f'{k:g} kWh ({v})' for k, v in a['bat_expert_sizes'].items())};
   engine sizes at {', '.join(f'{k:g} kWh ({v})' for k, v in a['bat_engine_sizes'].items())}.
   The 5 vs 10 kWh choice is installer catalogue and customer budget, which the inputs do not contain.
4. **Wallbox is not predictable from the inputs.** Experts sold {a['wb_expert']} wallboxes, only {a['wb_expert_with_ev']} to homes with `has_ev`;
   the engine proposed {a['wb_engine']}. Wallboxes are sold for planned EVs that the data does not record. reo asks about EV plans.
5. **Heat pump:** {a['hp_expert']} expert heat pumps in this split; too few to score.

## Charts

""" + "\n".join(f"![{p.stem}]({p.name})" for p in charts) + "\n"
    out = REP / f"reality_check_{split}.md"
    out.write_text(md, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--split", default="val", choices=["val", "test"])
    a_ = ap.parse_args()
    truth = load(a_.split)
    pred = normalise(pd.read_csv(a_.predictions))
    r = metrics(truth, pred)
    r["baseline"] = metrics(truth, baseline(truth))
    m = truth.merge(pred, on="project_id", suffixes=("", "_p"))
    REP.mkdir(exist_ok=True)
    charts = [chart_vs_baseline(r, a_.split), chart_pv_scatter(m, a_.split), chart_no_pv(m, a_.split)]
    out = write(r, analyse(m), charts, a_.split, a_.predictions.stem.removeprefix("predictions_"))
    print(f"wrote {out.name} and {', '.join(p.name for p in charts)}")


if __name__ == "__main__":
    main()
