# engine/ method: how a design is made

The engine turns what a homeowner tells reo (`HomeFacts`, [CONTRACT.md](CONTRACT.md)) into a complete, priced and explained design. It is **deterministic**: rules + physics + parameters measured on the expert designs (train split only) and on public data. No LLM, no state, no randomness. Same input, same output.

Status 2026-11-07, commit `e86dac3`: everything below is built, tested (42 tests) and served on `:8000`. Every outside number is listed with its source in [SOURCES.md](SOURCES.md); the build log is [PLAN.md](PLAN.md), the live backlog [STATUS.md](STATUS.md).

## Overview

| Step | What happens | Code |
|---|---|---|
| 1 | Read the inputs, fill defaults | `inputs.py` `read_inputs` |
| 2 | Size the PV (expert line, or installer package), minus existing PV | `inputs.py` `size_pv` |
| 3 | Roof check; spare roof + fossil heating → heat-pump suggestion and kW | `inputs.py` `size_pv` |
| 4 | Battery, wallbox; apply locks and budget | `design.py` `core`, `fit_budget` |
| 5 | Price: line items with low / high, KfW grant | `design.py` `core`, `prices.json` |
| 6 | Simulate one year hour by hour, corrected to measured homes | `sim.py` |
| 7 | Economics: bills before / after, savings, payback | `design.py` `core` |
| 8 | Ranges, ranked missing inputs, confidence, reasons, bundle | `design.py` `design` |
| 9 | What-ifs per component | `design.py` `explain` |

One `/design` call takes ~20–30 ms (repeated: ~0 ms, the simulation is cached); `/explain` ~5–10 ms.

## 1. Inputs

reo asks the customer; field names are the contract's. Missing values get a default listed in `assumptions`.

| Input | `HomeFacts` field | Default if not given |
|---|---|---|
| Total electricity per year D, incl. EV and electric heating | `total_demand_kwh` | `annual_demand_kwh` + EV (+ existing heat pump), else Stromspiegel 2025 by `num_inhabitants` (1,800 … 4,500 kWh), else 4,500 kWh |
| EV, km | `has_ev`, `ev_planned`, `ev_km_per_year` / `_week` (×52) / `_day` (×365) | no EV; 13,000 km/yr if EV without km; a planned EV (no `has_ev`) adds its kWh on top of the stated total |
| Existing PV / battery | `has_existing_pv`, `existing_pv_kwp`, `has_existing_battery` | none; 5 kWp if PV of unknown size |
| Heating | `heating_type` (gas, oil, heatpump, electric, district, other), `heating_demand_kwh` | unknown; heat demand from `house_size_sqm` × kWh/m² by `house_built_year` (200 / 150 / 100 / 60), else 15,800 kWh (train median) |
| Roof | `roof_area_sqm`, `roof_orientation_deg` (180 = south), `roof_tilt_deg`, `roof_type` | unknown area; south; flat roof = east-west 15° |
| Region | `region` (federal state code) | national sun |
| Tariff | `electricity_price_eur_per_kwh` | 0.32 €/kWh (owner's choice = the dataset's default; BDEW 2026 average is 37.3 ct) |
| Budget | `budget_eur` | none |
| Installer (request, not a fact) | `installer` | all-installer habits |

The dataset's `energy_demand_wh` **excludes** EV and heat pump (EV homes have a *lower* median demand). For dataset projects the engine therefore rebuilds D = household + EV km × 0.18 + existing heat-pump electricity (`dataset.py`).

## 2. PV size

**Free-design installers and the general case** (expert line, fitted on train):

```
kWp_need = (a + b × D_MWh) × Y_national / Y_home  −  existing PV kWp
a = 6.15 kWp, b = 0.603 kWp per MWh         (installer 2a8ba8e2: 5.90 + 0.607; 23c108b7: 7.85 + 0.444)
```

- Experts give every home a base system and add little per MWh. A fixed ratio (`kWp = D × c / Y`, c = 1.94: PV producing ~2× the demand) undersizes small and oversizes large homes (median error 2.8 vs 2.0 kWp for the line), so c is only used in the explanation.
- **Y_home** = the region's PVGIS yield (national 1,082 kWh/kWp/yr, 988 Schleswig-Holstein … 1,139 Bayern) × roof orientation / tilt factor (east or west at 35° ≈ 0.80). Dividing by Y_home keeps the yearly generation the same: a northern or east roof gets more modules.
- Snapped to whole modules: 430 W, 2.0 m² each (Jinko Tiger Neo datasheet).

**Package sellers.** An installer whose top 5 PV sizes cover ≥ 50% of its designs (23c108b7: 10.8 kWp alone is 35%) gets the package it sells most often for the home's demand band (6 bands, forced to grow with demand), in its own module size (450 W, so 10.8 kWp = 24 modules): ≤ 4,000 kWh → 6.3 kWp, above → 10.8 kWp. Free designers (2a8ba8e2) keep the line.

**Retrofit.** `has_existing_pv` → no new panels (experts sell storage or a wallbox; 51 of 52 no-PV test homes were retrofits), unless the installer locks PV. Existing panels take roof space.

Example, 4,500 kWh, no installer, national sun: 6.15 + 0.603 × 4.5 = 8.86 kWp → 21 modules → 9.0 kWp, 42 m² (in Bayern, with more sun: 20 modules, 8.6 kWp).

## 3. Roof check and heat pump

Usable roof = `roof_area_sqm` × 0.75 (placeholder, question for the Reonic experts) − area of existing panels, or the measured grid below. An unknown roof is not probed in the plausible re-runs (a guessed small roof would cap the range).

| Case | Engine |
|---|---|
| Roof unknown | Design kept; `roof_area_sqm` is a missing input |
| Roof known, holds fewer modules than wanted | **Hard cap**: modules = what fits, kWp = modules × module W, reasons say the roof is the limit; a PV lock above the cap is cut to it (reason says so). `components.pv.max_modules` exposes the cap; with `roof_area_sqm` only, a high-impact question names the shortfall |
| `roof_width_m` + `roof_length_m` given | They win over the area: best grid of 1.722 × 1.134 m modules (portrait or landscape) after a 0.3 m edge margin per side (`grid_modules`), minus existing panels |
| Roof fits, heating gas / oil / district / other, spare modules | Heat pump suggested: heat demand ÷ 2,000 full-load hours → nearest size offered in train (6, 8, 10, 12 kW); electricity = heat ÷ COP 3.3 (Fraunhofer ISE field test); extra PV = 0.603 kWp per extra MWh, capped by the spare modules |
| Heating already electric (`heatpump`, `electric`) | No heat pump |
| Heating unknown | Open question |

## 4. Battery, wallbox, locks, budget

- **Battery**: recommended whenever there is PV (new + existing) and no battery yet (95% of expert PV offers have one). Size = the experts' most common battery for that PV size band (train): ≤ 8 kWp → 5 kWh, ≤ 15 kWp → 10 kWh, larger → 15 kWh; installer 23c108b7 mostly 9 kWh (its package battery).
- **Wallbox**: 11 kW when `has_ev` or `ev_planned` (11 kW needs only a notification to the grid operator; 22 kW needs approval).
- **Locks** (installer edits): a locked component keeps its value; the rest re-derives (battery from locked PV, heat-pump PV from the roof left, price and economics recomputed).
- **Budget**: if the price exceeds `budget_eur`, the battery steps down through the catalogue, then off, then PV one module at a time; the cut is named in the reasons.

## 5. Price

`prices.json`, every key sourced and dated (SOURCES.md). Installed prices; PV and battery 0% VAT, heat pump incl. 19%.

| Item | Middle (low – high) |
|---|---|
| PV | 2,500 € (2,000–3,000) + 1,000 €/kWp (770–1,200) → 10 kWp: 12,500 € (9,700–15,000) |
| Battery | 800 € (500–1,200) + 350 €/kWh (280–500) → 10 kWh: 4,300 € |
| Wallbox 11 kW | 2,000 € (1,200–3,500) |
| Air-water heat pump | 18,000 € (14,000–24,000) + 1,300 €/kW (700–1,800) → 10 kW: 31,000 € (21,000–42,000) |
| KfW 458 base grant | −30% of the heat-pump cost, eligible ≤ 28,000 € (bonuses not applied); omitted when `heatpump_subsidy_share` = 0 (reo's customer view, persona rule) |

Total = sum at middle prices. `range_eur` = sum at low / high prices over the plausible designs (step 8), recommended components only. An installer override fixes a price (low = high = override).

## 6. One-year simulation

8,760 hours (`sim.py`, ~3 ms):
- Load = BDEW H0 household profile (2019, `demandlib`) × household kWh + EV charging 18–22 h + heat pump spread by heating degree hours (base 15 °C, 15% hot water flat).
- PV = PVGIS 2019 hourly output of 1 kWp (Kassel) × kWp × Y_home.
- Each hour: PV serves the load; surplus charges the battery (95% each way, max 0.5 × capacity per hour), the rest is exported; a shortfall drains the battery, the rest is imported.
- **Calibration**: H0 is the average of many homes and too smooth, so it overstates self-use. `tools/derive_calibration.py` simulated 74 measured single-family homes (HTW Berlin, 1-minute data) and stores measured ÷ H0 self-use per (PV generation ÷ demand, battery kWh per MWh): factors 0.71–0.95. Example, PV 2× demand + 2 kWh/MWh battery: H0 86% → measured 77% autarky.

## 7. Economics

- Bill before = grid kWh × tariff (+ gas / oil / district bill the heat pump replaces: heat ÷ 0.9 × 12 / 14 / 16 ct).
- Bill after = imported kWh × tariff − exported kWh × feed-in (7.71 ct up to 10 kWp, 6.66 ct above, EEG from Aug 2026).
- Savings = before − after; payback = price ÷ savings; autarky = self-used ÷ load; self-consumption = self-used ÷ generation; monthly bills = yearly ÷ 12.
- Example, 4,500 kWh, 8.6 kWp + 10 kWh, Bayern: 15,400 € (11,900–19,500), autarky 79%, savings 1,608 €/yr, payback 9.6 years, bill 120 → −14 €/month.

## 8. Ranges, missing inputs, confidence, reasons

- **Plausible re-runs**: for each input not given, the design is re-run at a low and a high plausible value (demand 4,000 / 7,000 kWh from train quartiles, region SH / BY, roof 25 / 80 m², east / south, gas / heat pump, heat 10,000 / 25,000 kWh, tariff 0.25 / 0.40, EV yes, existing PV yes).
- **`missing_inputs`**: impact of a field = the largest relative move of PV size, price or savings over its runs (high ≥ 15%, medium ≥ 5%); ranked. With nothing known the order is: existing PV, demand, roof orientation, tariff, EV, region, roof area, heating.
- **`range`**: min / max size over the runs, then widened to size × the 15–85% (battery 20–80%) spread of expert ÷ engine size on train, per installer (`tools/derive_spread.py`), so it shows what comparable expert designs choose.
- **`confidence`**: from the input-driven range only (< 10% wide: high, < 30%: medium), i.e. how much more facts could still move the size.
- **`reasons`**: 1–3 sentences naming the driving input; `bundle` S / M / L / XL by new PV kWp (< 6, < 10, < 14).

## 9. What-ifs (`/explain`)

Per component: off (or on), one size step down and one up (PV ±2 modules, battery / heat pump ±1 catalogue step, wallbox 11 ↔ 22 kW), each with Δ price, Δ savings, Δ payback, Δ autarky, Δ monthly bill and the `locks` that apply the variant.

## 10. Parameters and how to rebuild them

| Parameter | Value | From | Tool |
|---|---|---|---|
| Y, per-state Y, orientation factors | 1,082 kWh/kWp/yr | PVGIS + Marktstammdatenregister | `tools/derive_y.py` |
| Hourly H0, PV, temperature | 2019 | demandlib, PVGIS | `tools/derive_profiles.py` |
| Self-use calibration | 0.71–0.95 | 74 HTW homes | `tools/derive_calibration.py <htw folder>` |
| PV line, battery bands, catalogues, installer profiles + packages, c | see above | data's `projects.parquet`, **train only** | `tools/derive_params.py --split train` |
| Expert spread for ranges | PV 0.71–1.45, battery 0.67–1.40 | train | `tools/derive_spread.py --split train` |
| Prices, COP, EV kWh/km, Stromspiegel, module, full-load hours | — | public sources | hand-set with `_sources` in `prices.json` / `params.json` |

Rebuild order: `derive_y` → `derive_profiles` → `derive_calibration` → `derive_params --split train` → `derive_spread --split train` → `uv run pytest` → `predict.py`.

## 11. Validation and final results

Fitted on `train` (1,098 homes), choices made on `val` (238), scored on `test` (235, unseen) with data's official `score.py`. Baseline (same as data's): every home gets PV and a battery at the **train median size**, no heat pump, a wallbox only with an EV.

**Official test result (commit a56e3f9, not tuned after seeing test):**

| Test, 235 homes | Engine | With installer profile | Baseline |
|---|---|---|---|
| PV within ±20% of the expert | **49.2%** | 47.5% | 41.5% |
| PV size error, mean | **3.22 kWp** | 3.24 | 3.50 |
| PV median % error | 20.7% | 20.7% | — |
| Battery within ±20% | **45.6%** | 45.6% | 41.9% |
| Battery size error, mean | 3.58 kWh | **3.51** | 3.74 |
| Yes / no: PV / battery / wallbox | 79 / 92 / 69% | same | same |
| Bundle match (all four yes / no) | 52.8% | 52.8% | 52.3% |
| Range coverage (expert size inside our range): PV / battery | 73 / 67% | 70 / 82% | — |

`val` for comparison (choices were made here, so it is optimistic): PV within ±20% 46% (with profile 55%), battery 43% (42%), coverage PV 79%, battery 87%.

What the results say:
- **PV size beats the naive baseline** (49% vs 42% within ±20%, typical miss ~1.9 kWp on 9–10 kWp systems). Demand alone explains only part of expert sizing: roof, budget and customer wishes are not in the data, which is why reo asks for them.
- **Battery by expert size bands generalises** (test 38.6% → 45.6% within ±20%, now above the baseline).
- **Yes / no decisions equal the baseline**: misses are facts the data does not record: existing PV (51 of 52 no-PV homes are retrofits; reo now asks first) and planned EVs (91% of expert wallboxes went to homes without an EV flag).
- **Installer packages did not generalise**: 23c108b7 PV within ±20% val 37% → 65%, but test 49% → 45%. With ~50 homes per installer per split, the band choice overfit `val`. The profile does remove each installer's systematic PV offset (data: median bias −0.70 → −0.05 kWp on val).
- **Ranges are narrower than intended** on unseen homes (PV coverage 70–73% vs the 80% target).
- **Heat pumps cannot be scored**: 2 in test, and the dataset has no roof areas.

Earlier official test (commit ac50586, before battery bands / profiles / retrofit): PV 49.2% / 3.22 kWp, battery 38.6% / 3.47 kWh.

## 12. Known limits

- Payback ignores electricity price increases (the dataset's default is 3% a year), panel ageing and the monthly grid base fee; heat pump gets only the 30% base grant.
- Simulation: one weather year and one PV shape (Kassel) scaled per region; EV always charges 18–22 h; the calibration was measured on household load and is also applied to EV and heat-pump load; no battery standby losses.
- Prices come mostly from installer / comparison sites; no site extras (meter cabinet, difficult scaffolding, roof type).
- Placeholders without a source: usable roof share 0.75, existing PV 5 kWp when the size is unknown.

## 13. Which dataset fields are customer facts

The data has no "source" column; this split is **inferred** from fill rates, round values and repeated defaults ([dataset_explanation.md](../docs/dataset_explanation.md)).

- **Customer facts**: `energy_demand_wh` (100%, mostly round estimates: 4,500,000 Wh most common), `has_ev` + km (3–6%), existing PV / battery / wallbox (~1%), `heating_existing_type` (12–14%), heating demand and cost (sparse), house size / year / inhabitants (< 1%).
- **Tool or planner defaults**: `energy_price_per_wh` (71% of 2a8ba8e2 = 0.32 €/kWh), `energy_price_increase`, `load_profile` (H0 in 92%), feed-in fields.
- Open questions for the Reonic experts: usable roof share; which fields the customer enters vs the planner; is 0.32 €/kWh the tool default; which offer option was delivered when a project has several.

## 14. Considered, not built: learned scorer

The first plan was to enumerate every candidate design (PV × battery × wallbox × heat pump from the installer catalogue), remove infeasible ones (no battery without PV, locks, budget), describe each with features (PV fit to demand, battery ratio, wallbox with / without EV, simulated autarky), score them with weights learned by conditional logit on train, and pick the highest score (confidence = softmax probability, alternatives = runners-up, reasons = feature contributions vs the runner-up). Not built: with ~1,100 train homes and almost only demand as an input, the targeted rules above were faster to validate and easier to explain, and the scores show demand-only sizing is the limiting factor, not the choice method.
