# data/ — Data & Eval (owner: `EywaSahbi`)

You turn the raw CSVs into a clean table of homes with the design the expert actually delivered, fix the train / val / test split, and own the scoring that proves (or disproves) that the engine decides like an expert.
You write only in `data/`. `Project Data/` is read-only.

## Deliverables

1. **`data/processed/projects.parquet`** — one row per project: cleaned inputs (explicit units in column names: `energy_demand_kwh`, `energy_price_eur_per_kwh`, …) and expert targets (`has_pv, pv_kwp, has_battery, battery_kwh, has_heatpump, heatpump_kw, has_wallbox, wallbox_kw`), plus `installer` (source folder) and the `option_id` the targets came from.
2. **`data/processed/split.csv`** — `project_id,split` with `train` / `val` / `test`, fixed seed, stratified by installer. Never changes after M0 without a `DECISION`.
3. **Scoring tool** — `cd data && uv run python score.py <predictions.csv> [--split val|test]` prints metrics and writes `data/reports/score_<name>_<split>.json`. Predictions format is in [CONTRACT.md](CONTRACT.md).
4. **Reports for the pitch** — test-set metrics, deviation analysis (where and why the engine differs from experts), a few charts as PNG in `data/reports/`.

Metrics to start with: per component, presence accuracy / F1; size MAE and median absolute % error where both have the component; share of sizes within a tolerance (e.g. PV ±1 kWp, battery ±2 kWh); whole-bundle match. Compare against a naive baseline (e.g. median design) so numbers mean something.

## Data notes to verify first

- Several options per project: decide which one is "the expert design" (signed? lowest `option_number`?). If unclear, `DECISION` to ask the Reonic experts and use a documented default meanwhile.
- `inverter_power_kw` is filled on `BatteryStorage` rows and `battery_capacity_kwh` on `Inverter` rows: likely swapped columns. Verify against component names.
- PV size: `Module` rows with `module_watt_peak` are rare. Try package names ("10.8kWp + 9kWh"), module or substructure counts × typical Wp, and say which rule produced each value.
- Heat pumps only appear in `2a8ba8e2`; `23c108b7` sells packages. Keep `installer` as a column; per-installer behaviour may differ.
- Many input columns are mostly empty. Report coverage so the engine knows which inputs are real.

Write findings in `data/NOTES.md` (short, bullets). Post the important ones as `FYI` to engine.

## Commands

```bash
cd data && uv sync
uv run python build.py      # raw CSV -> processed/ (idempotent)
uv run python score.py ../engine/out/predictions_val.csv --split val
uv run pytest
```
(Create these files as you need them; keep it to a few scripts.)
