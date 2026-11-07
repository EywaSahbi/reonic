# data/ notes

Full profiling: `docs/dataset_explanation.md`. This file lists only the rules `build.py` applies.

## Expert design per project
- **Option:** the highest `option_number` that contains hardware (Module, BatteryStorage, Wallbox, Heatpump, Inverter, substructure, or a "Complete Package"). Default until the Reonic experts say which option was signed (open question in `docs/plan.md`).
- 48 projects drop out (26 without parts, 22 whose options hold only fees). 1,571 remain.

## Sizes
- **PV kWp**, first rule that applies:
  1. `package_name`: "Complete Package 2 Sigenergy 10.8kWp + 9kWh" → 10.8 (145 projects, `23c108b7`).
  2. Module count × Wp. Count = max(sum of `Module` rows, largest quantity on a Substructure / Roof Mounting / DC Install row). Wp = the option's module rows, else the installer's median `module_watt_peak` (fallback 460 W). `target_source` = `module_rows` or `mount_count` (1,060 projects; an estimate, ±5 % from the Wp guess).
  3. Otherwise no PV (`none`).
- **Battery kWh:** sum of `inverter_power_kw × quantity` on `BatteryStorage` rows ÷ 1000 (column swap, Wh). Else the package name ("+ 9kWh").
- **Heat pump kW:** from the name ("Heat Pump 12.5kW" → 12.5); the spec column is rounded down. Else spec ÷ 1000.
- **Wallbox kW:** `wb_charging_speed_kw` ÷ 1000, else from the name.

## Inputs
- Wh → kWh for demand and heat demand; per-Wh → per-kWh for prices. 0 demand → null. Price outside 0.05–2 €/kWh → null (2 rows).
- `heating_existing_type` → `heating_type`: Heatpump→heatpump, Gas→gas, Oil→oil, OtherRenewable/OtherNonRenewable→other.
- `annual_demand_kwh` excludes EV and the existing heat pump; their consumption is in `ev_km_per_year` and `existing_heating_electricity_kwh`.

## What the targets look like (all 1,571)
- PV 79 % (median 9.5 kWp), battery 91 % (median 9 kWh), wallbox 26 % (11 kW), heat pump 1.4 % (22 projects).
- 330 projects without PV: 214 battery only, 68 wallbox only, 28 battery + wallbox, 11 heat pump only.
- A few large commercial-size projects (PV up to 100 kWp, battery up to 108 kWh). Kept; score with median-based metrics.
