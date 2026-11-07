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

Built by `uv run python benchmarks.py` from `train` only.

```json
{"built_from": "train", "n_train": 1098, "min_n": 15,
 "demand_bands": ["0-3000", "3000-4000", "4000-5000", "5000-6000", "6000+"],
 "segments": [
  {"level": 2, "key": {"demand_band": "4000-5000", "has_ev": false}, "n": 403,
   "pv_kwp": {"p10": 4.8, "p50": 9.5, "p90": 13.5, "values": [0.47, 1.35, "... sorted"]},
   "battery_kwh": {"p10": 5.0, "p50": 7.0, "p90": 14.0, "values": [3.5, 4.6, "..."]},
   "battery_kwh_per_kwp": {"p10": 0.6, "p50": 0.9, "p90": 1.7, "values": ["..."]},
   "attach_rate": {"pv": 0.59, "battery": 0.86, "heatpump": 0.01, "wallbox": 0.26},
   "typical_sizes": {"battery_kwh": [{"size": 5.0, "share": 0.35}, {"size": 10.0, "share": 0.26}, {"size": 7.0, "share": 0.13}],
                     "pv_kwp": [{"size": 10.0, "share": 0.17}, {"size": 11.0, "share": 0.15}, {"size": 9.0, "share": 0.1}]}}
 ]}
```

- **Levels:** 3 = `demand_band` × `has_ev` × `heating_type`, 2 = band × EV, 1 = band, 0 = all homes. `heating_type` null → `"unknown"`, demand null → `"unknown"`.
- **Lookup:** take the segment with the highest level whose key matches the home and `n >= min_n`. Level 0 always exists. EV homes are rare (~4 %), so their level-2/3 segments are mostly below `min_n` and fall back to level 1.
- `values`: every expert size in the segment, sorted, so "larger than X % of similar homes" = share of `values` below the size. Sizes only over homes that have the component; `attach_rate` is the share of all homes in the segment.
- The example is the real level-2 segment at the time of writing; read the file for current values.
- Percentile fields: `p10`, `p25`, `p50`, `p75`, `p90` (p25 / p75 added for variant anchors).

## Lookups for reo (spec; reference code `data/lookup.py`, tested in `test_lookup.py`)

reo reads the files and implements these itself (no imports across folders). Only `train` homes are used or shown.

| Lookup | Rule |
|---|---|
| `demand_band(kwh)` | `annual_demand_kwh` (household only, WITHOUT EV / heat pump) → the `demand_bands` label with `lo <= kwh < hi` (`6000+` open); none → `"unknown"`. Do not band a customer's `total_demand_kwh`: the data's bands are household-only, so a total puts the home 1–2 bands too high. If only a total is known, use level 0 or ask for the household figure. |
| `home_key(home)` | `{demand_band, has_ev: has_ev or ev_planned, heating_type or "unknown"}` |
| `segment(home)` | segments with `n >= min_n` whose `key` fields all equal the home's; take the highest `level`. Level 0 always matches. |
| `percentile_of(home, c, size)` | `c ∈ {pv, battery}`: share of `segment[c_size].values` strictly below `size` (bisect left), 0..1. Flag when ≥ 0.85 or ≤ 0.15. |
| `size_at(home, c, q)` | `segment[c_size]["p" + q]` for q ∈ 10/25/50/75/90. Suggested variant anchors, to pass as locks to the engine (numbers still come from the engine): **Basic** battery at p25 (or none if `attach_rate.battery < 0.5`), **Recommended** = engine's own design, **Independence** PV and battery at p75. |
| `similar_projects(home, k=3)` | train homes, filtered step by step, each filter kept only if ≥ k homes remain: same EV group → same `has_existing_pv` → same `heating_type`. Then nearest `annual_demand_kwh`, ties by `installer`, `project_id`. Returns inputs + expert design per home. Installer view only, never to the customer or the LLM (hard rule 5). |

Retrofits: homes the expert sold no PV are mostly retrofits with unrecorded existing PV (`reports/reality_check_test.md`). PV size percentiles already exclude them (only homes with PV); `attach_rate.pv` does not.

## Predictions CSV (input to `score.py`)

`project_id,has_pv,pv_kwp,has_battery,battery_kwh,has_heatpump,heatpump_kw,has_wallbox,wallbox_kw` — sizes 0 or empty when not recommended.

## Score JSON (`data/reports/score_<name>_<split>.json`)

```json
{"split": "val", "model": "<file name after predictions_>", "n": 238, "missing_predictions": 0,
 "components": {"pv": {"n_expert": 185, "presence_acc": 0.782, "f1": 0.877, "size_n": 185, "size_mae": 2.49,
                       "size_mdape": 0.208, "within_tol": 0.465}, "...": {}},
 "bundle_match": 0.559,
 "by_installer": {"23c108b7": {"n": 51, "components": {}, "bundle_match": 0}, "2a8ba8e2": {"n": 187}},
 "baseline": {"n": 238, "components": {}, "bundle_match": 0.55},
 "tolerance": {"pv": 0.2, "battery": 0.2, "heatpump": 0.2, "wallbox": 0.05}}
```

- `presence_acc`: share of homes where the yes/no matches the expert. `f1`: for "component recommended".
- Size metrics only over homes where both expert and prediction have the component: `size_mae` (kWp / kWh / kW), `size_mdape` (median relative error), `within_tol` (share within the relative tolerance).
- `bundle_match`: all four yes/no decisions match.
- `baseline`: naive design from `train` (PV and battery always at the train median, no heat pump, wallbox iff `has_ev`).
