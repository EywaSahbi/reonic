import { useCallback, useEffect, useId, useRef, useState } from "react";

// reo, standalone: the finished pose from the intro (ReoIntro.tsx), alive.
// SVG + CSS (styles.css, "reo avatar"); motion is driven by CSS vars and classes, so the cursor never re-renders React.
// Built from Reonic's arrow blades: the eyebrows are two blades, flat cut outside, point in the middle.
// Alive: eyes follow the cursor from reo's own position, wander when the cursor rests, idle blink + breathing,
// a greeting wave on mount and on hover, a wink on click (or when `winkKey` changes), now and then a wink on its own.

export type ReoVariant = "ink" | "grapefruit";

export const INK = "#141414";
export const PINK = "#FF6B7A";
export const ORANGE = "#FF9A3C";

// Reonic's arrow blade (icon space, centred -50..50): the band between a circle (r 30) and an ellipse
// (17.7 × 30) sharing one centre, flat cut at one end, sharp point at the other.
const R = 30;
const RI = 17.7;
export const topBlade = (px: number, py: number) =>
  `M${px - R} ${py}A${R} ${R} 0 0 0 ${px} ${py + R}A${RI} ${R} 0 0 1 ${px - RI} ${py}Z`;
export const bottomBlade = (px: number, py: number) =>
  `M${px - R} ${py}A${R} ${R} 0 0 1 ${px} ${py - R}A${RI} ${R} 0 0 0 ${px - RI} ${py}Z`;

// Final-pose layout (avatar space: body is -50..50)
export const EYE_X = 18;
export const EYE_Y = 2;
export const BROW_LIFT = -44;
export const BROW_SPREAD = 1.14;
export const browTransform = (lift: number, spread: number, rot: number) =>
  `translate(0 ${lift}) translate(0 -9) scale(${spread}) translate(0 9) rotate(${rot})`;
export const LEFT_ARM = [-42, 16, -62, 30] as const;
export const RIGHT_ARM = [42, 10, 62, -8] as const;
export const FOOT = { x: 22, y: 52, rx: 14, ry: 9 } as const;

const WAVE_MS = 2000; // two wave cycles (styles.css reo-wave, 1 s each)
const WINK_MS = 460;

type Props = {
  /** Rendered width in px (height follows). */
  size?: number;
  variant?: ReoVariant;
  /** Wave the raised arm (loops while true). */
  waving?: boolean;
  /** Where reo looks, each -1..1 (x: left→right, y: up→down). Set it to steer the eyes yourself; omit it and reo follows the cursor. */
  look?: { x: number; y: number };
  /** Freeze reo: no blinking, breathing, following or greeting (e.g. screenshots). */
  still?: boolean;
  /** Wave on hover, wink + wave on click. */
  interactive?: boolean;
  /** Wave once shortly after mounting. */
  greet?: boolean;
  /** Change this number to make reo wink (e.g. on a new message). */
  winkKey?: number;
  className?: string;
  title?: string;
};

export function ReoAvatar({
  size = 96,
  variant = "grapefruit",
  waving = false,
  look,
  still = false,
  interactive = true,
  greet = true,
  winkKey,
  className,
  title = "reo",
}: Props) {
  const id = useId().replace(/:/g, "");
  const fill = variant === "grapefruit" ? `url(#${id}-g)` : INK;
  const ref = useRef<SVGSVGElement>(null);
  const [greeting, setGreeting] = useState(false);
  const [winking, setWinking] = useState(false);
  const busy = useRef({ wave: false, wink: false });
  const timers = useRef<number[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const later = useCallback((fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms));
  }, []);
  const wave = useCallback(() => {
    if (busy.current.wave || reducedMotion()) return;
    busy.current.wave = true;
    setGreeting(true);
    later(() => { busy.current.wave = false; setGreeting(false); }, WAVE_MS);
  }, [later]);
  const wink = useCallback(() => {
    if (busy.current.wink || reducedMotion()) return;
    busy.current.wink = true;
    setWinking(true);
    later(() => { busy.current.wink = false; setWinking(false); }, WINK_MS);
  }, [later]);

  const aimEyes = useCallback((x: number, y: number) => {
    ref.current?.style.setProperty("--lx", clamp(x).toFixed(3));
    ref.current?.style.setProperty("--ly", clamp(y).toFixed(3));
  }, []);

  // Steered by the parent
  const lookX = look?.x;
  const lookY = look?.y;
  useEffect(() => {
    if (lookX !== undefined && lookY !== undefined) aimEyes(lookX, lookY);
  }, [lookX, lookY, aimEyes]);

  // Self-driven: follow the cursor from reo's own centre; look around when the cursor rests
  const steered = look !== undefined;
  useEffect(() => {
    const el = ref.current;
    if (steered || still || !el) return;
    let px = 0, py = 0, frame = 0, lastMove = 0;
    const aim = () => {
      frame = 0;
      const r = el.getBoundingClientRect();
      const dx = px - (r.left + r.width / 2);
      const dy = py - (r.top + r.height * 0.56); // eye line
      const d = Math.hypot(dx, dy) || 1;
      const reach = Math.min(1, d / Math.max(160, r.width * 1.6)); // close cursor = small glance, far = full
      aimEyes((dx / d) * reach, (dy / d) * reach);
    };
    const onMove = (e: PointerEvent) => {
      px = e.clientX;
      py = e.clientY;
      lastMove = performance.now();
      if (!frame) frame = requestAnimationFrame(aim);
    };
    addEventListener("pointermove", onMove, { passive: true });
    const wander = reducedMotion()
      ? 0
      : window.setInterval(() => {
          if (performance.now() - lastMove < 3000) return;
          aimEyes(Math.random() * 1.6 - 0.8, Math.random() - 0.6);
          if (Math.random() < 0.1) wink();
        }, 2400);
    return () => {
      removeEventListener("pointermove", onMove);
      cancelAnimationFrame(frame);
      clearInterval(wander);
    };
  }, [steered, still, aimEyes, wink]);

  useEffect(() => {
    if (greet && !still) later(wave, 700);
    // greet once per mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const lastWinkKey = useRef(winkKey);
  useEffect(() => {
    if (lastWinkKey.current === winkKey) return;
    lastWinkKey.current = winkKey;
    wink();
  }, [winkKey, wink]);

  const react = interactive && !still;
  const cls = [
    "reo-mascot",
    waving && "is-waving",
    greeting && "is-greeting",
    winking && "is-winking",
    still && "is-still",
    className,
  ].filter(Boolean).join(" ");

  const eye = (side: 1 | -1) => (
    <g key={side} transform={`translate(${EYE_X * side} ${EYE_Y})`}>
      <g className={`reo-wink ${side === 1 ? "reo-wink-r" : "reo-wink-l"}`}>
        <g className="reo-eye">
          <ellipse rx={12.5} ry={16.5} fill="#fff" />
          <g clipPath={`url(#${id}-eye)`}>
            <g className="reo-pupil">
              <ellipse cx={1.5} cy={1.5} rx={8.6} ry={12} fill={INK} />
              <ellipse cx={4.2} cy={-3.6} rx={2.4} ry={3.6} fill="#fff" />
            </g>
          </g>
        </g>
      </g>
    </g>
  );

  return (
    <svg
      ref={ref}
      className={cls}
      viewBox="-72 -76 144 140"
      width={size}
      height={(size * 140) / 144}
      role="img"
      aria-label={title}
      onPointerEnter={react ? wave : undefined}
      onClick={react ? () => { wink(); wave(); } : undefined}
    >
      <defs>
        <linearGradient id={`${id}-g`} gradientUnits="userSpaceOnUse" x1={-60} y1={-60} x2={60} y2={60}>
          <stop offset="0" stopColor={PINK} />
          <stop offset="1" stopColor={ORANGE} />
        </linearGradient>
        {/* pupils travel far enough to reach the eye's rim; the clip keeps them inside */}
        <clipPath id={`${id}-eye`}>
          <ellipse rx={12.5} ry={16.5} />
        </clipPath>
      </defs>

      <g className="reo-hop">
        <g fill={fill}>
          {[-1, 1].map((s) => (
            <ellipse key={s} cx={FOOT.x * s} cy={FOOT.y} rx={FOOT.rx} ry={FOOT.ry} />
          ))}
        </g>

        <g className="reo-breathe">
          {/* arms behind the body */}
          <g stroke={fill} strokeWidth={15} strokeLinecap="round">
            <line className="reo-arm-rest" x1={LEFT_ARM[0]} y1={LEFT_ARM[1]} x2={LEFT_ARM[2]} y2={LEFT_ARM[3]} />
            <line className="reo-arm-wave" x1={RIGHT_ARM[0]} y1={RIGHT_ARM[1]} x2={RIGHT_ARM[2]} y2={RIGHT_ARM[3]} />
          </g>

          <rect x={-50} y={-50} width={100} height={100} rx={26} fill={fill} />

          <g className="reo-face">
            {/* eyebrows: the two inner Reonic blades, turned 90° and lifted; body-coloured outline keeps them readable off the head.
                After the 90° turn the top blade sits on reo's right (+x), the bottom blade on the left. */}
            {[topBlade(6, -30), bottomBlade(6, 30)].map((d, i) => (
              <g key={d} className={i === 0 ? "reo-brow reo-brow-r" : "reo-brow reo-brow-l"}>
                <path
                  d={d}
                  fill="#fff"
                  stroke={fill}
                  strokeWidth={7}
                  strokeLinejoin="round"
                  paintOrder="stroke"
                  transform={browTransform(BROW_LIFT, BROW_SPREAD, 90)}
                />
              </g>
            ))}

            {eye(-1)}
            {eye(1)}
          </g>
        </g>
      </g>
    </svg>
  );
}

const clamp = (v: number) => Math.min(1, Math.max(-1, v));
const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
