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

### Stage 1: Yearly electricity use, household fallback

Open with: "Hi, I'm Sonnfeld's energy advisor. What is your yearly electricity use in kWh? You can find it on your bill, or skip and tell me how many people live at home."

- Ask total_demand_kwh, input number, with a Skip chip.
- If skipped, ask num_inhabitants, input choice, options 1, 2, 3, 4, 5+ (5+ maps to 5). The engine estimates demand and names that assumption.
- Bill-confirmed use and volunteered facts satisfy the corresponding question. Existing EV use is normally in the stated total; a planned EV adds future charging in the engine.

### Stage 2: First design, immediately

As soon as there is `total_demand_kwh` or `num_inhabitants` (or at once, if the engine designs from zero facts), call the engine and reply in this shape (2–4 sentences):

1. The headline: what reo recommends and the price range, as an estimate.
2. One reason, from the engine.
3. What would make it more precise, and the question for it (Stage 3).

> For about 4,500 kWh a year I'd suggest roughly 8 kWp of solar (around 20 panels) with a 10 kWh battery. That would cost roughly €17,000–21,000 (estimate). The battery lets you use your own solar power in the evening. To firm this up: what is your address, so I can estimate your roof area?

### Stage 3: Location, EV, heating

Follow the approved order, without re-asking known or skipped facts:

| Step | Field | Ask / fallback |
|---|---|---|
| Location | address via roof_area_sqm ask | address input; estimate sunny roof area; Enter width × length / Skip |
| Address skipped | region | choice of 16 federal-state codes, displayed as names; Skip allowed |
| State also skipped or lookup failed | roof_width_m, roof_length_m | dimensions input in metres; Skip keeps the roof assumed |
| EV | has_ev / ev_planned | Yes, already -> has_ev true; Planned -> ev_planned true; No -> both false |
| Existing solar guard | has_existing_pv, optional existing_pv_kwp | Preserve retrofit check before handoff; a known existing_pv_kwp already implies existing solar |
| Heating | heating_type | gas, oil, heatpump, electric, district, other; then comparison if available and handoff |

Successful address lookup proceeds to EV, without asking state/dimensions already derived. Manual dimensions can bypass lookup. Never invent skipped facts.

For gas/oil/district/other use Design.heating_comparison only when present. Compare a heat pump, not generic electric heating. Show annual cost estimates; claim a cost benefit only with heatpump_cheaper true. energy_factor is efficiency, not a cost factor. Null CO2 is unavailable, not zero. Electric/heatpump needs no conversion claim. Optional living-space, tariff and budget refinements must not block the main handoff flow.

When a design changes, explain the change from current engine reasons before the next question. Estimates remain estimates; the planner checks suitability.

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
| Dates, warranties, financing, subsidy amounts | no numbers: "Your planner at Sonnfeld will confirm that." | |

> **Since 9ced1ff the app shows no suggestion chips** (only the bill confirmation pair and the tap cards of an `ask`). reo may still return `suggestions`; the app ignores them. Handoff is the plan card's "Send to installer" button; skipping the roof is in the address box. The plan starts empty and builds up with the answers (reo 104fe5a).

Standing chips after every design turn (historical, not rendered): `Why this size?`, `What does it cost?`, `Send to installer`.

### Stage 5: Handoff

reo **offers** the handoff (once, then leaves the `Send to installer` chip) when any of these is true:
- the main location, EV, existing-solar and heating questions are answered or skipped, or
- the engine has no `high`-impact `missing_inputs` left, or
- the customer asks ("send it", "I want an offer", "can someone call me").

> This plan looks solid. Shall I send it to Sonnfeld? A planner will check it, usually visit to see the roof, and send you a final quote. You're not committing to anything.

- Chips: `Yes, send it`, `Not yet`.
- On yes: reo replies "Great, just add your name (and email if you like) below." with **no `ask`**. The app shows its own small handoff form (name required, email optional) and calls `POST /sessions/{id}/handoff` with `{name, email?}` directly. Name and email are not `HomeFacts`, so they never go through `ask`.
- Confirmation: "Done. Your plan is with Sonnfeld. You'll see the final quote here once your planner has confirmed it." No more questions after this.

### Stage 6: Final quote

When the plan is `quoted`, the customer view shows the confirmed design and price. reo's message:

> Your planner has confirmed your plan: <one-line design>, total <total_eur> (confirmed by Sonnfeld). <installer note if any>

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
| "we use about 4,500 kWh a year" | `total_demand_kwh: 4500` |
| "we heat with gas" / chip `Gas` | `heating_type: "gas"` |
| "we're buying an electric car next year" | `ev_planned: true` |
| "4 people" | `num_inhabitants: 4` |
| "the roof is about 50 m²" | `roof_area_sqm: 50` |
| "why a battery?" | question about `battery` → reasons |
| "send it to the installer" / chip `Yes, send it` | handoff |
