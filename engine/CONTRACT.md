# engine/ contract (v1 — owner `egeunluer`)

HTTP JSON API on `http://localhost:8000`. Consumers: reo (all endpoints), data (via `predict.py` output).
Changes: additive → `CONTRACT` message to reo and qa; breaking → reo must `ACK` (after M1: `DECISION`).

## Types

```ts
// Every field optional. Field names are shared with data/processed/projects.parquet.
type HomeFacts = {
  total_demand_kwh?: number;            // total electricity per year INCL. EV and electric heating, as the customer states it; preferred for PV sizing
  annual_demand_kwh?: number;           // household electricity, WITHOUT EV and heat pump
  num_inhabitants?: number;             // used to estimate demand if no demand is given
  building_type?: "detached" | "semi" | "terraced";   // refines the inhabitants-based demand estimate
  house_size_sqm?: number;
  house_built_year?: number;
  heating_type?: "gas" | "oil" | "heatpump" | "electric" | "district" | "other";
  heating_demand_kwh?: number;          // heat per year; else house_size_sqm × typical demand by house_built_year
  has_ev?: boolean; ev_planned?: boolean; ev_km_per_year?: number;
  ev_km_per_week?: number; ev_km_per_day?: number;   // customer's estimate; used when ev_km_per_year is absent (×52, ×365)
  roof_area_sqm?: number; roof_orientation_deg?: number; roof_tilt_deg?: number;   // 180 = south
  roof_width_m?: number; roof_length_m?: number;   // sunny roof face as measured; both given = they win over roof_area_sqm (best grid of 1.722 × 1.134 m modules after a 0.3 m edge margin); a known roof is a HARD cap on new PV modules
  roof_type?: "gable" | "flat" | "mono" | "other";   // flat without orientation = east-west racks
  region?: "BW" | "BY" | "BE" | "BB" | "HB" | "HH" | "HE" | "MV" | "NI" | "NW" | "RP" | "SL" | "SN" | "ST" | "SH" | "TH";   // federal state (ISO 3166-2 code); sets the PV yield, else the national value
  electricity_price_eur_per_kwh?: number;
  has_existing_pv?: boolean; existing_pv_kwp?: number; has_existing_battery?: boolean;   // existing PV = retrofit: no new panels unless pv is locked
  budget_eur?: number;                  // design steps the battery, then the PV down until the price fits
};

type ComponentKey = "pv" | "battery" | "heatpump" | "wallbox";

type Component = {
  recommended: boolean;
  size: number | null;                  // kWp (pv), kWh (battery), kW (heatpump, wallbox)
  unit: "kWp" | "kWh" | "kW";
  range: [number, number] | null;       // sizes comparable expert designs choose, incl. what is still unknown (~80% of expert sizes fall inside on val)
  quantity?: number;                    // e.g. number of PV modules
  max_modules?: number;                 // pv only, when the roof is known: modules the roof holds (net of existing panels); size/quantity never exceed it, a pv lock above it is cut to it with a reason
  confidence: "low" | "medium" | "high";   // how much the still-missing inputs could move the size
  locked: boolean;
  reasons: string[];                    // 1–3, name the input that drove the decision
};

type PriceList = Record<string, number>;   // keys as returned by GET /prices; each has `<key>_low` / `<key>_high`.
                                           // Overriding `<key>` fixes that price (low = high = the override).

type Design = {
  components: Record<ComponentKey, Component>;
  price: { items: { label: string; qty: number; unit: string; unit_price_eur: number; total_eur: number }[];
           total_eur: number; range_eur: [number, number] };
  economics: { total_demand_kwh: number; self_consumption_pct: number; autarky_pct: number;
               annual_savings_eur: number; payback_years: number | null;
               bill_today_eur_per_month: number; bill_after_eur_per_month: number };   // after < 0 = net feed-in credit
  bundle: "S" | "M" | "L" | "XL" | null;                                          // by new PV kWp: < 6, < 10, < 14, else XL
  installer_profile: string | null;     // installer whose expert habits were used, null = all installers
  heating_comparison: {                                                           // null unless heating is gas / oil / district / other
    fuel: string; heat_kwh: number; efficiency_now: number; cop: number;
    energy_factor: number;                                                        // COP ÷ old efficiency: heat per kWh of electricity vs per kWh of fuel (gas 3.7)
    cost_now_eur_per_year: number; cost_heatpump_eur_per_year: number;            // heat pump on grid power, at the home's tariff
    cost_factor: number | null;                                                   // now ÷ heat pump (>1 = heat pump cheaper)
    heatpump_cheaper: boolean;                                                    // heat pump runs cheaper than today's heating on grid power: only then claim a cost benefit
    co2_now_kg_per_year: number | null; co2_heatpump_kg_per_year: number | null; co2_reduction_pct: number | null;   // null for district / other: no official factor
    note: string | null } | null;                                                 // how the heat demand was estimated, if not given
  assumptions: { field: keyof HomeFacts; value: unknown; note: string }[];     // defaults the engine used
  missing_inputs: { field: keyof HomeFacts; why: string; impact: "high" | "medium" | "low" }[];  // ranked
  params_version: string;
};
```

## Endpoints

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok: true, params_version}` | M0 |
| GET | `/installers` | → `{[id]: {projects, pv_line, battery_by_pv_band}}` (profiles fitted on that installer's train projects) | M1 |
| GET | `/prices` | → `PriceList` (defaults, with `_low` / `_high`) | M0 |
| POST | `/design` | `{facts: HomeFacts, locks?: Partial<Record<ComponentKey, {recommended: boolean, size?: number}>>, prices?: PriceList, installer?: string}` → `Design` (< 100 ms) | M1 |
| POST | `/explain` | `{facts, locks?, prices?, installer?, component: ComponentKey}` → `{reasons: string[], what_if: WhatIf[]}`: component off (or on), one size step down and up | M1 |

```ts
type WhatIf = { change: string; effect: string;
  delta: { price_eur: number; annual_savings_eur: number; payback_years: number | null; autarky_pct: number;
           bill_after_eur_per_month: number };
  locks: Record<ComponentKey, {recommended: boolean, size?: number}> };   // pass to /design to apply this variant
```
