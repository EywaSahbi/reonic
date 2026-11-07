# engine/ contract (v0 draft — owner `egeunluer` agrees v1 with app at M0)

HTTP JSON API on `http://localhost:8000`, CORS open to `http://localhost:5173`.
Changes: additive → `CONTRACT` message to app; breaking → app must `ACK` (after M1: `DECISION`).

## Types

```ts
// All fields optional except energy_demand_kwh; the engine fills gaps and says so in `assumptions`.
type HomeInput = {
  energy_demand_kwh: number;            // annual household electricity, without heat pump / EV
  energy_price_eur_per_kwh?: number;
  num_inhabitants?: number;
  house_size_sqm?: number;
  has_ev?: boolean; ev_annual_km?: number;
  heating_existing_type?: "Gas" | "Oil" | "Heatpump" | "Electric" | "Other" | null;
  heating_demand_kwh?: number;
  has_existing_pv?: boolean; has_existing_storage?: boolean;
  budget_eur?: number;
};

type ComponentKey = "pv" | "battery" | "heatpump" | "wallbox";

type Component = {
  recommended: boolean;
  size: number | null;                  // kWp (pv), kWh (battery), kW (heatpump, wallbox)
  unit: "kWp" | "kWh" | "kW";
  confidence: number;                   // 0..1
  alternatives: number[];               // other sensible sizes
  locked: boolean;                      // true when the planner fixed it
  reasons: string[];                    // short, planner-grade
};

type Design = {
  components: Record<ComponentKey, Component>;
  summary: string;                      // 1–3 sentences explaining the design as a whole
  kpis?: { self_consumption_pct?: number; autarky_pct?: number; annual_savings_eur?: number; payback_years?: number };
  assumptions: string[];                // inputs the engine filled in
  similar_projects?: { project_id: string; similarity: number; design: Record<ComponentKey, number | null> }[];
  model_version: string;
};
```

## Endpoints

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok: true, model_version}` | M0 |
| POST | `/design` | `HomeInput` → `Design` | M0 stub, M1 real |
| POST | `/refine` | `{home: HomeInput, locks?: Partial<Record<ComponentKey, {recommended: boolean, size?: number}>>}` → `Design` (locked parts kept, the rest re-derived) | M1 |
| GET | `/projects?split=test&limit=50` | → `{project_id, home: HomeInput}[]` for the demo picker | M2 |
| GET | `/compare/{project_id}` | → `{home, proposed: Design, expert: Record<ComponentKey, {recommended, size}>}` | M2 |
| GET | `/metrics?split=test` | → data's score JSON for the current model | M2 |
| POST | `/parse` (stretch) | `{home, text}` → `{home: HomeInput, changes: string[]}` natural-language refine | M2 |
