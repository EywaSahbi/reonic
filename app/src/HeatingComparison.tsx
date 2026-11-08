import type { HeatingComparison as Comparison } from "./types";
const money = (n: number) => `€${Math.round(n).toLocaleString("en")}`;
export function HeatingComparison({ comparison: c }: { comparison: Comparison }) {
  return <section className="heating-comparison" aria-label="Estimated heating comparison">
    <h4>Could a heat pump suit your home?</h4>
    <p>{c.heatpump_cheaper ? "The engine estimates lower running costs with a heat pump." : "The engine does not estimate lower running costs on grid electricity."}</p>
    <dl><div><dt>Current heating · {c.fuel}</dt><dd>{money(c.cost_now_eur_per_year)} / year</dd></div><div><dt>Heat pump · grid electricity</dt><dd>{money(c.cost_heatpump_eur_per_year)} / year</dd></div></dl>
    {c.fuel === "electric" ? (
      // direct electric heating vs heat pump on the same tariff: heat from 1 kWh of electricity (engine efficiency_now and cop)
      <div className="heat-per-kwh" aria-label="Heat from 1 kWh of electricity">
        <span className="heat-per-kwh-label">Heat from 1 kWh of electricity</span>
        {([["Electric heating", c.efficiency_now], ["Heat pump", c.cop]] as const).map(([name, kwh]) => (
          <div key={name} className="heat-bar"><span>{name}</span><i style={{ width: `${(kwh / c.cop) * 100}%` }} /><b>{kwh.toFixed(1)} kWh</b></div>
        ))}
      </div>
    ) : c.energy_factor > 0 && <p>Estimated heat per unit of purchased energy: {c.energy_factor.toFixed(1)}× the current system. This is an efficiency comparison, not a cost saving.</p>}
    {c.co2_reduction_pct == null ? <p>CO₂ comparison unavailable for this heating source.</p> : <p>{c.co2_reduction_pct > 0 ? `Estimated CO₂ reduction: ${Math.round(c.co2_reduction_pct)}%.` : "No CO₂ reduction is estimated with the current assumptions."}</p>}
  </section>;
}
