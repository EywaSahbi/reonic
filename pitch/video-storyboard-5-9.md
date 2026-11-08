# reo product video — storyboard, scenes 5–9 (0:46–2:00), v2

> Continues [video-storyboard-1-4.md](video-storyboard-1-4.md); scenes 1–4 are built in `pitch/video/`.
> **v2 changes:** (1) scene 5 is **only the customer site**, one big window, with a **camera** (zoom in/out) and a **large pointer** that shows what is being clicked; the planner window comes in with scene 6. (2) The customer UI is rebuilt against the **latest app** (pulled at `cb69b75`, app up to `9289fa1`). (3) Scene 5 no longer mentions the engine being deterministic; trust is argued in scenes 6 and 8.

## The camera and the pointer (how the zooms work)

Yes, both are doable, and they are cleaner than a baked screen recording because they are **authored in the video, not recorded**.

| Piece | How |
|---|---|
| **Capture** | The real app is recorded once, in one continuous take, **without a cursor**, as a high-resolution clip: viewport 1440×900 at 2× (2880×1800), 30 fps, clean state. The clip is placed in a browser-style window frame. |
| **Pointer track** | The capture is driven by a script (or by hand with an injected logger) that writes `{t, x, y, down}` for every move and click to a JSON file. The video draws its **own pointer** from that track, so the pointer can be big, smooth and re-timed, and it always lands exactly where the real click happened. |
| **Pointer look** | 72 px arrow (≈ 2× a normal cursor on this canvas): ink `#1B1D20` fill, 6 px white outline, soft shadow (0 6 16 / 25 %). Hotspot = the tip. Moves between targets in 0.5–0.8 s on `power2.inOut`, decelerating into the target. **Press** = pointer scales 0.86 for 0.1 s then settles with a small back-out, while the app's own button press state shows. **No click rings** (a known generated-video tell). |
| **Camera** | The window is wrapped in a camera layer that animates `scale`, `x`, `y` (GSAP, seekable). Every move is aimed at a **target rectangle** in capture pixels, so "zoom to the step card" is one line of data. Moves: `power3.inOut`, 0.8–1.2 s, a short motion-blur on pans (6–12 px). The camera **never moves while a label is being read**: land, hold ≥ 0.8 s, then go. |
| **Zoom levels** | 1.0 = whole window (establishing). 1.5 = a card or a tile group. 1.9 = a single number. **Never above 1.9**, so the 2× capture stays sharp. |
| **Cuts inside the capture** | Waiting is cut out (typing sped 1.5–2×, loading hidden behind a whip). Cuts happen at the fastest frame of a camera move, never in a hold. |

**Why not a plain screen recording:** a baked recording gets a thin OS cursor and one fixed framing. Here the camera and pointer are data, so changing a zoom or slowing a click is an edit, not a re-record.

## What the customer UI is now (checked in the running app)

Opening **Plan my home** drops a full-screen **Energy advisor · Sonnfeld** sheet; the page behind it is blurred and dimmed. Left: the **3D house stage**, where the advisor character glides to what changed, speaks in a glass bubble, and status pills confirm each engine step (e.g. "Engine sized your system · 10.5 kWp · 24 panels · 12 kWh battery"). Right: one **question per screen** with a "Step n of 4" progress bar and tiles:

1. **Yearly electricity use** (number bar; "Don't know" falls back to **People at home** tiles)
2. **Your address** + Find roof (→ "Your roof" glows once a roof is found; a satellite roof photo is a second tab)
3. **Electric car?** Yes / Planned / No
4. **Current heating** Gas / Oil / Heat pump / Electric / District heating / Other (then an optional heating-use number)

**Results:** the stage on top (house with panels, wallbox, car), an **Ask your advisor** panel (chips: "Why this battery?", "What would make it cheaper?", "Is there funding?"), then **Your cost estimate** with the price range marked *estimate*, "Tap any number to see why.", and tiles **Savings / yr · ROI · Own power** (payback is now labelled ROI). Then **Send plan to Sonnfeld** → name and email.

> Checked against the **mock** build on :5183: step 1 started at *People at home*. The live backend starts at *Yearly electricity use* (`experience/flow.md`). **The capture must run on the live stack** so the numbers are the engine's; mock numbers (e.g. €38,800–48,400) must never appear in the film.

## Last frame of scene 4 → first frame of scene 5

Scene 4 ends with reo centred, hands on the homeowner's bubble (left) and the "Ready offer" card (right). **Object becomes the world:** the bubble grows (0.65 s, ease-in-out, radius shrinking) into the **customer window**, filling the centre at 1600×1000. The "Ready offer" card slides off to the right (it returns as the planner window in scene 6). reo shrinks into the window's advisor spot on the page and stays there.

---

## Scene 5 — "A few taps" (0:46–1:10) · customer window only

**Voice-over:** "On Sonnfeld's website, an energy advisor talks to the homeowner in the installer's name. A few taps: their usage, an address, a car, a heating system. And they get a design, a price range, and a reason for every number. Tap any number, and the advisor explains it."

| Shot | Time | What the capture shows | Camera | Pointer | VO / SFX |
|---|---|---|---|---|---|
| 5.1 | 0:46–0:50 | Bubble grows into the **Sonnfeld homepage** (hero, "Plan my home" pill, the advisor under it). Coral label above the window: "Homeowner". | 1.0 establishing, still. | Enters from the right edge, glides to **Plan my home**, presses. | "On Sonnfeld's website…" · soft grow, then click |
| 5.2 | 0:50–0:54 | The advisor sheet drops in, page blurs. **Step 1: Yearly electricity use.** Type **4500**, Next. | Push to **1.5** on the step card (right half) as the sheet lands; hold while it types. | Moves to the number bar, presses (caret), then to **Next**, presses. | "…an energy advisor talks to the homeowner…" · key ticks |
| 5.3 | 0:54–0:58 | **Step 2: Your address.** Type **Musterstraße 12, 80331 München**, **Find roof**. The roof is found: the house stage glows "Your roof". | 1.5 on the card, then **pans left to the stage** (1.3) as "Your roof" glows; hold on the glow. | Press **Find roof**, then the pointer **leaves the card and points at the glow** on the stage. | "A few taps: their usage, an address…" · tap pop, soft glow chime |
| 5.4 | 0:58–1:01 | **Step 3: Electric car? → Planned.** The car and wallbox appear on the 3D house. **Step 4: Current heating → Gas.** (heating-use step: *Don't know*.) | Back to 1.5 on the tiles, a **whip** (0.2 s) between steps. Quick hold on the car appearing (1.2). | Presses **Planned**, then **Gas**, then **Don't know**; one 0.5 s hop each. | "…a car, a heating system." · pop per tile |
| 5.5 | 1:01–1:05 | **Results.** The stage builds panels and the pills confirm sizes; **Your cost estimate** appears, price range marked *estimate*; tiles **Savings / yr · ROI · Own power**. | **Zoom OUT to 1.0** to show the whole results page (the reveal), hold 1 s; then **push to 1.9 on the price range** ("estimate" legible); then a slow pan down across the three tiles at 1.5. | Rests off to the side during the reveal; then travels to the **estimate** and the **Savings** tile. | "And they get a design, a price range, and a reason for every number." · soft panel clicks as modules land |
| 5.6 | 1:05–1:08 | **Tap any number to see why.** Tap **Savings / yr**; the advisor's glass bubble explains it on the house. Optional: a chip in **Ask your advisor**. | Camera **swings to the stage** (1.5) so bubble + number are both in frame; hold for the reading time. | **Presses the Savings number**; the pointer then waits (a still pointer is a hold). | "Tap any number, and the advisor explains it." · pop |
| 5.7 | 1:08–1:10 | Scroll to **Send plan to Sonnfeld**, name **Anna Demo**, **Send plan**. The sent banner. | Back out to 1.0 as the banner lands. | Presses **Send plan** (the film's one big press: 0.86 scale, longer settle). | silence · whoosh as the plan leaves |
| (hand-off) | 1:09.5–1:10 | The plan leaves the window as a card and **flies right**; the window slides left and settles at 880 px wide, the **gap** opens, the right half is empty. | Whole-window slide, `power3.inOut`. | — | whoosh across the gap |

**Capture plan (one continuous take):** local live stack (engine, reo, app), "Start over", voice off, exact inputs `4500` · `Musterstraße 12, 80331 München` · EV *Planned* · heating *Gas* · heating use *Don't know* · name **Anna Demo**. Record the **actual** price range, kWp and savings from this run and use only those if a number is ever shown as text. Re-record after the code freeze (M3) if the UI changes.
**Frames to review:** K7 (5.2, step card at 1.5 with big pointer on Next), K8 (5.3, "Your roof" glow with the pointer pointing at it), K9 (5.5 at 1.9, price range + *estimate*), K10 (5.6, bubble explaining Savings).

---

## Scene 6 — "Already working" (1:10–1:26) · planner window (16 s, was 18)

**Voice-over:** "Meanwhile, reo is already working for the planner. It compares similar homes, builds three designs, drafts the offer, and checks every number against the engine. Then it asks. Nothing happens until the planner says yes."

| Shot | Time | Frame | Camera / pointer | VO / SFX |
|---|---|---|---|---|
| 6.1 | 1:10–1:13 | The **planner window** slides in on the right (emerald edge, label "Planner"). The sent plan lands as a new inbox row "Anna Demo"; open it. **reo appears in the planner view wearing the vest** (first use, small pop-in). | The customer window dims to 60 %; the camera pushes to the planner window at 1.0→1.2. Pointer opens the row. | "Meanwhile, reo is already working for the planner." |
| 6.2 | 1:13–1:18 | **Offer pack** timeline streams (reads the plan → compares ~1,100 similar homes → three engine designs → drafts the message → ✓ numbers verified). Show ~5 s of the ~15 s run. | 1.5 on the timeline, a hold on the green **numbers verified** tick (1.2 s) with a callout. Pointer stays still (nothing to click). | "It compares similar homes, builds three designs, drafts the offer, and checks every number against the engine." |
| 6.3 | 1:18–1:21 | The three **variant cards** and the **Quotation** card; the planner selects one. | Pull to 1.0; pointer selects a variant (edge turns emerald). | · click |
| 6.4 | 1:21–1:26 | **Proposed action** "Book site visit" with *Approve / Reject*. Cursor goes to **Approve**. | Push to 1.9 on the button; everything holds 0.5 s before the press. | "Then it asks. Nothing happens until the planner says yes." · single firm click |

## Scene 7 — "The planner stays in charge" (1:26–1:36)

**Voice-over:** "The planner stays in charge: change anything, and every number re-derives. The estimate becomes a confirmed quote, in the installer's own words."

| Shot | Time | Frame | Camera / pointer | VO / SFX |
|---|---|---|---|---|
| 7.1 | 1:26–1:30 | **Design studio**: drag two modules off the roof, **Apply to plan**; the re-derive banner shows the change. | 1.5 on the studio; the big pointer **drags** (pressed state held) and releases; callout "Re-derived". | "…change anything, and every number re-derives." |
| 7.2 | 1:30–1:33 | Note, **Finalise and send quote**. *Quote sent*. | 1.5 on the button, a press. | · click |
| 7.3 | 1:33–1:36 | Customer window back to full: **"Your planner has confirmed your plan … (confirmed by Sonnfeld)"**, card *Estimate* → **Confirmed quote**. **The gap closes:** the windows slide together; coral and emerald edges merge into the sunset gradient. | Whole-frame, no zoom. | "The estimate becomes a confirmed quote, in the installer's own words." · two-part click as they meet |

## Scene 8 — "Tested on homes it never saw" (1:36–1:52), on paper

Voice-over: "You can only trust an agent you can check. On 235 homes it never saw, the engine beats the baseline on solar size. Batteries are still hard, and we say so. Its biggest miss taught reo the question to ask."

| Shot | Time | Frame |
|---|---|---|
| 8.1 | 1:36–1:40 | **235** counts up (hero number) over a field of 235 dots; "homes the engine never saw". |
| 8.2 | 1:40–1:44 | **49 % vs 42 %** bars (engine in sunset, baseline neutral): "Solar size within ±20 % of the expert"; "Median miss 1.9 kWp". |
| 8.3 | 1:44–1:48 | **Honest beat**: "Battery size: 39 % vs 42 %", engine bar shorter, in amber: "Still hard. We say so." Silence. |
| 8.4 | 1:48–1:52 | 52 dots, 49 highlighted ("49 of 52 'no solar' misses already had solar") collapse into the question bubble **"Do you already have solar?"**. |

Numbers come only from data's frozen M3 report (`data/reports/reality_check_test.md`); **hold 8.3 until data republishes** (the engine's own re-score says 45.6 %, the published report 39 %).

## Scene 9 — "Two sides, one gap" (1:52–2:00), close

Voice-over: "Two sides, one gap. reo does the work in between." A coral shape and an emerald shape slide in with a gap between them (1:52); reo drops into the gap and the **`ReoIntro` lockup** builds with *in between* in the sunset gradient (1:55); hold, one blink, the demo URL (1:58–2:00). **Open:** the live demo is behind a demo PIN; decide URL-only, PIN, or a QR.

---

## Voice-over lines to append (global seconds, draft; `vo.json` is untouched until the engine agent's first run lands)

| id | start | until | text |
|---|---|---|---|
| 11-sonnfeld | 46.6 | 51.4 | On Sonnfeld's website, an energy advisor talks to the homeowner in the installer's name. |
| 12-taps | 52.0 | 57.4 | A few taps: their usage, an address, a car, a heating system. |
| 13-design | 61.2 | 65.6 | And they get a design, a price range, and a reason for every number. |
| 14-explain | 65.8 | 68.6 | Tap any number, and the advisor explains it. |
| 15-planner | 70.4 | 73.2 | Meanwhile, reo is already working for the planner. |
| 16-work | 73.4 | 80.8 | It compares similar homes, builds three designs, drafts the offer, and checks every number against the engine. |
| 17-asks | 81.4 | 86.0 | Then it asks. Nothing happens until the planner says yes. |
| 18-charge | 86.2 | 91.8 | The planner stays in charge: change anything, and every number re-derives. |
| 19-confirmed | 93.2 | 96.0 | The estimate becomes a confirmed quote, in the installer's own words. |
| 20-trust | 96.3 | 99.8 | You can only trust an agent you can check. |
| 21-tested | 99.9 | 104.2 | On 235 homes it never saw, the engine beats the baseline on solar size. |
| 22-batteries | 104.3 | 108.0 | Batteries are still hard, and we say so. |
| 23-miss | 108.2 | 112.0 | Its biggest miss taught reo the question to ask. |
| 24-close | 112.2 | 118.0 | Two sides, one gap. reo does the work in between. |

Removed from v1: "Every number comes from a deterministic engine. The advisor only explains." (scene 5 now says only that the advisor explains a number when tapped.)

## Sound

No music before the reveal; a soft bed enters at 34.9 and ducks 12 dB under the voice. Effects only on visible actions: click, tap pop, key ticks, whoosh when the plan leaves. Silence on the battery beat. (Music source still open.)

## What exists vs what is new

| Item | Status |
|---|---|
| Customer UI (latest) | **exists** in `app/`; verified in the mock build, **to be recorded on the live stack**. |
| Capture script + pointer track (`{t,x,y,down}`) | **new** (small script; falls back to an injected logger on a manual take). |
| Camera layer (zoom/pan to target rects), big pointer overlay, window frame | **new**, built in HyperFrames; the capture is a `<video>` inside it. |
| Object-becomes-world (bubble → window), hand-off slide, gap closing | **new**. |
| reo in a vest, pop-in | avatar **exists**, pop-in new. |
| Scene 8 motion graphics, scene 9 close | **new** / `ReoIntro` lockup **exists**. |
| Music bed | **not sourced**. |

## Open decisions

- **Live stack for the capture:** local engine + reo + app (I will start it; takes a few minutes) vs the deployed `sonnfeld-reo.vercel.app` (PIN gate, not redeployed since the Living advisor work). Recommendation: local live stack.
- **Pronoun** in the VO ("they" is used).
- **Battery number** (8.3) and **end-card URL / PIN / QR** (9).
- **Music**: have a track, or let me source one?

## Next

1. Start the live stack, do one clean customer take with the pointer logger on.
2. Build scene 5 in HyperFrames: window frame, camera keyframes from target rects, big pointer from the track, bubble → window transition, hand-off.
3. Then scene 6 (planner capture), scene 7, then the pure-motion scenes 8–9.
