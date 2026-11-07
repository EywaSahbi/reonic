# engine/ contract (v0 draft — owner `egeunluer` agrees v1 with reo at M0)

HTTP JSON API on `http://localhost:8000`. Consumers: reo (all endpoints), data (via `predict.py` output).
Changes: additive → `CONTRACT` message to reo and qa; breaking → reo must `ACK` (after M1: `DECISION`).

## Types

```ts
// Every field optional. Field names are shared with data/processed/projects.parquet.
type HomeFacts = {
  total_demand_kwh?: number;            // total electricity per year INCL. EV and electric heating, as the customer states it; preferred for PV sizing
  annual_demand_kwh?: number;           // household electricity, WITHOUT EV and heat pump
  num_inhabitants?: number;             // used to estimate demand if annual_demand_kwh is missing
  house_size_sqm?: number;
  house_built_year?: number;
  heating_type?: "gas" | "oil" | "heatpump" | "electric" | "district" | "other";
  heating_demand_kwh?: number;
  has_ev?: boolean; ev_planned?: boolean; ev_km_per_year?: number;
  ev_km_per_week?: number; ev_km_per_day?: number;   // customer's estimate; used when ev_km_per_year is absent (×52, ×365)
  roof_area_sqm?: number; roof_orientation_deg?: number; roof_tilt_deg?: number;   // 180 = south
  electricity_price_eur_per_kwh?: number;
  has_existing_pv?: boolean; existing_pv_kwp?: number; has_existing_battery?: boolean;
  budget_eur?: number;
};

type ComponentKey = "pv" | "battery" | "heatpump" | "wallbox";

type Component = {
  recommended: boolean;
  size: number | null;                  // kWp (pv), kWh (battery), kW (heatpump, wallbox)
  unit: "kWp" | "kWh" | "kW";
  range: [number, number] | null;       // plausible sizes given what is still unknown
  quantity?: number;                    // e.g. number of PV modules
  confidence: "low" | "medium" | "high";
  locked: boolean;
  reasons: string[];                    // 1–3, name the input that drove the decision
};

type PriceList = Record<string, number>;   // keys as returned by GET /prices

type Design = {
  components: Record<ComponentKey, Component>;
  price: { items: { label: string; qty: number; unit: string; unit_price_eur: number; total_eur: number }[];
           total_eur: number; range_eur: [number, number] };
  economics: { total_demand_kwh: number; self_consumption_pct: number; autarky_pct: number;
               annual_savings_eur: number; payback_years: number | null };
  assumptions: { field: keyof HomeFacts; value: unknown; note: string }[];     // defaults the engine used
  missing_inputs: { field: keyof HomeFacts; why: string; impact: "high" | "medium" | "low" }[];  // ranked
  params_version: string;
};
```

## Endpoints

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok: true, params_version}` | M0 |
| GET | `/prices` | → `PriceList` (defaults with labels) | M0 |
| POST | `/design` | `{facts: HomeFacts, locks?: Partial<Record<ComponentKey, {recommended: boolean, size?: number}>>, prices?: PriceList}` → `Design` | M0 stub, M1 real |
| POST | `/explain` | `{facts, locks?, prices?, component: ComponentKey}` → `{reasons: string[], what_if: {change: string, effect: string}[]}` | M2 |
