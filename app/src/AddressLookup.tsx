import type { HomeFacts, RoofLookup } from "./types";
import "./address.css";

// The address itself is typed or spoken in the normal composer; reo runs the roof lookup while this ask is open (reo f358828).
export function AddressLookup({ prompt, busy, onDimensions, onSkip }: {
  prompt: string; busy: boolean; onSubmit?: (address: string) => void; onDimensions: () => void; onSkip: () => void;
}) {
  return <section className="address-lookup" aria-busy={busy}>
    <div className="address-heading"><span aria-hidden>⌖</span><div><strong>Find your roof</strong><p>{prompt}</p></div></div>
    <p className="address-note">Type or say your address below. We use OpenStreetMap to estimate the sunny roof area; your planner checks it before the final quote.</p>
    <div className="address-alternatives"><button type="button" disabled={busy} onClick={onDimensions}>Enter roof dimensions</button><button type="button" disabled={busy} onClick={onSkip}>Skip for now</button></div>
  </section>;
}

export type RoofResult = { roof: RoofLookup; facts: HomeFacts };
const area = (n: number) => `${new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(n)} m²`;
export function RoofResultCard({ result, onChange }: { result: RoofResult; onChange?: () => void }) {
  const { roof, facts } = result;
  return <section className="roof-result" aria-label="Roof lookup result">
    <div className="roof-result-heading"><span className="roof-found">Roof estimate found</span><span className="roof-source">{roof.source === "demo data" ? "Demo address" : "OpenStreetMap"}</span></div>
    <strong className="roof-address">{roof.label}</strong>
    <dl>{facts.roof_area_sqm != null && <div><dt>Estimated sunny roof</dt><dd>{area(facts.roof_area_sqm)}</dd></div>}{roof.footprint_sqm != null && <div><dt>Building footprint</dt><dd>{area(roof.footprint_sqm)}</dd></div>}{facts.roof_tilt_deg != null && <div><dt>Roof tilt</dt><dd>{facts.roof_tilt_deg}°</dd></div>}</dl>
    <p>Map-based estimate, not a roof survey. Shading and usable space still need to be checked on site.</p>
    {onChange && <button type="button" className="btn-ghost small" onClick={onChange}>Change address or dimensions</button>}
  </section>;
}
