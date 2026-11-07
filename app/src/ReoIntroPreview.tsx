import { useState } from "react";
import { ReoIntro, REO_INTRO_END, REO_LOCKUP_END, type ReoVariant } from "./ReoIntro";
import { ReoAvatar } from "./ReoAvatar";

// Pitch stage for the intro at "#/reo-intro": replay, colour, background, and a scrubber to stop on any beat.
export function ReoIntroPreview() {
  const [variant, setVariant] = useState<ReoVariant>("grapefruit");
  const [dark, setDark] = useState(false);
  const [key, setKey] = useState(0);
  const [scrub, setScrub] = useState<number | null>(null);
  const [wordmark, setWordmark] = useState(true);
  const end = (wordmark ? REO_LOCKUP_END : REO_INTRO_END) + 400;
  const [waving, setWaving] = useState(false);
  const [wink, setWink] = useState(0);

  return (
    <div className={`reo-stage ${dark ? "is-dark" : ""}`}>
      <ReoIntro
        className="reo-stage-art"
        variant={variant}
        theme={dark ? "dark" : "light"}
        withWordmark={wordmark}
        playKey={key}
        time={scrub ?? undefined}
      />
      <div className="reo-stage-bar">
        <button onClick={() => { setScrub(null); setKey((k) => k + 1); }}>Replay</button>
        <button onClick={() => setVariant(variant === "ink" ? "grapefruit" : "ink")}>
          {variant === "ink" ? "Grapefruit" : "Ink"}
        </button>
        <button onClick={() => setDark(!dark)}>{dark ? "Light" : "Dark"} background</button>
        <button onClick={() => { setWordmark(!wordmark); setScrub(null); setKey((k) => k + 1); }}>
          {wordmark ? "Without" : "With"} wordmark
        </button>
        <input
          type="range"
          min={0}
          max={end}
          step={10}
          value={scrub ?? end}
          onChange={(e) => setScrub(Number(e.target.value))}
          aria-label="Scrub the animation"
        />
      </div>

      {/* standalone <ReoAvatar />: each one follows the cursor from where it stands; hover = wave, click = wink */}
      <div className="reo-stage-avatars">
        {[40, 72, 120].map((size) => (
          <ReoAvatar key={size} size={size} variant={variant} waving={waving} winkKey={wink} />
        ))}
      </div>
      <div className="reo-stage-bar">
        <button onClick={() => setWaving(!waving)}>{waving ? "Stop waving" : "Wave"}</button>
        <button onClick={() => setWink((w) => w + 1)}>Wink</button>
      </div>
    </div>
  );
}
