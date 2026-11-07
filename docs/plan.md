# Plan

Times are Munich time. Each milestone ends with a `DONE` on the board from every role that delivered into it (addressed to its consumers and qa).
Humans own this file; agents propose changes with a `DECISION`.
Restructured Sat ~17:30 for the reo vision (see `AGENTS.md` → Product).

## Milestones

| | When | engine (Ege) | reo (Eywa) | data (Eywa) | app (Raneem) |
|---|---|---|---|---|---|
| **M0 Contracts + stubs** | Sat 19:00 | `CONTRACT.md` v1 agreed with reo; stub `/design` | `CONTRACT.md` v1 agreed with app; stub API with canned turns | `projects.parquet` + `split.csv` | `persona.md` + `flow.md`; UI skeleton on the reo mock |
| **M1 Minimum, end to end** | Sat 23:30 | real coupled design, price, economics, reasons, locks; `val` score | conversation loop with Claude + scripted fallback; plan store, handoff, installer edit, finalise | `score.py` + baseline; `benchmarks.json` | customer flow + installer view live against reo; demo script draft |
| **M2 Expert-grade** | Sun 09:00 | `/explain` + what-ifs; refined params | flags, similar projects, "ask why", address mock, `/validation` | test report, deviation analysis, charts | flags, reality-check panel, address input, polish |
| **M3 Freeze** | Sun 12:00 | bug fixes only | bug fixes only | final numbers frozen | rehearsed demo, fallback recording, deck, README |
| **Submit** | Sun 14:30 | | | | humans submit (deadline 15:00) |

qa (Raneem's Codex) verifies every delivery as it lands, runs the end-to-end demo walk from M1, and does a final clean-clone run at M3.

**M1 is the challenge's minimum result:** a customer gives a few facts → complete design with explanation and price → one more fact changes the design → handoff → installer changes something → updated design and final quote; plus validation numbers against expert designs on `val`. Nobody starts M2 work while an M1 item of theirs is open.

## Handoffs (who waits on whom)

- app → reo: `experience/persona.md` + `flow.md` (M0), UI needs as `NEED`s.
- engine → reo: contract + stub (M0), real `/design` with locks and prices (M1), `/explain` (M2).
- reo → app: contract + stub (M0), live customer + installer endpoints (M1), flags, ask, validation (M2).
- data → engine: `projects.parquet` + `split.csv` (M0), `score.py` (M1).
- data → reo: `benchmarks.json` (M1), score JSON for `/validation` (M2).
- data → app: charts and numbers for the deck (M2).

## Demo story (five minutes)

1. A homeowner on the installer's website tells reo "we use about 4,500 kWh a year" → instant first design and price range.
2. reo asks for more; they mention gas heating and "we're buying an electric car next year" → the design adapts, reo explains why.
3. They hand the plan over. The installer opens it: reasons, flags vs similar real projects, edits one component → everything re-derives → finalise → the customer sees the final quote.
4. Reality check: the engine's designs compared with expert designs on projects it never saw.

## Budget

Only an Anthropic API key for reo. No other paid services (the address lookup is mocked). Anything else is a `DECISION`.

## Decided

- Engine parameters are fitted on `train` only; headline accuracy is data's `test` score (Sat 20:10).
- reo uses a fast model (Sonnet 5.5) for customer chat turns and Opus 5.5 for the background offer agent (Sat 20:10).
- Expert design = highest `option_number` with hardware, until Reonic confirms which option was signed.

## Phase 2: installer side + agentic reo (Sat 20:30 → Sun 09:00)

Phase 1 delivered the customer flow end to end (reo + app on the engine stub, data's validation). Phase 2 turns reo from a smart configurator into an **agent that does the planner's work**, while the engine finishes real numbers.

**Where we stand (val/test):** engine ≈ naive baseline on yes/no decisions (52 % bundle match on test, same as baseline); PV size better (49 % vs 42 % within ±20 %); battery size worse (experts pick catalogue steps); 51 of 52 "no PV" homes are retrofits with unrecorded existing PV. Each installer has its own sizing style (opposite PV bias). See `data/reports/reality_check_test.md`.

**Demo story, updated step 3:** the customer hands over → **reo's offer agent prepares an offer pack in the background** (3 variants, flags vs similar homes, site-visit checklist, draft message, proposed actions, visible trace of what it did) → the planner picks a variant, tweaks one thing, approves "book site visit" and "send quote" → the customer sees the final quote.

### Agent guardrails (apply to everything below)

- Agents call **deterministic tools only** (engine, benchmarks, mocked calendar / CRM). Every number in a variant, message or summary comes from an engine call (hard rule 2).
- **Nothing customer-facing or binding happens without the planner's approval**: quotes, booked visits, sent messages are `proposed` until approved.
- Every agent run leaves a **trace** (steps, tool, one-line result) the UI can show.
- Works without an API key: scripted fallback builds the same pack from fixed lock sets.

### engine (Ege): real numbers first, then expert-likeness

1. **Finish M1 core** (blocker for the demo's real numbers): hourly simulation → battery + wallbox, `prices.json`, economics incl. monthly bill before/after, ranges, ranked `missing_inputs`, locks. → `DONE` to reo, data, qa.
2. **Snap to catalogue sizes** like the experts (battery 5 / 7 / 10 / 15 kWh, PV to module counts); data shows this is where battery size loses.
3. **Installer style:** optional `installer_profile` (params per installer, fitted on that installer's `train` projects). Pitch line: "reo learns each installer's own style". Score per installer with data's tool.
4. **`/explain` what-ifs** (component off/on, size ±1 step: Δ price, Δ savings, Δ payback): the offer agent and goal planning use it.
5. Use existing PV / retrofit inputs (`has_existing_pv`) so retrofits get no new PV.

### reo (Eywa): the agent

1. **Model split:** Sonnet 5.5 for chat turns, Opus 5.5 for the offer agent (env-overridable).
2. **Offer agent** (`POST /plans/{id}/prepare`, runs automatically on handoff): tool loop over engine `/design` (with locks) + `/explain` + benchmarks → `Plan.offer_pack`:
   `{status: "preparing" | "ready", variants: [{name: "Basic" | "Recommended" | "Independence", locks, design, why}], flags, site_visit_checklist: string[], open_questions: string[], customer_message_draft, actions: [{id, kind: "book_visit" | "send_quote" | "create_crm_task" | "request_document", label, payload, status: "proposed" | "approved" | "done"}], trace: [{step, tool, summary}], duration_s}`.
3. **Approval-gated actions:** `POST /plans/{id}/actions/{action_id}/approve` executes a mocked tool (calendar slots / CRM log in JSON under `reo/`) and records it; `send_quote` = finalise.
4. **Bill photo:** `POST /sessions/{id}/bill` (image) → Claude vision reads yearly kWh, ct/kWh, provider → facts → `Turn` with "I read this from your bill: … correct?" chips.
5. **Goal planning:** goals like "under €20,000", "as independent as possible", "lowest monthly bill" (customer `/messages`, installer `/plans/{id}/ask`) → tool loop over engine variants → recommendation + 2 alternatives + trace.
6. Ask "do you already have solar?" early (fixes the retrofit misses).
7. Stretch: follow-up nudge for abandoned sessions (draft only, approval-gated).

Post the new types and endpoints as a `CONTRACT` to app and qa **before** building, so app can mock them.

### data (Eywa): keep the evidence current

1. Re-score `val` whenever the engine posts `DONE`; per-installer scores once `installer_profile` exists.
2. For the offer agent: a `similar_projects(home, k)` helper output or documented lookup over `projects.parquet` + percentile lookup over `benchmarks.json` (reo reads files, no imports).
3. Final frozen `test` numbers and charts at M3 for the deck.

### app (Raneem): polish + installer agent UI

1. Clean up the demo site (less "vibe coded"): one type scale, spacing system and component set from `experience/brand.md`, real copy, no decorative noise. (Raneem steering directly.)
2. Installer **offer pack** view: three variant cards side by side, "reo prepared this in 38 s" trace timeline, flags, site-visit checklist, editable draft message, approve buttons per action.
3. Customer widget: bill photo upload (camera icon), goal chips ("Keep it under €20,000", "As independent as possible").
4. Reality-check panel from `/validation` (test numbers, per installer, honest where we lose).
5. `pitch/demo-script.md`, deck, README.

### qa (Raneem's Codex)

Verify every phase-2 `DONE`; check hard rule 2 on offer packs (every number in variants, drafts and summaries appears in an engine design of that run); check nothing executes without approval; check the offer pack also works without an API key; from Sun 09:00 rehearse the demo script daily-driver style; M3 clean-clone run.

### Timing

| When | Done |
|---|---|
| Sat 23:30 (M1) | engine core real numbers live; reo phase-2 contract posted; app clean-up underway |
| Sun 03:00 | offer agent + approvals working on mocks; bill photo; offer-pack UI against mock |
| Sun 09:00 (M2) | everything live end to end, goal planning, reality-check panel, installer style if engine has it |
| Sun 12:00 (M3) | freeze, final test numbers, rehearsal, recording |
