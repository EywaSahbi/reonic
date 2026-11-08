import { useState } from "react";
import { ReoAvatar } from "./ReoAvatar";
import "./installer.css";

export function ReoVestPreview() {
  const [waving, setWaving] = useState(false);
  const [wink, setWink] = useState(0);
  const [still, setStill] = useState(false);
  return <main className="reo-vest-preview">
    <header><p className="muted">Installer edition</p><h1>reo, ready for site</h1>
      <p>Same companion. A little workwear.</p></header>
    <div className="reo-vest-sizes">
      {[40, 96, 160].map((size) => <figure key={size}>
        <ReoAvatar size={size} outfit="vest" waving={!still && waving} winkKey={wink} still={still} greet={false} />
        <figcaption>{size} px</figcaption>
      </figure>)}
    </div>
    <div className="reo-vest-controls">
      <button className="btn-ghost" disabled={still} aria-pressed={waving} onClick={() => setWaving(!waving)}>Wave</button>
      <button className="btn-ghost" disabled={still} onClick={() => setWink((n) => n + 1)}>Wink</button>
      <button className="btn-ghost" aria-pressed={still} onClick={() => setStill(!still)}>{still ? "Resume motion" : "Pause motion"}</button>
    </div>
    <p className="muted">Move the pointer to guide the eyes. Hover to wave, click to wink. Reduced-motion preferences are respected.</p>
    <a href="#/installer">Open planner →</a>
  </main>;
}
