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

### reo (Eywa): the reo agent harness

**Goal:** not a set of one-off LLM endpoints, but **one small agent harness** that every reo capability runs on. This is the technical centrepiece of the pitch: "reo is an agent runtime for installers: skills, tools, guardrails, traces". reo's phase-2 contract draft (4263518: offer pack, actions, bill, goals) stays; those features become **skills on the harness**.

Built in `reo/harness/` (a few files, no agent framework: the Anthropic SDK tool-use loop plus our own code):

1. **Tool registry** (`tools.py`). Each tool = name, JSON schema, handler, and a declared **effect class**:
   - `read`: no side effects (`engine.design`, `engine.explain`, `evidence.similar`, `evidence.percentile`, `plan.read`, `calendar.slots`, `bill.read` (vision)),
   - `propose`: writes only a proposal to the plan (`plan.propose_variant`, `plan.propose_action`, `plan.draft_message`, `plan.add_question`),
   - `execute`: real side effect (`calendar.book`, `crm.create_task`, `quote.send`). **Never callable by a model.** Only the approve endpoint runs them, after a human click.
2. **Skills** (`skills/*.md` + one entry each in `skills.py`): a skill = system prompt + allowed tools + budget (max steps, max seconds) + output schema. Start with:
   `chat_turn` (Sonnet 5.5, today's loop), `offer_prep` (Opus 5.5, on handoff), `goal_planner` (Opus 5.5, budget / independence / lowest bill), `bill_reader` (vision), `installer_qa` ("why …?", "what if …?"), stretch `follow_up` (draft only).
3. **Runner** (`runner.py`): one loop for all skills: model call → tool calls → results → repeat until the output schema is filled or the budget runs out. Every step is appended to a **Run** `{id, skill, plan_id, trigger, status: running|done|failed|needs_approval, steps: [{n, kind: think|tool|guard, tool?, args_summary, result_summary, ms}], output, model, started_at, duration_s}` stored with the plan.
4. **Guardrails in code, not in the prompt** (`guards.py`), each logged as a `guard` step:
   - **Grounding check:** every number in any text the skill outputs must appear in a tool result of the same run (rounding tolerance as in persona.md). Fail → one retry with the violation listed → else fall back to the scripted output.
   - **Effect gate:** a skill can only call tools its definition allows; `execute` tools are not in any skill's list.
   - **Budget:** max steps and seconds per skill; on timeout return the best partial output, marked.
   - **Scope:** a run only sees its own plan's facts (hard rule 5).
5. **Triggers** (`triggers.py`): handoff → `offer_prep`; goal message → `goal_planner`; bill upload → `bill_reader`; installer edit → re-run the guard checks on the pack and mark stale variants; stretch: idle session → `follow_up`.
6. **Live trace:** `GET /runs/{id}` and `GET /runs/{id}/events` (Server-Sent Events, one event per step) so the installer view can show reo working in real time; `GET /plans/{id}/runs` lists runs. `OfferPack` and `GoalResult` carry `run_id`; `OfferPack.trace` stays as the summary.
7. **Approvals:** `POST /plans/{id}/actions/{action_id}/approve` and `/reject`; approving runs the matching `execute` tool and appends a step to the run.
8. **Scripted mode:** the same skills run without a key via a scripted planner (fixed tool sequence per skill), so runs, traces and guards look identical in the demo, with `model: "scripted"`.
9. **Harness evals** (`reo/evals/`, run by `uv run python -m evals`): 6–10 scenarios from `val` homes + demo homes; per run assert: grounded numbers, no `execute` without approval, three variants that differ, budget respected, trace present. Print a table; qa runs it after every reo `DONE`.
10. Keep from before: model split (Sonnet 5.5 chat / Opus 5.5 agents), ask "already have solar?" early.

**Order:** (a) post the harness types + run/approve/SSE endpoints as a `CONTRACT` to app and qa first; (b) registry + runner + guards with `offer_prep` scripted end to end; (c) `offer_prep` on Opus; (d) `bill_reader`, `goal_planner`; (e) evals; (f) `installer_qa` moves onto the harness; (g) `follow_up` if time.

### data (Eywa): keep the evidence current

1. Re-score `val` whenever the engine posts `DONE`; per-installer scores once `installer_profile` exists.
2. For the offer agent: a `similar_projects(home, k)` helper output or documented lookup over `projects.parquet` + percentile lookup over `benchmarks.json` (reo reads files, no imports). (Done: c0cb87e.)
4. **Harness eval scenarios:** `data/processed/scenarios.json`, 6–10 `val` homes covering the hard cases (retrofit with existing PV, EV planned, gas → heat pump, tiny demand, big demand, tight budget) with the expert design attached, for reo's `evals`.
3. Final frozen `test` numbers and charts at M3 for the deck.

### app (Raneem): polish + installer agent UI

1. Clean up the demo site (less "vibe coded"): one type scale, spacing system and component set from `experience/brand.md`, real copy, no decorative noise. (Raneem steering directly.)
2. Installer **offer pack** view: three variant cards side by side, a **live run timeline** fed by `GET /runs/{id}/events` ("reo is checking 12 similar homes…", guard steps shown as small ✓ "numbers verified"), flags, site-visit checklist, editable draft message, approve / reject buttons per action.
3. Customer widget: bill photo upload (camera icon), goal chips ("Keep it under €20,000", "As independent as possible").
4. Reality-check panel from `/validation` (test numbers, per installer, honest where we lose).
5. `pitch/demo-script.md`, deck, README.

### qa (Raneem's Codex)

Run reo's harness evals (`cd reo && uv run python -m evals`) after every reo `DONE` and report regressions; additionally try to break the guards (prompted to invent a number, to call an `execute` tool, to read another plan). Verify every phase-2 `DONE`; check hard rule 2 on offer packs (every number in variants, drafts and summaries appears in an engine design of that run); check nothing executes without approval; check the offer pack also works without an API key; from Sun 09:00 rehearse the demo script daily-driver style; M3 clean-clone run.

### Timing

| When | Done |
|---|---|
| Sat 21:00 | engine core real numbers live (done); reo harness `CONTRACT` posted |
| Sat 23:30 (M1) | harness registry + runner + guards; `offer_prep` scripted end to end with approvals; app offer-pack view on mock; data scenario set |
| Sun 03:00 | `offer_prep` on Opus with live SSE trace in the installer view; `bill_reader`; harness evals green |
| Sun 09:00 (M2) | `goal_planner`, `installer_qa` on the harness, reality-check panel, installer style if engine has it |
| Sun 12:00 (M3) | freeze, final test numbers, rehearsal, recording |
