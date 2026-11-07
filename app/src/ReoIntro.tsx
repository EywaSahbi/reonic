import { useEffect, useId, useRef, useState } from "react";
import {
  BROW_LIFT, BROW_SPREAD, EYE_X, EYE_Y, FOOT, INK, LEFT_ARM, ORANGE, PINK, RIGHT_ARM,
  bottomBlade, browTransform, topBlade, type ReoVariant,
} from "./ReoAvatar";

// reo's intro: the Reonic logo turns into reo.
// 1 icon slides across "Reonic" and erases it, 2 glides back to centre, 3 turns 90° so the arrows point down,
// 4 the upper arrow lifts into eyebrows while the lower arrow curls into eyes, 5 feet and arms pop out, 6 wave.
// Pure SVG driven by one clock (ms), so it can autoplay or be scrubbed (pass `time`).

export type { ReoVariant };

// Timeline (ms)
const T = {
  slide: [250, 1050],
  glide: [1050, 1500],
  turn: [1500, 1950],
  brows: [1950, 2450],
  collapse: [1950, 2250],
  eyes: [2100, 2550],
  feet: [2450, 2800],
  arms: [2550, 2900],
  wave: [2900, 3900],
  // lockup (withWordmark): reo steps left, the wordmark builds in beside it
  shift: [2900, 3400],
  r: [3150, 3550],
  e: [3300, 3650],
  o: [3400, 3750],
  tag: [3650, 4050],
} as const;
export const REO_INTRO_END = T.wave[1];
export const REO_LOCKUP_END = T.tag[1];

// ---- easing ----
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const seg = (t: number, [a, b]: readonly [number, number]) => clamp((t - a) / (b - a));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const inOutCubic = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const outBack = (p: number, s = 1.70158) => 1 + (s + 1) * Math.pow(p - 1, 3) + s * Math.pow(p - 1, 2);
const inOutBack = (p: number, s = 1.70158 * 1.525) =>
  p < 0.5
    ? (Math.pow(2 * p, 2) * ((s + 1) * 2 * p - s)) / 2
    : (Math.pow(2 * p - 2, 2) * ((s + 1) * (p * 2 - 2) + s) + 2) / 2;

// ---- geometry (icon space: centred, -50..50) ----
// Reonic's arrow blade: the band between a circle (r 30) and an ellipse (17.7 × 30) sharing one centre,
// flat cut at one end, sharp point at the other. Top blades sweep down-right, bottom blades mirror them.

// After the 90° turn: blade 1 (inner column) forms the upper V → eyebrows, blade 2 forms the lower V → eyes.
const BLADES = [
  { d: topBlade(6, -30), role: "brow", side: 1 },
  { d: bottomBlade(6, 30), role: "brow", side: -1 },
  { d: topBlade(27, -30), role: "eye", side: 1 },
  { d: bottomBlade(27, 30), role: "eye", side: -1 },
] as const;


// Scene (viewBox 600 × 220): logo start, avatar end.
const W = 600;
const H = 220;
const CY = 110;
const START_X = 99; // icon centre in the Reonic lockup
const ERASE_X = 520; // icon centre at the end of the slide
const END_X = W / 2;
const END_S = 1.25;

// Wordmark lockup: avatar left, "reo" right, "by Reonic" under it, centred as a group.
const LOCK_X = 161; // avatar centre in the lockup
const WM_X = 288; // left edge of the "r"
const WM_BASE = 150; // baseline
const WM_XH = 70; // x-height = height of the r blade
const WM_EO_W = 160; // width of "eo"
const WM_RIGHT = WM_X + WM_XH + 6 + WM_EO_W;

// The "r" is one Reonic blade after the 90° turn: flat cut on the right, sweeping left and down to a point
// on the baseline. Thickness at the flat cut = 30 − ri; ri 15 makes it a touch heavier than the "eo", like the sketch.
function rPath() {
  const k = WM_XH / 30;
  const P = (u: number, v: number) => `${(WM_X + u * k).toFixed(2)} ${(WM_BASE + (v - 6) * k).toFixed(2)}`;
  const ri = 15;
  return `M${P(30, -24)}A${30 * k} ${30 * k} 0 0 0 ${P(0, 6)}A${30 * k} ${ri * k} 0 0 1 ${P(30, 6 - ri)}Z`;
}
const R_PATH = rPath();

type Props = {
  variant?: ReoVariant;
  /** Wordmark colour; use "dark" on dark backgrounds. */
  theme?: "light" | "dark";
  /** Controlled clock in ms. Omit to autoplay. */
  time?: number;
  /** Change to replay from the start. */
  playKey?: number | string;
  /** End on the full lockup: reo + "reo" wordmark + "by Reonic". */
  withWordmark?: boolean;
  className?: string;
  title?: string;
};

export function ReoIntro({ variant = "grapefruit", theme = "light", time, playKey, withWordmark = false, className, title = "Reonic becomes reo" }: Props) {
  const clock = useClock(time === undefined, playKey);
  const t = time ?? clock;
  const id = useId().replace(/:/g, "");
  const ink = theme === "dark" ? "#f4f4f5" : INK;

  // ---- 1-2: slide across the wordmark, then glide back to centre ----
  const pSlide = inOutCubic(seg(t, T.slide));
  const pGlide = inOutCubic(seg(t, T.glide));
  const pShift = withWordmark ? inOutCubic(seg(t, T.shift)) : 0;
  const x = t < T.glide[0] ? lerp(START_X, ERASE_X, pSlide) : lerp(lerp(ERASE_X, END_X, pGlide), LOCK_X, pShift);
  const s = lerp(1, END_S, pGlide);
  // speed (0..1) for the motion streaks
  const dt = 16;
  const speed = clamp(
    (Math.abs(inOutCubic(seg(t + dt, T.slide)) - inOutCubic(seg(t - dt, T.slide))) * (ERASE_X - START_X)) / (2 * dt) / 0.9,
  );

  // ---- 3: turn 90° with a small hop; ink → gradient ----
  const pTurnRaw = seg(t, T.turn);
  const rot = 90 * inOutBack(pTurnRaw);
  const hop = -14 * Math.sin(Math.PI * pTurnRaw);
  // colour swaps in the second half of the turn so the ink→pink mix never sits on screen looking muddy
  const tint = variant === "grapefruit" ? inOutCubic(clamp((pTurnRaw - 0.45) / 0.4)) : 0;

  // ---- 4: brows lift, lower V curls into eyes ----
  const pBrow = outBack(seg(t, T.brows));
  const pCollapse = inOutCubic(seg(t, T.collapse));
  const pEyes = seg(t, T.eyes);
  const eyeOpen = pEyes === 0 ? 0 : outBack(pEyes, 2.2);

  // ---- 5: feet + arms; 6: wave; then idle blinks ----
  const pFeet = outBack(seg(t, T.feet), 2.4);
  const pArms = outBack(seg(t, T.arms), 2.4);
  const pWave = seg(t, T.wave);
  const wave = pWave > 0 && pWave < 1 ? 22 * Math.sin(pWave * Math.PI * 4) * (1 - pWave * 0.6) : 0;
  const blink = blinkAt(t - (withWordmark ? REO_LOCKUP_END : REO_INTRO_END));

  // wordmark beats
  const pR = seg(t, T.r);
  const rScale = pR === 0 ? 0 : outBack(pR, 2);
  const rise = (span: readonly [number, number]) => {
    const p = seg(t, span);
    return { opacity: clamp(p * 2), dy: 16 * (1 - outBack(p, 2)) };
  };
  const pE = rise(T.e);
  const pO = rise(T.o);
  const pTag = inOutCubic(seg(t, T.tag));
  const wmFill = variant === "grapefruit" ? `url(#${id}-wm)` : ink;

  const body = (fillDark: string) => (
    <>
      <rect x={-50} y={-50} width={100} height={100} rx={26} fill={fillDark} />
      {tint > 0 && <rect x={-50} y={-50} width={100} height={100} rx={26} fill={`url(#${id}-gb)`} opacity={tint} />}
    </>
  );
  const limbFill = variant === "grapefruit" && tint > 0 ? `url(#${id}-gl)` : INK;

  const bladeTransform = (b: (typeof BLADES)[number]) => {
    if (b.role === "brow") {
      const lift = BROW_LIFT * pBrow;
      return browTransform(lift, lerp(1, BROW_SPREAD, pBrow), rot);
    }
    // eye blades: centroid (after the turn) drifts to the eye centre while shrinking away
    const bcx = 17 * b.side;
    const bcy = 7;
    const k = lerp(1, 0.15, pCollapse);
    const cx = lerp(bcx, EYE_X * b.side, pCollapse);
    const cy = lerp(bcy, EYE_Y, pCollapse);
    return `translate(${cx} ${cy}) scale(${k}) translate(${-bcx} ${-bcy}) rotate(${rot})`;
  };

  const eye = (side: 1 | -1) => (
    <g key={side} transform={`translate(${EYE_X * side} ${EYE_Y}) scale(1 ${Math.max(0.04, eyeOpen * blink)})`} opacity={clamp(pEyes * 4)}>
      <ellipse rx={12.5} ry={16.5} fill="#fff" />
      <ellipse cx={1.5} cy={1.5} rx={8.6} ry={12} fill={INK} />
      <ellipse cx={4.2} cy={-3.6} rx={2.4} ry={3.6} fill="#fff" />
    </g>
  );

  // arms grow from the shoulder; right arm waves
  const arm = (sx: number, sy: number, ex: number, ey: number, angle = 0) => (
    <g transform={`rotate(${angle} ${sx} ${sy})`}>
      <line x1={sx} y1={sy} x2={lerp(sx, ex, pArms)} y2={lerp(sy, ey, pArms)} stroke={limbFill} strokeWidth={15} strokeLinecap="round" />
    </g>
  );

  const textClipX = x + 40;

  return (
    <svg className={className} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} style={{ overflow: "visible" }}>
      <defs>
        {/* gradient in the body's own (rotated) frame: pre-rotated −90° so it reads top-left → bottom-right */}
        <linearGradient id={`${id}-gb`} gradientUnits="userSpaceOnUse" x1={-55} y1={55} x2={55} y2={-55}>
          <stop offset="0" stopColor={PINK} />
          <stop offset="1" stopColor={ORANGE} />
        </linearGradient>
        <linearGradient id={`${id}-gl`} gradientUnits="userSpaceOnUse" x1={-70} y1={-70} x2={70} y2={70}>
          <stop offset="0" stopColor={PINK} />
          <stop offset="1" stopColor={ORANGE} />
        </linearGradient>
        <linearGradient id={`${id}-wm`} gradientUnits="userSpaceOnUse" x1={WM_X} y1={WM_BASE - WM_XH} x2={WM_RIGHT} y2={WM_BASE}>
          <stop offset="0" stopColor={PINK} />
          <stop offset="1" stopColor={ORANGE} />
        </linearGradient>
        <clipPath id={`${id}-erase`}>
          <rect x={textClipX} y={0} width={Math.max(0, W - textClipX)} height={H} />
        </clipPath>
      </defs>

      {/* Reonic wordmark, erased behind the icon */}
      {t < T.glide[0] && (
        <g clipPath={`url(#${id}-erase)`}>
          <text
            x={190}
            y={154}
            fontFamily="Geist, Inter, system-ui, sans-serif"
            fontWeight={500}
            fontSize={124}
            letterSpacing={-2}
            textLength={361}
            lengthAdjust="spacingAndGlyphs"
            fill={ink}
          >
            Reonic
          </text>
        </g>
      )}

      {/* motion streaks */}
      {speed > 0.05 && (
        <g stroke={ink} strokeLinecap="round" strokeWidth={3} opacity={speed * 0.35}>
          {[-26, 0, 26].map((dy, i) => (
            <line key={dy} x1={x - 58 - speed * (60 + i * 18)} y1={CY + dy} x2={x - 58} y2={CY + dy} />
          ))}
        </g>
      )}

      <g transform={`translate(${x} ${CY + hop}) scale(${s})`}>
        {/* limbs sit behind the body and pop out of it */}
        {pFeet > 0 && (
          <g fill={limbFill}>
            {[-1, 1].map((side) => (
              <ellipse
                key={side}
                cx={FOOT.x * side}
                cy={lerp(FOOT.y - 14, FOOT.y, pFeet)}
                rx={FOOT.rx}
                ry={FOOT.ry}
              />
            ))}
          </g>
        )}
        {pArms > 0 && (
          <>
            {arm(...LEFT_ARM)}
            {arm(...RIGHT_ARM, wave)}
          </>
        )}

        <g transform={`rotate(${rot})`}>{body(INK)}</g>

        {BLADES.map((b, i) => (
          <path
            key={i}
            d={b.d}
            fill="#fff"
            // body-coloured outline: invisible on the icon, keeps the brows readable once they lift off the head
            stroke={tint > 0.5 ? `url(#${id}-gb)` : INK}
            strokeWidth={7}
            strokeLinejoin="round"
            paintOrder="stroke"
            transform={bladeTransform(b)}
            opacity={b.role === "eye" ? 1 - clamp((pCollapse - 0.55) / 0.45) : 1}
          />
        ))}

        {pEyes > 0 && [eye(-1), eye(1)]}
      </g>

      {withWordmark && pR > 0 && (
        <g aria-hidden>
          {/* r grows out of its own point on the baseline */}
          <path
            d={R_PATH}
            fill={wmFill}
            transform={`translate(${WM_X} ${WM_BASE}) scale(${rScale}) translate(${-WM_X} ${-WM_BASE})`}
          />
          <text
            fontFamily="Geist, Inter, system-ui, sans-serif"
            fontWeight={700}
            fontSize={134}
            letterSpacing={-3}
            fill={wmFill}
            y={WM_BASE}
          >
            <tspan x={WM_X + WM_XH + 6} dy={pE.dy} opacity={pE.opacity}>e</tspan>
            <tspan x={WM_X + WM_XH + 6 + WM_EO_W / 2} dy={pO.dy - pE.dy} opacity={pO.opacity}>o</tspan>
          </text>
          <text
            x={WM_RIGHT}
            y={WM_BASE + 34}
            textAnchor="end"
            fontFamily="Geist, Inter, system-ui, sans-serif"
            fontWeight={500}
            fontSize={22}
            fill={ink}
            opacity={pTag}
          >
            by Reonic
          </text>
        </g>
      )}
    </svg>
  );
}

// Idle blink: closes for ~170ms every 3.4s once the intro has finished.
function blinkAt(idle: number) {
  if (idle < 600) return 1;
  const q = ((idle - 600) % 3400) / 170;
  return q < 1 ? 1 - 0.92 * Math.sin(Math.PI * q) : 1;
}

// rAF clock in ms; respects reduced motion (jumps to the final pose).
function useClock(running: boolean, playKey?: number | string) {
  const [t, setT] = useState(0);
  const start = useRef(0);
  useEffect(() => {
    if (!running) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    start.current = performance.now() - (reduce ? REO_INTRO_END : 0);
    let raf = 0;
    const tick = (now: number) => {
      setT(now - start.current);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, playKey]);
  return t;
}
