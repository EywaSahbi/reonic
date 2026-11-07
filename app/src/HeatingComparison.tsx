import type { HeatingComparison as Comparison } from "./types";
const money = (n: number) => `€${Math.round(n).toLocaleString("en")}`;
export function HeatingComparison({ comparison: c }: { comparison: Comparison }) {
  return <section className="heating-comparison" aria-label="Estimated heating comparison">
    <h4>Could a heat pump suit your home?</h4>
    <p>{c.heatpump_cheaper ? "The engine estimates lower running costs with a heat pump." : "The engine does not estimate lower running costs on grid electricity."}</p>
    <dl><div><dt>Current heating · {c.fuel}</dt><dd>{money(c.cost_now_eur_per_year)} / year</dd></div><div><dt>Heat pump · grid electricity</dt><dd>{money(c.cost_heatpump_eur_per_year)} / year</dd></div></dl>
    {c.energy_factor > 0 && <p>Estimated heat per unit of purchased energy: {c.energy_factor.toFixed(1)}× the current system. This is an efficiency comparison, not a cost saving.</p>}
    {c.co2_reduction_pct == null ? <p>CO₂ comparison unavailable for this heating source.</p> : <p>{c.co2_reduction_pct > 0 ? `Estimated CO₂ reduction: ${Math.round(c.co2_reduction_pct)}%.` : "No CO₂ reduction is estimated with the current assumptions."}</p>}
    {c.note && <p className="muted">{c.note}</p>}
    <small>Estimates use the engine's heat demand, tariff and efficiency assumptions. Installation costs and solar effects are separate; your planner checks suitability.</small>
  </section>;
}
