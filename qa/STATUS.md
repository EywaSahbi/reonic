# qa/ status (owner: `RaneemK-commits`, Codex agent)

## Backlog (top = next)

- [x] `smoke.py` v0 from the first `engine/CONTRACT.md` and `data/CONTRACT.md`
- [x] Rewrite `smoke.py` for the restructured `engine/CONTRACT.md` and the new `reo/CONTRACT.md` (v0 targets the retired engine contract)
- [x] Verify each M0 `DONE` (engine stub, reo stub, data table + split, app skeleton) as it lands
- [x] M1: engine-backed full flow, no-key fallback, hard-rule-2 customer estimate check, and `val` score reproduced; earlier response/card mismatch was fixed by reo. Variant selection exposed a stale quote draft and was reported to app (new BLOCKED).
- [x] Test-leak check on `engine/`: fitted params declare `split: train`; reproduced val/test prediction runs use the fixed held-out splits
- [x] M2: offer-pack demo rehearsed without API keys; `/validation` serves fixed test, val, and installer-profile report files. Held-out test-set reproduction remains for M3 per data's instruction to rescore test once at final validation.
- [ ] M3: final full run on a clean clone before submission

## Published

- `qa/smoke.py` v2: current engine/reo response shapes, regional sizing, explanation/assumption consistency, and Parquet/split/benchmark contract checks, including customer-level split isolation. `--skip-engine`/`--skip-reo` allow per-service checks.
- `qa/reproduce_score.py`: runs the engine predictor and official data scorer for val/test while directing temporary outputs to `qa/` only.
- Latest Phase 2 verification: data 6/6, engine 38/39 (the 0.10 s latency assertion missed by 0.03 s once and passed when rerun alone), reo 13/13, app production build passes; expanded live smoke and reo scripted harness evals pass.
- Reproduced current `val` metrics with params fitted on train: standard PV MAE 2.50 / ±20% 46.2%; battery MAE 3.09 / ±20% 42.9%; bundle match .559. Installer-profile val: PV MAE 2.46 / ±20% 50.0%; battery MAE 2.93 / ±20% 42.4%; bundle match .559. Baselines are documented in the report.
- Rehearsed current no-key browser flow: 4,500 kWh, gas, planned EV → Anna Demo handoff → three distinct offer variants. Selecting Basic recalculated from 10 to 6 kWh battery and €20,433 to €18,633, but the customer quote draft stayed at 10 kWh / €15,200–28,700; reported to app. Local harness approval gates remain passing.
- Verified app mock flow (`0e16e40`), tap-first opening (`9ac9490`), Reonic branding (`e0b56cf`), and picture cards/house illustration (`adfa400`): production builds pass; customer design → handoff → installer edit/re-derive → rationale → finalise → confirmed quote; both views reviewed.
- Verified reo API v1 (`2d6428f`): dependency sync and 4 tests pass; offline-mode smoke passed all current routes and confirms the API reports unavailability without numeric claims.
- Verified app integration (`28527ca`): production build passes. Live customer flow against reo with the engine offline keeps the plan paused, displays no sizes/prices, and continues collecting inputs without a handoff action. Full engine-backed journey remains pending the engine service.
- Reo engine-down behavior (`9b01a6c`): reo pytest suite and live smoke confirm offline fallback; API key was unset for the scripted fallback test.
- Verified reo voice turn (`2756583`): the mocked ElevenLabs transcription and TTS path passes, including an empty-audio response with no state change.
- Verified engine stub and correction (`3c0b18b`, `1031712`): all 26 engine tests pass; live `/health`, `/prices`, `/design` demand/EV/region/reason/assumption checks pass. Region smoke confirms northern Schleswig-Holstein yields a larger PV size than southern Bavaria for the same demand.
- Full live `qa/smoke.py` passes current engine and reo routes through handoff, edit, finalize, `/explain`, `/validation`, and the published data checks. `/validation` currently serves an older val report; refresh is requested from data.
- M0 suites/builds pass: data 3 tests, engine 34 tests, reo 7 tests, app production build; expanded live smoke passes all current engine/reo routes and published data artifacts.
- Live engine-backed app walk passes without API keys through final customer quote. BLOCKED sent to reo for a customer response range that differs from the same-turn plan card. Data also needs to publish the current val score so `/validation` stops serving the older `model: all` report; demo rehearsal awaits `pitch/demo-script.md`.

## Decisions

(one line each: what, why)
