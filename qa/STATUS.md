# qa/ status (owner: `RaneemK-commits`, Codex agent)

## Backlog (top = next)

- [x] `smoke.py` v0 from the first `engine/CONTRACT.md` and `data/CONTRACT.md`
- [x] Rewrite `smoke.py` for the restructured `engine/CONTRACT.md` and the new `reo/CONTRACT.md` (v0 targets the retired engine contract)
- [x] Verify each M0 `DONE` (engine stub, reo stub, data table + split, app skeleton) as it lands
- [ ] M1: full engine-backed end-to-end demo walk; fallback without API key; hard-rule-2 number check; reproduce engine's `val` score — walkthrough, fallback, and score pass; hard-rule 2 BLOCKED on a response/card range mismatch
- [x] Test-leak check on `engine/`: fitted params declare `split: train`; reproduced val/test prediction runs use the fixed held-out splits
- [ ] M2: reproduce test-set numbers; rehearse `pitch/demo-script.md` — test numbers reproduced; demo script file is not yet published; `/validation` currently serves a stale val report
- [ ] M3: final full run on a clean clone before submission

## Published

- `qa/smoke.py` v2: current engine/reo response shapes, regional sizing, explanation/assumption consistency, and Parquet/split/benchmark contract checks, including customer-level split isolation. `--skip-engine`/`--skip-reo` allow per-service checks.
- `qa/reproduce_score.py`: runs the engine predictor and official data scorer for val/test while directing temporary outputs to `qa/` only.
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
