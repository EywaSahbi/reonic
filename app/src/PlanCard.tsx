import { COMPONENT_KEYS, isOffline, type ComponentKey, type Plan } from "./types";
import { House } from "./House";

const NAMES: Record<ComponentKey, string> = { pv: "Solar panels", battery: "Battery", heatpump: "Heat pump", wallbox: "Wallbox" };
// Display rounding only (persona.md): sizes to 1 decimal, payback to whole years.
const num = (n: number) => String(Math.round(n * 10) / 10);
const eur = (n: number) => "€" + (Math.round(n / 100) * 100).toLocaleString("en");

// Live plan card: components, sizes, price range that narrows as facts arrive, reasons, assumptions.
// Displays engine numbers as received (rounded to €100 per experience/persona.md); computes nothing.
export function PlanCard({ plan, onHandoff }: { plan: Plan; onHandoff?: () => void }) {
  const d = plan.design;
  if (isOffline(d)) {
    return (
      <aside className="plan" aria-label="Your plan">
        <div className="plan-offline">
          <strong>Calculation paused</strong>
          <p>reo can't reach its design engine right now, so there are no sizes or prices yet. Everything you've told reo is saved; the plan appears as soon as the engine is back.</p>
        </div>
      </aside>
    );
  }
  const quoted = plan.status === "quoted";
  const [lo, hi] = d.price.range_eur;
  const spreadPct = d.price.total_eur ? ((hi - lo) / d.price.total_eur) * 100 : 0;
  const prev = plan.history.length > 1 ? plan.history[plan.history.length - 2].total_eur : null;

  return (
    <aside className="plan" aria-label="Your plan">
      <House design={d} />
      <div className="plan-head">
        <span className="plan-kicker">
          {quoted ? "Confirmed quote" : plan.status === "handed_over" ? "With your planner" : "Your plan so far"}
        </span>
        {quoted ? (
          <div className="plan-price">{eur(d.price.total_eur)}<small>confirmed by Sonnfeld</small></div>
        ) : (
          <div className="plan-price" key={`${lo}-${hi}`}>
            {eur(lo)}–{eur(hi).slice(1)}
            <small>estimate{prev !== null && prev !== d.price.total_eur ? ` · was about ${eur(prev)}` : ""}</small>
          </div>
        )}
        {!quoted && (
          <div className="precision" title="The bar fills as reo learns more about your home">
            <span style={{ transform: `scaleX(${Math.min(100, Math.max(10, 100 - spreadPct * 2)) / 100})` }} />
          </div>
        )}
      </div>

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
