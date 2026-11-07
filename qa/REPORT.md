# QA report

Newest first. Only build, contract, metric, and demo findings are tracked.

## 2026-11-07 — engine M0 stub (`3c0b18b`, contract addition `718cd3f`)

- `cd engine && uv run pytest`: passed, 25 tests. One upstream Starlette `TestClient` deprecation warning was reported.
- Started the engine API locally and ran `python qa/smoke.py` against live engine and reo services: passed `/health`, `/prices`, no-demand/total-demand/household-demand design, weekly and daily EV inputs, regional PV sizing, reo customer flow, handoff, installer edit, and finalize. The regional check confirms the same 4,500 kWh demand sizes larger in Schleswig-Holstein than Bavaria and stops requesting region once known.
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
