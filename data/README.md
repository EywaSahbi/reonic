# data/ — expert designs, the fixed split, scoring and benchmarks

> Back to the [project README](../README.md). Owner: `EywaSahbi`. The raw data stays in [`Project Data/`](../Project%20Data/) (read-only, never edited, never leaves the team).

This folder turns the two installers' raw CSVs into **one row per project** (the home's facts and the expert design), fixes the train/val/test split, and is the **only** place that produces test scores.

## Pipeline

| Step | File | Output |
|---|---|---|
| Raw CSVs → one expert design per project, inputs under the engine's `HomeFacts` names | [`build.py`](build.py) | `processed/projects.parquet`, `processed/split.csv` (1,098 train / 238 val / 235 test, by customer, no leakage) |
| What experts deliver for similar homes (train only) | [`benchmarks.py`](benchmarks.py) | `processed/benchmarks.json` (reo's flags) |
| Hard-case homes for the harness evals | [`scenarios.py`](scenarios.py) | `processed/scenarios.json` |
| Engine predictions vs experts | [`score.py`](score.py) | JSON reports in `reports/` |
| Per-installer comparison with and without profile | [`installers.py`](installers.py) | `reports/installer_style_val.md` |
| Reality-check report with charts | [`report.py`](report.py) | `reports/reality_check_*.md` + PNGs |
| Lookups reo uses (reference spec in code) | [`lookup.py`](lookup.py) | |

## Rules that make the numbers honest

- The split is fixed. The engine's parameters are fitted on `train`, choices made on `val`, and `test` is scored once with `score.py`, reported as it comes out, including where we lose.
- Expert design = the highest option with hardware per project (which option was signed is an open question for Reonic). 1,571 of 1,619 projects remain; the build rules are in [NOTES.md](NOTES.md).
- `lookup.py` and the benchmarks only ever use `train` homes.

## Read next

[CONTRACT.md](CONTRACT.md) (files and formats others rely on) · [NOTES.md](NOTES.md) (extraction rules, what the targets look like) · [`reports/`](reports/) (reality checks, charts) · [STATUS.md](STATUS.md) · [dataset profiling](../docs/dataset_explanation.md).

## Run

```bash
cd data
uv sync
uv run python build.py && uv run python benchmarks.py
uv run python score.py ../engine/out/predictions_test.csv --split test
uv run pytest
```
