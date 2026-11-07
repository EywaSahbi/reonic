# engine/ method: learned scoring + constrained choice

How the engine turns a home into a design: an ML model **scores** candidate designs by how expert-like they are, and an integer programme (solved by enumeration) **picks** the best one that obeys the hard rules.

- **ML = the judge:** given one complete candidate design, returns a score.
- **IP = the search:** checks all allowed designs, removes those that break rules, returns the highest-scoring one.

Values marked *placeholder* are invented for the worked example. The real ones are measured on `split == train`, tuned on `val`, never on `test`.

## Overview

| Step | What happens | Output |
|---|---|---|
| 0 | Read the home's inputs | home h |
| 1 | Compute total electricity demand | D |
| 2 | List every possible design | candidates c |
| 3 | Remove impossible designs | feasible set C(h) |
| 4 | Simulate each design for one year | autarky |
| 5 | Describe each design with features | φ1 … φ6 |
| 6 | Score each design | score |
| 7 | Turn scores into probabilities | p |
| 8 | Pick the best design | design, alternatives, confidence |
| 9 | Explain it | reasons |
| 10 | Planner changes something → re-run | updated design |

Steps 1–10 run per request. r_PV, r_B and the weights w (steps 5–6) are learned once, beforehand ([Training](#training-r_pv-r_b-and-w)).

## Abbreviations

| | Meaning |
|---|---|
| PV | Photovoltaics (solar panels) |
| EV | Electric vehicle |
| kW | Kilowatt: power at one moment (wallbox, heat pump) |
| kWh / MWh | Kilowatt-hour: energy over time (demand, battery capacity). 1 MWh = 1,000 kWh |
| kWp | Kilowatt-peak: rated PV power under standard test sunlight |
| H0 | German standard household load profile (how yearly use spreads over hours) |
| IP | Integer programming: optimisation with whole-number (here 0/1) variables |
| φ (phi) | Feature: one number describing a (home, design) pair |
| w | Weight of a feature, learned in training |
| Σ | Sum |
| e | Euler's number ≈ 2.718 |
| softmax | Turns scores into probabilities that add up to 1 |
| argmax | The option giving the maximum value |

## Step 0: inputs

**h** = the home, everything we know about it.

| Symbol | Meaning | Data column | Example |
|---|---|---|---|
| E_house | Household electricity demand per year (kWh) | `energy_demand_wh` ÷ 1,000 | 4,500 |
| has_EV | EV present (1/0) | `has_ev` | 1 |
| km_EV | km driven per year (0 without EV) | `ev_annual_drive_distance_km` | 15,000 |
| inst | Installer (different catalogues and habits) | `installer` | A |

### What reo asks the customer (implemented in `inputs.py`)

Field names are the `HomeFacts` names from [CONTRACT.md](CONTRACT.md) (the contract is the source of truth).

| Input | `HomeFacts` field | Default if not given |
|---|---|---|
| E_house | `annual_demand_kwh` | 4,500 (dataset's most common value) |
| has_EV | `has_ev` | false |
| km_EV | `ev_km_per_year`, else `ev_km_per_week` × 52, else `ev_km_per_day` × 365 (only used with an EV) | 13,000 km/yr (average, *placeholder*) |
| existing PV / battery | `has_existing_pv`, `has_existing_battery` | false |
| existing heating | `heating_type`: gas, oil, heatpump, electric, district, other | unknown |
| price (€/kWh) | `electricity_price_eur_per_kwh`, asked directly | 0.32 €/kWh |

Every default used goes into `assumptions`.

### Which inputs come from the customer

The data has no "source" column, so this split is **inferred** from fill rates, round values and repeated defaults ([dataset_explanation.md](../docs/dataset_explanation.md)). To confirm with the Reonic experts.

Probably from the customer (facts about their home):

| Column | Fill rate | Why |
|---|---|---|
| `energy_demand_wh` | 100% | Mostly round values (4,500,000 Wh most common, then 3.0 / 3.5 / 4.0 / 5.0 MWh): a customer's estimate, not a meter reading |
| `has_ev`, `ev_annual_drive_distance_km` | EV in 3–6% | Only the customer knows |
| `has_solar` + `solar_size_kwp`, `solar_angle`, `solar_orientation`, `solar_built_year` | ~1% | Existing equipment (angle / orientation may be measured by the planner) |
| `has_storage` + `storage_size_kwh`, `storage_built_year` | ~1% | Existing battery |
| `has_wallbox` + `wallbox_charge_speed_kw` | ~0.3% | Existing charger |
| `heating_existing_type` | 12–14% | "We heat with gas" |
| `heating_existing_cost_per_year`, `heating_existing_electricity_demand_kwh`, `heating_existing_heating_demand_wh` | sparse | From bills; heat demand may be the planner's estimate |
| `house_size_sqm`, `house_built_year`, `num_inhabitants` | < 1% | Customer facts, almost never filled |
| `energy_price_per_wh` | 100% | Only partly: 71% of `2a8ba8e2` share 0.32 €/kWh, so mostly the tool's pre-filled default |
| `energy_price_with_flexible_tariff`, `base_price_per_month` | sparse | Possibly from the customer's contract |

Probably set by the planner or the software (assumptions and defaults):

| Column | Why |
|---|---|
| `energy_price_increase`, `base_price_increase` | Forecasts for the payback calculation, not customer facts |
| `load_profile`, `load_profile_editor_id` | `H0` is the default in 92%; the rarer profiles are picked by the planner from what the customer says |
| `solar_feedin_renumeration*` | Feed-in tariff rules |

Not inputs: `project_id`, `customer_contact_id` (IDs), `country` (always Germany), `request_created_at`, `offer_created_at`, `first_signed_at` (timeline).

What this means for the engine:
- **Core customer inputs** are annual demand, EV (+ km), existing heating type and existing PV / battery / wallbox. Price and price increase are optional, pre-filled defaults.
- **inst** is not a customer input but is still a model input: the two installers design differently.
- **Missing inputs** get explicit defaults (listed in `assumptions`) and widen each size's `range`. `missing_inputs` ranks the absent facts by how much they would narrow the design (e.g. EV km and heating type move D the most), so reo can pick its next question.

Open questions for the Reonic experts: which fields does the customer enter vs the planner or the tool? Is 0.32 €/kWh the tool's default? Is `heating_existing_heating_demand_wh` measured or estimated?

## Step 1: total demand D

```
D = E_house + km_EV × k_EV
```

| Symbol | Meaning | Example |
|---|---|---|
| D | Total yearly electricity use incl. EV (kWh) | 7,200 |
| k_EV | EV consumption per km (kWh/km), standard value | 0.18 |

The home's own consumption plus what the car draws: 4,500 + 15,000 × 0.18 = 7,200 kWh, so D_MWh = 7.2.
The EV is added because `energy_demand_wh` appears to exclude it (EV homes have *lower* median demand). Whether experts size PV on D or on E_house alone is checked on `val`.
A heat pump would add heat demand ÷ 3.5 (typical heat-pump efficiency, *placeholder*) the same way.

## Step 2: list all candidates

A **candidate c** is one complete design, one choice per component. Size 0 = not recommended, so "no battery" is a real option.

| Symbol | Meaning | Allowed values (installer A, *placeholder*) |
|---|---|---|
| PV_c | Solar size (kWp) | 0, 6, 8, 10, 12, 15 |
| B_c | Battery capacity (kWh) | 0, 5, 8, 10, 15 |
| WB_c | Wallbox power (kW) | 0, 11, 22 |
| HP_c | Heat pump power (kW) | 0, 7, 9, 12 |

All combinations: 6 × 5 × 3 × 4 = 360 candidates. Real catalogues come from the sizes that occur in train per installer.

## Step 3: remove impossible designs

**C(h)** = feasible candidates for home h.

| Rule | Formula | Meaning |
|---|---|---|
| No battery without solar | B_c > 0 ⇒ PV_c > 0 | Nothing to charge it from (unless existing PV) |
| Battery not oversized | B_c ≤ 1.5 × PV_c | Panels could never fill it (*placeholder* factor) |
| Catalogue | sizes ∈ catalogue(inst) | Only products this installer sells |
| Locks | e.g. B_c = 5 | Whatever the planner fixed (step 10) |

These are rules, not preferences: a violating candidate is deleted, not scored low. About 150 of 360 survive.

## Step 4: simulate one year per candidate

| Symbol | Meaning |
|---|---|
| t | Hour of the year, 1 … 8,760 |
| H0_t | Share of yearly demand in hour t (sums to 1) |
| L_t | Load: electricity used in hour t (kWh) |
| Y_t | Solar yield per kWp in hour t (kWh/kWp), typical German year, ≈ 950 kWh/kWp/yr in total |
| G_t | Generation in hour t (kWh) |
| SoC_t | Battery state of charge at end of hour t, 0 ≤ SoC_t ≤ B_c |
| Import_t | Electricity bought from the grid in hour t |

```
L_t = E_house × H0_t + EV_t        (EV_t = car charging, placed in evening hours)
G_t = PV_c × Y_t
```

Hourly rule:

```
if G_t ≥ L_t:                         surplus
    charge   = min(G_t − L_t, B_c − SoC_{t−1})
    SoC_t    = SoC_{t−1} + charge     (the rest is exported)
    Import_t = 0
else:                                 shortfall
    discharge = min(L_t − G_t, SoC_{t−1})
    SoC_t     = SoC_{t−1} − discharge
    Import_t  = L_t − G_t − discharge
```

1. Solar serves the home directly first.
2. Surplus fills the battery (`min` = only as much as fits); the rest is exported.
3. Shortfall: the battery gives what it has (`min` = only what is stored); the rest is bought.

```
autarky = 1 − Σ_t Import_t / Σ_t L_t
```

Share of the year's electricity the home does not buy.
Shortcut: no battery losses or power limits; enough to rank designs.

### Worked example: 10 kWp + 10 kWh, D = 7,200 kWh (19.7 kWh/day, of which 7.4 EV in the evening)

Summer day (PV ≈ 50 kWh), battery starts at 4.3 kWh:

| Block | Use | PV | What happens | Battery after | Import |
|---|---|---|---|---|---|
| Night 0–6 | 2.0 | 0 | battery gives 2.0 | 2.3 | 0 |
| Morning 6–10 | 2.5 | 6 | surplus 3.5 → battery | 5.8 | 0 |
| Midday 10–16 | 3.5 | 38 | surplus 34.5: 4.2 to battery, 30.3 exported | 10.0 | 0 |
| Evening 16–24 | 4.3 + 7.4 EV | 6 | shortfall 5.7 → battery | 4.3 | 0 |

Autarky = 1 − 0 / 19.7 = **100%**.

Winter day (PV ≈ 8 kWh), battery empty:

| Block | Use | PV | What happens | Battery after | Import |
|---|---|---|---|---|---|
| Night | 2.0 | 0 | battery empty | 0 | 2.0 |
| Morning | 2.5 | 1 | shortfall 1.5 | 0 | 1.5 |
| Midday | 3.5 | 6 | surplus 2.5 → battery | 2.5 | 0 |
| Evening | 11.7 | 1 | shortfall 10.7, battery gives 2.5 | 0 | 8.2 |

Autarky = 1 − 11.7 / 19.7 = **41%**. Over the full year ≈ **60%**.

What sizes change:
- **No battery:** summer 61%, winter 28%. The battery is worth roughly +15 to +40 points, by moving midday surplus to evening EV charging.
- **Battery 15 instead of 10 kWh:** summer evening + night need only ~7.7 kWh, winter has no surplus to fill it, so almost no gain. Hence battery ≈ PV size (φ2).
- **PV 15 instead of 10 kWp:** more summer export, a bit more winter autarky; small gain. Hence φ1 penalises oversizing.
- **EV charging at midday:** comes straight from the panels, battery matters less. The EV changes *when* power is used, not only how much: this is the coupling.

## Step 5: features

**φ_k(h, c)** = feature k for home h and candidate c; each measures one expert habit.

**φ1, PV fit**

```
φ1 = −(PV_c / D_MWh − r_PV)²
```

| Symbol | Meaning | Example |
|---|---|---|
| PV_c / D_MWh | kWp per MWh of demand | 10 / 7.2 = 1.39 |
| r_PV | Typical expert ratio (median over train) | 1.4 *placeholder* |

How far this PV size is from what experts usually install for this demand. Perfect match = 0 (best). Squared: too big and too small both count, large misses much more. Minus: a miss is a penalty. Example: 8 kWp → −(1.11 − 1.4)² = −0.084.

**φ2, battery fit**

```
φ2 = −(B_c / PV_c − r_B)²      (0 if B_c = 0)
```

| Symbol | Meaning | Example |
|---|---|---|
| B_c / PV_c | Battery kWh per kWp | 10 / 10 = 1.0 |
| r_B | Typical expert ratio (median over train) | 1.0 *placeholder* |

0 without a battery: nothing to fit. Whether to have one at all is φ3.

**φ3, has battery**

```
φ3 = 1 if B_c > 0, else 0
```

The general expert tendency to sell a battery, regardless of size.

**φ4, φ5, wallbox**

```
φ4 = 1 if WB_c > 0 and has_EV = 1, else 0
φ5 = 1 if WB_c > 0 and has_EV = 0, else 0
```

Separate features so the model can learn opposite signs.

**φ6, autarky**

```
φ6 = autarky from step 4
```

What the design achieves physically; keeps designs sensible for homes unlike the data.

## Step 6: score

```
score(h, c) = Σ_k w_k × φ_k(h, c) = w1·φ1 + w2·φ2 + w3·φ3 + w4·φ4 + w5·φ5 + w6·φ6
```

| Symbol | Meaning | Example (*placeholders*) |
|---|---|---|
| w_k | Weight: how much experts care about habit k | w1 = 3.0, w2 = 2.0, w3 = 1.0, w4 = 1.5, w5 = −1.0, w6 = 1.0 |

A weighted sum of points: big weight = experts care a lot, negative = experts avoid it. Higher score = more expert-like.

| Candidate | φ1 | φ2 | φ3 | φ4 | φ6 | Score |
|---|---|---|---|---|---|---|
| B 10 kWp + 10 kWh + wallbox | 0 | 0 | 1 | 1 | 0.62 | **3.12** |
| A 8 kWp + 8 kWh + wallbox | −0.084 | 0 | 1 | 1 | 0.58 | 2.83 |
| C 10 kWp, no battery, wallbox | 0 | 0 | 0 | 1 | 0.35 | 1.85 |
| E 10 kWp + 10 kWh, no wallbox | 0 | 0 | 1 | 0 | 0.62 | 1.62 |
| D 15 kWp + 15 kWh, no wallbox | −0.467 | 0 | 1 | 0 | 0.70 | 0.30 |

B: 3.0·0 + 2.0·0 + 1.0·1 + 1.5·1 − 1.0·0 + 1.0·0.62 = 3.12.

## Step 7: probabilities

```
p(c | h) = e^score(h,c) / Σ_{c' ∈ C(h)} e^score(h,c')
```

| Symbol | Meaning |
|---|---|
| p(c \| h) | Probability an expert picks c for home h |
| e^x | Exponential; makes any score positive and widens gaps |
| c' | Runs over all feasible candidates |

Each design's share of the total. Example: e^3.12 = 22.6 of 52.4 → B 43%, A 32%, C 12%, E 10%, D 3%.

## Step 8: pick the design

```
c* = argmax_{c ∈ C(h)} score(h, c)
```

The feasible design with the highest score. **Confidence** = p(c* | h) (43%). **Alternatives** = next best (A, C).

The same step as an integer programme:

```
x[comp, s] ∈ {0,1}              1 = component comp gets size s
Σ_s x[comp, s] = 1               exactly one size per component (incl. "none")
x[batt, none] ≥ x[pv, none]      PV "none" forces battery "none"
x[batt, 5] = 1                   example lock
maximise score
```

φ2 and φ6 depend on PV and battery together, so the score is non-linear in x. A solver would need pair variables y[p,b] = x[pv,p] · x[batt,b], linearised by

```
y[p,b] ≤ x[pv,p]
y[p,b] ≤ x[batt,b]
y[p,b] ≥ x[pv,p] + x[batt,b] − 1
```

With ~150 feasible candidates, enumerating them gives the identical optimum with far less code. The IP is the formal description; enumeration is the solver. With a price per candidate (pricing), a budget is one more rule in step 3 (multiple-choice knapsack). It is not bin packing: nothing is packed into containers.

## Step 9: explanation

```
contribution_k = w_k × (φ_k(h, c*) − φ_k(h, runner-up))
```

Points the chosen design gained over the second best, per feature; the largest become the reasons.
Example B vs A: PV fit 3.0 × (0 − (−0.084)) = +0.25 → "10 kWp matches your 7,200 kWh incl. the EV, as in comparable expert designs; 8 kWp would be undersized."

## Step 10: refine

- **Lock a component** (battery = 5 kWh): one more rule in step 3, re-run steps 3–9. The rest re-optimises around it, e.g. 8 kWp + 5 kWh + wallbox.
- **Change an input** (buying an EV): D changes in step 1, so simulation, features and scores change, and a new design comes out.

## Training: r_PV, r_B and w

Ratios: what experts typically did (median, robust to odd projects):

```
r_PV = median over train of (expert PV kWp / D_MWh)
r_B  = median over train of (expert battery kWh / expert PV kWp)
```

Weights: make the experts' actual designs as probable as possible.

```
LL(w) = Σ_{h ∈ train} log p(c_h^expert | h)
```

| Symbol | Meaning |
|---|---|
| LL | Log-likelihood: how well the model predicts the experts (higher is better) |
| c_h^expert | Design the expert delivered for train home h |
| log | Turns a product of probabilities into a sum, easier to maximise |

Gradient ascent:

```
w_k ← w_k + η × Σ_h [ φ_k(h, c_h^expert) − Σ_c p(c|h) × φ_k(h, c) ]
```

| Symbol | Meaning |
|---|---|
| η (eta) | Learning rate (step size, e.g. 0.01) |
| φ_k(h, c_h^expert) | Feature k on the expert's actual pick |
| Σ_c p(c\|h) × φ_k(h, c) | Feature k on what the model currently expects |

If expert designs have more of a feature than the model expects, raise its weight; if less, lower it. Stops when expectations match the experts. Conditional logit: `statsmodels` `ConditionalLogit`, or ~20 lines of numpy.
Feature choices (e.g. D with or without EV) are compared on `val`; `test` is used once for the reported numbers.

## Roadmap and open points

- **M1:** baseline first (kNN over demand / EV / heating / installer, or gradient-boosted trees with PV → battery chained), scored on `val`. The scorer above is the M2 upgrade.
- **Heat pump:** ~31 examples, too few to learn; rule + physics (existing gas/oil, heat demand) instead.
- **Targets are noisy:** PV kWp is reconstructed from package names and module counts; which option was signed is unconfirmed (question for the Reonic experts).
- **Placeholders to replace with data:** r_PV, r_B, battery ≤ 1.5 × PV, k_EV = 0.18, yield ≈ 950 kWh/kWp, catalogue sizes, all weights.
