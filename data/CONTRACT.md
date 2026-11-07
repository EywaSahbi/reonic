# data/ contract (v0 draft — owner `EywaSahbi` finalises at M0)

What `data/` publishes. Consumers: engine (`projects.parquet`, `split.csv`, `score.py`), reo (`benchmarks.json`, `projects.parquet`, score JSON).
Changes: additive → `CONTRACT` message; breaking → consumers must `ACK` (after M1: `DECISION`).

## `data/processed/projects.parquet`

One row per project. Input columns use the `HomeFacts` names from `engine/CONTRACT.md` (`annual_demand_kwh`, `has_ev`, `ev_km_per_year`, `heating_type`, `heating_demand_kwh`, `electricity_price_eur_per_kwh`, …; missing → null). Plus:

| Column | Type | Notes |
|---|---|---|
| `project_id` | str | key |
| `installer` | str | source folder |
| `option_id` | str | option used as the expert design |
| `has_pv`, `pv_kwp` | bool, float | expert target |
| `has_battery`, `battery_kwh` | bool, float | expert target |
| `has_heatpump`, `heatpump_kw` | bool, float | expert target |
| `has_wallbox`, `wallbox_kw` | bool, float | expert target |
| `target_source` | str | how sizes were derived |

## `data/processed/split.csv`

`project_id,split` with `split ∈ {train, val, test}`. Fixed.

## `data/processed/benchmarks.json`

```json
{"built_from": "train", "segments": [
  {"key": {"demand_band": "4000-6000", "has_ev": true, "heating_type": "gas"}, "n": 87,
   "pv_kwp": {"p10": 6.3, "p50": 9.5, "p90": 12.6}, "battery_kwh": {"p10": 5, "p50": 9, "p90": 12},
   "attach_rate": {"battery": 0.71, "heatpump": 0.08, "wallbox": 0.62}}
]}
```

## Predictions CSV (input to `score.py`)

`project_id,has_pv,pv_kwp,has_battery,battery_kwh,has_heatpump,heatpump_kw,has_wallbox,wallbox_kw` — sizes 0 or empty when not recommended.

## Score JSON (`data/reports/score_<name>_<split>.json`)

```json
{"split": "val", "n": 240, "model": "<params_version>",
 "components": {"pv": {"presence_acc": 0.97, "f1": 0.98, "size_mae": 1.1, "size_mdape": 0.09, "within_tol": 0.71}, "...": {}},
 "bundle_match": 0.62, "baseline": {"...": {}}}
```
