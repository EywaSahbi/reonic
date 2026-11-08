# data/ — evidence and validation (owner: `EywaSahbi`)

We do not train a model on the data. The data is the **evidence**: it defines what expert installers actually delivered, we validate the engine against it on projects it has never seen, and it powers reo's flags ("unusually large for a home like this").
You write only in `data/`. `Project Data/` is read-only. Facts already established are in `docs/dataset_explanation.md`.

## Deliverables

1. **`data/processed/projects.parquet`** — one row per project: inputs using the engine's `HomeFacts` field names (see `engine/CONTRACT.md`, so `predict.py` can feed rows straight in) and expert targets `has_pv, pv_kwp, has_battery, battery_kwh, has_heatpump, heatpump_kw, has_wallbox, wallbox_kw`, plus `installer` and the `option_id` used. Remember: battery kWh sits in `inverter_power_kw` (swapped, Wh); `energy_demand_wh` excludes EV and heat pump.
2. **`data/processed/split.csv`** — `project_id,split` (`train` / `val` / `test`), fixed seed, stratified by installer. Never changes after M0 without a `DECISION`.
3. **`score.py`** — `cd data && uv run python score.py <predictions.csv> --split val|test` → stdout + `data/reports/score_<name>_<split>.json` (format in [CONTRACT.md](CONTRACT.md)). Always include a naive baseline (e.g. median design) so numbers mean something.
4. **`data/processed/benchmarks.json`** — for reo's flags and the installer view: per segment (demand band × EV × heating), percentiles (p10/p50/p90) of PV kWp and battery kWh, attach rates of battery / heat pump / wallbox, and typical package sizes. Built from `train` only.
5. **Reality-check report** (M2): test-set scores, where and why the engine deviates from experts, 2–3 charts as PNG in `data/reports/` for the pitch.

Multiple options per project: use a documented default (e.g. the largest-numbered complete option, or the one with the most parts) and ask the Reonic experts via `DECISION` if unsure.

## Commands

```bash
cd data && uv sync
uv run python build.py      # raw CSV -> processed/ (idempotent)
uv run python score.py ../engine/out/predictions_val.csv --split val
```
