# reo/ status (owner: `EywaSahbi`)

## Handover (session ended 2026-11-07 by Eywa's decision)

Everything above the open items works and is pushed. To resume: read this file, CONTRACT.md, run `uv run pytest` (27 pass), start `uv run uvicorn api:app --port 8001` with the engine on :8000.
Open: Haiku vs Sonnet for installer_qa (human call, models in `llm.py`), German scripted replies, chat_turn onto the harness, live bill test, final voice. Possible engine NEED: 5 kWh battery suggested even when the roof caps PV at ~1 kWp.

## Installer-backend cleanup (2026-11-08)

Reproduced and fixed (regressions in `test_installer.py`, fake engine; live check on engine :8000 + real reo, see CONTRACT "State rules v1.3"):
- Torn reads: GET endpoints and SSE read `plans.json` without the lock while the offer thread rewrote it → `JSONDecodeError` 500 (hit on `/handoff`). All reads now go through `_read()`.
- Customer `/sessions` responses carried the installer `offer_pack` and the planner's working design (grant line) before the quote.
- After handoff/quote a customer message re-ran the design and changed the confirmed quote; a second `/handoff` reset `quoted` → `handed_over` and restarted prep.
- `send_quote` without a chosen variant re-applied the proposed Recommended locks and dropped the planner's edits; the message described the old design.
- Draft kept proposing the original slot after a different slot was booked.
- `/finalize` then approving `send_quote` sent a second confirmation; edits after quote changed the confirmed design (now 409).
- Edits during preparation left the landed variants not stale; an older run could overwrite a newer pack; a reo restart left packs `preparing` forever and their runs 404.
- engine 11f5a6a answers 422 for demand/roof <= 0: reo drops those customer values (asks again) and /edit returns 422, so a 422 never reads as "engine down".
Checks: `uv run pytest` 27 pass; `uv run python -m evals` 9/9 (scripted, live engine); live journey incl. SSE replay, Sonnet pack, 409s on repeat approve/reject, restart mid-prep → failed.
Not covered: engine downtime only with the fake engine (did not stop Ege's engine); customer `installer_edits`/`history` still visible to the customer (totals only, no change in this pass).

## Backlog (top = next)

- [x] Deployment guard: planner Bearer token (`REO_INSTALLER_TOKEN`) on installer routes + `REO_ALLOWED_ORIGINS` CORS (`test_auth.py`)
- [ ] Roof lookup: OSM building relations (multipolygon), app NEED 23:4x (Platz der Republik 1 Berlin, Schellingstraße 3 München)

- [ ] Harness evals on data's scenarios.json (`uv run python -m evals`)
- [x] bill_reader skill (`/sessions/{id}/bill`, vision; live vision not yet tried on a real bill) and goal_planner skill (Turn.goal_result, /plans/{id}/ask)
- [x] installer_qa on the harness (Sonnet 5.5 / scripted)
- [x] Mocked address lookup (`addresses.json`: Musterstraße München, Hauptstraße Hamburg, Lindenweg Dresden)
- [x] Roof from address via OpenStreetMap (roof.py), width x length input, skip; engine cap delivered (ad07027), verified with app's dimensions input (de19c1e)
- [ ] chat_turn onto the harness; German scripted replies; follow_up (stretch)

- [x] `CONTRACT.md` v1; API (`api.py`) with plan store, all customer + installer endpoints, Claude loop, scripted fallback, engine-offline mode (M0/M1)
- [x] Verified live against engine stub 3c0b18b: full demo (kWh, Gas, EV, why battery, Bavaria, handoff, installer edit + ask, finalise) works
- [ ] LLM turns take ~6 s (Opus 5.5, effort low); consider a faster model if the demo feels slow (human call)
- [ ] Offline/scripted replies in German when the customer writes German (now English only)
- [x] Flags + similar projects from data's benchmarks (`evidence.py`); `/plans/{id}/ask`; `/validation` (M2)
- [x] Voice via ElevenLabs (`voice.py`, `/sessions/{id}/voice`, `/tts`, `/health.voice`)

## Published

- Agent harness (`harness/`: tools with effect classes, runner, guards, skills) with `offer_prep` (Opus 5.5 / scripted): offer pack on handoff, runs + SSE, variant choice, approve / reject (only path to execute tools). Live Opus run: 30 s, grounding ok.

- API on :8001 (`uv run uvicorn api:app --port 8001`), CONTRACT v1, tests `test_api.py` (demo flow with fake engine, engine-down mode).

- LLM layer (`llm.py`: `extract` facts via structured output, `reply` from engine result; `--check` verifies the key), `engine.py` client, `flow.py` next question + handoff, `prompt.md` operating rules. Key goes in `reo/.env` (see `.env.example`).

## Decisions

(one line each: what, why)
- Two LLM calls per turn (extract -> engine -> reply), not a tool loop: the engine is always called in code each turn, so every number is from this turn (hard rule 2).
- Chat model `claude-haiku-5-5`, offer agent `claude-sonnet-5-5` (EywaSahbi's call, replaces Sonnet chat / Opus agent), effort `low` (override `REO_MODEL`, `REO_EFFORT`); server-side `fallbacks: "default"` on; any LLM failure returns None -> scripted fallback.
- Persona stays in `experience/persona.md` (app); reo only adds `reo/prompt.md` (how to use the engine result).
- Heating and EV are always asked while unknown (engine only assumes them, never lists them as missing); after that reo asks what the engine lists as high or medium impact. Handoff offer: heating + EV known, or nothing left to ask.
- `region` (engine 718cd3f) asked after roof as a choice of state codes; extracted from state or city names.
- Customer-stated yearly kWh -> `total_demand_kwh` (engine 336060e), not `annual_demand_kwh`.
- Engine down -> contract-shaped design with no numbers (`params_version: engine-offline`), reo says it can't calculate; installer edits return 503.
- Existing solar is asked after EV (choice 'Yes, I have solar' / 'No solar yet'): data's test report 7fd5ecb shows 49 of 52 PV yes/no misses are homes that already have solar.
- goal_planner runs as a fixed, logged search over engine what-ifs + anchors (< 1 s), not an Opus loop: a customer chat turn can't wait 30 s; EV homes keep their wallbox. Customer goal = customer's choice, so the best variant becomes the plan; installer goal questions apply nothing.
- bill_reader: facts from the bill wait for the customer's 'Yes, that's right' before they enter the plan.
- Harness: models get `read`/`propose` tools only; `evidence.similar` (individual homes) is NOT a model tool (hard rule 5), the model sees aggregate percentiles only. Grounding guard: every number in output text within persona rounding of a tool-result number of the same run; small counts <= 12 allowed.
- Customer-side engine calls send prices {heatpump_subsidy_share: 0}: no grant line or post-grant price in the customer chat (persona + app FYI 20:27, until Raneem decides); installer views and the offer pack keep the KfW line. A planner-approved quote shows whatever the planner sent.
- Roof lookup: OpenStreetMap (EywaSahbi's choice over Google Solar: free, no key). Overpass was at capacity, so building outlines come from the OSM map API (0.4 s). Sunny face = footprint (flat) or footprint / cos 35° / 2 (pitched), said as an estimate. Address goes to OSM (third party), only for that lookup; results cached in roof_cache.json (gitignored).
- Similar projects never go to the customer or the LLM (hard rule 5); flags are aggregate and may (persona).
- Promised app (ACK on board): `Plan.summary?`, `GET /prices` passthrough, locks persist across `/edit` (merged per field); instant chip turns without LLM; zero-fact first design.
