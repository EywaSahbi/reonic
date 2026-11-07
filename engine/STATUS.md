# engine/ status (owner: `egeunluer`)

## Backlog (top = next)

Plan and what each item became: [PLAN.md](PLAN.md). Method: [METHOD.md](METHOD.md).

- [x] Step 0 (`inputs.py`): HomeFacts → home, PV from the expert line, existing PV, orientation, roof check, heat-pump suggestion and kW
- [x] Y from PVGIS + MaStR (`tools/derive_y.py`); line, r_B, catalogues from the dataset (`tools/derive_params.py`); hourly profiles (`tools/derive_profiles.py`)
- [x] Hourly simulation (`sim.py`), battery, wallbox, price list, economics, bills (`design.py`, `prices.json`)
- [x] Ranges, ranked `missing_inputs`, reasons, confidence, bundle, locks, budget (`design.py`)
- [x] API `/health`, `/prices`, `/design`, `/explain` (`api.py`); `predict.py` evaluation
- [ ] Open points in PLAN.md: battery clustering on 5 / 10 kWh, H0 optimism, subsidies, remaining placeholders

## Published

- `CONTRACT.md` v1: `ev_km_per_week`, `ev_km_per_day` (f38af8a), `total_demand_kwh` (336060e), `region` (718cd3f); `building_type`, `roof_type`, `bundle`, monthly bills, `_low` / `_high` prices, `/explain` live (7055607)
- `api.py` on :8000: full design (7055607)

## Scores

Engine self-evaluation over all 1,593 projects (`predict.py`; in-sample for the line, r_B and catalogues). Baseline: PV and battery always at the experts' median size, wallbox iff EV.

| Params | Split | Key numbers | Commit |
|---|---|---|---|
| fixed c = 1.93 | all | PV median abs error 2.9 kWp | 718cd3f |
| line 5.86 + 0.623 × D | all | PV presence 80% (baseline 79%), size MAE 2.78 kWp (3.10), within ±20% 45% (45%); battery presence 90% (91%), MAE 2.67 kWh (3.04), within ±20% 37% (41%); wallbox presence 76% (76%); heat pump 99% (never suggested: no roof data) | 7055607 |
| per installer | all | 23c108b7 PV MAE 3.23, battery 3.04; 2a8ba8e2 PV MAE 2.62, battery 2.56 | 7055607 |

## Decisions

- D is asked directly (`total_demand_kwh`); `annual_demand_kwh` + EV km only as fallback (owner).
- Customer price asked directly, default 0.32 €/kWh; no PLZ lookup (owner).
- Region = federal state; Y per state from PVGIS weighted by MaStR, national Y when unknown (owner).
- Parameters computed from all dataset projects, no train split, no DECISION round; whole dataset used for evaluation (owner, 2026-11-07).
- PV sized by the expert line instead of a fixed c (owner, 2026-11-07).
- Roof too small stays an open question, PV is not capped (owner); the range shows the gap.
- Battery recommended whenever there is PV and no battery (95% of expert PV offers); size by r_B, not by economics (economics alone would rarely pick one).
- Module 430 W, 1.95 m² (area placeholder until the module datasheet is chosen).
