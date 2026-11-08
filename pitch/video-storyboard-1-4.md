# reo product video — storyboard, scenes 1–4 (0:00–0:46)

> Part of [submission-scripts.md](submission-scripts.md) (section A). Covers the setup of the two parties, the friction, and the reveal. Scenes 5–9 (demo, proof, close) come next.
> Job of these 46 seconds: make the viewer **feel the gap** between homeowner and installer, then make reo's arrival feel like the answer. No product UI of ours until scene 4 ends.

## Look and motion rules (apply to every shot)

| | |
|---|---|
| Canvas | 1920×1080, 30 fps (60 fps for capture clips later). Safe margin 120 px. |
| Colour | Paper `#FDFDFB`, ink `#1B1D20`, secondary `#71717A`, hairline `#E4E4E7`. Sunset gradient (`#F7A35C → #F2784B → #EE6A5B`) on **one hero word per scene**, never on areas. Status UI of the "today" world is **deliberately generic and grey**; only reo and Sonnfeld carry colour. |
| Type | Geist (same as `ReoIntro`). Hero numbers 700, 280 px, tracking −3. Titles 600, 96 px. Captions 500, 36 px, `#71717A`. Max 6 words per screen. |
| Motion | Same language as the intro: `inOutCubic` for moves (400–600 ms), `outBack` only for objects that "pop" (reo, buttons), never for text. Text enters by rising 16 px + fade (like the "e" and "o" in the wordmark). |
| The split | From 0:12 the frame is two halves, **left = homeowner, right = installer**, divided by a 160 px empty **gap** in the middle. The gap is the character of the film: it holds the clock, the lost message, then reo. |
| Audio | Warm room tone throughout, no music until 0:24. Sound design is small and physical (keys, clicks, a soft pad). One musical swell at the reveal, resolving on the wave. |

---

## Scene 1 — "One number" (0:00–0:12) · homeowner

**Goal:** an ordinary person, one fact, a dead end. **Voice-over:** "A homeowner wants solar. All they know is one number from their bill. They fill in a form, and then they wait."

| Shot | Time | Frame | Motion | VO / SFX |
|---|---|---|---|---|
| 1.1 | 0:00–0:03 | Empty paper. Centre-left: **4,500** types in, digit by digit, huge. A caret blinks after it. "kWh a year" rises under it in grey. | Digits appear at 120 ms intervals; caret blinks 1 Hz. Slow 3 % push-in over the shot. | VO starts 0:01 "A homeowner wants solar." · SFX: soft key ticks per digit |
| 1.2 | 0:03–0:06 | Caption bottom-left: "A homeowner wants solar. This is all they know." The number **shrinks and flies into a form field** on a generic grey web form ("Get your free solar quote": *Electricity use* [4,500 kWh], a black *Get quote* button). | Number scales 0.25× along an arc into the field (500 ms). Form card rises beneath it (outBack, small). | VO "All they know is one number from their bill." · SFX: whoosh into field |
| 1.3 | 0:06–0:09 | A cursor clicks **Get quote**. Button depresses (scale 0.97), card swaps to a big grey check and "Thanks! We'll call you back." | Click is the frame's only fast action. Check draws in (stroke 300 ms). | VO "They fill in a form…" · SFX: click, soft chime |
| 1.4 | 0:09–0:12 | The check dissolves; in its place a slow **clock face** with the caption "Waiting…" (no numbers, no day count). The form greys out. | Clock hands accelerate (ease-in) and spin. Everything desaturates slightly. | VO "…and then they wait." · SFX: tick-tick accelerating, ends on a held low note |

**Key frame K1 (1.1):**
```
┌──────────────────────────────────────────────┐
│                                              │
│   4,500▌                                     │
│   kWh a year                                 │
│                                              │
│                                              │
└──────────────────────────────────────────────┘
```
**Key frame K2 (1.4):** grey form card centre-left, spinning clock + "Waiting…", everything flat and quiet.

---

## Scene 2 — "Same questions, every time" (0:12–0:24) · installer

**Goal:** the other side has a mirror problem. Neither person is the villain; the gap is. **Voice-over:** "On the other side, an installer gets another lead that starts from zero. A planner will spend hours turning it into a design and a price."

| Shot | Time | Frame | Motion | VO / SFX |
|---|---|---|---|---|
| 2.1 | 0:12–0:14.5 | Scene 1 **slides left and compresses to the left half** (spring, 600 ms). The right half is revealed: a generic installer **lead inbox**. Caption top: "The installer." A **hairline gap** (160 px) now separates the two halves. | Camera-style slide, left content scales to 0.5×. Right half enters from the right edge. | VO "On the other side…" · SFX: soft swish, low pad begins |
| 2.2 | 0:14.5–0:18 | Inbox rows drop in: "New lead — Homeowner · 4,500 kWh" and four more leads under it. That row opens into a **blank profile**: *Roof ?  Heating ?  EV ?  Budget ?* Each "?" pops in one by one. | Rows stagger 120 ms. "?" pops use outBack. | VO "…an installer gets another lead that starts from zero." · SFX: soft pops |
| 2.3 | 0:18–0:21 | A **checklist of questions** types itself down the profile ("Call back. Ask roof size. Ask heating. Ask EV…"), then a **bar fills slowly** with a label "hours". Other lead rows below stay untouched, stacked. | Typing 40 ms/char. Bar fill ease-out over 3 s, never completes. | VO "A planner will spend hours…" · SFX: keys, a long sustained hum under |
| 2.4 | 0:21–0:24 | **The gap.** From the left half a small message bubble ("We'll call you back") drifts toward the right, enters the gap, slows and **fades before it arrives**. Left clock still spinning, right bar still filling. Gap lit by a dashed centre line pulsing once. | Bubble travel 2 s, decelerates, opacity 1→0 in the gap. | VO "…turning it into a design and a price." · SFX: hum drops out, one dry tick |

**Key frame K3 (2.4):**
```
┌───────────────────┬────┬───────────────────┐
│ Homeowner         │ ┊  │ Installer         │
│ (clock) Waiting…  │ ┊  │ Lead: Homeowner   │
│ "Thanks! We'll    │ ┊──╳  Roof ? Heat ?    │
│  call you back"   │ ┊  │ EV ?  Budget ?    │
│                   │ ┊  │ [██████░░] hours  │
└───────────────────┴────┴───────────────────┘
```
The message bubble dies in the gap. That single image carries the film's premise.

---

## Scene 3 — "We wanted to go further" (0:24–0:32) · the turn

**Goal:** acknowledge Reonic honestly (it already connects them), then raise the stakes. This is the breath before the reveal. **Voice-over:** "Reonic already connects installers and their customers. We wanted to go further."

| Shot | Time | Frame | Motion | VO / SFX |
|---|---|---|---|---|
| 3.1 | 0:24–0:27 | Both halves **fade to 12 % and defocus**. A thin ink line **draws across the gap** from the left card to the right card. Title rises above it: "Reonic already connects the two." | Line draws left to right over 800 ms, with a tiny pulse travelling along it. Title text rise-in. | VO "Reonic already connects installers and their customers." · SFX: pad rises, a single pulse tone as the line completes |
| 3.2 | 0:27–0:30 | The pulse travels the line again, slower. Nothing else moves. Hold on the stillness. Then the title swaps to "We wanted to go **further**" with *further* in the sunset gradient. | Gradient wipes across the word left to right (600 ms). | VO "We wanted to go further." (hold the pause before "further") · SFX: pulse tone sustains |
| 3.3 | 0:30–0:32 | Everything fades to blank paper. A **Reonic lockup** (icon + "Reonic" wordmark, exactly the start frame of `ReoIntro`) fades in dead centre. | Crossfade 700 ms; lockup is static at t=0. | SFX: silence for 1 s |

**Honesty note:** scene 3 must not imply Reonic did nothing. The line across the gap is already drawn; the point is that it only *carries* messages, and reo does *work*.

---

## Scene 4 — "Meet reo" (0:32–0:46) · reveal

**Goal:** the signature moment. The logo becomes a character, the character does a job. reo is simply *dropped onto the installer's website*; the scene makes no claim about how (the suggested implementation lives in the Q&A). **Voice-over:** "Meet reo. An agentic companion, dropped onto the installer's website, doing the work in between."

`ReoIntro withWordmark` clock starts at **0:32.00** (t = 0). Beats are fixed by the component, so cut the VO to them:

| Shot | Time | Clock (ms) | Frame | VO / SFX |
|---|---|---|---|---|
| 4.1 | 0:32.25–0:33.05 | 250–1050 | Icon **slides across** "Reonic", erasing it behind motion streaks. | SFX: whoosh matching the streaks |
| 4.2 | 0:33.05–0:33.5 | 1050–1500 | Glides back to centre, grows. | SFX: whoosh tail |
| 4.3 | 0:33.5–0:33.95 | 1500–1950 | Turns 90° with a small hop; ink → pink/orange gradient. | SFX: soft thud on landing |
| 4.4 | 0:33.95–0:34.55 | 1950–2550 | Brows lift, eyes open. | SFX: eye "pop" |
| 4.5 | 0:34.55–0:34.9 | 2550–2900 | Feet and arms pop out. | VO **"Meet reo."** lands here · SFX: two quick pops, swell begins |
| 4.6 | 0:34.9–0:35.9 | 2900–3900 | **Wave.** Lockup builds: avatar steps left, "r", "e", "o" rise in. | SFX: musical swell resolves on the wave |
| 4.7 | 0:35.9–0:38.0 | 3900–6000 | Hold the full lockup "**reo** by Reonic", blink. Subtitle rises: "An agentic companion for installers." (*agentic* in the gradient) | VO silence, one breath |
| 4.8 | 0:38.0–0:40.1 | — | **Drop-in.** The wordmark leaves and reo steps to centre. A generic installer website (**Greenleaf Solar**, green) rises. reo lifts above it, winds up, and **drops onto the page under the call-to-action**, landing with a squash and a back-out bounce, and **takes the site's colour** as it falls. | VO "An agentic companion, dropped onto the installer's website…" · SFX: soft drop and settle |
| 4.8b | 0:40.5–0:43.6 | — | **Fits any website.** Two more fictional installer sites slide through the centre one after another: **Bluepeak Energy** (light, blue, square corners) then **Amberline Power** (dark, amber, sharp, uppercase), then the real **Sonnfeld** site. reo stays fixed at the centre; the pages pass beneath it and **reo's colour morphs to each theme** (green, blue, amber, then back to its own sunset on Sonnfeld). Each site has its own layout, type treatment and call-to-action, so it reads as three different companies. | VO continues "…any installer's website…" · SFX: one soft whoosh per slide, a small pop per recolour |
| 4.9 | 0:43.6–0:46.0 | — | reo stays **plain, no vest** (the vest is saved for the planner side of the demo, scene 6). It gives a small happy hop on landing. The gap returns on either side of the browser: left a customer chat bubble, right a planner card. reo's **arms reach out to both**; one hand touches the bubble, the other the card; both light up in the sunset gradient. Last frame: reo centred in the gap, the gap now bridged. | VO "…doing the work in between." · SFX: two soft taps, a held warm note |

**Key frame K4 (4.6):** "reo" lockup, avatar left of the wordmark, mid-wave, ink on paper, gradient on the wordmark.
**Key frame K5 (4.8):** browser window, reo centred under a "Plan my home" pill, hero copy faded behind.
**Key frame K6 (4.9):**
```
┌──────────────┬──────────────┬──────────────┐
│ 💬 customer  │     reo      │  planner     │
│   bubble ◄───┼── arms ──────┼──► card      │
│              │              │              │
└──────────────┴──────────────┴──────────────┘
```
Last 0.5 s: the browser window grows to fill the left half, which becomes scene 5's customer window (continuity into the demo).

---

## What exists vs what is new

| Item | Status |
|---|---|
| `ReoIntro withWordmark` (4.1–4.7) | **exists**, frame-exact via the `time` prop. |
| `ReoAvatar outfit="vest"` | **not used in scenes 1–4.** Reserved for the planner view in scene 6 (`#/reo-vest`). |
| Arms reaching toward two targets (4.9) | **new** (arm angles are parameterised in `ReoAvatar`; needs a reach pose). |
| Generic form, inbox, clock, bubble, browser frame (1–2, 4.8) | **new**, simple vector UI, built as HTML in the video composition. |
| Reonic lockup start frame (3.3) | **exists** (`ReoIntro` at t = 0). |
| Sonnfeld site (4.8) | exists in the app; for 4.8 a simplified wireframe is enough. |

## Open decisions for these scenes

Decided: "a homeowner", no name; the planner's work "takes hours" (said, never a number); reo is an agentic companion dropped onto an installer's website (no "vision" or implementation talk in the video; the suggested implementation is for Q&A); no vest until the planner demo.

- **Reonic's line in scene 3:** still needs one confirmed sentence from the team on how reo connects to the Reonic system today (the draft says Reonic "already connects installers and their customers").

## Next

Build an **animatic** of scenes 1–4 (stills with timings and the VO as placeholder text) in HyperFrames, then replace each placeholder with the real motion, starting with 3.3 → 4.1–4.7 since `ReoIntro` is already there.
