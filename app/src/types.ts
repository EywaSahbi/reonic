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
  roof_width_m?: number;
  roof_length_m?: number;
  roof_orientation_deg?: number;
  roof_tilt_deg?: number;
  region?: "BW" | "BY" | "BE" | "BB" | "HB" | "HH" | "HE" | "MV" | "NI" | "NW" | "RP" | "SL" | "SN" | "ST" | "SH" | "TH"; // federal state; sets PV yield
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
  max_modules?: number; // pv only, roof known: modules the roof holds (engine/CONTRACT.md)
  confidence: "low" | "medium" | "high";
  locked: boolean;
  reasons: string[];
};

export type PriceList = Record<string, number>;

export type PriceItem = { label: string; qty: number; unit: string; unit_price_eur: number; total_eur: number };

export type HeatingComparison = {
  fuel: string; heat_kwh: number; efficiency_now: number; cop: number; energy_factor: number;
  cost_now_eur_per_year: number; cost_heatpump_eur_per_year: number; cost_factor: number | null;
  heatpump_cheaper: boolean; co2_now_kg_per_year: number | null; co2_heatpump_kg_per_year: number | null;
  co2_reduction_pct: number | null; note: string | null;
};

export type Design = {
  heating_comparison?: HeatingComparison | null;
  components: Record<ComponentKey, Component>;
  price: { items: PriceItem[]; total_eur: number; range_eur: [number, number] };
  economics: {
    total_demand_kwh: number;
    self_consumption_pct: number;
    autarky_pct: number;
    annual_savings_eur: number;
    payback_years: number | null;
    bill_today_eur_per_month?: number;
    bill_after_eur_per_month?: number;
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
  installer_edits: { at: string; change: string; before: unknown; after: unknown }[];
  history: { at: string; trigger: string; total_eur: number }[];
  updated_at: string;
  summary?: string; // reo's installer paragraph, set once handed over
  offer_pack?: OfferPack; // installer endpoints only (reo v1.1)
  customer_estimate?: { total_eur: number; range_eur: [number, number] }; // installer view: what the customer was told at handoff
  roof_location?: RoofLocation; // set by an address lookup that found the building: satellite view on the plan card
};

export type Ask = {
  field: keyof HomeFacts;
  prompt: string;
  input: "number" | "boolean" | "choice" | "address" | "dimensions";
  options?: string[];
};

export type RoofLocation = { label: string; lat: number; lon: number; outline?: [number, number][] };
export type RoofLookup = { source: "OpenStreetMap" | "demo data"; label: string; footprint_sqm?: number };
/** GET /sessions/{id}/address/suggest: demo addresses (label only) or a Photon hit with its point. */
export type AddressSuggestion = { label: string; lat?: number; lon?: number; housenumber?: string; state?: string };

export type Turn = { roof?: RoofLookup; messages: Message[]; plan: Plan; suggestions: string[]; ask?: Ask; bill?: { read: Partial<HomeFacts> & { provider?: string }; confirmed: false }; goal_result?: GoalResult; heatpump_option?: HeatpumpOption };
/** reo/CONTRACT.md heat pump option: the plan as it stands and the same home with a heat pump, both from the engine. */
export type HeatpumpOption = { without: Design; with: Design };

/** POST /sessions/{id}/voice: a normal turn plus what reo heard and its spoken reply (base64 mp3). */
export type VoiceTurn = Turn & { heard: string; audio: string | null };

export type PlanSummary = Pick<Plan, "id" | "customer" | "status" | "updated_at"> & { total_eur: number };
export type GoalResult = { goal: "budget" | "independence" | "lowest_bill"; budget_eur?: number; recommendation: Variant; alternatives: Variant[]; trace: TraceStep[] };

export type Health = { demo_auth_required?: boolean; ok: boolean; llm: boolean; voice: boolean; engine: boolean };

/** reo marks designs made while the engine was unreachable: no numbers, never show as a real design. */
export const isOffline = (d: Design) => d.params_version === "engine-offline";

export type Locks = Partial<Record<ComponentKey, { recommended: boolean; size?: number }>>;

// ---- reo phase 2 (reo/CONTRACT.md v1.1, f1d56f1) ----
export type VariantName = "Basic" | "Recommended" | "Independence";
export type Variant = { name: VariantName; locks: Locks; design: Design; why: string; stale?: boolean }; // stale: after installer edits (v1.2)
export type Action = {
  id: string;
  kind: "book_visit" | "send_quote" | "create_crm_task" | "request_document";
  label: string;
  payload: Record<string, unknown>;
  status: "proposed" | "approved" | "done" | "rejected";
  result?: string;
  at?: string;
};
export type TraceStep = { step: number; tool: string; summary: string };
export type OfferPack = {
  status: "preparing" | "ready" | "failed";
  variants: Variant[];
  recommended: VariantName;
  flags: Plan["flags"];
  site_visit_checklist: string[];
  open_questions: string[];
  customer_message_draft: string;
  actions: Action[];
  trace: TraceStep[];
  duration_s: number;
  model: string; // "claude-opus-5-5" | "scripted"
  prepared_at: string;
  chosen?: VariantName;
  draft_for?: VariantName; // which variant customer_message_draft describes (requested from reo; optional)
  run_id?: string; // harness v1.2: live trace via GET /runs/{id}/events
};

// ---- reo agent harness (reo/CONTRACT.md v1.2, cfb01fd) ----
export type RunStep = {
  n: number;
  kind: "think" | "tool" | "guard";
  tool?: string;
  effect?: "read" | "propose" | "execute";
  args_summary: string;
  result_summary: string;
  ms: number;
  ok?: boolean; // guards: false = violation
};
export type Run = {
  id: string;
  skill: "chat_turn" | "offer_prep" | "goal_planner" | "bill_reader" | "installer_qa" | "follow_up";
  plan_id: string;
  trigger: string;
  status: "running" | "done" | "failed" | "needs_approval";
  steps: RunStep[];
  output: unknown | null;
  model: string;
  started_at: string;
  duration_s: number | null;
};
