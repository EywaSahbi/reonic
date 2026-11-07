# reo — visual brand

> Owner: `RaneemK-commits` (app). Extracted from reonic.com/de-de (Sat 7 Nov) so reo looks like it belongs to Reonic. Tokens below are measured from the live CSS unless marked *(by eye)*.
> Use the style, not Reonic's assets: no copied logo files or images. Write "Reonic" as text.

## The feel

Calm, light, precise software, with one warm burst of energy. Near-white warm paper, near-black ink, neutral greys (Tailwind **zinc**), lots of whitespace, tight bold headlines. Colour arrives as a **warm sunset gradient** (orange → coral → peach) on hero words and feature cards, and as small **emerald** status pills. Product shots float on soft, large shadows. Buttons are black pills.

## Colour tokens

```css
:root {
  /* surfaces */
  --paper:        #FDFDFB;  /* page background (warm off-white) */
  --paper-warm:   #FBFAF7;  /* alternate section background */
  --paper-sand:   #F7F5EF;  /* subtle cards / chips */
  --white:        #FFFFFF;  /* cards on paper */

  /* ink (zinc scale) */
  --ink:          #1B1D20;  /* headlines, logo, primary button */
  --ink-950:      #09090B;  /* body text */
  --ink-700:      #3F3F46;  /* secondary text */
  --ink-500:      #71717A;  /* muted text, captions */
  --ink-400:      #A1A1AA;  /* placeholders, dividers on dark */
  --line:         #E4E4E7;  /* borders, hairlines */
  --line-strong:  #D4D4D8;

  /* accents */
  --success:      #10B981;  /* emerald-500: "Stark" pills, progress bars, positive deltas */
  --warning:      #F59E0B;  /* amber-500: "Mittel" pills, assumptions, flags */
  --info:         #53BDEB;  /* sky: small icons, links in diagrams */
  --danger-soft:  #FDE7E7;  /* (by eye) light red tint for warnings */

  /* the Reonic gradient (their gradients are images; stops by eye) */
  --sunset: linear-gradient(120deg, #F7A35C 0%, #F2784B 45%, #EE6A5B 70%, #F3A6A0 100%);
  --sunset-text: linear-gradient(90deg, #F59E4C, #F28A5E);   /* hero keyword, e.g. "KI-Betriebssystem" */

  /* dark panels (in-product screenshots on gradient cards) */
  --night: linear-gradient(135deg, #3F3F46 0%, #27272A 50%, #09090B 100%);
}
```

Rules:
- Background is always paper or white; never a full-page gradient. The sunset gradient is for **one hero word** (gradient-filled text) and **feature cards** (white text on gradient, phone/panel mock on top).
- Emerald and amber only for small status things (pills, progress, deltas), never large areas.
- Text on the sunset gradient: white. Text on paper: ink.

## Typography

- **Geist** (sans) for everything: free, `npm i geist` or Google Fonts "Geist". Fallback: Inter, system-ui.
- **Noto Serif** (regular, upright) only for quotes / testimonials, e.g. reo's "homes like yours" quotes or a customer quote in the pitch. The challenge brief also uses a serif italic for one emphasised word ("*minutes,* not hours"): fine for one word per screen, no more.

| Role | Size / line height | Weight | Letter spacing | Colour |
|---|---|---|---|---|
| Hero (h1) | 50 / 1.0 (≈ 40–52 px) | 600 | −1 px | ink; key word in `--sunset-text` |
| Section (h2) | 36 / 1.1 | 600 | −0.72 px (−2%) | ink |
| Card title (h3) | 24 / 32 | 700 | 0 | ink, or white on gradient |
| Lead paragraph | 18 / 28 | 400 | 0 | `--ink-500` |
| Body | 16 / 24 | 400 | 0 | `--ink-700` |
| Label / button | 14 / 20 | 500–600 | 0 | — |
| Pill | 10–12 | 500 | 0 | white on emerald/amber |

Headlines are short and declarative, often two lines: a statement, then the audience ("Das KI-Betriebssystem / für Installateure erneuerbarer Energien.").

## Shape, depth, spacing

- **Radius:** buttons and pills fully round (`9999px`); inputs and small cards 10 px (`--radius: .625rem`); cards 14–16 px; big feature cards and media 24–32 px.
- **Shadows:** soft and large for floating product shots: `0 22px 70px rgba(0,0,0,.14)`; small UI: `0 1px 3px rgba(0,0,0,.1), 0 1px 2px -1px rgba(0,0,0,.1)`. Dark buttons get a subtle inset bevel: `inset 0 1px 0 rgba(255,255,255,.08), inset 0 -1px 0 rgba(0,0,0,.35)`.
- **Space:** generous. Sections ~96–128 px apart, content max-width ~1100 px, 24 px card padding.
- **Icons:** thin line icons (Lucide style), ink colour, 16–20 px, next to labels.

## Components (how reo should look)

- **Primary button:** black pill (`--ink` bg, `--paper` text, 14 px / 500, 8×16 padding, icon on the right like "↗"). Secondary: text link in ink with an arrow.
- **reo chat widget:** white card, 16 px radius, big soft shadow, floating bottom-right of the installer site. Header: small reo mark + "reo · powered by Reonic". reo's bubbles on `--paper-sand`, customer bubbles in `--ink` with white text. Quick-reply chips: white pills with a `--line` border, ink text.
- **Picture-card questions:** white 14 px cards, line illustration on top, label below, `--line` border → ink border + light sunset tint when selected.
- **Plan card:** white card; component rows with line icons; sizes in ink 600; price range bar in zinc with the narrowing range in `--sunset`; assumptions as amber pills, confirmed facts as emerald.
- **Precision / confidence:** thin rounded bars like Reonic's lead-score card (emerald fill on zinc track) with a short label ("Stark", "Mittel").
- **Installer dashboard:** the Reonic product look: paper background, white panels, zinc hairlines, black pill actions, emerald/amber pills for flags. A score ring (like the lead score "85") works well for plan confidence.
- **Hero / feature moments** (landing page, pitch slides): a sunset-gradient card with white headline + a dark (`--night`) phone or panel mock showing reo in action.

## Voice on screen

Matches `persona.md`: short, plain, confident. Reonic's own copy uses "du" and active verbs ("Plane PV-Anlagen…, erstelle Angebote…"). reo's customer chat uses "Sie" (persona.md), the installer view can use "du" like Reonic's product.
