// In-browser mock of reo/CONTRACT.md so the UI runs before reo is live.
// shortcut: fake sizing + prices (numbers are placeholders, NOT engine output); delete once reo serves M1.
// Plans persist in localStorage so the installer view (another tab) sees handed-over plans.
import type { Api } from "./api";
import type { Ask, Component, Design, HomeFacts, Locks, Message, Plan, PriceList, Turn, Variant, VariantName } from "./types";

const KEY = "reo-mock-plans";
const now = () => new Date().toISOString();
const delay = <T,>(v: T) => new Promise<T>((r) => setTimeout(() => r(structuredClone(v)), 350));

function load(): Record<string, Plan> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}
function save(plan: Plan) {
  const all = load();
  all[plan.id] = { ...plan, updated_at: now() };
  try {
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch {
    /* storage blocked: mock still works for this tab */
  }
  return all[plan.id];
}
function get(id: string): Plan {
  const p = load()[id];
  if (!p) throw new Error(`mock: plan ${id} not found`);
  return p;
}

// Calibrated to the real engine on 2026-11-08 for the demo path (4,500 kWh, 48 m² roof, EV planned, gas heating).
// Engine: 7.74 kWp (18 modules, roof-limited) + 5 kWh battery + 11 kW wallbox = EUR 14,186; with the 8 kW heat pump
// EUR 42,121 before the KfW grant; solar + battery ROI 8.5 yrs; savings EUR 1,471/yr; own power 29.6 % (with heat pump).
// Still a mock: formulas fitted to those outputs, NOT engine output. Prices are shown without the KfW grant, as reo does for customers.
const MODULE_KWP = 0.43; // 430 W per module, as in the engine
const M2_PER_MODULE = 2.65; // roof area one module needs (engine: 48 m² holds 18)
const YIELD_KWH_PER_KWP = 1082; // German average, as in the engine's reasons

const DEFAULT_PRICES: PriceList = {
  pv_per_kwp: 869, // modules + mounting + roof installation + DC/AC cabling
  battery_per_kwh: 275,
  battery_base: 1786, // battery inverter, BMS, installation
  heatpump_base: 11500, // incl. hydraulics and installation
  heatpump_per_kw: 2054,
  wallbox: 1644, // device + installation
  installation: 1975, // meter cabinet, commissioning, scaffolding
};

function comp(unit: Component["unit"], partial: Partial<Component>): Component {
  return { recommended: false, size: null, unit, range: null, confidence: "low", locked: false, reasons: [], ...partial };
}

function inverterFor(kwp: number): { label: string; qty: number; unit_price_eur: number } {
  if (kwp <= 8.6) return { label: "Hybrid inverter 6 kW", qty: 1, unit_price_eur: 679 };
  if (kwp <= 13.5) return { label: "Hybrid inverter 10 kW", qty: 1, unit_price_eur: 1050 };
  return { label: "Hybrid inverter 10 kW", qty: 2, unit_price_eur: 1050 };
}

function heatingComparison(f: HomeFacts, heatKwh: number): Design["heating_comparison"] {
  const t = f.heating_type;
  if (t !== "gas" && t !== "oil" && t !== "district" && t !== "other") return null;
  const eff = t === "oil" ? 0.85 : t === "district" ? 1 : 0.9;
  const fuelEur = t === "oil" ? 0.11 : t === "district" ? 0.11 : 0.12; // EUR per kWh of fuel
  const co2 = t === "gas" ? 0.201 : t === "oil" ? 0.266 : null; // kg per kWh of fuel (official factors only)
  const cop = 3.3;
  const now = Math.round((heatKwh / eff) * fuelEur);
  const hp = Math.round((heatKwh / cop) * 0.32);
  const co2Now = co2 === null ? null : Math.round((heatKwh / eff) * co2);
  const co2Hp = co2 === null ? null : Math.round((heatKwh / cop) * 0.344);
  return {
    fuel: t, heat_kwh: heatKwh, efficiency_now: eff, cop, energy_factor: Math.round((cop / eff) * 10) / 10,
    cost_now_eur_per_year: now, cost_heatpump_eur_per_year: hp, cost_factor: Math.round((now / hp) * 100) / 100,
    heatpump_cheaper: now > hp,
    co2_now_kg_per_year: co2Now, co2_heatpump_kg_per_year: co2Hp,
    co2_reduction_pct: co2Now === null || co2Hp === null ? null : Math.round(((co2Now - co2Hp) / co2Now) * 1000) / 10,
    note: "median heat demand in the expert projects",
  };
}

function design(f: HomeFacts, locks: Locks = {}, prices: PriceList = DEFAULT_PRICES): Design {
  const assumptions: Design["assumptions"] = [];
  let stated = f.total_demand_kwh ?? f.annual_demand_kwh;
  if (stated === undefined) {
    stated = f.num_inhabitants ? 1000 + f.num_inhabitants * 900 : 4000;
    assumptions.push({ field: "annual_demand_kwh", value: stated, note: f.num_inhabitants ? `estimated from ${f.num_inhabitants} people` : "typical home" });
  }
  const evPlanned = !f.has_ev && !!f.ev_planned;
  const ev = !!f.has_ev || evPlanned;
  const evKwh = evPlanned ? 2340 : 0; // a planned EV adds future charging; an existing one is already in the stated total
  const hpWanted = f.heating_type === "gas" || f.heating_type === "oil" || f.heating_type === "district" || f.heating_type === "other";
  const living = f.house_size_sqm ?? 140;
  const hpKw = Math.max(5, Math.round(living / 17.5));
  const heatKwh = Math.round(((15800 * living) / 140) / 100) * 100;

  // PV: comparable expert designs install 6.2 kWp + 0.60 kWp per MWh (engine rule), limited by the roof when it is known
  const pvLoad = stated + evKwh;
  const wantModules = Math.round((6.2 + 0.6 * (pvLoad / 1000)) / MODULE_KWP);
  const roofModules = f.roof_area_sqm !== undefined ? Math.floor(f.roof_area_sqm / M2_PER_MODULE) : undefined;
  const modules = roofModules !== undefined ? Math.min(wantModules, roofModules) : wantModules;
  const roofLimited = roofModules !== undefined && roofModules < wantModules;
  const pv = Math.round(modules * MODULE_KWP * 100) / 100;
  if (f.roof_area_sqm === undefined) assumptions.push({ field: "roof_area_sqm", value: "not limited", note: "no roof limit assumed until the roof is known" });
  if (f.electricity_price_eur_per_kwh === undefined) assumptions.push({ field: "electricity_price_eur_per_kwh", value: 0.32, note: "German average household tariff" });

  const missing: Design["missing_inputs"] = [];
  if (!f.heating_type) missing.push({ field: "heating_type", why: "decides whether a heat pump makes sense", impact: "high" });
  if (f.has_ev === undefined && f.ev_planned === undefined) missing.push({ field: "has_ev", why: "an EV adds demand and a wallbox", impact: "high" });
  if (f.roof_area_sqm === undefined) missing.push({ field: "roof_area_sqm", why: "limits how many panels fit", impact: "medium" });
  if (hpWanted && f.house_size_sqm === undefined) missing.push({ field: "house_size_sqm", why: "sizes the heat pump", impact: "medium" });
  if (f.electricity_price_eur_per_kwh === undefined) missing.push({ field: "electricity_price_eur_per_kwh", why: "drives savings and ROI", impact: "low" });

  const hi = missing.filter((m) => m.impact === "high").length;
  const med = missing.filter((m) => m.impact === "medium").length;
  const score = hi * 2 + med;
  const conf: Component["confidence"] = score >= 3 ? "low" : score >= 1 ? "medium" : "high";
  const s = 0.1 + 0.05 * score;
  const r = (x: number, sp = s): [number, number] => [Math.round(x * (1 - sp) * 2) / 2, Math.round(x * (1 + sp) * 2) / 2];

  const battKwh = pv < 8.5 ? 5 : pv < 14 ? 10 : 15; // what comparable expert designs pair with that much PV
  const components: Design["components"] = {
    pv: comp("kWp", {
      recommended: true, size: pv, range: r(pv), quantity: modules, confidence: conf,
      reasons: [
        `${pvLoad.toLocaleString("en")} kWh/yr: comparable expert designs install 6.2 kWp + 0.60 kWp per MWh`,
        `${modules} new modules produce ~${Math.round(pv * YIELD_KWH_PER_KWP).toLocaleString("en")} kWh/yr (1,082 kWh per kWp, German average)`,
        ...(roofLimited ? [`the roof is the limit: it holds only ${roofModules} modules (${wantModules} would match your demand)`] : []),
      ].slice(0, 3),
    }),
    battery: comp("kWh", stated > 2500
      ? { recommended: true, size: battKwh, range: r(battKwh), confidence: conf, reasons: [`${battKwh} kWh is what comparable expert designs most often pair with ~${Math.round(pv)} kWp of PV (a battery is in 95% of expert PV offers)`, "stores the midday surplus for the evening"] }
      : { reasons: ["demand too low for a battery to pay off"] }),
    heatpump: comp("kW", hpWanted
      ? { recommended: true, size: hpKw, range: r(hpKw, s + 0.05), confidence: f.house_size_sqm ? "medium" : "low", reasons: [`replaces ${f.heating_type} heating`, f.house_size_sqm ? `${living} m² living space` : "living space assumed 140 m²"] }
      : { reasons: [f.heating_type ? `${f.heating_type} heating: no heat pump needed` : "heating type unknown"] }),
    wallbox: comp("kW", ev ? { recommended: true, size: 11, range: [11, 11], confidence: "high", reasons: [f.has_ev ? "you have an EV" : "EV planned"] } : { reasons: ["no EV"] }),
  };

  for (const [k, lock] of Object.entries(locks) as [keyof Locks, NonNullable<Locks[keyof Locks]>][]) {
    const c = components[k];
    c.locked = true;
    c.recommended = lock.recommended;
    if (lock.size !== undefined) c.size = lock.size;
    if (!lock.recommended) c.size = null;
    if (k === "pv") c.quantity = c.size ? Math.round((c.size * 1000) / (MODULE_KWP * 1000)) : undefined; // same module rule as above
    c.reasons = ["set by planner", ...c.reasons].slice(0, 3);
  }

  const items: Design["price"]["items"] = [];
  const add = (label: string, qty: number, unit: string, unit_price_eur: number) => items.push({ label, qty, unit, unit_price_eur, total_eur: Math.round(qty * unit_price_eur) });
  const p = { ...DEFAULT_PRICES, ...prices };
  const pvKwp = components.pv.recommended ? components.pv.size ?? 0 : 0;
  const battSize = components.battery.recommended ? components.battery.size ?? 0 : 0;
  if (pvKwp) {
    add("Solar modules, mounting and roof installation", pvKwp, "kWp", p.pv_per_kwp);
    const inv = inverterFor(pvKwp);
    add(inv.label, inv.qty, "pc", inv.unit_price_eur);
  }
  if (battSize) { add("Battery storage", battSize, "kWh", p.battery_per_kwh); add("Battery inverter, BMS and installation", 1, "pc", p.battery_base); }
  if (components.heatpump.recommended && components.heatpump.size) add(`Air-water heat pump ${components.heatpump.size} kW incl. installation`, 1, "pc", p.heatpump_base + p.heatpump_per_kw * components.heatpump.size);
  if (components.wallbox.recommended) add("Wallbox 11 kW incl. installation", 1, "pc", p.wallbox);
  add("Grid connection, commissioning and scaffolding", 1, "pc", p.installation);
  const total_eur = items.reduce((sum, i) => sum + i.total_eur, 0);
  const solarEur = items.filter((i) => !/heat pump|wallbox/i.test(i.label)).reduce((sum, i) => sum + i.total_eur, 0); // ROI = solar + battery only, as in the engine

  // economics, fitted to the engine's outputs for the demo path
  const hpOn = components.heatpump.recommended && !!components.heatpump.size;
  const load = stated + evKwh + (hpOn ? Math.round(heatKwh / 3.3) : 0);
  const pvKwh = pvKwp * YIELD_KWH_PER_KWP;
  const share = 0.3 + 0.012 * battSize + (hpOn ? 0.05 : 0);
  const selfKwh = Math.min(pvKwh * share, load * 0.42);
  const exportKwh = pvKwh - selfKwh;
  const savings = Math.round(selfKwh * 0.34 + exportKwh * 0.06);
  const tariff = hpOn ? 0.3695 : 0.3193; // EUR per kWh, incl. the standing charge, as the engine's bills imply
  const spreadLo = 0.046 + 0.01 * hi + 0.005 * med;
  const spreadHi = 0.064 + 0.012 * hi + 0.006 * med;
  return {
    components,
    price: { items, total_eur, range_eur: [Math.round((total_eur * (1 - spreadLo)) / 10) * 10, Math.round((total_eur * (1 + spreadHi)) / 10) * 10] },
    economics: {
      total_demand_kwh: load,
      self_consumption_pct: pvKwh > 0 ? Math.round((selfKwh / pvKwh) * 100) : 0,
      autarky_pct: Math.round((selfKwh / load) * 100),
      annual_savings_eur: savings,
      payback_years: savings > 0 ? Math.round((solarEur / savings) * 10) / 10 : null,
      bill_today_eur_per_month: Math.round((load * tariff) / 12),
      bill_after_eur_per_month: Math.round(((load - selfKwh) * tariff - exportKwh * 0.09) / 12),
    },
    heating_comparison: heatingComparison(f, heatKwh),
    assumptions,
    missing_inputs: missing,
    params_version: "mock-1",
  };
}

// --- conversation (follows experience/flow.md) --------------------------------------------------

function extract(text: string): Partial<HomeFacts> {
  const t = text.toLowerCase().replace(/(\d)[.,](\d{3})/g, "$1$2");
  const f: Partial<HomeFacts> = {};
  const kwh = t.match(/(\d{3,6})\s*kwh/);
  if (kwh) f.total_demand_kwh = Number(kwh[1]);
  const ppl = t.match(/(\d+)\s*(people|persons|of us)/);
  if (ppl) f.num_inhabitants = Number(ppl[1]);
  const roof = t.match(/(\d{2,3})\s*(m²|m2|sqm|square)/);
  if (roof) f.roof_area_sqm = Number(roof[1]);
  for (const h of ["gas", "oil", "district", "electric"] as const) if (t.includes(h) && !t.includes("electric car")) f.heating_type = h;
  if (t.includes("heat pump already") || t.includes("we have a heat pump")) f.heating_type = "heatpump";
  if (/(electric car|ev\b|e-auto)/.test(t)) {
    if (/(next year|planned|plan|buying|will get|soon)/.test(t)) f.ev_planned = true;
    else if (/(no |don't|dont)/.test(t)) { f.has_ev = false; f.ev_planned = false; }
    else f.has_ev = true;
  }
  if (t === "yes, already") f.has_ev = true;
  if (t === "planned") f.ev_planned = true;
  if (t === "no") { f.has_ev = false; f.ev_planned = false; }
  return f;
}

const QUESTIONS: { field: keyof HomeFacts; done: (f: HomeFacts) => boolean; ask: Ask; chips: string[]; say: string }[] = [
  { field: "total_demand_kwh", done: (f) => f.total_demand_kwh !== undefined || f.num_inhabitants !== undefined || f.annual_demand_kwh !== undefined, ask: { field: "total_demand_kwh", prompt: "Yearly electricity use (kWh, from your bill)", input: "number" }, chips: ["Don't know"], say: "What is your yearly electricity use in kWh? You can find it on your bill. Or skip, and tell me how many people live at home." },
  { field: "num_inhabitants", done: (f) => f.total_demand_kwh !== undefined || f.num_inhabitants !== undefined || f.annual_demand_kwh !== undefined, ask: { field: "num_inhabitants", prompt: "People in your home", input: "choice", options: ["1", "2", "3", "4", "5+"] }, chips: [], say: "How many people live in your home?" },
  { field: "roof_area_sqm", done: (f) => f.roof_area_sqm !== undefined, ask: { field: "roof_area_sqm", prompt: "Roof area facing the sun (m²) or your address", input: "address" }, chips: ["Enter width × length", "Skip"], say: "How big is the roof area that faces the sun? Or give me your address and I'll look it up." },
  { field: "has_ev", done: (f) => f.has_ev !== undefined || f.ev_planned !== undefined, ask: { field: "has_ev", prompt: "Electric car?", input: "choice", options: ["Yes, already", "Planned", "No"] }, chips: ["Yes, already", "Planned", "No"], say: "Do you have an electric car, or plan to get one? It changes the solar size and adds a wallbox." },
  { field: "heating_type", done: (f) => !!f.heating_type, ask: { field: "heating_type", prompt: "How do you heat today?", input: "choice", options: ["gas", "oil", "heatpump", "electric", "district", "other"] }, chips: ["Gas", "Oil", "Heat pump already", "Other"], say: "How do you heat your home today? That decides whether a heat pump makes sense." },
];

function msg(text: string): Message {
  return { role: "reo", text, at: now() };
}

const eur = (n: number) => "€" + (Math.round(n / 100) * 100).toLocaleString("en");

function headline(d: Design) {
  const c = d.components;
  const parts = [`about ${c.pv.size} kWp of solar (around ${c.pv.quantity} panels)`];
  if (c.battery.recommended) parts.push(`a ${c.battery.size} kWh battery`);
  if (c.heatpump.recommended) parts.push(`a ${c.heatpump.size} kW heat pump`);
  if (c.wallbox.recommended) parts.push("an 11 kW wallbox");
  const list = parts.length > 1 ? parts.slice(0, -1).join(", ") + " and " + parts.at(-1) : parts[0];
  return `I'd suggest ${list}. That would cost roughly ${eur(d.price.range_eur[0])}–${eur(d.price.range_eur[1]).slice(1)} (estimate).`;
}

function nextTurn(plan: Plan, skipped: Set<string>, prefix: string[]): Turn {
  const q = QUESTIONS.find((q) => !q.done(plan.facts) && !skipped.has(q.field));
  const ready = (plan.facts.heating_type && (plan.facts.has_ev !== undefined || plan.facts.ev_planned !== undefined)) || !q;
  const texts = [...prefix];
  let suggestions: string[];
  let ask: Ask | undefined;
  if (q && !ready) {
    texts.push(q.say);
    suggestions = q.chips;
    ask = q.ask;
  } else if (q) {
    texts.push("This plan looks solid. Shall I send it to Sonnfeld? A planner will check it and send you a final quote. You're not committing to anything. Or tell me your roof size to firm it up.");
    suggestions = ["Yes, send it", ...q.chips.slice(0, 2), "Why this size?"];
  } else {
    texts.push("This plan looks solid. Shall I send it to Sonnfeld? A planner will check it and send you a final quote. You're not committing to anything.");
    suggestions = ["Yes, send it", "Why this size?", "What does it cost?"];
  }
  const messages = [msg(texts.join(" "))];
  plan.transcript.push(...messages);
  return { messages, plan: save(plan), suggestions, ask };
}

const skippedBySession: Record<string, Set<string>> = {};

function applyFacts(plan: Plan, facts: Partial<HomeFacts>, trigger: string): string[] {
  const before = plan.design;
  plan.facts = { ...plan.facts, ...facts };
  if (facts.roof_width_m && facts.roof_length_m) plan.facts.roof_area_sqm = facts.roof_width_m * facts.roof_length_m;
  plan.design = design(plan.facts);
  plan.history.push({ at: now(), trigger, total_eur: plan.design.price.total_eur });
  const c = plan.design.components;
  const changes: string[] = [];
  if (before.components.wallbox.recommended !== c.wallbox.recommended && c.wallbox.recommended) changes.push("added an 11 kW wallbox");
  if (before.components.heatpump.recommended !== c.heatpump.recommended && c.heatpump.recommended) changes.push(`added a ${c.heatpump.size} kW heat pump`);
  if (before.components.pv.size !== c.pv.size) changes.push(`${(c.pv.size ?? 0) > (before.components.pv.size ?? 0) ? "raised" : "lowered"} the solar to about ${c.pv.size} kWp`);
  return changes;
}

function answerWhy(plan: Plan, text: string): string | null {
  const t = text.toLowerCase();
  if (!/(why|how come|what does it cost|cost|price)/.test(t)) return null;
  const c = plan.design.components;
  const because = (rs: string[]) => rs.filter((r) => r !== "set by planner").join("; ") + (rs.includes("set by planner") ? " (size set by the planner)" : "");
  if (t.includes("battery")) return c.battery.recommended ? `A ${c.battery.size} kWh battery: ${because(c.battery.reasons)}.` : `No battery for now: ${c.battery.reasons[0]}.`;
  if (t.includes("heat pump")) return c.heatpump.recommended ? `The heat pump ${c.heatpump.reasons.join("; ")}.` : `No heat pump: ${c.heatpump.reasons[0]}.`;
  if (/(cost|price|expensive)/.test(t)) {
    const top = [...plan.design.price.items].sort((a, b) => b.total_eur - a.total_eur).slice(0, 2);
    return `Most of the cost is ${top.map((i) => `the ${i.label.toLowerCase()} (about ${eur(i.total_eur)})`).join(" and ")}. All prices are estimates until your planner confirms them.`;
  }
  return `About ${c.pv.size} kWp because of ${c.pv.reasons.join(", ")}.`;
}

export const mockApi: Api = {
  async startSession() {
    const id = "mock-" + Math.random().toString(36).slice(2, 8);
    const plan: Plan = {
      id, status: "drafting", customer: {}, facts: {}, design: design({}), transcript: [], flags: [],
      installer_edits: [], history: [], updated_at: now(),
    };
    skippedBySession[id] = new Set();
    const q0 = QUESTIONS[0];
    const messages = [msg(`Hi, I'm the energy advisor at Sonnfeld. A few taps and I'll sketch your solar system with a price estimate. ${q0.say}`)];
    plan.transcript.push(...messages);
    return delay({ messages, plan: save(plan), suggestions: q0.chips, ask: q0.ask });
  },

  async sendMessage(id, text) {
    // like reo f358828: an address typed while the roof ask is open runs the roof lookup
    if (get(id).facts.roof_area_sqm === undefined && /\D{3,}\s\d+\w?\s*,/.test(text)) return mockApi.sendAddress(id, text);
    const plan = get(id);
    plan.transcript.push({ role: "customer", text, at: now() });
    const skipped = (skippedBySession[id] ??= new Set());
    const t = text.toLowerCase();

    if (/^(yes, send it|send it|send to installer)/.test(t)) {
      const messages = [msg("Great, just add your name (and email if you like) below.")];
      plan.transcript.push(...messages);
      return delay({ messages, plan: save(plan), suggestions: [] });
    }
    if (t === "i know my yearly kwh") {
      const messages = [msg("Great, that's the most precise. What does your bill say per year?")];
      plan.transcript.push(...messages);
      return delay({ messages, plan: save(plan), suggestions: ["About 3,000 kWh", "About 4,500 kWh"], ask: { field: "total_demand_kwh", prompt: "Yearly electricity use (kWh, from your bill)", input: "number" } });
    }
    if (t === "enter width × length") {
      const messages = [msg("Enter the width and length of the sunny roof area in metres.")];
      plan.transcript.push(...messages);
      return delay({ messages, plan: save(plan), suggestions: ["Skip"], ask: { field: "roof_area_sqm", prompt: "Sunny roof dimensions", input: "dimensions" } });
    }
    const why = answerWhy(plan, text);
    if (why) {
      const messages = [msg(why)];
      plan.transcript.push(...messages);
      return delay({ messages, plan: save(plan), suggestions: ["Send to installer", "What does it cost?"] });
    }
    if (/not sure|skip|don't know/.test(t)) {
      const q = QUESTIONS.find((q) => !q.done(plan.facts) && !skipped.has(q.field));
      if (q) skipped.add(q.field);
      return delay(nextTurn(plan, skipped, ["No problem, I'll work with a typical value for now."]));
    }
    const facts = extract(text);
    if (Object.keys(facts).length === 0) {
      const messages = [msg("I'm only here to help with your home's energy plan. Could you tell me a bit more about your home, for example your yearly electricity use?")];
      plan.transcript.push(...messages);
      return delay({ messages, plan: save(plan), suggestions: ["About 4,500 kWh", "4 people"] });
    }
    return delay(respondToFacts(plan, facts, text, skipped));
  },

  async sendFacts(id, facts, skip = []) {
    const plan = get(id);
    const skipped = (skippedBySession[id] ??= new Set());
    skip.forEach((f) => skipped.add(f));
    return delay(respondToFacts(plan, facts, "facts", skipped));
  },

  async sendBill(id, _image) {
    const plan = get(id);
    const read = { total_demand_kwh: 4500, electricity_price_eur_per_kwh: 0.34, provider: "Demo supplier" };
    const messages = [msg("I read the yearly use and tariff from your bill. Please check these before I add them to your plan.")];
    plan.transcript.push(...messages);
    return delay({ messages, plan: save(plan), suggestions: ["Yes, that's right", "Not quite"], bill: { read, confirmed: false } });
  },

  async suggestAddress(_id, q) {
    const demo = ["Musterstraße 12, 80331 München", "Hauptstraße 5, 20095 Hamburg"];
    return delay({ suggestions: q.trim().length < 3 ? [] : demo.filter((a) => a.toLowerCase().includes(q.trim().toLowerCase().slice(0, 5))).map((label) => ({ label })) });
  },

  async sendAddress(id, address) {
    const plan = get(id);
    const known = /musterstra|hauptstra/i.test(address);
    if (!known) {
      const messages = [msg("I can't find that roof in the demo lookup. Enter the sunny roof width and length, or skip.")];
      plan.transcript.push(...messages);
      return delay({ messages, plan: save(plan), suggestions: ["Skip"], ask: { field: "roof_area_sqm", prompt: "Sunny roof dimensions", input: "dimensions" } });
    }
    const turn = respondToFacts(plan, { roof_area_sqm: 48, roof_orientation_deg: 180, roof_tilt_deg: 35 }, `address: ${address}`, (skippedBySession[id] ??= new Set()));
    return delay({ ...turn, roof: { source: "demo data", label: address } });
  },

  async handoff(id, name, email) {
    const plan = get(id);
    plan.status = "handed_over";
    plan.customer = { name, email };
    plan.flags = plan.design.components.battery.recommended && (plan.design.components.battery.size ?? 0) >= 10
      ? [{ component: "battery", text: "Battery larger than 85% of similar homes (mock)", severity: "warn" }]
      : [];
    const d = plan.facts.total_demand_kwh ?? 4500;
    plan.transcript.push(msg(`Done. Your plan is with Sonnfeld, ${name}. You'll see the final quote here once your planner has confirmed it.`));
    startPrep(plan);
    return delay(save(plan));
  },

  async getSession(id) { return delay(get(id)); },

  async listPlans(status) {
    return delay(Object.values(load())
      .filter((p) => !status || p.status === status)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map((p) => ({ id: p.id, customer: p.customer, status: p.status, updated_at: p.updated_at, total_eur: p.design.price.total_eur })));
  },

  async getPlan(id) { return delay(advancePrep(get(id))); },

  async putLayout() { throw new Error("Module placement needs the reo backend (not available in the offline demo)"); },
  async resetLayout() { throw new Error("Module placement needs the reo backend (not available in the offline demo)"); },

  async editPlan(id, edit) {
    const plan = get(id);
    const before = plan.design.price.total_eur;
    if (edit.facts) plan.facts = { ...plan.facts, ...edit.facts };
    const locks: Locks = {};
    for (const [k, c] of Object.entries(plan.design.components)) if (c.locked) locks[k as keyof Locks] = { recommended: c.recommended, size: c.size ?? undefined };
    Object.assign(locks, edit.locks);
    plan.design = design(plan.facts, locks, edit.prices);
    const what = [
      ...Object.entries(edit.locks ?? {}).map(([k, l]) => (l!.recommended ? `${k} set to ${l!.size ?? "recommended"}` : `${k} removed`)),
      ...Object.entries(edit.facts ?? {}).map(([k, v]) => `${k} = ${v}`),
      ...(edit.prices ? ["prices edited"] : []),
    ].join(", ");
    plan.installer_edits.push({ at: now(), change: what || "no change", before, after: plan.design.price.total_eur });
    plan.history.push({ at: now(), trigger: "installer edit", total_eur: plan.design.price.total_eur });
    return delay(save(plan));
  },

  async askPlanVoice(id) {
    const heard = "Why this battery size?";
    const { answer } = await mockApi.askPlan(id, heard);
    return { heard, answer, audio: null };
  },

  async speak() { return null; },

  async askPlan(id, text) {
    const plan = get(id);
    return delay({ answer: answerWhy(plan, "why " + text) ?? "I don't have a reason recorded for that yet." });
  },

  async finalizePlan(id, note) {
    const plan = get(id);
    plan.status = "quoted";
    plan.transcript.push(msg(`Your planner has confirmed your plan, total ${eur(plan.design.price.total_eur)} (confirmed by Sonnfeld).${note ? " " + note : ""}`));
    return delay(save(plan));
  },

  async preparePlan(id) { const plan = get(id); startPrep(plan); return delay(save(plan)); },

  async chooseVariant(id, name) {
    const plan = advancePrep(get(id));
    const v = plan.offer_pack?.variants.find((x) => x.name === name);
    if (!plan.offer_pack || !v) throw new Error(`mock: no variant ${name}`);
    const before = plan.design.price.total_eur;
    plan.design = design(plan.facts, v.locks);
    plan.offer_pack.chosen = name;
    plan.installer_edits.push({ at: now(), change: `variant ${name}`, before, after: plan.design.price.total_eur });
    plan.history.push({ at: now(), trigger: `variant ${name}`, total_eur: plan.design.price.total_eur });
    return delay(save(plan));
  },

  async approveAction(id, actionId, payload) {
    const plan = advancePrep(get(id));
    const pack = plan.offer_pack;
    const a = pack?.actions.find((x) => x.id === actionId);
    if (!pack || !a || a.status !== "proposed") throw new Error(`mock: action ${actionId} not proposed`);
    a.payload = { ...a.payload, ...payload };
    a.status = "done";
    a.at = now();
    if (a.kind === "book_visit") a.result = `Site visit booked for ${a.payload.slot} (mock calendar)`;
    if (a.kind === "create_crm_task") a.result = "Task created in CRM (mock log)";
    if (a.kind === "request_document") a.result = "Request sent to the customer (mock)";
    if (a.kind === "send_quote") {
      plan.status = "quoted";
      const note = typeof a.payload.message === "string" ? a.payload.message : "";
      plan.transcript.push(msg(`Your planner has confirmed your plan, total ${eur(plan.design.price.total_eur)} (confirmed by Sonnfeld).${note ? " " + note : ""}`));
      a.result = "Quote sent to the customer";
    }
    pack.trace.push({ step: pack.trace.length + 1, tool: a.kind === "book_visit" ? "calendar" : a.kind === "send_quote" ? "quote" : "crm", summary: `approved by planner: ${a.result}` });
    return delay(save(plan));
  },

  async deletePlan(id) {
    const all = load();
    delete all[id];
    try {
      localStorage.setItem(KEY, JSON.stringify(all));
    } catch {
      /* storage blocked: nothing persisted to remove */
    }
    return delay({ deleted: id });
  },

  async rejectAction(id, actionId) {
    const plan = advancePrep(get(id));
    const a = plan.offer_pack?.actions.find((x) => x.id === actionId);
    if (!a || a.status !== "proposed") throw new Error(`mock: action ${actionId} not proposed`);
    a.status = "rejected";
    a.at = now();
    return delay(save(plan));
  },

  async calendarSlots() { return delay({ slots: nextSlots() }); },

  // The mock has no harness runs; the timeline falls back to offer_pack.trace.
  async getRun(runId) { throw new Error(`mock: no run ${runId}`); },
  watchRun() { return () => {}; },


  // Mock voice: no speech-to-text in the browser, so "heard" is the next demo line the plan still needs.
  // shortcut: fake transcript + no audio; the real path is reo -> ElevenLabs (reo/VOICE.md).
  async health() { return delay({ ok: true, llm: false, voice: true, engine: true }); },
  async sendVoice(id) {
    const f = get(id).facts;
    const heard = f.total_demand_kwh === undefined && f.num_inhabitants === undefined ? "We use about 4,500 kWh a year"
      : !f.heating_type ? "We heat with gas"
      : f.has_ev === undefined && f.ev_planned === undefined ? "We're buying an electric car next year"
      : "Why a battery?";
    const turn = await mockApi.sendMessage(id, heard);
    return { ...turn, heard, audio: null };
  },
};

function respondToFacts(plan: Plan, facts: Partial<HomeFacts>, trigger: string, skipped: Set<string>): Turn {
  const first = plan.history.length === 0;
  const changes = applyFacts(plan, facts, trigger);
  const d = plan.design;
  if (first) {
    return nextTurn(plan, skipped, [`For about ${d.economics.total_demand_kwh.toLocaleString("en")} kWh a year, ${headline(d)}`, d.components.battery.recommended ? "The battery lets you use your own solar power in the evening." : "", "To firm this up:"].filter(Boolean));
  }
  const lead = changes.length ? `Got it, so I've ${changes.join(" and ")}. The new estimate is roughly ${eur(d.price.range_eur[0])}–${eur(d.price.range_eur[1]).slice(1)}.` : `Thanks, noted. The estimate is now roughly ${eur(d.price.range_eur[0])}–${eur(d.price.range_eur[1]).slice(1)}.`;
  return nextTurn(plan, skipped, [lead]);
}

// ---- mock offer agent (reo/CONTRACT.md v1.1): scripted pack, ready ~4 s after handoff ----
// shortcut: fixed lock sets like reo's scripted mode; numbers come from the mock design(), not from reo.
function nextSlots(): string[] {
  const out: string[] = [];
  const d = new Date();
  for (let i = 1; out.length < 4; i++) {
    const x = new Date(d.getFullYear(), d.getMonth(), d.getDate() + i);
    if (x.getDay() === 0 || x.getDay() === 6) continue;
    const day = x.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
    out.push(`${day}, ${out.length % 2 ? "14:00" : "09:00"}`);
  }
  return out;
}

function startPrep(plan: Plan) {
  plan.offer_pack = {
    status: "preparing", variants: [], recommended: "Recommended", flags: plan.flags, site_visit_checklist: [], open_questions: [],
    customer_message_draft: "", actions: [], trace: [{ step: 1, tool: "plan.read", summary: "read the handed-over plan" }],
    duration_s: 0, model: "scripted", prepared_at: now(),
  };
}

const PREP_STEPS: [string, string][] = [
  ["plan.read", "read the handed-over plan"],
  ["evidence.similar", "checked 12 similar homes (mock)"],
  ["engine.design", "Basic: smaller battery"],
  ["engine.design", "Recommended: reo's design"],
  ["engine.design", "Independence: bigger PV + battery"],
  ["guard", "numbers verified against engine results"],
];

function advancePrep(plan: Plan): Plan {
  const pack = plan.offer_pack;
  if (!pack || pack.status !== "preparing") return plan;
  const elapsed = (Date.now() - Date.parse(pack.prepared_at)) / 1000;
  pack.trace = PREP_STEPS.slice(0, Math.min(PREP_STEPS.length, 1 + Math.floor(elapsed / 0.7))).map(([tool, summary], i) => ({ step: i + 1, tool, summary }));
  if (elapsed < 4.2) return save(plan);

  const c = plan.design.components;
  const pv = c.pv.size ?? 6;
  const bat = c.battery.recommended ? c.battery.size ?? 8 : 0;
  const variant = (name: VariantName, locks: Locks, why: (d: Design) => string): Variant => {
    const d = design(plan.facts, locks);
    return { name, locks, design: d, why: why(d) };
  };
  const slots = nextSlots();
  Object.assign(pack, {
    status: "ready",
    variants: [
      variant("Basic", { battery: bat > 5 ? { recommended: true, size: 5 } : { recommended: false } },
        (d) => `Lowest price: ${eur(d.price.total_eur)}, ${d.components.battery.recommended ? `${d.components.battery.size} kWh battery` : "no battery"}, payback ~${d.economics.payback_years ?? "-"} yrs.`),
      variant("Recommended", {}, (d) => `reo's design: ${d.components.pv.size} kWp + ${d.components.battery.size ?? 0} kWh, ${d.economics.autarky_pct}% own power, ${eur(d.price.total_eur)}.`),
      variant("Independence", { pv: { recommended: true, size: Math.round(pv * 1.3 * 2) / 2 }, battery: { recommended: true, size: Math.max(10, bat + 3) } },
        (d) => `Most own power: ${d.economics.autarky_pct}% with ${d.components.pv.size} kWp + ${d.components.battery.size} kWh, ${eur(d.price.total_eur)}.`),
    ],
    recommended: "Recommended",
    flags: plan.flags,
    site_visit_checklist: [
      "Check roof condition and usable area",
      "Photo of the meter cabinet",
      "Space for battery and inverter",
      ...(c.wallbox.recommended ? ["Cable route to the wallbox"] : []),
      ...(plan.facts.has_existing_pv ? ["Existing PV: inverter model and age"] : []),
    ],
    open_questions: plan.design.missing_inputs.slice(0, 3).map((m) => `${String(m.field)}: ${m.why}`),
    customer_message_draft: `Hello ${plan.customer.name ?? ""}, thank you for your request. Based on your details we recommend ${pv} kWp of solar${bat ? ` with a ${bat} kWh battery` : ""} for about ${eur(plan.design.price.total_eur)}. We would like to visit to check the roof before confirming the final price.`,
    actions: [
      { id: "a1", kind: "book_visit", label: "Book the site visit", payload: { slot: slots[0] }, status: "proposed" },
      { id: "a2", kind: "request_document", label: "Ask for a photo of the electricity bill", payload: {}, status: "proposed" },
      { id: "a3", kind: "create_crm_task", label: "Create CRM task: follow up in 3 days", payload: {}, status: "proposed" },
      { id: "a4", kind: "send_quote", label: "Send the quote to the customer", payload: {}, status: "proposed" },
    ],
    duration_s: 4.2,
  });
  return save(plan);
}
