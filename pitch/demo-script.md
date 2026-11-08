# reo — five-minute demo script (draft v1)

> Owner: `RaneemK-commits` (app). Draft for rehearsal; qa rehearses it and reports where it breaks.
> Story from `docs/plan.md` (demo story + phase 2 step 3). Every number on screen comes from the engine in that turn; say "estimate" for customer prices.

## Setup (before the judges arrive)

| What | Command / check |
|---|---|
| engine on :8000 | `cd engine && uv run uvicorn api:app --port 8000` → `curl localhost:8000/health` |
| reo on :8001 | `cd reo && uv run uvicorn api:app --port 8001` → `curl localhost:8001/health` shows `"engine": true` (and `"llm": true` if `reo/.env` has the Anthropic key) |
| app on :5173, live | `cd app && VITE_API_URL=http://localhost:8001 npm run dev` (PowerShell: `$env:VITE_API_URL='http://localhost:8001'; npm run dev`) |
| Two browser windows | **A** customer: `http://localhost:5173/` · **B** planner: `http://localhost:5173/#/installer` |
| Clean state | In window A: reo → "Start over". Old plans in B's inbox are fine; the new one appears on top. |
| Fallbacks ready | Recording of this exact run (see bottom); deck open on the validation slide; report PNGs from `data/reports/` as backup |

Models (reo 7848076): chat on Haiku 5.5 (~4 s per typed reply, taps < 0.2 s), offer agent on Sonnet 5.5 (~15 s). Without a key everything runs scripted with the same screens.

## The run (target 5:00)

### 0:00 — The problem (20 s, slide or spoken)

> "An installer's planner spends hours turning 'we use about 4,500 kWh' into a system design and a quote. Homeowners wait days for a number. reo does the first draft in two minutes, explains every number, and hands the planner a ready offer, not a lead."

### 0:20 — Sonnfeld's website (window A)

- Show the homepage: a normal installer site. "This is Sonnfeld, an installer. reo runs on their website under their own name: white-label, no Reonic branding for their customers."
- Click **Plan my home** (the character in the middle). The page pulls back, the advisor sheet slides down.

### 0:40 — Minimal facts → instant first design

| Do | Expect on screen | Say |
|---|---|---|
Question order (reo `c53ba6c`): yearly kWh → address → EV → heating → existing solar → handoff offer. Skipping kWh asks for household size; skipping the address asks for the federal state, then roof width × length.

| Do | Expect on screen | Say |
|---|---|---|
| Type: **we use about 4,500 kWh a year** | First design in the plan card: PV, battery, price range marked *estimate*; the house fills with panels | "One sentence, and it already has a design and a price range, from a deterministic engine, not the LLM." |
| Address ask: type **Musterstraße 12, 80331 München** | "I looked up your address: …" 48 m², south, 35°, Bavaria; PV re-derived to fit the roof (mocked lookup, reo 9979655) | "An address is enough; reo reads roof size and orientation." |
| Tap **Planned** (electric car) | Wallbox + car appear on the house; PV grows because the planned EV adds charging demand (engine 11f5a6a) | "Buying an EV next year: the design adapts and reo explains why." |
| Tap **Gas** | reo's heat-pump advice and the heating comparison card: today's running cost vs a heat pump on grid power, CO₂ change (engine `heating_comparison`) | "Every figure here is the engine's estimate from public rates. It only says 'cheaper' when the engine finds it cheaper." |
| Tap **No solar yet** | The handoff offer | "This question exists because our validation showed it was missing (step 4)." |
| Optional: type **why a battery?** | reo answers from the engine's reasons | "It explains, it doesn't invent numbers." |

Before rehearsal: run the flow once and write the actual kWp, price range and heating-card figures into this table (they depend on the engine version at freeze).

### 1:50 — Handoff

- Type **send it to the installer** (or tap **Yes, send it**). Name: **Anna Demo** → Send plan.
- "The customer is done. The plan goes to the planner, and reo's agent starts working on it."

### 2:05 — Planner view (window B)

| Do | Expect | Say |
|---|---|---|
| Open the new **Anna Demo** plan in the inbox | Summary from reo, flags vs similar real homes, design with reasons and confidence | "The planner sees why each decision was made and where it differs from what experts built for similar homes." |
| Watch the **Offer pack** timeline | Steps stream in: reads the plan, compares with ~1,100 similar homes, three engine designs, calendar, ✓ *numbers verified*; ready in ~15 s | "That's reo's agent running on our harness: deterministic tools only, and a code guard checks every number against an engine result." |
| Point at the **Quotation** card | One offer = the engine's design: price, own power, payback | |
| Scroll to **Design studio**, pick **Erase**, click 2 modules off the roof, **Apply to plan** | 3D house updates; re-derive banner shows PV kWp and total change, highlighted | "The planner stays in control: drag, drop, and the engine re-derives every number." |
| Edit one sentence in the **Message to the customer** | | |
| **Approve** "site visit" (pick a slot), **Reject** the CRM task, **Approve** "send quote" | Each step done / rejected; plan status *Quote sent* | "Nothing customer-facing happens without the planner's approval." |

### 3:40 — Customer sees the quote (window A)

- Within ~4 s the chat shows the visit booking and **"Your planner has confirmed your plan … (confirmed by Sonnfeld)"** with the edited message; the plan card says *Confirmed quote*.
- "Estimate became a confirmed quote, with the installer's own words."

### 4:00 — Reality check (deck slide, honest numbers, 45 s)

The in-app Reality check panel and reo's `/validation` were removed (`0af678a`), so this step is a **deck slide**: a headline table plus `data/reports/vs_baseline_test.png` and `no_pv_test.png`. Setting: 235 homes the engine never saw, parameters from train only, baseline = train medians.

- "On unseen homes the engine sizes PV within about 2 kWp of the experts (median miss 1.9 kWp) and beats the naive baseline on PV size: 49 % vs 42 % within ±20 %."
- "Battery sizing is still difficult: [battery %] vs [baseline %] within ±20 %. Full-bundle decisions are no better than the baseline (about 52 % both)."
- "The biggest miss was data, not sizing: 49 of 52 'no PV' homes were retrofits with existing solar nobody recorded. So reo now asks 'do you already have solar?'. The data told us which question was missing."

**Number check before the slide is final.** Two test results exist and disagree on the battery:
- data's published report (`data/reports/reality_check_test.md`, `score_test_test.json`, data `7fd5ecb`, Sat 20:39): PV 49 % vs 42 %, battery **39 % vs 42 %** (worse than the baseline), bundle 52 % vs 52 %.
- engine's official re-score of the current engine (`engine/STATUS.md`, `a56e3f9`): PV 49.2 % vs 41.5 %, battery **45.6 % vs 41.9 %**, bundle 52.8 % vs 52.3 %.

The slide uses only data's frozen M3 numbers (hard rule 3). Until data republishes, the battery line stays as a placeholder; if the freeze still shows the battery below the baseline, say so.

### 4:45 — Close (15 s)

> "reo: a number on the first tap for homeowners, a ready, explained offer for installers, and every number from a deterministic engine we validated on homes it never saw."

## If something breaks

| Problem | Do |
|---|---|
| Typed reply slow / LLM down | Use taps only (no LLM needed); reo falls back to scripted replies automatically |
| Offer pack stuck on *preparing* > 30 s | Click **Prepare again** (scripted pack in < 1 s if the model fails) |
| Engine down | Plan card shows *Calculation paused*; restart engine, then "Start over" |
| Anything else | Switch to the recording |

## Optional moments (only if time allows)

- **Voice** (if `reo/.env` has the ElevenLabs key, real Chrome, mic allowed): tap the mic, say "we heat with gas" → reo answers out loud (~5–8 s).
- **Installer edit**: change the battery size by hand → banner shows what re-derived.

## Recording plan (fallback)

Record one clean run of steps 0:20–3:40 with two windows side by side (screen recorder at 1080p), plus the reality-check slide. Re-record after the last code freeze (M3, Sun 12:00).

## Open before M3

- Build the validation slide from data's frozen M3 test numbers (battery figure currently disputed, see step 4).
- Rehearse the new question order and heating card; fill in the on-screen figures.
- Bill photo + goal chips are available; test the reader on a real bill before including it.
- Brand search found no exact installer match in the initial search, but related names exist; retain Sonnfeld as a fictional demo brand pending Raneem review.
