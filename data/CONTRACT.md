# data/ contract (v0 draft — owner `EywaSahbi` finalises at M0)

What `data/` publishes for engine and app. Changes: additive changes → `CONTRACT` message; breaking changes → consumers must `ACK` (after M1: `DECISION`).

## `data/processed/projects.parquet`

One row per project. Units are in the column names.

| Column | Type | Notes |
|---|---|---|
| `project_id` | str | key |
| `installer` | str | source folder (`2a8ba8e2`, `23c108b7`) |
| `energy_demand_kwh` | float | annual household electricity demand |
| `energy_price_eur_per_kwh` | float | |
| `has_ev`, `ev_annual_km` | bool, float | |
| `heating_existing_type` | str / null | `Heatpump`, `Gas`, `Oil`, … |
| `heating_demand_kwh` | float / null | |
| `has_existing_pv`, `has_existing_storage`, `has_wallbox_existing` | bool | |
| `house_size_sqm`, `num_inhabitants` | float / null | mostly empty |
| … | | more inputs as found useful; list them here |
| `option_id` | str | the option used as the expert design |
| `has_pv`, `pv_kwp` | bool, float | expert target |
| `has_battery`, `battery_kwh` | bool, float | expert target |
| `has_heatpump`, `heatpump_kw` | bool, float | expert target |
| `has_wallbox`, `wallbox_kw` | bool, float | expert target |
| `target_source` | str | how sizes were derived (e.g. `module_rows`, `package_name`) |

## `data/processed/split.csv`

`project_id,split` with `split ∈ {train, val, test}`. Fixed. Test is used only for final reported numbers.

## Predictions CSV (input to the scoring tool)

`project_id,has_pv,pv_kwp,has_battery,battery_kwh,has_heatpump,heatpump_kw,has_wallbox,wallbox_kw`
Sizes are 0 or empty when the component is not recommended. Engine writes these to `engine/out/predictions_<split>.csv`.

## Scoring

`cd data && uv run python score.py <predictions.csv> --split val|test` → stdout summary + `data/reports/score_<name>_<split>.json`:

```json
{"split": "val", "n": 240, "model": "<name>",
 "components": {"pv": {"presence_acc": 0.97, "f1": 0.98, "size_mae": 1.1, "size_mdape": 0.09, "within_tol": 0.71}, "...": {}},
 "bundle_match": 0.62, "baseline": {"...": {}}}
```
