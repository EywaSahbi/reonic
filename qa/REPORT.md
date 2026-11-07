# QA report

Newest first. Only build, contract, metric, and demo findings are tracked.

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
