<p align="center"><img src="docs/reo-logo.svg" alt="reo" width="160"></p>

# reo — an AI companion that designs home energy systems like an expert installer

**Give reo one number from your electricity bill and it answers in seconds: a complete system (solar, battery, heat pump, wallbox), a price range, and a reason for every number. The installer's planner then receives a ready offer, not a lead, and can change anything while the rest of the design re-derives.**

*Built for the Reonic Hackathon (Munich, 7–8 Nov 2026) — challenge "AI-designed home energy systems".*

---

## Try it live

| | |
|---|---|
| **Live app** | **https://sonnfeld-reo.vercel.app** |
| **Access code (demo gate)** | **`1234`** — asked once when the site opens |
| **Planner workspace** | https://sonnfeld-reo.vercel.app/#/installer |
| **Planner access code** | **`1234`** — asked when the planner workspace opens |

**Three-minute tour**

1. Open the live app, enter `1234`, click **Plan my home**.
2. Type a yearly use of **4500** kWh, the address **Sandstraße 33 80335 München** (or the offline demo address *Musterstraße 12, 80331 München*), say you plan an **electric car** and heat with **gas**. You get a design, a price range marked *estimate*, savings, payback, and a gas-vs-heat-pump comparison with CO₂. Toggle the heat pump off and on; the design re-derives.
3. Hand the plan over, then open the **planner workspace** (`/#/installer`, code `1234`). The new plan is on top: see the modules already placed on the roof photo, drag one, watch price and savings change, tap *Ask reo why*, and approve the proposed actions.
4. Finalise and send the quote: the customer's page now shows the confirmed plan.

> The live backend runs on a team laptop behind a tunnel. If the page reports that it cannot calculate, see [Run it yourself](#run-it-yourself) (three commands, no API key needed). Details: [app/DEPLOYMENT.md](app/DEPLOYMENT.md).

---

## Navigator — one click per folder

| Folder | What lives there | Open |
|---|---|---|
| **app/** | the web UI: white-label installer website with the reo advisor, and the planner workspace (roof editor, design studio, offer pack) | [**app/README.md**](app/README.md) |
| **reo/** | the reo backend: LLM layer, conversation, agent harness, roof vision, plan store, handoff | [**reo/README.md**](reo/README.md) |
| **engine/** | the deterministic design core: sizing, pricing, hourly economics, reasons, locks | [**engine/README.md**](engine/README.md) |
| **data/** | expert designs, the fixed train/val/test split, scoring, benchmarks, reality-check reports | [**data/README.md**](data/README.md) |
| **experience/** | reo's persona, conversation flow and visual brand | [**experience/README.md**](experience/README.md) |
| **pitch/** | demo script, submission scripts, storyboard and the product video | [**pitch/README.md**](pitch/README.md) |
| **qa/** | independent verification: smoke tests, score reproduction, clean-clone run | [**qa/README.md**](qa/README.md) |
| **docs/** | challenge brief, dataset explanation, plan | [**docs/README.md**](docs/README.md) |
| **tools/** | the agent message board and the folder-ownership hook | [**tools/README.md**](tools/README.md) |
| **Project Data/** | the raw CSVs (read-only, never leaves the team) — [what is in them](docs/dataset_explanation.md) | |

Also: [challenge PDF](Reonic_Hackathon_Challenge_final.pdf) · [challenge brief](docs/challenge-brief.md) · [how the team worked (AGENTS.md)](AGENTS.md)

**Jump to:** [The idea](#the-idea) · [How it works](#how-it-works) · [The engine](#the-engine-decides-like-an-expert) · [reo](#reo-talks-explains-and-prepares-the-offer) · [The planner](#the-planners-workspace) · [Run it yourself](#run-it-yourself)

---

## The idea

An installer's planner spends hours turning "we use about 4,500 kWh" into a system design and a quote. Homeowners wait days for a number and fear being oversold; planners fear a black box. reo does the first draft in a minute, **explains every number**, and lets the planner override any part.

**Two sides, one engine**

- **Homeowner** (on the installer's own website, white-label *Sonnfeld*): starts with the bare minimum, gets a first design and a price range at once, and each answer narrows the range. They are told what would make the estimate more precise, can try variants (heat pump on/off, wallbox), and hand the plan to the installer when happy.
- **Planner** (the installer's workspace): receives the plan with the design, *why* each decision was made, how sure reo is, and flags where the design differs from what experts did for similar homes. They edit anything, the rest re-derives, and they send the final quote.

### The architecture principle

> **Numbers come from the engine. Words come from reo.**

```mermaid
flowchart LR
  subgraph UI["app/  (React, :5173)"]
    C["Customer site<br/>+ reo advisor"]
    P["Planner workspace"]
  end
  R["reo/  (:8001)<br/>LLM layer · conversation<br/>agent harness · plan store"]
  E["engine/  (:8000)<br/>deterministic design core<br/>no LLM, no state"]
  D[("data/<br/>expert designs · split<br/>benchmarks · scoring")]
  X["experience/<br/>persona · flow · brand"]
  C -- HTTP --> R
  P -- HTTP --> R
  R -- every number --> E
  X -. loaded at runtime .-> R
  D -. benchmarks, flags .-> R
  D -- predictions scored on unseen homes --> E
```

- The **engine** is deterministic: every size, yes/no and price is computed by code, reproducible, with reasons. No LLM.
- **reo** is an LLM layer around it: it talks, decides what to ask next, calls the engine as tools, and explains the engine's reasons. It **never creates or changes a number**; a grounding guard checks this in code.
- The **dataset** is the evidence: it defines what experts actually delivered, and we validate against it on homes the engine has never seen.

---

## How it works

```
  "we use about 4,500 kWh"
          │
          ▼
  reo extracts facts ──► engine /design ──► sizes · price band · savings · reasons · missing inputs
          ▲                                        │
          │                                        ▼
  reo asks the ONE question that tightens the        customer sees a useful answer immediately,
  design most (ranked by the engine)  ◄───────────── plus what would make it more precise
          │
          ▼  handoff
  offer agent (background) ──► offer pack: design, flags vs similar homes, site-visit checklist,
                                draft message, proposed actions — with a visible step trace
          │
          ▼  planner reviews, edits (locks), approves   ← nothing binding happens without a click
  final quote ──► customer
```

### What makes it more than a configurator

| | |
|---|---|
| **Coupled decisions** | An EV or heat pump raises demand and so the PV size; PV size drives the battery; a small roof caps the modules. One hourly simulation ties it together, so the parts fit as a whole. |
| **Honest about gaps** | Missing inputs get explicit defaults (listed as assumptions), widen the price and size ranges, and are ranked by how much each would tighten the design. That ranking *is* reo's next question. |
| **Refine by locks** | The planner fixes any component (on/off and/or size); everything else re-derives around it and the planner sees what changed and why. |
| **Learns each installer's style** | Optional per-installer profiles (fitted on that installer's training projects only): the two installers in the data have opposite sizing habits. |
| **Real prices, with sources** | Quote lines are real products with real German shop prices plus sourced labour rates; the installer can override any price. Customer prices are always labelled estimates. |
| **Real roof** | From an address: the building outline (OpenStreetMap), traced on the satellite photo by Claude vision, with the sunny area computed in code. |

---

## The engine decides like an expert

[engine/](engine/README.md) · method in [engine/METHOD.md](engine/METHOD.md) · every outside number in [engine/SOURCES.md](engine/SOURCES.md)

1. **PV size** from the expert line learned on training homes (`kWp ≈ 6.15 + 0.603 × MWh`), adjusted for the region's sun (PVGIS) and roof orientation, snapped to whole modules, minus existing PV (a retrofit gets no new panels — 51 of 52 "no PV" test homes were retrofits). Installers who sell fixed packages get the package they sell most for that demand band.
2. **Demand rebuilt honestly**: the dataset's demand *excludes* EV and heat pump, so the engine adds EV km × 0.18 kWh and heat-pump electricity.
3. **Battery** by the experts' most common size per PV band; **wallbox** with an EV; **heat pump** only with fossil heating, spare roof and no existing one.
4. **Hourly simulation** (H0 household profile, EV evening charging, heat pump by outdoor temperature, PVGIS PV) → self-consumption, autarky, bills before/after, savings, payback. Calibrated on 74 homes with measured data.
5. **Ranges and confidence**: the design is re-run at plausible values of every missing input; the spread gives the range and a high/medium/low confidence, widened by the experts' own spread.
6. **Reasons**: 1–3 planner-grade sentences per component that name the input that drove them ("EV adds ~2,700 kWh/yr, so PV goes from 7 to 9 kWp").

All parameters are fitted on the `train` split only and chosen on `val`; the engine runs in ~25 ms per design.

---

## reo talks, explains and prepares the offer

[reo/](reo/README.md) · API in [reo/CONTRACT.md](reo/CONTRACT.md)

- **Customer conversation**: fixed, impact-ordered question flow, instant chip turns without an LLM, voice in/out, bill reading by vision, a goal planner ("lowest bill", "stay under €X"), a heat-pump comparison with running cost and CO₂ for gas/oil/district homes. Persona and flow are plain files in [experience/](experience/README.md), loaded at runtime.
- **An agent harness, not a pile of prompts**: every capability is a *skill* (prompt + allowed tools + budget + output schema) on one runtime. Tools have effect classes — `read`, `propose`, `execute` — and **`execute` (book a visit, send the quote) can never be called by a model**: only the planner's approve click runs it. Guards in code check that every number in a model's output matches a tool result of that run. Every step lands in a trace the UI shows live.
- **Evidence without leaks**: flags such as "battery larger than 85% of similar homes" use aggregate benchmarks built from training homes; individual homes never reach a customer or an LLM.
- **Works without luck**: with no API key (or on any LLM error) a scripted mode produces the same screens and the same approval workflow, so the demo cannot depend on the network. Harness evals on nine hard-case homes pass 9/9 in scripted mode.
- **Models**: chat on Haiku 5.5, offer agent and planner Q&A on Sonnet 5.5, roof tracing on Opus 5.5.

---

## The planner's workspace

[app/](app/README.md)

- **Inbox → plan detail**: customer, design, price breakdown, reasons per component, confidence, flags against similar homes, offer pack with replayable agent trace.
- **Roof editor**: the real satellite photo and the traced outline, with the PV modules **already placed** on the roof. Drag, rotate, add and remove modules, undo, reset to automatic placement; overlapping modules or ones outside the outline turn red. The module *count* feeds the engine, so price and savings re-derive; moving a module changes no number.
- **Design studio**: 3D build mode for modules and hardware sizes (inverter, battery, heat pump, wallbox).
- **Ask reo why**: grounded answers from the engine's reasons and what-ifs, by text or voice.
- **Approvals**: proposed actions (book visit, send quote) wait for a planner click; finalising shows the customer the confirmed plan.

---

## Run it yourself

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js and npm. **No API key is needed**; without one reo runs in scripted mode with the same screens.

```bash
# terminal 1 — engine
cd engine && uv sync && uv run uvicorn api:app --port 8000

# terminal 2 — reo
cd reo && uv sync && uv run uvicorn api:app --port 8001

# terminal 3 — app
cd app && npm install && VITE_API_URL=http://localhost:8001 npm run dev
```

Open the [customer site](http://localhost:5173/) and the [planner workspace](http://localhost:5173/#/installer). For the LLM voice, roof tracing and spoken answers, copy `reo/.env.example` to `reo/.env` and add `ANTHROPIC_API_KEY` / `ELEVENLABS_API_KEY` (never commit keys).

**Checks**

```bash
cd engine && uv run pytest                       # 65 tests
cd reo    && uv run pytest && uv run python -m evals   # 69 tests, 9 harness scenarios
cd data   && uv run pytest
cd app    && npm run build
# score the engine on homes it has not seen:
cd engine && uv run python predict.py --split test
cd ../data && uv run python score.py ../engine/out/predictions_test.csv --split test
```
