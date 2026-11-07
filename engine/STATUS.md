# engine/ status (owner: `egeunluer`)

## New session: start here

1. [METHOD.md](METHOD.md): how a design is made, every rule and parameter, final results, known limits.
2. This file: backlog, what is published, scores, decisions.
3. [CONTRACT.md](CONTRACT.md): the API reo calls. [SOURCES.md](SOURCES.md): where every outside number comes from. [PLAN.md](PLAN.md): build log.
4. Run: `cd engine && uv sync && uv run uvicorn api:app --port 8000`; check: `uv run pytest`; rebuild parameters: METHOD.md section 10.

## Backlog (top = next)

Plan and what each item became: [PLAN.md](PLAN.md). Method: [METHOD.md](METHOD.md). Every outside number: [SOURCES.md](SOURCES.md).

- [x] Step 0 (`inputs.py`): HomeFacts → home, PV from the expert line, existing PV, orientation, roof check, heat-pump suggestion and kW
- [x] Y from PVGIS + MaStR (`tools/derive_y.py`); line, r_B, catalogues from the dataset (`tools/derive_params.py`); hourly profiles (`tools/derive_profiles.py`)
- [x] Hourly simulation (`sim.py`), battery, wallbox, price list, economics, bills (`design.py`, `prices.json`)
- [x] Ranges, ranked `missing_inputs`, reasons, confidence, bundle, locks, budget (`design.py`)
- [x] API `/health`, `/prices`, `/design`, `/explain` (`api.py`); `predict.py` evaluation
- [x] Phase 2: battery by expert bands, installer profiles, retrofit rule, /explain deltas + step what-ifs
- [x] Phase 2: H0 optimism calibrated on 74 measured homes; sourced price list; placeholders replaced by published values (two left, PLAN.md)

## Published

- `CONTRACT.md` v1: `ev_km_per_week`, `ev_km_per_day` (f38af8a), `total_demand_kwh` (336060e), `region` (718cd3f); `building_type`, `roof_type`, `bundle`, monthly bills, `_low` / `_high` prices, `/explain` live (7055607)
- `api.py` on :8000: full design (7055607)

## Scores

Baseline (same as data's `score.py`): every home gets PV and a battery at the **train** median size, no heat pump, a wallbox iff it has an EV.
**Official: params fitted on `train` only, chosen on `val`, scored on `test` (235 homes) with data's `score.py`. Latest official test row first; earlier test row kept for history.**

| Params | Split | Key numbers | Commit |
|---|---|---|---|
| **current engine (battery bands, installer profiles + packages, expert-spread ranges), fit on train** | **test** | **without installer profile: PV within ±20% 49.2% (baseline 41.5%), MAE 3.22 (3.50); battery within ±20% 45.6% (41.9%), MAE 3.58 (3.74); presence PV 79% / battery 92% / wallbox 69% (= baseline); bundle 52.8% (52.3%). With installer profile: PV 47.5%, MAE 3.24; battery 45.6%, MAE 3.51. Per installer with profile: 23c108b7 PV 45% (49% without), battery 59% (57%); 2a8ba8e2 PV 49%, battery 42%. Range coverage: PV 70% (73% without profile), battery 82% (67%). Installer packages did not generalise (val 65% → test 45% for 23c108b7, ~50 homes per split). Not tuned after seeing test.** | a56e3f9 |
| line 6.15 + 0.603 × D, fit on train (earlier) | test | **PV within ±20% 49% (baseline 42%), MAE 3.22 kWp (3.50), median AE 1.89 (2.38), presence 78% (78%); battery within ±20% 39% (42%), MAE 3.47 kWh (3.74), presence 92% (92%); wallbox presence 68% (68%); heat pump 99% (99%, F1 0); bundle match 52% (52%)** | |
| same | val | PV MAE 2.49 (2.71), within ±20% 46% (50%); battery MAE 2.79 (2.99), within ±20% 38% (41%) | ac50586 |
| + battery bands | val | battery within ±20% 43% (41%), MAE 3.09 (2.99) | |
| + installer profiles | val | PV within ±20% 50% (50%), MAE 2.46 (2.71); battery within ±20% 42% (41%), MAE 2.93 (2.99) | b99a3f5 |
| + installer packages | val | PV within ±20% 55% (baseline 50%), MAE 2.33 (2.71); 23c108b7 PV 65% within ±20%; battery unchanged | |
| + expert spread in ranges | val | range coverage PV 79% (was 30%), battery 87% (was 43%) | |
| fixed c = 1.93 | all (in-sample) | PV median abs error 2.9 kWp | 718cd3f |
| line 5.86 + 0.623 × D | all (in-sample) | PV presence 80% (baseline 79%), size MAE 2.78 kWp (3.10), within ±20% 45% (45%); battery presence 90% (91%), MAE 2.67 kWh (3.04), within ±20% 37% (41%); wallbox presence 76% (76%); heat pump 99% (never suggested: no roof data) | 7055607 |
| per installer | all (in-sample) | 23c108b7 PV MAE 3.23, battery 3.04; 2a8ba8e2 PV MAE 2.62, battery 2.56 | 7055607 |

## Decisions

- D is asked directly (`total_demand_kwh`); `annual_demand_kwh` + EV km only as fallback (owner).
- Customer price asked directly, default 0.32 €/kWh; no PLZ lookup (owner).
- Region = federal state; Y per state from PVGIS weighted by MaStR, national Y when unknown (owner).
- Parameters fitted on data's `train` split only; `test` scored once, reported as it came out (owner + data's NEED, 2026-11-07). Earlier all-data fit superseded.
- PV sized by the expert line instead of a fixed c (owner, 2026-11-07).
- Roof known = hard cap on new PV modules (reo NEED, 2026-11-07, supersedes "PV is not capped"); `roof_width_m`/`roof_length_m` grid fit with 0.3 m edge margin win over `roof_area_sqm`; unknown roof is not probed in ranges.
- Battery recommended whenever there is PV and no battery (95% of expert PV offers); size = experts' most common size per PV band (chosen on val over ratio rule and fixed 5/7/10/15 steps).
- Existing PV = retrofit, no new panels unless locked (51 of 52 no-PV test homes).
- Test is not re-scored after these changes; data freezes final test numbers at M3.
- Ranges include the experts' own spread (calibrated to ~80% coverage on val); confidence still measures only what missing inputs could change.
- Package sellers: most common package per demand band, forced to grow with demand (noisy ~40-project bands); free designers keep the line and 430 W steps.
- Module 430 W, 2.0 m² (Jinko Tiger Neo 430 W datasheet).
- Prices: sourced market ranges (prices.json `_sources`), KfW base grant 30% only; default tariff stays 0.32 €/kWh (owner).
- HTW load profiles (CC BY-NC 4.0) are not in the repo; only the derived factor table is.
