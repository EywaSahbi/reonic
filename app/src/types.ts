// Mirrors engine/CONTRACT.md (336060e) and reo/CONTRACT.md v1 (2d6428f). Keep in sync; never extend locally.

export type HomeFacts = {
  total_demand_kwh?: number; // yearly use as the customer states it, incl. EV + electric heating
  annual_demand_kwh?: number; // household only, without EV and heat pump
  num_inhabitants?: number;
  house_size_sqm?: number;
  house_built_year?: number;
  heating_type?: "gas" | "oil" | "heatpump" | "electric" | "district" | "other";
  heating_demand_kwh?: number;
  has_ev?: boolean;
  ev_planned?: boolean;
  ev_km_per_year?: number;
  ev_km_per_week?: number;
  ev_km_per_day?: number;
  roof_area_sqm?: number;
  roof_orientation_deg?: number;
  roof_tilt_deg?: number;
  electricity_price_eur_per_kwh?: number;
  has_existing_pv?: boolean;
  existing_pv_kwp?: number;
  has_existing_battery?: boolean;
  budget_eur?: number;
};

export type ComponentKey = "pv" | "battery" | "heatpump" | "wallbox";
export const COMPONENT_KEYS: ComponentKey[] = ["pv", "battery", "heatpump", "wallbox"];

export type Component = {
  recommended: boolean;
  size: number | null;
  unit: "kWp" | "kWh" | "kW";
  range: [number, number] | null;
  quantity?: number;
  confidence: "low" | "medium" | "high";
  locked: boolean;
  reasons: string[];
};

export type PriceList = Record<string, number>;

export type PriceItem = { label: string; qty: number; unit: string; unit_price_eur: number; total_eur: number };

export type Design = {
  components: Record<ComponentKey, Component>;
  price: { items: PriceItem[]; total_eur: number; range_eur: [number, number] };
  economics: {
    total_demand_kwh: number;
    self_consumption_pct: number;
    autarky_pct: number;
    annual_savings_eur: number;
    payback_years: number | null;
  };
  assumptions: { field: keyof HomeFacts; value: unknown; note: string }[];
  missing_inputs: { field: keyof HomeFacts; why: string; impact: "high" | "medium" | "low" }[];
  params_version: string;
};

export type Message = { role: "reo" | "customer" | "installer"; text: string; at: string };

export type Plan = {
  id: string;
  status: "drafting" | "handed_over" | "quoted";
  customer: { name?: string; email?: string };
  facts: HomeFacts;
  design: Design;
  transcript: Message[];
  flags: { component: ComponentKey; text: string; severity: "info" | "warn" }[];
  similar_projects: { project_id: string; facts: HomeFacts; expert: Record<ComponentKey, number | null> }[];
  installer_edits: { at: string; change: string; before: unknown; after: unknown }[];
  history: { at: string; trigger: string; total_eur: number }[];
  updated_at: string;
  summary?: string; // reo's installer paragraph, set once handed over
};

export type Ask = {
  field: keyof HomeFacts;
  prompt: string;
  input: "number" | "boolean" | "choice" | "address";
  options?: string[];
};

export type Turn = { messages: Message[]; plan: Plan; suggestions: string[]; ask?: Ask };

export type PlanSummary = Pick<Plan, "id" | "customer" | "status" | "updated_at"> & { total_eur: number };

export type Health = { ok: boolean; llm: boolean; voice: boolean; engine: boolean };

/** reo marks designs made while the engine was unreachable: no numbers, never show as a real design. */
export const isOffline = (d: Design) => d.params_version === "engine-offline";

export type Locks = Partial<Record<ComponentKey, { recommended: boolean; size?: number }>>;
