# SPEC — reo product video, scenes 1–4 (0:00–0:46)

Source: [../video-storyboard-1-4.md](../video-storyboard-1-4.md). Silent animatic-grade build: no voice-over or music yet (VO is recorded separately; timings below are the cue points).

GOAL: the viewer feels the gap between a homeowner and an installer, then sees reo arrive as the thing that works in it.
OUTPUT: HyperFrames, 1920×1080, 30 fps. 46 s = 1380 frames.

LOOK: brand from `experience/brand.md` (Reonic's own style, so the paper ground is the brand's, not a default).
- Ground paper `#FDFDFB`, ink `#1B1D20` (logo/avatar `#141414`), secondary `#71717A`, hairline `#E4E4E7`, "today world" UI in grey `#3F3F46`/`#A1A1AA`.
- Accent: sunset gradient `#F7A35C → #F2784B → #EE6A5B` only on one hero word per scene (scene 3: "further"; scene 4: "agentic"), plus reo's own body/limbs (`#FF6B7A → #FF9A3C`).
- Type: Geist (files in `assets/fonts/`). Hero number 300 px/700/−3%; titles 96 px/600/−2%; captions 44 px/500; UI text ≥ 24 px.
- Medium: flat product UI, one soft shadow (0 24 60 / 8% ink), no glow, no glass, no grain.

OBJECTS: generic grey web form + clock (the old way, deliberately dull); installer lead list + profile + hours bar; message bubble; the real Sonnfeld hero photo in a browser frame (real asset); reo drawn from the Reonic blade geometry in `app/src/ReoIntro.tsx` (ported 1:1, same clock).

MOTION: arrivals `expo.out`/`power3.out` 0.5–0.9 s; layout moves `power3.inOut` 0.8–0.9 s; pops `back.out(1.7–2.2)` on objects only; text rises 16 px or blur-in, never both on every line; titles land dead still. reo intro uses the component's own easing (inOutCubic/outBack).

SHOTS (global seconds):
- 0.0–3.0 "4,500" types in (5 chars, 0.25 s apart), unit under it. Caption 2.4.
- 3.0–4.2 form card rises, number flies into the field. 6.0–7.8 cursor clicks, "Thanks!" check. 9.0–12.0 clock + "Waiting…".
- 12.0–12.9 form slides to left half (scale 0.62); 12.3 installer list enters; 13.4 rows; 15.0 profile; 15.8–16.7 four "?" pop; 18.0–20.7 checklist; 18.5–24.6 hours bar fills, never completes; 21.0–23.2 bubble dies in the gap.
- 24.0–31.0 both halves dim to 12 %; line draws across the gap, pulse; "Reonic already connects the two." → "We wanted to go further" (gradient wipe on "further"); all fades 30.2.
- 30.0–32.0 Reonic lockup fades in, still. 32.0 ReoIntro clock t=0 (slide 32.25, turn 33.5, eyes 33.95, arms 34.55, wave 34.9, lockup 35.9, tagline 36.3).
- 38.0 wordmark leaves, reo centres; 38.2 site rises; 39.2–40.2 reo lifts then drops into the hero (back.out + squash); 41.8–43.0 window shrinks, bubble and card slide in; 43.0–43.9 arms reach both ways; hold to 46.0.

BANNED (this film): dark void, glow/bloom, purple/blue gradients, glass cards, three-cards-in-a-row, logo docked in a corner, titles that drift after landing, vest (not until the planner scene), any named person, any hours/days number.

QA frames: 1.6 (number typed), 4.4 (card + field), 7.6 (thanks), 11.5 (clock), 14.0 (split), 17.0 (profile), 22.0 (bubble in gap), 26.0 (link + title), 29.5 (further), 31.5 (lockup still), 34.0 (eyes), 35.0 (wave), 37.0 (lockup + tagline), 40.5 (reo in hero), 44.5 (reach), 45.8 (hold).
