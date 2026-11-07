# qa/ status (owner: `RaneemK-commits`, Codex agent)

## Backlog (top = next)

- [x] `smoke.py` v0 from the first `engine/CONTRACT.md` and `data/CONTRACT.md`
- [x] Rewrite `smoke.py` for the restructured `engine/CONTRACT.md` and the new `reo/CONTRACT.md` (v0 targets the retired engine contract)
- [ ] Verify each M0 `DONE` (engine stub, reo stub, data table + split, app skeleton) as it lands — engine, reo, and app verified; data artifacts still pending
- [ ] M1: full engine-backed end-to-end demo walk; fallback without API key; hard-rule-2 number check; reproduce engine's `val` score
- [ ] Test-leak check on `engine/`
- [ ] M2: reproduce test-set numbers; rehearse `pitch/demo-script.md`
- [ ] M3: final full run on a clean clone before submission

## Published

- `qa/smoke.py` v1: engine + reo route/shape checks, including empty/total/household demand and weekly/daily EV distance inputs, plus optional processed-data/split checks. `--skip-engine`/`--skip-reo` allow per-service checks; later milestone endpoints skip on 404/405.
- Verified app mock flow (`0e16e40`), tap-first opening (`9ac9490`), Reonic branding (`e0b56cf`), and picture cards/house illustration (`adfa400`): production builds pass; customer design → handoff → installer edit/re-derive → rationale → finalise → confirmed quote; both views reviewed.
- Verified reo API v1 (`2d6428f`): dependency sync and 4 tests pass; offline-mode smoke passed all current routes and confirms the API reports unavailability without numeric claims.
- Verified app integration (`28527ca`): production build passes. Live customer flow against reo with the engine offline keeps the plan paused, displays no sizes/prices, and continues collecting inputs without a handoff action. Full engine-backed journey remains pending the engine service.
- Reo engine-down behavior (`9b01a6c`): reo pytest suite and live smoke confirm offline fallback; API key was unset for the scripted fallback test.
- Verified reo voice turn (`2756583`): the mocked ElevenLabs transcription and TTS path passes, including an empty-audio response with no state change.
- Verified engine stub (`3c0b18b`): all 25 engine tests pass; live `/health`, `/prices`, `/design` demand/EV/region checks pass. Region smoke confirms northern Schleswig-Holstein yields a larger PV size than southern Bavaria for the same demand.
- Full live `qa/smoke.py` passes engine and reo routes through handoff, edit, and finalize. `/explain` and `/validation` remain milestone-gated; processed data and split artifacts are not yet published.

## Decisions

(one line each: what, why)
