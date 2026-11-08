import { COMPONENT_KEYS, isOffline, type ComponentKey, type Plan } from "./types";
import { House } from "./House";
import { Satellite } from "./Satellite";
import { lazy, Suspense, useEffect, useState } from "react";

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
import type { Topic } from "./live/narrate";

const NAMES: Record<ComponentKey, string> = { pv: "Solar panels", battery: "Battery", heatpump: "Heat pump", wallbox: "Wallbox" };
// Display rounding only (persona.md): sizes to 1 decimal, payback to whole years.
const num = (n: number) => String(Math.round(n * 10) / 10);
const eur = (n: number) => "€" + (Math.round(n / 100) * 100).toLocaleString("en");

// Results screen of the step form: components, sizes, price range, savings, payback.
// Displays engine numbers as received (rounded to €100 per experience/persona.md); computes nothing.
export function PlanCard({ plan, onHandoff, onToggleHeatpump, onExplain }: { plan: Plan; onHandoff?: () => void; onToggleHeatpump?: (on: boolean) => void; onExplain?: (t: Topic) => void }) {
  // With onExplain (results screen with the living stage): numbers are buttons, the advisor explains them in the scene,
  // and the house lives in the stage instead of the card.
  const tap = (t: Topic, label: string, node: React.ReactNode) => onExplain
    ? <button type="button" className="explain-btn" onClick={() => onExplain(t)} aria-label={`Why ${label}?`}>{node}</button> : node;
  const d = plan.design;
  const hpToggle = onToggleHeatpump && plan.facts.heating_type != null && plan.facts.heating_type !== "heatpump";
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

  return (
    <aside className="plan" aria-label="Your plan">
      {!onExplain && <HouseView plan={plan} />}
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
            {tap("price", "this price", <>{eur(lo)}–{eur(hi).slice(1)}</>)}
            <small>estimate</small>
          </div>
        )}
      </div>

      <dl className="econ">
        <div><dt>Savings / yr</dt><dd>{tap("savings", "these savings", eur(d.economics.annual_savings_eur))}</dd></div>
        <div><dt>Payback</dt><dd>{tap("payback", "this payback", d.economics.payback_years !== null ? `~${Math.round(d.economics.payback_years)} yrs` : "none")}</dd></div>
        <div><dt>Own power</dt><dd>{tap("autarky", "this share of own power", `${d.economics.autarky_pct}%`)}</dd></div>
      </dl>

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
                <span className="comp-end">
                  <span className="comp-size">
                    {tap(k, NAMES[k].toLowerCase(), <>
                      {c.recommended && c.size !== null ? `${num(c.size)} ${c.unit}` : "not included"}
                      {c.recommended && c.quantity ? <em> · {c.quantity} panels</em> : null}
                    </>)}
                  </span>
                  {k === "heatpump" && hpToggle && (
                    <button type="button" role="switch" aria-checked={c.recommended} aria-label="Heat pump in my plan"
                      className={`switch ${c.recommended ? "is-on" : ""}`} onClick={() => onToggleHeatpump(!c.recommended)}><i /></button>
                  )}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {d.heating_comparison && <HeatingComparison comparison={d.heating_comparison} />}

      {onHandoff && <button className="btn-primary plan-cta" onClick={onHandoff}>Send plan to Sonnfeld</button>}
      {!quoted && <p className="plan-fine">All prices are estimates until your planner confirms the quote.</p>}
    </aside>
  );
}
