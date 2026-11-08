import type { HeatpumpOption } from "./types";

const eur = (n: number) => "€" + (Math.round(n / 100) * 100).toLocaleString("en");
const num = (n: number | null) => String(Math.round((n ?? 0) * 10) / 10);

// Between-step for non-electric heating: the plan stays as it is, the heat pump version sits next to it.
// Numbers are the engine's, rounded for display only; prices are estimates.
export function HeatpumpOptionCard({ option }: { option: HeatpumpOption }) {
  const cols: [string, HeatpumpOption["without"], string][] = [["Your plan", option.without, "without"], ["With a heat pump", option.with, "with"]];
  return (
    <section className="hp-option" aria-label="Heat pump option">
      <div className="hp-option-cols">
        {cols.map(([title, d, key]) => {
          const c = d.components;
          return (
            <div key={key} className={`hp-option-col ${key === "with" ? "is-option" : ""}`}>
              <strong>{title}</strong>
              <div className="hp-option-price">{eur(d.price.range_eur[0])}–{eur(d.price.range_eur[1]).slice(1)}<small>estimate</small></div>
              <dl>
                <div><dt>Solar</dt><dd>{c.pv.recommended ? `${num(c.pv.size)} kWp` : "–"}</dd></div>
                <div><dt>Battery</dt><dd>{c.battery.recommended ? `${num(c.battery.size)} kWh` : "–"}</dd></div>
                <div><dt>Heat pump</dt><dd>{c.heatpump.recommended ? `${num(c.heatpump.size)} kW` : "–"}</dd></div>
                <div><dt>Savings / yr</dt><dd>{eur(d.economics.annual_savings_eur)}</dd></div>
                <div><dt>Payback</dt><dd>{d.economics.payback_years == null ? "–" : `~${Math.round(d.economics.payback_years)} yrs`}</dd></div>
              </dl>
            </div>
          );
        })}
      </div>
    </section>
  );
}
