import type { Ask, ComponentKey, Design, HomeFacts, Plan, Turn } from "../types";

// What the advisor says and shows while the customer answers. Pure functions, no React.
// Words: reo's own reply first (LLM or scripted, grounded in the engine), engine reasons as fallback.
// Numbers: only from the engine's design in the same turn, rounded for display (persona.md). Computes nothing.

export type Spot = "door" | "roof" | "car" | "heatpump" | "battery";
export type Say = { key: number; spot: Spot; text: string; lines?: string[]; more?: string };
export type TraceStep = { id: string; label: string; state: "run" | "done" | "fail"; detail?: string };
export type Kind = "start" | "usage" | "people" | "address" | "dims" | "ev" | "heating" | "toggle" | "skip" | "other";
export type Topic = "price" | "savings" | "payback" | "autarky" | ComponentKey;

const r1 = (n: number) => String(Math.round(n * 10) / 10);
const eur = (n: number) => "€" + (Math.round(n / 100) * 100).toLocaleString("en");
let seq = 0;
const k = () => ++seq;

/** Which kind of answer this is, from the open ask and the facts sent. */
export function kindOf(ask: Ask | undefined, f: Partial<HomeFacts> & { heatpump_option?: boolean }, skipped?: string[]): Kind {
  if ("heatpump_option" in f) return "toggle";
  if (skipped?.length && !Object.keys(f).length) return "skip";
  const field = String(ask?.field ?? "");
  if (field === "total_demand_kwh") return "usage";
  if (field === "num_inhabitants") return "people";
  if (field === "roof_dims" || "roof_width_m" in f) return "dims";
  if (field === "roof_area_sqm") return "address";
  if (field === "has_ev" || field === "ev_planned") return "ev";
  if (field === "heating_type") return "heating";
  return "other";
}

/** Steps shown while the call runs: what reo and the engine actually do for this kind of answer. */
export function pendingSteps(kind: Kind): TraceStep[] {
  const s = (id: string, label: string): TraceStep => ({ id, label, state: "run" });
  switch (kind) {
    case "address": return [s("roof", "Looking up your roof on the map"), s("size", "Sizing your system")];
    case "dims": return [s("roof", "Measuring your roof"), s("size", "Fitting panels to it")];
    case "ev": return [s("size", "Adding charging for your car")];
    case "heating": return [s("heat", "Comparing your heating with a heat pump"), s("size", "Sizing your system")];
    case "toggle": return [s("size", "Re-calculating your plan")];
    case "start": return [s("start", "Getting ready")];
    default: return [s("size", "Sizing solar and battery with real product prices")];
  }
}

const pvLine = (d: Design) => {
  const pv = d.components.pv, b = d.components.battery;
  if (!pv.recommended || !pv.size) return null;
  return `${r1(pv.size)} kWp${pv.quantity ? ` · ${pv.quantity} panels` : ""}${b.recommended && b.size ? ` · ${r1(b.size)} kWh battery` : ""}`;
};
const similarN = (p: Plan) => {
  for (const f of p.flags) { const m = f.text.match(/n\s*=\s*([\d,]+)/); if (m) return m[1]; }
  return null;
};

/** The finished steps, with the engine's numbers from this turn. */
export function doneSteps(kind: Kind, t: Turn & { roof?: { label: string } }): TraceStep[] {
  const d = t.plan.design, c = d.components, out: TraceStep[] = [];
  const ok = (id: string, label: string, detail?: string): TraceStep => ({ id, label, state: "done", detail });
  if (kind === "address" || kind === "dims") {
    const area = t.plan.facts.roof_area_sqm;
    if (kind === "address" && !t.roof) out.push({ id: "roof", label: "Address not found", state: "fail", detail: "enter the roof size instead" });
    else out.push(ok("roof", "Roof found", area != null ? `about ${Math.round(area)} m²` : undefined));
  }
  if (kind === "heating" && c.heatpump.recommended && c.heatpump.size) out.push(ok("heat", "Heat pump sized", `${r1(c.heatpump.size)} kW`));
  else if (kind === "heating") out.push(ok("heat", "Heating noted"));
  if (kind === "ev") out.push(ok("size", c.wallbox.recommended ? "Wallbox added" : "No wallbox needed", c.wallbox.recommended && c.wallbox.size ? `${r1(c.wallbox.size)} kW` : undefined));
  else if (kind !== "start") {
    const line = pvLine(d);
    if (line) out.push(ok("size", "Engine sized your system", line));
  }
  const n = similarN(t.plan);
  if (n && kind !== "start") out.push(ok("similar", "Checked against similar homes", `${n} real projects`));
  return out;
}

/** One or two sentences from reo's reply, without the follow-up question (the step title asks it). */
export function reoLine(t: Turn): string | null {
  const reply = [...t.messages].reverse().find((m) => m.role === "reo")?.text;
  if (!reply) return null;
  const sentences = reply.replace(/\s+/g, " ").split(/(?<=[.!])\s+(?=[A-ZÄÖÜ€0-9"“])/).map((s) => s.trim()).filter(Boolean);
  const keep: string[] = [];
  for (const s of sentences) {
    if (s.endsWith("?") || /\?\s*$/.test(s)) continue;
    if (keep.join(" ").length + s.length > 170) break;
    keep.push(s);
    if (keep.length === 2) break;
  }
  return keep.length ? keep.join(" ") : null;
}

const spotFor = (kind: Kind, d: Design): Spot => {
  const c = d.components;
  if (kind === "ev") return c.wallbox.recommended ? "car" : "door";
  if (kind === "heating" || kind === "toggle") return c.heatpump.recommended ? "heatpump" : "door";
  if (kind === "start" || kind === "skip" || kind === "other") return c.pv.recommended ? "roof" : "door";
  return c.pv.recommended ? "roof" : "door";
};

/** What the advisor says after this answer, and where it stands. */
export function sayFor(kind: Kind, t: Turn): Say {
  const d = t.plan.design, c = d.components;
  const fromReo = reoLine(t);
  let fallback = "Got it.";
  if (c.pv.recommended && c.pv.reasons[0]) fallback = c.pv.reasons[0];
  if (kind === "ev" && c.wallbox.reasons[0]) fallback = c.wallbox.reasons[0];
  if ((kind === "heating" || kind === "toggle") && c.heatpump.reasons[0]) fallback = c.heatpump.reasons[0];
  return { key: k(), spot: spotFor(kind, d), text: fromReo ?? fallback };
}

export const greeting = (): Say => ({ key: k(), spot: "door", text: "Hi! Tell me a little about your home and I'll build your plan right here." });

const ITEM_SPOT: Partial<Record<Topic, Spot>> = { pv: "roof", battery: "battery", heatpump: "heatpump", wallbox: "car" };
const NAME: Record<ComponentKey, string> = { pv: "solar", battery: "battery", heatpump: "heat pump", wallbox: "wallbox" };

/** Tap-a-number: the engine's own reasons and figures for that number, and a question to ask for more. */
export function explain(topic: Topic, d: Design): Say {
  const e = d.economics;
  if (topic === "price") {
    const top = [...d.price.items].sort((a, b) => b.total_eur - a.total_eur).slice(0, 3);
    return { key: k(), spot: "door", text: `Your estimate is ${eur(d.price.range_eur[0])}–${eur(d.price.range_eur[1]).slice(1)}. The biggest parts:`,
      lines: top.map((i) => `${i.label}: ${eur(i.total_eur)}`), more: "What would make my plan cheaper?" };
  }
  if (topic === "savings") return { key: k(), spot: "roof", text: `About ${eur(e.annual_savings_eur)} a year off your energy costs, estimated from your usage and today's tariffs.`,
    lines: [`You use ${e.self_consumption_pct}% of your own solar power`], more: "How do you calculate my savings?" };
  if (topic === "payback") return { key: k(), spot: "door", text: e.payback_years != null ? `The savings pay the system back in about ${Math.round(e.payback_years)} years.` : "With these savings the system doesn't pay back on its own.",
    more: "How could the payback be shorter?" };
  if (topic === "autarky") return { key: k(), spot: "battery", text: `${e.autarky_pct}% of the power your home uses would come from your own roof${d.components.battery.recommended ? " and battery" : ""}.`,
    more: "How could I be more independent?" };
  const c = d.components[topic];
  const size = c.recommended && c.size != null ? `${r1(c.size)} ${c.unit}${c.quantity ? ` (${c.quantity} panels)` : ""}` : "not in your plan";
  return { key: k(), spot: ITEM_SPOT[topic] ?? "door", text: `Why ${size} of ${NAME[topic]}?`, lines: c.reasons.slice(0, 3),
    more: `Why ${c.recommended ? "this size of" : "no"} ${NAME[topic]}?` };
}
