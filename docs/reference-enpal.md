# Reference: what we take from Enpal (and where reo beats it)

Enpal (enpal.de) is Germany's biggest solar + heat pump seller and a Reonic-style funnel at scale. Walked through on Sat 7 Nov; humans own this file. Goal for us: **results faster, from less information, and nicer to use.**

## What Enpal does

- **Hero = the finished house.** The landing page is a house with panels on the roof, a car at the wallbox and a heat pump outside. One button: "Zum Haus-Check".
- **The "Haus-Check" is all taps, no typing.** Big picture cards and a progress bar ("19% geschafft"): interest (solar / heat pump / both) → building type (Einfamilienhaus, Doppelhaushälfte, Reihenhaus, …) → roof shape (Satteldach, Flachdach, Pultdach) → where the heating is → owner? → existing PV? → postcode. Never asks for kWh.
- **No number before the sales funnel.** Through the postcode step (64%) it has not shown a single size or price; the next steps lead to booking a consultation.
- **Simple money story.** "0 € Anzahlung", fixed price incl. installation, "in 6 weeks to your own system", a 5-step timeline.
- **Social proof with real systems.** Customer stories show city + system ("PV 8.6 kWp, battery 12.44 kWh, Bosch heat pump"). Battery sizes cluster on a few product sizes (5 / 10 / 12.4 kWh).

## Where reo wins (pitch this)

- **A number on the first tap**, not after a sales call. Then every answer visibly sharpens it.
- **Transparent:** every size and price comes with the reason, and the customer can ask "why?".
- **Grounded in what experts actually built:** "homes like yours" comes from ~1,600 real installer projects, not hand-picked testimonials.
- **The installer gets a ready plan, not a lead.** Planning hours drop to minutes; the installer's own prices and judgement stay in charge.

## What to change, by role

### engine (fast, from almost nothing)

1. **Design from zero facts.** `POST /design {facts: {}}` returns a complete design for a typical home (median of the data, wide `range`). Every fact only narrows it. No required fields.
2. **Accept easy proxies, not just kWh.** Add optional `HomeFacts`: `building_type` (`detached`, `semi`, `terraced`), `roof_type` (`gable`, `flat`, `mono`, `other`). Estimate demand from `num_inhabitants` (+ building type) when kWh is unknown, and list it in `assumptions`. kWh stays the precise path ("from your bill").
3. **Snap to packages.** Real installers sell bundles ("Complete Package 2: 10.8 kWp + 9 kWh"). Snap PV to module counts and battery to the few real product sizes, and name the bundle (S / M / L). Easier to explain, closer to expert decisions, faster to quote.
4. **Rank questions by impact.** For each missing field, evaluate the design over its plausible values; `impact` = how much the price range / PV size would move. This makes "fewest questions" principled, and gives reo a stop rule (offer the handoff once the range is narrow).
5. **Monthly framing.** Add `economics.bill_today_eur_per_month` and `bill_after_eur_per_month` next to savings and payback: "≈ €140 → €55 a month" lands harder than kWh. (No financing offers: persona forbids them.)
6. **Instant.** Pure function, < 100 ms, so the UI can update on every tap.

### reo (no waiting)

- **Taps skip the LLM.** A chip or card answer goes `/facts` → engine → templated reply from `experience/flow.md`, instantly. The LLM is only for free text and "why?" questions, and its text arrives after the numbers are already on screen.
- **First turn = first design.** Even "hello" returns the zero-fact design with a range, then one question.
- **Stop asking** when the engine has no `high`-impact `missing_inputs` left; offer the handoff.

### app / experience (the sexy part)

- **Tap-first chat.** Questions render as big picture cards inside the chat (house types, roof shapes, heating), like Enpal's Haus-Check, but each tap updates the plan live. Typing stays possible.
- **The house builds itself.** An illustrated house beside the chat: panels appear on the roof (count = engine module count), a battery in the garage, a car at the wallbox, a heat pump outside, each animating in as the engine adds it, out when removed.
- **Precision you can see.** Price range bar that narrows with every answer, plus a "plan accuracy" meter (already started in `app`).
- **Monthly bill before / after** as the headline number; total price and payback one level down.
- **"Homes like yours"** strip: aggregate from data's benchmarks ("Most similar homes chose 9–11 kWp").
- **Address = map moment** (mocked): pin drops, roof outline highlights, panel count updates.

## Do not copy

- Gating the result behind contact details.
- Urgency or "0 € down" financing claims: our persona rules them out, and the installer owns pricing and financing.
