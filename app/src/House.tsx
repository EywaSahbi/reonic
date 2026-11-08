import type { Design } from "./types";

// The house that builds itself (docs/reference-enpal.md): panels appear on the roof (count = engine module count),
// battery on the wall, heat pump outside, car at the wallbox. Purely a picture of the engine's design; computes nothing.
const COLS = 8, ROWS = 3, MAX = COLS * ROWS;

export function House({ design }: { design: Design }) {
  const c = design.components;
  const pvOn = c.pv.recommended && (c.pv.size ?? 0) > 0;
  const panels = pvOn ? c.pv.quantity ?? null : 0; // null: engine gave kWp but no module count
  const drawn = panels === null ? MAX / 2 : Math.min(panels, MAX);
  const on = (b: boolean) => `h-part ${b ? "on" : ""}`;

  return (
    <figure className="house" aria-label={`House with ${panels ?? c.pv.size + " kWp of"} solar panels${c.battery.recommended ? ", a battery" : ""}${c.heatpump.recommended ? ", a heat pump" : ""}${c.wallbox.recommended ? ", a wallbox" : ""}`}>
      <svg viewBox="0 0 320 190" role="img">
        <defs>
          <linearGradient id="h-sun" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#f7a35c" /><stop offset="1" stopColor="#ee6a5b" />
          </linearGradient>
        </defs>

        <circle cx="290" cy="28" r="13" fill="url(#h-sun)" className={on(pvOn)} />
        <line x1="8" y1="170" x2="312" y2="170" className="h-line" />

        {/* house body + roof */}
        <rect x="102" y="98" width="120" height="72" className="h-wall" />
        <rect x="118" y="118" width="22" height="18" rx="2" className="h-line" />
        <rect x="152" y="132" width="20" height="38" rx="2" className="h-line" />
        <polygon points="120,48 262,48 232,98 90,98" className="h-roof" />

        {/* panels, laid on the skewed roof plane */}
        <g transform="translate(124 52) matrix(1 0 -0.6 1 0 0)">
          {Array.from({ length: MAX }).map((_, i) => {
            const r = ROWS - 1 - Math.floor(i / COLS), col = i % COLS;
            return (
              <rect key={i} x={col * 17} y={r * 14.5} width="15.5" height="12.5" rx="1.2"
                className={`h-panel ${i < drawn ? "on" : ""}`} style={{ transitionDelay: `${i * 25}ms` }} />
            );
          })}
        </g>

        {/* battery on the wall */}
        <g className={on(c.battery.recommended)}>
          <rect x="192" y="122" width="20" height="36" rx="3" className="h-box" />
          <path d="M203 130l-5 9h4l-2 8 6-10h-4l2-7z" className="h-accent" />
        </g>

        {/* heat pump outside */}
        <g className={on(c.heatpump.recommended)}>
          <rect x="44" y="134" width="46" height="36" rx="3" className="h-box" />
          <circle cx="60" cy="152" r="10" className="h-line" />
          <path d="M60 144v16M52 152h16" className="h-line" />
          <path d="M78 141v22M84 141v22" className="h-line" />
        </g>

        {/* wallbox + car */}
        <g className={on(c.wallbox.recommended)}>
          <rect x="238" y="128" width="12" height="20" rx="2" className="h-box" />
          <path d="M250 140c8 0 8 8 14 10" className="h-line" />
          <path d="M256 170v-10l7-11h34l7 11v10z" className="h-car" />
          <circle cx="268" cy="170" r="5" className="h-wheel" /><circle cx="294" cy="170" r="5" className="h-wheel" />
        </g>
      </svg>
    </figure>
  );
}
