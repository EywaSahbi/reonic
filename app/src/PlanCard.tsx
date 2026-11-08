import { COMPONENT_KEYS, isOffline, type ComponentKey, type HomeFacts, type Plan } from "./types";
import { House } from "./House";
import { Satellite } from "./Satellite";
import { lazy, Suspense, useEffect, useRef, useState } from "react";

const House3D = lazy(() => import("./scene/House3D"));
let gl: boolean | null = null;
const webglOk = () => {
  if (gl === null) { try { const c = document.createElement("canvas"); gl = !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { gl = false; } }
  return gl;
};

/** 3D house (engine design drawn on the roof); once an address was found, the satellite photo of the customer's
 *  building replaces it (EywaSahbi), with the 3D plan one tab away. */
function HouseView({ plan }: { plan: Plan }) {
  const label = plan.roof_location?.label;
  const [view, setView] = useState<"3d" | "photo">(label ? "photo" : "3d");
  useEffect(() => { if (label) setView("photo"); }, [label]); // a new address switches to its photo
  const design = plan.design; // reo builds it up with the answers: empty house first, filled as facts arrive
  const flat = <House design={design} />;
  const three = webglOk() ? <Suspense fallback={flat}><House3D design={design} facts={plan.facts} /></Suspense> : flat;
  if (!plan.roof_location) return three;
  return (
    <div className="house-views">
      {view === "3d" ? three : <Satellite loc={plan.roof_location} fallback={flat} />}
      <div className="house-toggle" role="tablist" aria-label="House view">
        <button role="tab" aria-selected={view === "photo"} onClick={() => setView("photo")}>Your roof</button>
        <button role="tab" aria-selected={view === "3d"} onClick={() => setView("3d")}>3D plan</button>
      </div>
    </div>
  );
}
import { HeatingComparison } from "./HeatingComparison";

const NAMES: Record<ComponentKey, string> = { pv: "Solar panels", battery: "Battery", heatpump: "Heat pump", wallbox: "Wallbox" };
// Display rounding only (persona.md): sizes to 1 decimal, payback to whole years.
const num = (n: number) => String(Math.round(n * 10) / 10);
const eur = (n: number) => "€" + (Math.round(n / 100) * 100).toLocaleString("en");

// Live plan card: components, sizes, price range that narrows as facts arrive, reasons, assumptions.
// Displays engine numbers as received (rounded to €100 per experience/persona.md); computes nothing.
// The inputs the customer can give, as groups of facts (any one fact of a group counts). The precision bar is
// answered / INPUTS.length: deterministic, and it only moves forward (kept per plan in a ref).
const INPUTS: [string, (keyof HomeFacts)[]][] = [
  ["yearly use", ["total_demand_kwh", "annual_demand_kwh", "num_inhabitants"]],
  ["roof size", ["roof_area_sqm", "roof_width_m"]],
  ["state", ["region"]],
  ["roof direction", ["roof_orientation_deg"]],
  ["electric car", ["has_ev", "ev_planned"]],
  ["heating", ["heating_type"]],
  ["heat demand", ["heating_demand_kwh", "house_size_sqm"]],
  ["existing solar", ["has_existing_pv"]],
  ["electricity price", ["electricity_price_eur_per_kwh"]],
];

export function PlanCard({ plan, onHandoff }: { plan: Plan; onHandoff?: () => void }) {
  const reached = useRef<{ id: string; n: number }>({ id: plan.id, n: 0 });
  const d = plan.design;
  if (isOffline(d)) {
    return (
      <aside className="plan" aria-label="Your plan">
        <div className="plan-offline">
          <strong>Calculation paused</strong>
          <p>We can't calculate your plan right now, so there are no sizes or prices yet. Everything you've told us is saved; the plan appears as soon as the calculation is back.</p>
        </div>
      </aside>
    );
  }
  const quoted = plan.status === "quoted";
  const [lo, hi] = d.price.range_eur;
  const answered = INPUTS.filter(([, keys]) => keys.some((k) => plan.facts[k] != null)).length;
  if (reached.current.id !== plan.id) reached.current = { id: plan.id, n: 0 };
  reached.current.n = Math.max(reached.current.n, answered);            // never moves back
  const given = reached.current.n;
  const prev = plan.history.length > 1 ? plan.history[plan.history.length - 2].total_eur : null;

  return (
    <aside className="plan" aria-label="Your plan">
      <HouseView plan={plan} />
      <div className="plan-head">
        <span className="plan-kicker">
          {quoted ? "Confirmed quote" : plan.status === "handed_over" ? "With your planner" : "Your cost estimate"}
        </span>
        {quoted ? (
          <div className="plan-price">{eur(d.price.total_eur)}<small>confirmed by Sonnfeld</small></div>
        ) : d.price.total_eur === 0 ? (
          <div className="plan-price plan-price-empty">–<small>your plan builds up as you answer</small></div>
        ) : (
          <div className="plan-price" key={`${lo}-${hi}`}>
            {eur(lo)}–{eur(hi).slice(1)}
            <small>estimate{prev && prev !== d.price.total_eur ? ` · was about ${eur(prev)}` : ""}</small>
          </div>
        )}
        {!quoted && (<>
          <div className="precision" role="progressbar" aria-valuemin={0} aria-valuemax={INPUTS.length} aria-valuenow={given}>
            <span style={{ transform: `scaleX(${Math.max(0.04, given / INPUTS.length)})` }} />
          </div>
          <p className="precision-note">Every answer you add narrows the range.</p>
        </>)}
      </div>

      {d.price.items.length > 0 && (
        <details className="price-lines">
          <summary>Price breakdown</summary>
          <ul>
            {d.price.items.map((i) => (
              <li key={i.label}><span>{i.label}{i.unit === "pc" && i.qty > 1 ? ` × ${i.qty}` : ""}</span><b>{eur(i.total_eur)}</b></li>
            ))}
          </ul>
          <small>{quoted ? "Confirmed by Sonnfeld" : "Estimates; your planner confirms the final price"}</small>
        </details>
      )}

      <ul className="components">
        {COMPONENT_KEYS.map((k) => {
          const c = d.components[k];
          return (
            <li key={k} className={c.recommended ? "on" : "off"}>
              <div className="comp-row">
                <span className="comp-name">{NAMES[k]}</span>
                <span className="comp-size">
                  {c.recommended && c.size !== null ? `${num(c.size)} ${c.unit}` : "not needed"}
                  {c.recommended && c.quantity ? <em> · {c.quantity} panels</em> : null}
                </span>
              </div>
              {c.reasons[0] && <p className="comp-reason">{c.reasons[0]}</p>}
              {c.recommended && <span className={`conf conf-${c.confidence}`}>{c.confidence} confidence</span>}
            </li>
          );
        })}
      </ul>

      <dl className="econ">
        <div><dt>Savings / yr</dt><dd>{eur(d.economics.annual_savings_eur)}</dd></div>
        <div><dt>Payback</dt><dd>{d.economics.payback_years !== null ? `~${Math.round(d.economics.payback_years)} yrs` : "none"}</dd></div>
        <div><dt>Own power</dt><dd>{d.economics.autarky_pct}%</dd></div>
      </dl>

      {d.heating_comparison && <HeatingComparison comparison={d.heating_comparison} />}

      {d.assumptions.length > 0 && !quoted && (
        <div className="assumptions">
          <span>Assumed for now</span>
          <ul>{d.assumptions.map((a) => <li key={String(a.field)}>{a.note}</li>)}</ul>
        </div>
      )}

      {onHandoff && <button className="btn-primary plan-cta" onClick={onHandoff}>Send to installer</button>}
      {!quoted && <p className="plan-fine">All prices are estimates until your planner confirms the quote.</p>}
    </aside>
  );
}
