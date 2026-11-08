# engine/ method: how a design is made

The engine turns what a homeowner tells reo (`HomeFacts`, [CONTRACT.md](CONTRACT.md)) into a complete, priced and explained design. It is **deterministic**: rules + physics + parameters measured on the expert designs (train split only) and on public data. No LLM, no state, no randomness. Same input, same output.

Everything below is built, tested (65 tests) and served on `:8000`. Every outside number is listed with its source in [SOURCES.md](SOURCES.md); the build log is [PLAN.md](PLAN.md), the live backlog [STATUS.md](STATUS.md).

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

- Experts give every home a base system and add little per MWh; the line captures this. The fixed ratio `kWp = D × c / Y` (c = 1.94: PV producing about twice the demand) is used in the explanation.
- **Y_home** = the region's PVGIS yield (national 1,082 kWh/kWp/yr, 988 Schleswig-Holstein … 1,139 Bayern) × roof orientation / tilt factor (east or west at 35° ≈ 0.80). Dividing by Y_home keeps the yearly generation the same: a northern or east roof gets more modules.
- Snapped to whole modules: 430 W, 2.0 m² each (Jinko Tiger Neo datasheet).

**Package sellers.** An installer whose top 5 PV sizes cover ≥ 50% of its designs (23c108b7: 10.8 kWp alone is 35%) gets the package it sells most often for the home's demand band (6 bands, forced to grow with demand), in its own module size (450 W, so 10.8 kWp = 24 modules): ≤ 4,000 kWh → 6.3 kWp, above → 10.8 kWp. Free designers (2a8ba8e2) keep the line.

**Retrofit.** `has_existing_pv` → no new panels (experts sell storage or a wallbox; 51 of 52 no-PV test homes were retrofits), unless the installer locks PV. Existing panels take roof space.

Example, 4,500 kWh, no installer, national sun: 6.15 + 0.603 × 4.5 = 8.86 kWp → 21 modules → 9.0 kWp, 42 m² (in Bayern, with more sun: 20 modules, 8.6 kWp).

## 3. Roof check and heat pump

Usable roof = `roof_area_sqm` × 0.75 − area of existing panels, or the measured grid below. An unknown roof is not probed in the plausible re-runs (a guessed small roof would cap the range).

| Case | Engine |
|---|---|
| Roof unknown | Design kept; `roof_area_sqm` is a missing input |
| Roof known, holds fewer modules than wanted | **Hard cap**: modules = what fits, kWp = modules × module W, reasons say the roof is the limit; a PV lock above the cap is cut to it (reason says so). `components.pv.max_modules` exposes the cap; with `roof_area_sqm` only, a high-impact question names the shortfall |
| `roof_width_m` + `roof_length_m` given | They win over the area: best grid of 1.722 × 1.134 m modules (portrait or landscape) after a 0.3 m edge margin per side (`grid_modules`), minus existing panels |
| Roof fits, heating gas / oil / district / other, spare modules | Heat pump suggested: heat demand ÷ 2,000 full-load hours → nearest size offered in train (6, 8, 10, 12 kW); electricity = heat ÷ COP 3.3 (Fraunhofer ISE field test); extra PV = 0.603 kWp per extra MWh, capped by the spare modules |
| Heating already electric (`heatpump`, `electric`) | No heat pump |
| Heating unknown | `heating_type` is a missing input, ranked by impact |

`components.pv.module` gives the sizing module (`id`, `wp`, `w_m` short side, `h_m` long side, in metres; area scales with W). `quantity = size × 1000 / wp`, so a layout of n modules is the pv lock `{recommended: true, size: n × wp / 1000}` and the engine returns quantity n (design in [ROOF_LAYOUT.md](ROOF_LAYOUT.md)).

## 4. Battery, wallbox, locks, budget

- **Battery**: recommended whenever there is PV (new + existing) and no battery yet (95% of expert PV offers have one). Size = the experts' most common battery for that PV size band (train): ≤ 8 kWp → 5 kWh, ≤ 15 kWp → 10 kWh, larger → 15 kWh; installer 23c108b7 mostly 9 kWh (its package battery).
- **Wallbox**: 11 kW when `has_ev` or `ev_planned` (11 kW needs only a notification to the grid operator; 22 kW needs approval).
- **Locks** (installer edits): a locked component keeps its value; the rest re-derives (battery from locked PV, heat-pump PV from the roof left, price and economics recomputed).
- **Budget**: if the price exceeds `budget_eur`, the battery steps down through the catalogue, then off, then PV one module at a time; the cut is named in the reasons.

## 5. Price

Quote lines are real products from `catalog.json` × quantity at their shop price, plus installation labour from sourced rates `[low, mid, high]` (SOURCES.md). PV, inverter and battery at 0% VAT, wallbox and heat pump incl. 19%.

| Item | How it is priced |
|---|---|
| PV | module (JA Solar 440 W) × modules + mounting kit × modules + hybrid inverter (smallest model that carries the array) + roof installation, DC and AC cabling per kWp + meter cabinet, commissioning, scaffolding flat |
| Battery | catalogue size at its list price + installation |
| Wallbox | 11 / 22 kW device + installation and registration |
| Air-water heat pump | reference price + €/kW by size + installation (hydraulics, electrics, storage) |
| KfW 458 base grant | −30% of the heat-pump cost, eligible ≤ 28,000 € (bonuses not applied); omitted when `heatpump_subsidy_share` = 0 (reo's customer view, persona rule) |

Total = sum at mid prices. `range_eur` is a typical band: over the plausible designs (step 8), `price_band_share` 0.5 of the distance from the mid price to the cheapest and to the dearest sourced total, on each side, recommended components only. The installer can override any price (low = high = override).

## 6. One-year simulation

8,760 hours (`sim.py`, ~3 ms):
- Load = BDEW H0 household profile (2019, `demandlib`) × household kWh + EV charging 18–22 h + heat pump spread by heating degree hours (base 15 °C, 15% hot water flat).
- PV = PVGIS 2019 hourly output of 1 kWp (Kassel) × kWp × Y_home.
- Each hour: PV serves the load; surplus charges the battery (95% each way, max 0.5 × capacity per hour), the rest is exported; a shortfall drains the battery, the rest is imported.
- **Calibration**: H0 is the average of many homes. `tools/derive_calibration.py` simulated 74 measured single-family homes (HTW Berlin, 1-minute data) and stores measured ÷ H0 self-use per (PV generation ÷ demand, battery kWh per MWh): factors 0.71–0.95. Example, PV 2× demand + 2 kWh/MWh battery: H0 86% → measured 77% autarky.

## 7. Economics

- Bill before = grid kWh × tariff (+ gas / oil / district bill the heat pump replaces: heat ÷ 0.9 × 12 / 14 / 16 ct).
- Bill after = imported kWh × tariff − exported kWh × feed-in (7.71 ct up to 10 kWp, 6.66 ct above, EEG from Aug 2026).
- Savings = before − after; payback = price ÷ savings; autarky = self-used ÷ load; self-consumption = self-used ÷ generation; monthly bills = yearly ÷ 12.
- Example, 4,500 kWh, 8.6 kWp + 10 kWh, Bayern: 15,400 € (11,900–19,500), autarky 79%, savings 1,608 €/yr, payback 9.6 years, bill 120 → −14 €/month.

## 8. Ranges, missing inputs, confidence, reasons

- **Plausible re-runs**: for each input not given, the design is re-run at a low and a high plausible value (demand 4,000 / 7,000 kWh from train quartiles, region SH / BY, roof 25 / 80 m², east / south, gas / heat pump, heat 10,000 / 25,000 kWh, tariff 0.25 / 0.40, EV yes, existing PV yes).
- **`missing_inputs`**: impact of a field = the largest relative move of PV size, price or savings over its runs (high ≥ 15%, medium ≥ 5%); ranked. With nothing known the order is: existing PV, demand, roof orientation, tariff, EV, region, roof area, heating.
- **`range`**: min / max size over the runs, then widened to size × the 10–90% (battery 21–79%) spread of expert ÷ engine size on train, per installer (`tools/derive_spread.py`), so it shows what comparable expert designs choose.
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
| Expert spread for ranges | PV 0.61–1.47, battery 0.50–1.20 (all installers) | train | `tools/derive_spread.py --split train` |
| Prices, COP, EV kWh/km, Stromspiegel, module, full-load hours | — | public sources | hand-set with `_sources` in `prices.json` / `params.json` |

Rebuild order: `derive_y` → `derive_profiles` → `derive_calibration` → `derive_params --split train` → `derive_spread --split train` → `uv run pytest` → `predict.py`.

## 11. Validation and results

Fitted on `train` (1,098 homes), choices made on `val` (238), scored on `test` (235, unseen) with data's official `score.py`. Baseline (same as data's): every home gets PV and a battery at the **train median size**, no heat pump, a wallbox only with an EV. Nothing was tuned on `test`.

**Test, 235 homes (commit a56e3f9)**

| | Engine | With installer profile | Baseline |
|---|---|---|---|
| PV within ±20% of the expert | 49.2% | 47.5% | 41.5% |
| PV size error, mean | 3.22 kWp | 3.24 kWp | 3.50 kWp |
| PV median % error | 20.7% | 20.7% | — |
| Battery within ±20% | 45.6% | 45.6% | 41.9% |
| Battery size error, mean | 3.58 kWh | 3.51 kWh | 3.74 kWh |
| Yes / no: PV / battery / wallbox | 79 / 92 / 69% | 79 / 92 / 69% | 79 / 92 / 69% |
| Bundle match (all four yes / no) | 52.8% | 52.8% | 52.3% |
| Range coverage (expert size inside the range): PV / battery | 73 / 67% | 70 / 82% | — |

**Validation, 238 homes**

| | Engine | With installer profile | Baseline |
|---|---|---|---|
| PV within ±20% of the expert | 46.2% | 50.0% | 49.7% |
| PV size error, mean | 2.50 kWp | 2.46 kWp | 2.71 kWp |
| Battery within ±20% | 42.9% | 42.4% | 40.8% |
| Battery size error, mean | 3.09 kWh | 2.93 kWh | 2.99 kWh |
| Bundle match (all four yes / no) | 55.9% | 55.9% | 55.5% |

Reports and charts: [data/reports/](../data/reports/). Reproduce: `uv run python predict.py --split test`, then `cd ../data && uv run python score.py ../engine/out/predictions_test.csv --split test`.

## 12. Which dataset fields are customer facts

The data has no "source" column; this split is **inferred** from fill rates, round values and repeated defaults ([dataset_explanation.md](../docs/dataset_explanation.md)).

- **Customer facts**: `energy_demand_wh` (100%, mostly round estimates: 4,500,000 Wh most common), `has_ev` + km (3–6%), existing PV / battery / wallbox (~1%), `heating_existing_type` (12–14%), heating demand and cost (sparse), house size / year / inhabitants (< 1%).
- **Tool or planner defaults**: `energy_price_per_wh` (71% of 2a8ba8e2 = 0.32 €/kWh), `energy_price_increase`, `load_profile` (H0 in 92%), feed-in fields.
