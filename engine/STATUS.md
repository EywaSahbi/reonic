# engine/ status (owner: `egeunluer`)

## Backlog (top = next)

Full plan with how-to per item: [PLAN.md](PLAN.md). Method: [METHOD.md](METHOD.md).

- [x] Step 0 (`inputs.py`): HomeFacts → home, PV kWp from total demand, roof check, heat-pump suggestion; Y from PVGIS + MaStR (`tools/derive_y.py`), c from the dataset (`tools/derive_c.py`)
- [ ] Stub API `/health`, `/prices`, `/design` (PLAN #15) → `DONE` to reo, qa (M0)
- [ ] PV sizing line `a + b × D` instead of fixed c, existing PV (PLAN #1, #2) (M1)
- [ ] Hourly simulation, battery, wallbox (PLAN #5, #7, #8) (M1)
- [ ] `prices.json` from market ranges, economics, bills (PLAN #9, #10) (M1)
- [ ] Ranges, ranked `missing_inputs`, locks (PLAN #11, #12, #14) (M1)
- [ ] `predict.py` over all projects, scores below (PLAN #16) (M1)
- [ ] Orientation, usable roof share, heat-pump kW, reasons and confidence, `/explain` (PLAN #3, #4, #6, #13) (M2)

## Published

- `CONTRACT.md`: `ev_km_per_week`, `ev_km_per_day` (f38af8a), `total_demand_kwh` (336060e), `region`

## Scores

| Params | Split | Key numbers | Commit |
|---|---|---|---|
| fixed c = 1.93 | all (in-sample for c) | PV median abs error 2.9 kWp; line 6.7 + 0.58 × D: 2.1; constant 9.5 kWp: 2.1 | |

## Decisions

- D is asked directly (`total_demand_kwh`); `annual_demand_kwh` + EV km only as fallback (owner).
- Customer price asked directly, default 0.32 €/kWh; no PLZ lookup (owner).
- Region = federal state; Y per state from PVGIS weighted by MaStR, national Y when unknown (owner).
- c computed from all dataset projects, no train split, no DECISION round; whole dataset used for evaluation (owner, 2026-11-07).
- Module 430 W, 1.95 m² (placeholder area until the module datasheet is chosen).
