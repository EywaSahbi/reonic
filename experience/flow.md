# reo — conversation flow

> Owner: `RaneemK-commits` (app). The reo backend follows this for stages, question order, `ask` inputs, chips and the handoff.
> Field names are `HomeFacts` from [engine/CONTRACT.md](../engine/CONTRACT.md); `ask` / `suggestions` are `Turn` from [reo/CONTRACT.md](../reo/CONTRACT.md).
> Want to change the order or wording? `NEED` to app.

## Principles

1. **Useful answer every turn.** From the first fact on, every turn returns a full engine design, so the plan card always shows something.
2. **One question per turn**, highest impact first. The customer can skip any question; reo keeps going on the engine's assumptions and says which one it used.
3. **The customer can lead.** If they volunteer facts or ask "why?", handle that first, then come back to the next open question.
4. **Never re-ask** a fact that is already in `plan.facts` (or that the customer skipped, unless they bring it up).

## Customer side

### Stage 1: Hello (tap-first, no kWh needed)

Most people don't know their kWh. reo opens with something everyone can answer with one tap; kWh stays the precise option for people who have their bill at hand.

Opening message (`POST /sessions`). If the engine accepts `facts: {}`, include the typical-home design in this turn so the plan card already shows a wide range; otherwise the first design comes after the first tap.

> Hi, I'm reo, the energy advisor at SolarHaus Müller. A few taps and I'll sketch your solar system with a price estimate. To start: how many people live in your home?

- `ask`: `{field: "num_inhabitants", prompt: "People in your home", input: "choice", options: ["1", "2", "3", "4", "5+"]}` (the app renders `choice` asks as big tap cards; `5+` → `num_inhabitants: 5`)
- `suggestions`: `["I know my yearly kWh"]`
- `I know my yearly kWh` → `ask` `{field: "annual_demand_kwh", prompt: "Yearly electricity use (kWh, from your bill)", input: "number"}`, chips `["About 3,000 kWh", "About 4,500 kWh"]`.
- Free text works at any point: "we use about 4,500 kWh a year" → `annual_demand_kwh: 4500` (the demo opens this way).

### Stage 2: First design, immediately

As soon as there is `annual_demand_kwh` or `num_inhabitants` (or at once, if the engine designs from zero facts), call the engine and reply in this shape (2–4 sentences):

1. The headline: what reo recommends and the price range, as an estimate.
2. One reason, from the engine.
3. What would make it more precise, and the question for it (Stage 3).

> For about 4,500 kWh a year I'd suggest roughly 8 kWp of solar (around 20 panels) with a 10 kWh battery. That would cost roughly €17,000–21,000 (estimate). The battery lets you use your own solar power in the evening. To firm this up: how do you heat your home today?

### Stage 3: Refine, highest impact first

Ask for the open fields in this order. If the engine's `missing_inputs` ranks a field as `high` that is further down, ask it first.

| # | Field | Prompt (say why) | `ask` | Chips |
|---|---|---|---|---|
| 0 | `building_type` *(once engine ships it)* | "What kind of house is it? That tells me roughly how much roof and heating you have." | `choice`, options `detached, semi, terraced` | none (cards) |
| 1 | `heating_type` | "How do you heat today? That decides whether a heat pump makes sense." | `choice`, options `gas, oil, heatpump, electric, district, other` | `Gas`, `Oil`, `Heat pump already`, `Other` |
| 2 | `has_ev` / `ev_planned` | "Do you have an electric car, or plan to get one? It changes the solar size and adds a wallbox." | `choice`, field `has_ev`, options `Yes, already`, `Planned`, `No` | same as options |
| 3 | `roof_area_sqm` | "How big is the roof area that faces the sun? Or give me your address and I'll look it up." | `address` (falls back to `number` if lookup fails) | `Use my address`, `About 40 m²`, `Not sure` |
| 4 | `house_size_sqm` (+ `house_built_year`) | only if a heat pump is in play: "How big is the living space, and roughly when was the house built? That sizes the heat pump." | `number` | `About 120 m²`, `About 160 m²` |
| 5 | `electricity_price_eur_per_kwh` | "What do you pay per kWh? I've assumed a typical rate so far." | `number` | `About 35 ct`, `About 40 ct`, `Not sure` |
| 6 | `budget_eur` | "Do you have a budget in mind? Then I can show what fits." | `number` | `Under €15,000`, `€15,000–25,000`, `No fixed budget` |

Prefer `choice` asks wherever the answer has a few options: the app shows them as picture cards and every tap updates the plan live. `roof_type` (`gable, flat, mono, other`) can join row 3 once the engine ships it. Stop asking once the engine has no `high`-impact `missing_inputs` left, and offer the handoff (Stage 5).

Mapping notes for reo:
- EV chip `Yes, already` → `has_ev: true`; `Planned` → `ev_planned: true`; `No` → both `false`. Free text like "we're buying an electric car next year" → `ev_planned: true`.
- `Not sure` / `I don't know` / skip → leave the field empty, move to the next question, mention the assumption once: "I'll assume a typical roof for now."
- `has_existing_pv`, `has_existing_battery`: don't ask; pick them up if the customer mentions them.

**When the design changes**, start the reply with what changed and why, before the next question:

> Since you're getting an electric car, I've raised the solar to about 10.5 kWp and added an 11 kW wallbox. The new estimate is roughly €22,000–25,500. Next: how big is your roof, or shall I look up your address?

### Stage 4: Questions welcome, at any point

Answer from the engine's `reasons`, price `items` and (M2) `/explain` what-ifs, then return to the open question.

| Customer asks | reo answers from | Chips to offer afterwards |
|---|---|---|
| "Why a battery?" / "Why no heat pump?" | `components.<key>.reasons` | `What if I skip it?` |
| "Why does it cost that much?" | the 2–3 largest `price.items` | `What would make it cheaper?` |
| "What if we skip the battery?" | fresh engine call with lock `{recommended: false}`, or `/explain` what-if | `Keep the battery`, `Without battery` |
| "How much will I save?" | `economics.annual_savings_eur`, `payback_years` | |
| "Is there funding?" | general only, no amounts: "Heat pumps can qualify for federal funding; your planner will check what applies to you." | |
| "Is this normal for a home like mine?" | the plan's `flags` / benchmarks, aggregate only: "Most similar homes went with a battery around this size." | `Why this size?` |
| Dates, warranties, financing, subsidy amounts | no numbers: "Your planner at SolarHaus Müller will confirm that." | |

Standing chips after every design turn (when nothing more specific fits): `Why this size?`, `What does it cost?`, `Send to installer`.

### Stage 5: Handoff

reo **offers** the handoff (once, then leaves the `Send to installer` chip) when any of these is true:
- heating type and EV are known (the two facts that change the design most), or
- the engine has no `high`-impact `missing_inputs` left, or
- the customer asks ("send it", "I want an offer", "can someone call me").

> This plan looks solid. Shall I send it to SolarHaus Müller? A planner will check it, usually visit to see the roof, and send you a final quote. You're not committing to anything.

- Chips: `Yes, send it`, `Not yet`.
- On yes: reo replies "Great, just add your name (and email if you like) below." with **no `ask`**. The app shows its own small handoff form (name required, email optional) and calls `POST /sessions/{id}/handoff` with `{name, email?}` directly. Name and email are not `HomeFacts`, so they never go through `ask`.
- Confirmation: "Done. Your plan is with SolarHaus Müller. You'll see the final quote here once your planner has confirmed it." No more questions after this.

### Stage 6: Final quote

When the plan is `quoted`, the customer view shows the confirmed design and price. reo's message:

> Your planner has confirmed your plan: <one-line design>, total <total_eur> (confirmed by SolarHaus Müller). <installer note if any>

If the installer changed something, say what in one sentence ("Your planner adjusted the battery to 12 kWh after checking your usage"). This is the only point where reo drops the word "estimate".

## Installer side

### Plan summary (top of plan detail)

One paragraph, in this order, colleague tone (see persona):

1. **The home:** demand, people, heating, EV, roof, and which of these are assumptions.
2. **What the customer cares about:** from the transcript (e.g. "asked twice about cost", "wants to be ready for an EV").
3. **Proposed system and price:** components with sizes, total and range, payback.
4. **Needs your attention:** open questions (`missing_inputs`), assumptions, and `flags` ("Battery larger than 85% of similar homes").

Example:

> 4-person home, 4,500 kWh/yr, gas heating, EV planned next year; roof area assumed (no address given). Customer asked twice about cost and wants to be ready for the EV. Proposal: 10.5 kWp PV, 10 kWh battery, 11 kW wallbox, no heat pump yet; €23,800 (range €22,000–25,500), payback ~11 yrs. Check: roof area is an assumption; battery is larger than 85% of similar homes.

### Edits

- The planner can lock, resize or toggle any component, change facts, and edit prices. reo re-runs the engine and replies in 1–2 sentences with what changed downstream (sizes, total, payback). The UI highlights the changed lines.
- Never undo or argue an edit. If it creates an issue (e.g. PV larger than the roof allows), say it once.

### "Ask reo why"

The planner asks about any decision; reo answers from engine reasons, what-ifs and the plan's flags and similar projects. Individual similar real projects may be mentioned here (the customer chat gets aggregate comparisons only).

### Finalise

`Finalise and send` → plan becomes `quoted` → the customer sees Stage 6. Optional note from the planner is passed through verbatim.

## Demo phrases (scripted fallback must handle these)

These are the exact inputs in the demo; without an API key reo must still extract the facts:

| Customer types | Facts |
|---|---|
| "we use about 4,500 kWh a year" | `annual_demand_kwh: 4500` |
| "we heat with gas" / chip `Gas` | `heating_type: "gas"` |
| "we're buying an electric car next year" | `ev_planned: true` |
| "4 people" | `num_inhabitants: 4` |
| "the roof is about 50 m²" | `roof_area_sqm: 50` |
| "why a battery?" | question about `battery` → reasons |
| "send it to the installer" / chip `Yes, send it` | handoff |
