import { useState } from "react";
import type { HomeFacts, RoofLookup } from "./types";
import "./address.css";

export function AddressLookup({ prompt, busy, onSubmit, onDimensions, onSkip }: {
  prompt: string; busy: boolean; onSubmit: (address: string) => void; onDimensions: () => void; onSkip: () => void;
}) {
  const [address, setAddress] = useState("");
  return <section className="address-lookup" aria-busy={busy}>
    <div className="address-heading"><span aria-hidden>⌖</span><div><strong>Find your roof</strong><p>{prompt}</p></div></div>
    <form onSubmit={(e) => { e.preventDefault(); if (address.trim() && !busy) onSubmit(address.trim()); }}>
      <label htmlFor="roof-address">Street, house number, postcode and city</label>
      <div className="address-search"><input id="roof-address" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Musterstraße 12, 80331 München" autoComplete="street-address" required disabled={busy} /><button className="btn-primary" type="submit" disabled={busy || !address.trim()}>{busy ? "Looking up…" : "Find roof"}</button></div>
      <p className="address-note">We use OpenStreetMap to estimate the sunny roof area. Your planner checks it before the final quote.</p>
    </form>
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
