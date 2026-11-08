# reo presentation (parts 1–5)

HTML deck mirroring the video, scenes 1–5. Open `index.html` in a browser (works offline: GSAP and Geist are vendored).

- **Next / back:** click (left 15% of the screen = back), `→` `Space` `Enter` / `←`, `Home` `End`, `F` fullscreen. Each click plays one animated build; after the last build of a part, the next part transitions in. URL hash `#4.2` jumps to part 4, build 2.
- **PDF:** `node export-pdf.mjs` writes `reo-presentation.pdf` (1920×1080, one page per part, final state of each part). `--png` also writes a PNG per page. Needs Chrome or Edge (set `CHROME_PATH` otherwise); reuses `../video/node_modules/puppeteer-core`. Print view alone: `index.html?print`.
- **Builds per part:** 1 One number (3) · 2 Same questions (4) · 3 The turn (2) · 4 Meet reo (5, the video's own `meet` animation, clicks map to its clock) · 5 A few taps (7) · 6 Already working (3) · 7 The planner stays in charge (5). Team (2, before part 5) · Live demo with QR (2, before the close) · Then an Interlude (the meme, 2) · 8 Business impact (3) · 9 Environmental impact (2) · 10 Two sides, one gap, ending on "Reo, the AI companion for Installers" (3). Parts 6–7 use stills from `../video/capture/out/planner.mp4`.
- Real app screens in `assets/shots/` come from `../video/assets/customer-capture.mp4`.

Adding more parts: add a `<section class="slide" id="sN">`, a `buildN()` that returns a paused GSAP timeline with labels `b0…bn`, and register it in the `deck` array.
