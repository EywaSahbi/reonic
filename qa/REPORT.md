# QA report

Newest first. Only build, contract, metric, and demo findings are tracked.

## 2026-11-07 — M3 clean-clone verification (`f106ff7`)

- Fresh shallow clone under `qa/.m3-clean`; no API keys. `data`: 6 passed. `reo`: 15 passed. `app`: `npm ci` and production build passed (45 modules). `engine`: first cold full run had 40/41 because `test_fast_enough` measured 0.121 s against its 0.100 s threshold; second full run passed 41/41 in 3.85 s. Starlette's existing TestClient deprecation warning remains.
- Live smoke from that clean clone passed all engine/reo routes, variant-grounded quote draft, fixed `/validation` routing, and data artifacts. Reo scripted harness evals passed 9/9 scenarios with `ANTHROPIC_API_KEY=''`.
- Reproduced frozen val (238, 0 missing, params fitted on train): PV MAE 2.50 kWp / ±20% 46.2%; battery MAE 3.09 kWh / 42.9%; bundle match .559. Installer-profile val: PV MAE 2.46 / 50.0%; battery MAE 2.93 / 42.4%; bundle match .559.
- Final test reproduction (235, 0 missing, params fitted on train), twice: PV MAE 3.22 kWp / ±20% 49.2% (baseline 3.50 / 41.5%); battery MAE 3.58 kWh / 45.6% (baseline 3.74 / 41.9%); bundle match .528 (baseline .523); wallbox presence 68.5%. The fixed report `data/reports/score_test_test.json` disagrees on battery (3.47 / 38.6%) and bundle (.523), while PV agrees. **M3 remains pending** until data republishes the frozen report from the current predictor; NEED posted to data (`6712887538`).
- `npm ci` in the fresh clone reported 2 dependency advisories (1 moderate, 1 high); build completed successfully.

## 2026-11-07 — Phase 2 verification and offer-pack rehearsal

- Latest main: `data && uv run pytest` **6 passed**; `engine && uv run pytest` **41 passed** (one existing Starlette TestClient deprecation warning); `reo && uv run pytest` **15 passed**; `app && npm run build` passed (43 modules). An earlier pre-update engine run missed its 0.10 s timing threshold once and passed when rerun alone; this did not reproduce in the latest full suite.
- Live `qa/smoke.py` against engine `:8004` and reo `:8005`: passed `/health`, installer profiles, prices, sizing inputs, region and retrofit checks, `/explain` deltas/locks, handoff, offer-pack trace/SSE/grounding, approval gate, calendar slots, edit/ask/finalize, fixed `/validation` test/val/profile file selection, and data split/artifact checks (1,571 projects; fixed 1,098/238/235 splits).
- `cd reo && ENGINE_URL=http://127.0.0.1:8004 ANTHROPIC_API_KEY='' uv run python -u -m evals`: **9/9** scripted scenarios passed all grounded-number, no-execution, distinct-variant, budget, and trace checks.
- Current white-label home, CTA, advisor greeting, no-key intake and handoff were verified in the browser; the customer plan showed the estimate, assumptions, and installer action as expected.
- Current val score reproduction with train-fitted params: standard model — PV MAE 2.50 kWp, ±20% 46.2% (baseline 2.71 / 49.7%); battery MAE 3.09 kWh, ±20% 42.9% (baseline 2.99 / 40.8%); bundle match .559 vs .555 baseline. Installer profiles — PV MAE 2.46 / 50.0%; battery MAE 2.93 / 42.4%; bundle match .559. Did not rerun test metrics; data requested the final test re-score only at M3.
- No-key browser rehearsal reached Anna Demo's handoff and the live installer offer pack with Basic, Recommended, and Independence variants. Selecting Basic re-derived battery 10→6 kWh and total €20,433→€18,633, but left the prefilled customer message describing the original 10 kWh and €15,200–28,700 estimate. This stale draft can send details that disagree with the selected variant; finding posted to app as BLOCKED (board comment `6712714072`). The customer draft was manually brought into alignment for the local rehearsal. The scripted harness still confirms all actions are proposed until approval and does not execute actions itself.
- Reo `35f5a3d` refreshes `customer_message_draft` and the proposed quote payload on `/variant`; app `057048c` flags a draft for another variant, preserves planner edits, and adopts the refreshed draft when untouched. The expanded live smoke passed against those commits: the Basic selection's `draft_for`, battery size, price range, and proposed quote message all matched the chosen engine design.
- Browser regression passed without API keys: Basic refreshed the draft from 10 to 6 kWh and to €10,800–20,600. After manually changing the draft and selecting Independence, the planner text remained unchanged and an amber notice identified that it described Basic, with an explicit “Use reo's updated message” action. White-label CTA/greeting also passed. App production build after latest `05dec5b` intro update passed (45 modules).
- The first live smoke attempt exposed a QA assertion that incorrectly rejected the scenario manifest's valid `built_from: "... never test"` wording. Updated only `qa/smoke.py` to permit that phrase while still rejecting test-split cases; the rerun passed.

## 2026-11-07 — full M1 live flow, data, and score reproduction

- `cd data && uv run pytest`: passed, 3 tests; `cd engine && uv run pytest`: passed, 34 tests; `cd reo && uv run pytest`: passed, 7 tests; `cd app && npm run build`: passed.
- `cd data && uv run python ../qa/smoke.py --skip-engine --skip-reo`: passed data contract checks for 1,571 rows, unique project IDs, exact fixed 1,098/238/235 split coverage, no customer across splits, and `benchmarks.json` built from train. Full smoke against current engine `:8004` and reo `:8005` passed all live routes, including `/explain`, `/validation`, handoff/edit/finalize, plus data checks.
- Started current engine + reo + app on QA-local ports with Anthropic and ElevenLabs keys blank; `/health` reported `llm=false`, `voice=false`, `engine=true`. Browser walk passed 4,500 kWh → 35 ct tariff → gas → 60 m² roof → Bavaria → planned EV → handoff as QA Test → installer battery 9→10 kWh → re-derived total/payback → “Why this battery size?” → finalize → customer sees confirmed quote.
- **BLOCKED to reo:** after selecting Gas, reo said `€13,200–63,600`; the same-turn plan card showed `€13,200–63,700` while the raw engine range was `[13190, 63650]`. This same-turn price mismatch violates the number-source check; board report posted with reproduction details.
- `cd engine && uv run python ../qa/reproduce_score.py --split both`: passed with 0 missing predictions and params fitted on `train`. Current `val` (238): PV MAE 2.49 kWp / within ±20% 45.9%; battery MAE 2.79 kWh / 38.2%; bundle match 55.9%. Current `test` (235): PV MAE 3.22 kWp / within ±20% 49.2% vs baseline 41.5%; battery MAE 3.47 kWh / 38.6% vs baseline 41.9%; wallbox presence 68.5%; bundle match 52.3%. Outputs were kept in a temporary folder under `qa/` and removed after each run.
- `/validation` is available but still returns `data/reports/score_all_val.json` (`model: all`, commit `10e725a`), predating the current fitted design. NEED posted to data to publish the current val report. `pitch/demo-script.md` is not present; NEED posted to app for the draft before rehearsal.

## 2026-11-07 — engine M0 stub (`3c0b18b`, contract addition `718cd3f`)

- `cd engine && uv run pytest`: initially passed 25 tests; after the reasons/assumptions fix (`1031712`), passed 26 tests, including `test_reasons_match_facts`. One upstream Starlette `TestClient` deprecation warning was reported.
- Ran `ENGINE_URL=http://127.0.0.1:8003 python qa/smoke.py` against the corrected engine build and live reo service: passed `/health`, `/prices`, no-demand/total-demand/household-demand design, weekly and daily EV inputs, regional PV sizing, fact-consistent reasons/assumptions, reo customer flow, handoff, installer edit, and finalize. The regional check confirms the same 4,500 kWh demand sizes larger in Schleswig-Holstein than Bavaria and stops requesting region once known. The default `:8000` service was an older already-running build, so QA used a separate port for the fixed build.
- `/explain` correctly skips as a later milestone. `/validation` and processed data/split checks skip because data outputs are not published. The engine's battery, wallbox, prices, and economics are documented placeholders; this verifies M0 contract only, not M1 accuracy or the `val` score.

## 2026-11-07 — reo voice API (`2756583`)

- `cd reo && uv run pytest`: passed, 5 tests. `test_voice_turn` verifies mocked transcription updates `total_demand_kwh`, mocked speech is returned as base64 audio, and empty audio produces a “didn't catch” response without changing state.
- This covers the mocked API path. Live ElevenLabs credentials/audio are not part of this QA check.

## 2026-11-07 — app + reo offline integration (`28527ca`, `9b01a6c`)

- `cd app && npm run build`: passed.
- `cd reo && uv run pytest`: passed, 4 tests. The scripted fallback case ran with `ANTHROPIC_API_KEY` unset; engine-down handling also passed.
- Live customer flow against reo with the design engine offline: opening the widget and choosing household size and gas heating kept the plan in “Calculation paused”; the UI stated there were no sizes or prices, preserved entered inputs, and offered no handoff. No fabricated price or €0 estimate appeared.
- This verifies the offline integration state only. Engine-backed design, the engine `val` metric, validation data, and the full handoff-to-quote journey through live services remain pending.

## 2026-11-07 — reo API v1 (commit 2d6428f)

- `cd reo && uv sync && uv run pytest`: passed, 4 tests, including scripted fallback with `ANTHROPIC_API_KEY` unset and engine-down behavior.
- `python qa/smoke.py --skip-engine` against the live reo API on `:8002`: passed health, customer turn/facts/address/handoff/retrieval, installer list/detail/ask/finalize. The API returned the contracted HTTP 503 for `/prices` and installer edit while the engine was offline; the offline turn messages contained no numeric claims. The handed-over plan included its installer summary.
- Engine checks were skipped because the engine server is not yet available. `/validation` returned the documented unavailable response; processed data files are still unpublished.

## 2026-11-07 — engine total-demand contract update (commit 336060e)

- Smoke coverage now requests designs with no demand, `total_demand_kwh`, and household-only `annual_demand_kwh`, plus the separate weekly/daily EV distance cases. This validates acceptance and response shapes; the active engine stub is not yet available for runtime execution.
- reo's contract now documents voice routes as M2 and explicitly gated on a human DECISION; voice checks remain deferred until that decision and service implementation.

## 2026-11-07 — tap cards and house illustration (commit adfa400)

- `cd app && npm run build`: passed.
- Browser check passed: household-size and heating choices render as labelled tap cards; choosing four people updates demand to 4,600 kWh and displays a house illustration with 17 panels, matching `design.components.pv.quantity`. The estimate and plan card update with the same mock design.
- Runtime service integration remains pending; the displayed results are clearly marked as mock estimates.

## 2026-11-07 — engine EV distance contract update (commit f38af8a)

- Added smoke requests that submit `ev_km_per_week` and `ev_km_per_day` separately alongside an EV design, validating the returned Design shape. Syntax check passes; runtime acceptance awaits the engine service delivery.
- Contract says yearly distance takes precedence, otherwise weekly ×52, otherwise daily ×365, otherwise a 13,000 km/year default recorded as an assumption. Numeric conversion verification remains pending the live engine M1 implementation.

## 2026-11-07 — Reonic brand pass (commit e0b56cf)

- `cd app && npm run build`: passed.
- Browser review passed on both views: the customer site uses the revised black pill CTA and sunset hero card; the widget header reads “reo · powered by Reonic”, and the plan card retains clear estimate labels and status/confidence pills. The installer uses the updated white-panel theme and emerald `quoted` / amber `new` statuses; plan detail and controls remain legible.

## 2026-11-07 — tap-first customer opening (commit 9ac9490)

- `cd app && npm run build`: passed.
- Browser check passed: new session asks household size with one-tap choices `1`, `2`, `3`, `4`, `5+`; choosing `3` produces a design, a price range, and an assumption explaining the demand estimate. The current reo contract permits `num_inhabitants` as an ask field. New `building_type` and `roof_type` prompts are explicitly conditional on their engine contract fields shipping.

## 2026-11-07 — app installer mock handoff (commit 0e16e40)

- `cd app && npm run build`: passed after pulling the installer view.
- Browser mock walk passed end to end: created a plan using 4,500 kWh, gas heating, and a planned EV; handed it over; the installer inbox displayed it; reduced the battery from 12 to 11 kWh and applied the edit; the UI showed the re-derived total and payback plus an edit log; “Why this battery size?” returned a reason; finalisation disabled edit controls and marked the plan “Quote sent”; the customer view showed “Confirmed quote” and the updated 11 kWh battery.
- These are mock values and the mock API is visibly labelled. The live reo/engine endpoints and `/validation` remain unverified.

## 2026-11-07 — app customer mock skeleton (commit 8ce3904)

- `cd app && npm install`: passed; npm reported two dependency advisories (one moderate, one high).
- `cd app && npm run build`: passed (`tsc --noEmit` and Vite production build).
- Browser mock walk passed: opened reo, selected 4,500 kWh, selected Gas, typed “we're buying an electric car next year”, confirmed the 20.5 kWp / 11 kW wallbox update, and submitted the handoff form; plan moved to “With your planner.” The page marked itself “mock API.”
- `app/src/types.ts` matches the current HomeFacts, Design, Turn and Plan shapes in the reo/engine contracts. Live backend, installer dashboard, and final quote remain unverified because they are not delivered yet.

## 2026-11-07 — app experience contract check (commit 1155aa0)

- **BLOCKED app:** `experience/flow.md`, Stage 5 says to ask `{field: name, ..., input: "text"}`. In `reo/CONTRACT.md`, `Turn.ask.field` is `keyof HomeFacts` and `input` is only `number | boolean | choice | address`; `name` and `text` are invalid. Reproduce by comparing Stage 5's ask object with the `Turn` type. Expected: collect the name through a contract-valid handoff flow (the handoff body already has `name`). Actual: the prescribed ask object cannot conform to the reo response type.
- The documented HomeFacts field names otherwise match `engine/CONTRACT.md`. App build is not runnable yet because `app/` has no package manifest or source at this commit.
- **Verified fixed in app commit `fcd570d`:** Stage 5 now collects name/email in an app-owned form and sends them directly in the contracted `/handoff` body. Rechecked the Stage 5 text and confirmed the invalid `ask` object is gone.

## 2026-11-07 — persona update check (commit 5e3ecd0)

- Passed review of the new customer-facing statements: funding is described only as possible with no amounts or deadlines, and aggregate comparisons are allowed only when supported by the current plan's attached flags/benchmarks. Individual projects remain installer-only. No contract change was included.

## 2026-11-07 — smoke checks updated for reo architecture

- Rewrote `qa/smoke.py` for current engine and reo contract shapes, including every contracted endpoint and milestone-gated optional routes. Added data column and split coverage checks using the renamed `HomeFacts` fields.
- Syntax check: passed with `python -m py_compile qa/smoke.py`.
- Runtime check: `python qa/smoke.py` stops at the engine health call because `localhost:8000` actively refused the connection; engine/reo service code and processed artifacts are not yet published in this clone. Full checks await the M0 `DONE` handoffs.

## 2026-11-07 — initial QA setup

- `qa/smoke.py` v0 syntax check passed with `python -m py_compile qa/smoke.py` (superseded by current-contract rewrite above).
- Engine smoke: unable to connect to `http://localhost:8000` (`WinError 10013` in the restricted environment). No engine implementation is currently present in this clone, so `/health` and `/design` are not yet available to verify.
- Data artifact check: skipped; `data/processed/projects.parquet` and `split.csv` are not published in this clone.
- App build/API client check: skipped; app source and package manifest are not published in this clone.
