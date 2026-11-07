# engine/ plan: from Step 0 to the full design

Step 0 (`inputs.py`) gave PV kWp, module count, the roof check and the heat-pump suggestion. This plan closed every gap to the `Design` in [CONTRACT.md](CONTRACT.md). Status 2026-11-07: **all items built**; open points at the end.

| # | Gap | How it is built | Where |
|---|---|---|---|
| 1 | **PV sizing rule** | `kWp = (6.15 + 0.603 × D_MWh) × Y_nat / Y_home`, line fitted through demand-band medians of the expert designs (fixed c = 1.93 missed by 2.9 kWp, the line by 2.0) | `inputs.py`, `tools/derive_params.py` |
| 2 | **Existing PV** | New kWp = line − `existing_pv_kwp` (default 5 kWp if only `has_existing_pv`); battery sized on existing + new | `inputs.py`, `design.py` |
| 3 | **Orientation and tilt** | Y × PVGIS factor for the nearest stored aspect / tilt; flat roof without orientation = east-west 15° | `inputs.py` |
| 4 | **Usable roof share** | roof × 0.75 before the roof check (*placeholder*, question for the Reonic experts) | `params.json` |
| 5 | **Wallbox** | 11 kW when `has_ev` or `ev_planned` | `design.py` |
| 6 | **Heat-pump kW** | heat demand ÷ 2,000 full-load hours → nearest size offered in the data (5, 7, 10, 12 kW); heat from `heating_demand_kwh`, else `house_size_sqm` × typical demand by `house_built_year`, else the dataset median 15,800 kWh | `inputs.py` |
| 7 | **Hourly simulation** | 8,760 h: H0 × household, EV 18–22 h, heat pump by degree hours; PVGIS 2019 hourly PV; battery 95% each way, 0.5 C; self-use corrected by factors measured on 74 real homes (HTW Berlin, 1-minute) | `sim.py`, `tools/derive_profiles.py`, `tools/derive_calibration.py` |
| 8 | **Battery** | Yes whenever there is PV and no battery (95% of expert PV offers have one); size = the experts' most common battery for that PV size band (train), per installer when known. On val within ±20%: 43% (ratio rule 38%, fixed 5/7/10/15 steps 30%, baseline 41%) | `design.py`, `tools/derive_params.py` |
| 9 | **Price** | `prices.json`: base + per-unit price with low / high, every key sourced and dated in `_sources` (solarserver, Verbraucherzentrale, ADAC, Vattenfall, KfW, EEG, BDEW, Destatis); KfW 458 base grant as a negative line; tiered feed-in above 10 kWp; request `prices` overrides fix a key | `prices.json`, `design.py` |
| 10 | **Economics** | Before vs after from the simulation: import × tariff − export × feed-in (7.86 ct), plus fuel cost replaced by a heat pump; savings, payback, autarky, self-consumption, monthly bills | `design.py` |
| 11 | **Ranges** | Re-run the design at the low / high plausible value of each missing input (`params.json` `plausible`); range = min / max size over the runs | `design.py` |
| 12 | **`missing_inputs` ranked** | Same runs: impact = largest relative move of PV kWp, price or savings (high ≥ 15%, medium ≥ 5%); the roof check's own level is a floor | `design.py` |
| 13 | **Reasons and confidence** | Templates naming the driving input; confidence from range width ÷ size (< 10% high, < 30% medium) | `design.py` |
| 14 | **Locks** | Locked component keeps its value; battery re-derives from locked PV, heat-pump PV from the roof left, price and economics recomputed | `design.py` |
| 15 | **API** | `/health`, `/prices`, `/design`, `/explain` (what-ifs), CORS for :5173 / :8001, ~15–35 ms per design | `api.py` |
| 16 | **Evaluation** | `predict.py` over all 1,593 projects → `out/predictions_all.csv` (data's format) + `out/score_all.json`; scores in [STATUS.md](STATUS.md) | `predict.py`, `dataset.py` |
| + | **Installer profiles** | PV line and battery bands per installer from its own train projects; `installer` in requests, `GET /installers`. On val: PV MAE 2.46 (global 2.50, baseline 2.71), battery MAE 2.93 (3.09, baseline 2.99) | `tools/derive_params.py`, `design.py` |
| + | **Retrofit** | `has_existing_pv` → no new PV (storage / wallbox only) unless PV is locked; existing panels take roof space; asked first via `missing_inputs` | `design.py`, `inputs.py` |
| + | **Budget** (`budget_eur`) | Battery steps down, then PV, until the price fits; noted in reasons and assumptions | `design.py` |

## Open points

- Heat pumps: the dataset has no roof areas, so the engine never suggests one there (13 expert heat pumps in 1,593 projects); untestable on this data.
- Wallbox: experts sell one to 23% of homes without an EV (planned EVs are not recorded); the rule only follows `has_ev` / `ev_planned`.
- Payback ignores electricity price increases and the monthly grid base fee; the heat pump gets only the 30% KfW base grant (bonuses are case by case).
- The simulation calibration was measured on household load only; EV and heat-pump loads get the same factor (shortcut).
- Still placeholders (no published source): usable roof share 0.75 (question for the Reonic experts), existing PV 5 kWp when the size is unknown.
- Default electricity price 0.32 €/kWh (owner's choice, the dataset's default); BDEW's 2026 household average is 37.3 ct.
