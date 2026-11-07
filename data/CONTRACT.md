# data/ contract (v1 — owner `EywaSahbi`)

What `data/` publishes. Consumers: engine (`projects.parquet`, `split.csv`, `score.py`), reo (`benchmarks.json`, `projects.parquet`, score JSON).
Changes: additive → `CONTRACT` message; breaking → consumers must `ACK` (after M1: `DECISION`).
Rebuild: `cd data && uv sync && uv run python build.py` (idempotent). Derivation rules: [NOTES.md](NOTES.md).

## `data/processed/projects.parquet`

1,571 rows, one per project (projects without a hardware option are dropped). Missing values are null.

**Inputs, `HomeFacts` names** (`engine/CONTRACT.md`), so a row can be fed to `/design` as is:

| Column | Type | Notes |
|---|---|---|
| `annual_demand_kwh` | float | household only, WITHOUT EV and heat pump; 0 in raw → null |
| `num_inhabitants`, `house_size_sqm`, `house_built_year` | float | < 1 % filled |
| `heating_type` | str | `heatpump` / `gas` / `oil` / `other`; null for ~87 % |
| `heating_demand_kwh` | float | heat demand of the existing heating |
| `has_ev`, `ev_km_per_year` | bool, float | |
| `electricity_price_eur_per_kwh` | float | 0 and implausible values → null |
| `has_existing_pv`, `existing_pv_kwp`, `has_existing_battery` | bool, float, bool | |

Not in the data, so absent: `total_demand_kwh`, `ev_planned`, `ev_km_per_week/day`, `roof_*`, `region`, `budget_eur`.

**Extra context** (not HomeFacts): `existing_battery_kwh`, `has_existing_wallbox`, `existing_heating_electricity_kwh` (kWh/year the existing heat pump uses), `flexible_price_eur_per_kwh`, `load_profile`, `country`, `customer_contact_id`, `offer_created_at`.

**Expert design:**

| Column | Type | Notes |
|---|---|---|
| `project_id` | str | key |
| `installer` | str | source folder (`23c108b7`, `2a8ba8e2`) |
| `option_id` | str | option used as the expert design (rule in NOTES.md) |
| `has_pv`, `pv_kwp`, `pv_modules` | bool, float, float | kWp; module count where known |
| `has_battery`, `battery_kwh` | bool, float | |
| `has_heatpump`, `heatpump_kw` | bool, float | only 22 projects, all `2a8ba8e2` |
| `has_wallbox`, `wallbox_kw` | bool, float | |
| `target_source` | str | how `pv_kwp` was derived: `package_name`, `module_rows`, `mount_count` (estimate), `none`, `pv_size_unknown` |

Sizes are null when the component is absent.

## `data/processed/split.csv`

`project_id,split` with `split ∈ {train, val, test}` (1,098 / 238 / 235). Seed 42, 70/15/15 per installer, split by customer so no customer is in two splits. Fixed: changes only via `DECISION`.

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
