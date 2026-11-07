# engine/ plan: from Step 0 to the full design

Step 0 (`inputs.py`) gives PV kWp, module count, the roof check and the heat-pump suggestion. This plan closes every gap to the `Design` in [CONTRACT.md](CONTRACT.md). Order = build order.

## What the data says about Step 0 first

`tools/derive_c.py` over 1,243 expert projects: **c = 1.93** (experts install PV that produces about twice the yearly demand; IQR 1.41–2.67). But c is **not constant**:

| D (kWh/yr) | ≤ 3,000 | 3–4k | 4–5k | 5–6k | 6–8k | 8–12k | > 12k |
|---|---|---|---|---|---|---|---|
| Expert kWp (median) | 7.4 | 8.6 | 9.0 | 10.0 | 10.5 | 11.4 | 13.9 |
| c (median) | 3.08 | 2.50 | 2.06 | 1.87 | 1.54 | 1.35 | 0.99 |

Small homes get relatively much more PV. A fixed c misses experts by 2.9 kWp (median absolute error), worse than giving everyone 9.5 kWp (2.1). A straight line `kWp = 6.7 + 0.58 × D_MWh` matches 2.1. So step 1 of the plan is a better sizing rule; the roof check and everything below stay the same.

## The plan

| # | Gap | How, building on Step 0 | Needs |
|---|---|---|---|
| 1 | **PV sizing rule** | Replace `kWp = D × c / Y` by `kWp = (a + b × D) × Y_nat / Y_region` (line fitted on the expert designs, region scales it). Keep c as the explanation ("produces ~1.9× your demand"). Compare fixed c, line and demand bands with `predict.py` | dataset |
| 2 | **Existing PV** | New kWp = max(0, kWp − `existing_pv_kwp`); no battery rule change | — |
| 3 | **Orientation and tilt** | Y × `orientation_factors[aspect/tilt]` from `params.json` (contract 180 = south → PVGIS aspect = deg − 180, nearest stored value) | done in params |
| 4 | **Usable roof share** | A_roof × u before the roof check, u ≈ 0.75 until the Reonic experts answer | expert question |
| 5 | **Wallbox** | Recommend 11 kW when `has_ev` or `ev_planned` and no existing wallbox (11 kW is the dataset's dominant size; 22 kW needs grid-operator approval) | — |
| 6 | **Heat-pump size (kW)** | kW = Q_heat / full-load hours (~2,000 h/yr), snapped to the sizes in the data (5–12 kW). Q_heat from `heating_demand_kwh`, else `house_size_sqm` × specific demand by `house_built_year`, else open question | published specific demand values |
| 7 | **Hourly simulation (Step 4)** | 8,760 hours: H0 load profile (BDEW) × D, PVGIS hourly yield per region (stored once like Y), simple battery. Numpy, < 10 ms. Gives self-consumption and autarky for any (PV, battery) | H0 profile, PVGIS hourly |
| 8 | **Battery yes/no and kWh** | Candidates from the dataset's catalogue sizes (5, 8, 10, 15 kWh …); pick with the ratio to PV that experts use (r_B, median battery / kWp) and check the gain in autarky from #7. No battery without PV, none when one exists | dataset, #7 |
| 9 | **Price** | `prices.json`: public German market ranges (€/kWp falling with size, €/kWh battery, heat pump by kW incl. installation, wallbox, fixed fees). Line items × sizes = total; `range_eur` from low/high prices and the size ranges. Request `prices` overrides keys | market sources |
| 10 | **Economics** | From #7: self-consumed kWh × tariff + exported kWh × feed-in rate (EEG) = savings; payback = total / savings; `bill_today` / `bill_after` per month (app's NEED); heat pump: saved gas/oil cost minus its electricity | #7, #9 |
| 11 | **Ranges** | Re-run sizing at the low / high plausible value of each missing input (D: dataset quartiles; region: lowest / highest state Y; roof unknown: no cap). Size range = min / max over these runs | — |
| 12 | **`missing_inputs` ranked** | Same runs as #11: impact of a field = how far it moves kWp and price. Rank high / medium / low by that | #11 |
| 13 | **Reasons and confidence** | Templates naming the driving input ("7,200 kWh incl. your EV → 12.5 kWp", "roof holds 18 of 22 modules"). Confidence from range width ÷ size (< 10% high, < 30% medium, else low) | #11 |
| 14 | **Locks** | Apply after each rule: a locked component keeps its value, the rest re-derives from it (battery from locked PV, heat-pump PV from the roof left, price and economics recomputed) | #1–#10 |
| 15 | **API** | `api.py` (FastAPI, :8000): `/health`, `/prices`, `/design` per contract, CORS for :5173 and :8001. Stub first (real Step 0 PV, simple rules for the rest), then each item above replaces a stub part | — |
| 16 | **Evaluation** | `predict.py` runs `/design` logic on every dataset project and writes predictions; scored per component (PV kWp error, battery yes/no and kWh, wallbox, heat pump), per installer. c and the line in #1 come from the same projects, so PV numbers are in-sample for those 1–2 parameters; reported as such | dataset |

## Milestones

- **Now (M0):** #15 stub → reo shows real PV numbers.
- **M1 (Sat 23:30):** #1, #2, #5, #7, #8, #9, #10, #11, #12, #14, #16 first scores.
- **M2:** #3, #4, #6, #13 polish, `/explain`.
