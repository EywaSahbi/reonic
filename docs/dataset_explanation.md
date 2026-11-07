# Dataset Explanation: Reonic Project Data

This document describes the CSV files in `Project Data/`: what each column holds, the overall shape of the data, and the patterns and pitfalls found while profiling it.

**Confidence labels.** Statements about counts and distributions were computed directly from the files. Statements about what a column *means* are marked **(inferred)** when they come from column names, values and the challenge brief (`Reonic_Hackathon_Challenge_final.pdf`) rather than from documentation. Please confirm those with the Reonic experts at the hackathon.

---

## 1. Overview

```
Project Data/
├── 23c108b7/
│   ├── projects_status_quo.csv       342 projects × 36 columns
│   └── project_options_parts.csv     2,395 part rows × 15 columns
└── 2a8ba8e2/
    ├── projects_status_quo.csv       1,277 projects × 36 columns
    └── project_options_parts.csv     19,257 part rows × 15 columns
```

Both folders use an identical schema. The folder names are opaque hashes. The two folders differ systematically in brands, prices and tariffs (see section 5), so each is **probably a different installer's data (inferred)**.

**What the data represents.** Per the challenge brief, it is real residential projects:
- the **input conditions** of each home (`projects_status_quo.csv`), and
- the **system design an installer delivered** (`project_options_parts.csv`).

The intended ML task is: *given the home's facts, predict which components (PV, battery, wallbox, heat pump) the installer proposes and how large they are.*

### How the two files join

```
projects_status_quo (1 row per project_id)
        │  project_id
        ▼
project_options_parts (many rows per project)
        project_id → option_id (an offer variant) → one row per component line item
```

- `project_id` is unique in the status-quo files (no duplicates).
- A project has one or more **options** (offer variants), and an option has several **parts** (line items).
- Not every project has parts: 6 projects in `23c108b7` and 20 in `2a8ba8e2` have no rows in the parts file. No parts row refers to an unknown project.

---

## 2. `projects_status_quo.csv`: the home and customer (model inputs)

One row per project, 36 columns. Almost every column except the tariff and demand fields is sparse (see the fill rates in section 4).

### 2.1 Identifiers and timeline

| Column | Meaning |
|---|---|
| `project_id` | Unique project key; joins to the parts file. |
| `customer_contact_id` | Anonymised customer. Mostly unique, but a few customers appear in several projects (341 distinct of 342 in `23c108b7`, 1,235 of 1,277 in `2a8ba8e2`). Group by this when splitting train and test, to avoid leakage. |
| `request_created_at` | When the customer's request or lead was created. Mostly empty (277 of 342 filled in `23c108b7`, only 18 of 1,277 in `2a8ba8e2`). |
| `offer_created_at` | When the offer was created. Filled for all projects in `2a8ba8e2` and for 324 of 342 in `23c108b7`. |
| `first_signed_at` | When the offer was first signed. **Filled for every project in both datasets.** See the note below. |

Notes:
- Timestamps come in mixed formats. Most have fractional seconds (`2025-06-09 09:33:20.229000`), but some are date-only at midnight (`2025-09-12 00:00:00`: 22 rows in `23c108b7`, 14 in `2a8ba8e2`). A plain `pd.to_datetime` can fail; use `format="mixed"`.
- **Every project is signed.** The data therefore appears to contain only *won* deals, so the delivered design is a design the customer accepted. There is no signed or unsigned label to learn from. This is consistent with the brief's "design an installer actually delivered".
- Time from offer to signing: median about 28 days in `23c108b7` and about 20 days in `2a8ba8e2`. The mean is about 38 to 39 days, with a long tail (up to about 225 and 504 days). A handful of rows have signing *before* the offer (4 and 1 rows, by up to about 7 days), which is probably a data-entry artefact.

### 2.2 Location

| Column | Meaning |
|---|---|
| `country` | Germany in effectively all rows. There is one Slovenia row in `2a8ba8e2`. |

### 2.3 Electricity demand and tariff

| Column | Unit | Meaning |
|---|---|---|
| `energy_demand_wh` | Wh per year | Household annual electricity demand. 4,500,000 Wh = 4,500 kWh is the most common value. |
| `energy_price_per_wh` | currency per Wh | Grid electricity price. Multiply by 1,000 for a per-kWh price (0.00032 means 0.32 per kWh). Currency is not stated; presumably EUR **(inferred)**. |
| `energy_price_increase` | fraction per year | Assumed annual electricity price escalation (e.g. 0.03 means 3%). Range 0 to 0.06. |
| `energy_price_with_flexible_tariff` | currency per Wh | Price under a flexible or dynamic tariff **(inferred)**. Lower than the standard price (about 0.00021 to 0.00023 on average). Filled for 44% of projects in `23c108b7` and 5.5% in `2a8ba8e2`. |
| `base_price_per_month` | currency per month | Fixed monthly grid base fee. Sparse (30 and 56 rows). |
| `base_price_increase` | fraction per year | Escalation of the base fee. Sparse (71 and 73 rows). |
| `load_profile` | category | Standard household consumption-profile template: `H0` (the German standard household profile, 92% of rows), `FamilyOfFour`, `HomeOfficeOnePerson`, `SeniorOnePerson`, `FullTimeOnePerson`, `PartTimeOnePerson`, `SingleParentThreePersons`, `CustomFromEditor`. |
| `load_profile_editor_id` | id | Reference to a custom profile; the profile itself is not included. Empty in almost every row. **(inferred)** |

### 2.4 Existing or planned assets

The `has_*` flags are booleans. The detail columns next to them are mostly empty, because most customers have none of these assets.

| Group | Columns | Meaning |
|---|---|---|
| EV | `has_ev`, `ev_annual_drive_distance_km` | Customer has an EV and drives this many km per year (2,500 to 60,000). Only 21 projects in `23c108b7` and 41 in `2a8ba8e2` have an EV. |
| Solar | `has_solar`, `solar_size_kwp`, `solar_angle`, `solar_orientation`, `solar_built_year`, `solar_feedin_renumeration`, `solar_feedin_renumeration_post_eeg` | Existing PV: size, roof tilt in degrees, azimuth in degrees (180 is south), build year, feed-in remuneration (per Wh) and the feed-in rate after the German EEG guarantee ends. `solar_size_kwp` is stored in **Wh/W scale**: 9,260 means 9.26 kWp. Filled only for 18 projects in `2a8ba8e2` and none in `23c108b7`. |
| Storage | `has_storage`, `storage_size_kwh`, `storage_built_year` | Existing battery. `storage_size_kwh` is also in **Wh scale** (8,800 means 8.8 kWh). Very rare (5 and 6 projects). |
| Wallbox | `has_wallbox`, `wallbox_charge_speed_kw` | Existing EV charger, in **W scale** (11,000 means 11 kW). Very rare (0 and 4 projects). |

### 2.5 Existing heating

| Column | Meaning |
|---|---|
| `heating_existing_type` | `Heatpump`, `Gas`, `Oil`, `OtherRenewable`, `OtherNonRenewable`. Empty for most rows (86% and 88%). |
| `heating_existing_cost_per_year` | Annual cost of the current heating. |
| `heating_existing_cost_increase_per_year` | Annual cost escalation. **Always empty.** |
| `heating_existing_electricity_demand_kwh` | Electricity the existing heating consumes (1,000 to 12,000). Unlike the `_wh` columns, this one is actually in kWh. |
| `heating_existing_heating_demand_wh` | Annual heat demand in Wh (about 17 to 42 MWh). |

`heating_existing_type = Heatpump` is the most common value (43 and 128 projects). Because it is common, a heat-pump customer may already have a heat pump installed, so a heat-pump entry in `heating_existing_type` does not necessarily mean the installer is selling one **(inferred)**.

### 2.6 House

| Column | Meaning |
|---|---|
| `house_size_sqm`, `house_built_year`, `num_inhabitants` | Almost always empty (2 and 5 rows filled). Effectively unusable as model features. |

---

## 3. `project_options_parts.csv`: the delivered designs (model targets)

One row per component line item of an offer option, 15 columns.

| Column | Meaning |
|---|---|
| `project_id` | Joins to the status-quo file. |
| `option_id` | Unique id of one offer variant. |
| `option_number` | Position of the option within its project (1, 2, 3...). It is constant within an option. It is not always contiguous, and the maximum is 10 in `23c108b7` and 19 in `2a8ba8e2`. This may reflect options that were created and then deleted **(inferred)**. |
| `technology` | Which system family the line belongs to: `solar`, `ses` (a storage system, likely "solar energy storage"; **inferred**), `wallbox`, `heatpump`. The `heatpump` value appears only in `2a8ba8e2`. One row has an empty value. |
| `line_item_function` | Role of the line. `default` is about 99% of rows. The other values (`heatpump`, `other`, `warmwaterStorage`, `heatingStorage`) appear only in `2a8ba8e2`. |
| `component_type` | Category of the component (table below). |
| `component_name` | Free-text product or service name. 208 and 349 distinct names. |
| `component_brand` | Manufacturer. Often empty. |
| `quantity` | Number of units (1 to 222). |
| `quantity_units` | `Item`, `SquareMeter`, `LinearMeter`, `FlatRate`, or empty. |
| `module_watt_peak` | PV module rating in W. |
| `inverter_power_kw` | See the warning below. |
| `battery_capacity_kwh` | See the warning below. |
| `wb_charging_speed_kw` | Wallbox charging power in W (11,000 or 22,000). |
| `heatpump_nominal_power_kw` | Heat-pump power in W (5,000 to 12,000). Only in `2a8ba8e2`. |

### `component_type` values

| Group | Types |
|---|---|
| Core hardware | `Module`, `Inverter`, `BatteryStorage`, `Wallbox`, `Heatpump`, `HeatingStorage`, `WarmwaterStorage` |
| Accessories | `AccessoryToModule` (e.g. power optimizers), `AccessoryToInverter`, `AccessoryToBatteryStorage`, `AccessoryToWallbox`, `AccessoryToHeatpump`, `ModuleFrameConstruction` (roof substructure) |
| Services | `InstallationFee`, `ServiceFee` (e.g. "Grid Registration", "Delivery to Site", "Planning Your Solar System") |
| Catch-all | `Other`. Includes "Complete Package" bundles such as `Complete Package 2 Sigenergy 10.8kWp + 9kWh`, gateways and bonding rails. |

### WARNING: swapped and mis-scaled spec columns

The spec columns do not line up with their names:

| Row type | Column that actually holds the value | Column that is empty |
|---|---|---|
| `BatteryStorage` | **`inverter_power_kw`** holds the battery capacity (e.g. "Battery 10kWh" has `10000`) | `battery_capacity_kwh` |
| `Inverter` | **`battery_capacity_kwh`** holds the inverter power (e.g. "Hybrid Inverter 8kW" has `8000`) | `inverter_power_kw` |

This holds in both datasets: every populated `inverter_power_kw` value sits on a `BatteryStorage` row (292 and 1,488 rows), and every populated `battery_capacity_kwh` value sits on an `Inverter` row (46 and 6 rows). In effect the two column names are swapped.

Despite the `_kw` and `_kwh` suffixes, **all spec values are in W or Wh**, so divide by 1,000 to get kW or kWh. This matches `wb_charging_speed_kw` and `heatpump_nominal_power_kw`, which are also in W. `module_watt_peak` is genuinely in W.

Heat-pump power looks rounded down: "Heat Pump 12.5kW" is recorded as 12,000.

### Where the PV size is

Explicit `Module` rows are rare (65 rows in `23c108b7`, 4 in `2a8ba8e2`), so **PV system size is mostly not a clean column**. It has to be recovered from other fields (inferred):
- **Component names**, e.g. `Complete Package 2 Sigenergy 10.8kWp + 9kWh` (the `Other` bundles).
- **Quantities** of items that scale one-to-one with modules: `ModuleFrameConstruction` (the roof substructure quantity) and `AccessoryToModule` (e.g. "Power Optimizer 600W" with quantity 19 next to "Substructure Concrete Roof" with quantity 19).
- A module-wattage guess (typically 450 to 480 W) multiplied by the module count.

---

## 4. General features of the dataset as a whole

| Metric | `23c108b7` | `2a8ba8e2` |
|---|---|---|
| Projects | 342 | 1,277 |
| Part rows | 2,395 | 19,257 |
| Offer options | 357 | 1,637 |
| Projects with 1 option | 316 (92%) | 977 (77%) |
| Projects with 2 or more options | 20 | 280 |
| Median parts per option | 8 | 13 |
| Offer dates | Jun 2025 to Apr 2026 (peaks in Q4 2025 and Q1 2026) | Jun 2024 to Apr 2026 (spread roughly evenly, with a peak in 2025) |
| Countries | Germany | Germany (1,276), Slovenia (1) |
| Technologies present | solar, ses, wallbox | solar, ses, wallbox, heatpump |
| Distinct component names | 208 | 349 |

Overall character:
- **Small and tabular.** About 1,600 projects in total, so classical ML (trees or gradient boosting) and rule extraction are better suited than deep models.
- **Sparse inputs.** Only about five input features are reliably populated: `energy_demand_wh`, `energy_price_per_wh`, `energy_price_increase`, `load_profile` and `has_ev`. The heating-type fields are moderately filled. Roof geometry, house size, inhabitants and existing PV are almost never present. This matches the brief's question about the minimum input you need for a good design.
- **No prices in the data.** There is no cost, margin or offer-total column, so economics must be modelled from outside knowledge.
- **Targets are semi-structured.** The design is a bag of line items with free-text names, not a clean "PV size, battery size" record. Building a usable target means normalising components into a few numbers, such as PV kWp, battery kWh, inverter kW, wallbox kW and heat-pump kW.
- **Multiple options per project.** The data does not say which option the customer finally signed. The brief says the data contains the design that was delivered, but the files give no flag that picks it out. Check this with the Reonic experts, since it changes how training rows should be built.

Fill rates of the most useful columns (percent of projects):

| Column | `23c108b7` | `2a8ba8e2` |
|---|---|---|
| `energy_demand_wh`, `energy_price_per_wh`, `energy_price_increase`, `load_profile` | 100% | 100% |
| `has_ev = True` | 6% | 3% |
| `heating_existing_type` | 14% | 12% |
| `energy_price_with_flexible_tariff` | 44% | 5.5% |
| `has_solar = True` | 0% | 1.4% |
| `has_storage = True` | 1.5% | 0.5% |
| `has_wallbox = True` | 0% | 0.3% |
| `house_size_sqm`, `house_built_year`, `num_inhabitants` | 0.6% | 0.4% |

---

## 5. Patterns observed

### 5.1 The two datasets behave like two different installers (inferred)

| | `23c108b7` | `2a8ba8e2` |
|---|---|---|
| Most common energy price | 0.00039 per Wh (125 projects) | 0.00032 per Wh (913 of 1,277, or 71%) |
| Flexible tariff recorded | 44% | 5.5% |
| Main brands | Sigenergy (556 rows), Sunpro, GoodWe, EcoFlow, FoxESS | Huawei (1,825), EcoFlow, SAJ, Vaillant, SolarEdge, Enphase |
| Heat pumps in offers | none | 31 heat-pump components (Vaillant) |
| Packaging style | "Complete Package" bundles in `Other` rows | itemised parts: more accessories and more rows per option |

The most common energy price is probably a default value the installer's tool pre-fills, not a measured price, so it carries little information **(inferred)**. Because the installers differ in brands and product catalogue, **mixing the datasets without a dataset or installer indicator may confuse a model**. You could add a source flag, or evaluate each dataset separately and then jointly.

### 5.2 Typical customer

- Round demand values dominate. `4,500,000` Wh is the most frequent in both datasets (69 and 410 projects), followed by 3,000,000, 3,500,000, 4,000,000 and 5,000,000. Demand is likely entered as an estimate in round steps, not read from a bill. The median is 4.5 MWh in both.
- `H0` is the default profile in 92% of projects, so the profile adds little signal except for the rarer family, home-office and senior profiles.
- A project with an EV has a lower median demand (4.0 MWh) than one without (4.5 MWh). This is a surprise: it suggests EV consumption is not added to `energy_demand_wh` but modelled separately via `ev_annual_drive_distance_km` **(inferred)**.

### 5.3 What installers deliver (the target mix)

Option composition by system family, as the number of options containing each technology combination:

| Combination | `23c108b7` | `2a8ba8e2` |
|---|---|---|
| solar + storage (`ses`) | 205 | 868 |
| solar + storage + wallbox | 65 | 361 |
| solar only | 63 | 79 |
| storage only | 9 | 197 |
| wallbox only | 3 | 60 |
| solar + wallbox | 10 | 18 |
| storage + wallbox | 2 | 22 |
| heat pump only | 0 | 21 |
| heat pump + solar + storage (with or without wallbox) | 0 | 10 |

- **Solar plus storage is the dominant bundle** (about 76% of options in both datasets, counting variants with a wallbox or heat pump). A battery is attached to most PV offers, and "no battery" is the minority case (solar only: 18% of options in `23c108b7`, 5% in `2a8ba8e2`).
- Storage-only and wallbox-only offers also exist, mainly in `2a8ba8e2`, which matches the brief's point that a home does not always get every component.
- Heat pumps appear in only 31 option records, so the heat-pump decision is the hardest target to learn.
- Component sizes cluster at typical product values. Batteries run from about 2 to 21 kWh (commonly 5 to 15), inverters from about 4 to 20 kW, wallboxes are 11 or 22 kW, and modules are 450 to 480 W. These look like **catalogue-driven discrete sizes**, which suggests predicting a class or the nearest catalogue product rather than a continuous value.
- Within one option, a hybrid inverter, battery and accessories usually come as a matched set (for example, the battery accessory rows follow the battery rows). Each option is a coherent bundle, not independent picks, which echoes the brief's "decisions are coupled".

### 5.4 Fee and service lines are noise for sizing

`InstallationFee` and `ServiceFee` are the two largest line categories (690 and 528 rows in `23c108b7`; 6,683 and 3,811 in `2a8ba8e2`). Names such as "Grid Registration" and "Delivery to Site" appear in more than half of the options in `23c108b7`. They add rows but describe no system size, and they can be dropped when building the design target. They may help distinguish installers or offer styles.

### 5.5 Timeline

- Offers are created continuously over about 10 months (`23c108b7`) and about 22 months (`2a8ba8e2`). The later quarters of `2a8ba8e2` have fewer offers, and the last quarter is partial.
- Time from offer to signature is highly skewed. Half of projects sign within about 3 to 4 weeks, but some take over a year. Signature dates fall up to 25 April 2026, so very late data may be incomplete.
- A time-based train and test split is possible, since offer dates are present for nearly every project.

---

## 6. Data quality issues and pitfalls

1. **Swapped columns:** `inverter_power_kw` holds battery capacity and `battery_capacity_kwh` holds inverter power (section 3). Fix this before any feature work.
2. **Units:** nearly everything named `_kw` or `_kwh` is in W or Wh. `heating_existing_electricity_demand_kwh` is the one real kWh column.
3. **Outliers in `2a8ba8e2`:**
   - `energy_demand_wh = 0` in 14 projects. The maximum of 50,000,000 Wh (50 MWh) is far above a normal household.
   - `energy_price_per_wh` has a minimum of 0 and one value of 0.32, which looks like a per-kWh figure entered in a per-Wh column. These are 2 of 1,277 rows.
   - `heating_existing_cost_per_year` and `heating_existing_heating_demand_wh` contain zeros.
4. **Empty or unusable columns:** `heating_existing_cost_increase_per_year` (always empty), `solar_*` in `23c108b7` (all empty), `solar_feedin_renumeration*` (1 row or none), `wallbox_charge_speed_kw` in `23c108b7` (all empty), the house fields (under 1% filled), and `load_profile_editor_id`.
5. **Orphan projects:** 6 and 20 projects have no parts rows and cannot be used as supervised examples.
6. **Sparse module data:** explicit PV size is mostly missing, so it has to be reconstructed from names and quantities.
7. **Free-text component names:** names differ per installer and contain mixed languages and codes, so matching needs normalisation (for example regex for "10kWh" or "11kW").
8. **Ambiguous target:** several options per project with no "delivered" flag; the last or highest `option_number` might be the signed one, but that is unverified.
9. **Class imbalance:** very few heat-pump, EV and existing-asset examples.
10. **Customer leakage:** a few customers have several projects, so split by `customer_contact_id`.
11. **Date parsing:** mixed timestamp formats (section 2.1).
12. **Usage restriction:** per the brief, the data may only be used for the hackathon and must not be shared outside the team.

---

## 7. Suggested modelling implications

- **Inputs worth using:** `energy_demand_wh`, `energy_price_per_wh`, `energy_price_increase`, `load_profile`, `has_ev` and `ev_annual_drive_distance_km`, `heating_existing_type` and its demand fields, and the `has_*` existing-asset flags. A source (installer) indicator may also help.
- **Targets to derive per project:** battery kWh (or none), PV kWp (derived), inverter kW, wallbox kW (or none), heat pump kW (or none). Derive these from the cleaned, correctly labelled spec columns and from the module counts.
- **Treat the decision as two steps:** first whether each component is present, then its size.
- **Open questions for the Reonic experts:**
  1. Is the intended mapping of the swapped columns confirmed?
  2. Which option was actually delivered when a project has several?
  3. What exactly does `ses` stand for, and is `energy_price_with_flexible_tariff` a dynamic tariff?
  4. Why is energy demand lower for EV projects?
  5. Are the two folders two different installers?
