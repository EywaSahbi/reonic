# reo/ status (owner: `EywaSahbi`)

## Backlog (top = next)

- [x] `CONTRACT.md` v1; API (`api.py`) with plan store, all customer + installer endpoints, Claude loop, scripted fallback, engine-offline mode (M0/M1)
- [x] Verified live against engine stub 3c0b18b: full demo (kWh, Gas, EV, why battery, Bavaria, handoff, installer edit + ask, finalise) works
- [ ] LLM turns take ~6 s (Opus 5.5, effort low); consider a faster model if the demo feels slow (human call)
- [ ] Offline/scripted replies in German when the customer writes German (now English only)
- [x] Flags + similar projects from data's benchmarks (`evidence.py`); `/plans/{id}/ask`; `/validation` (M2)
- [x] Voice via ElevenLabs (`voice.py`, `/sessions/{id}/voice`, `/tts`, `/health.voice`)
- [ ] Mocked address lookup for the demo addresses (M2)

## Published

- API on :8001 (`uv run uvicorn api:app --port 8001`), CONTRACT v1, tests `test_api.py` (demo flow with fake engine, engine-down mode).

- LLM layer (`llm.py`: `extract` facts via structured output, `reply` from engine result; `--check` verifies the key), `engine.py` client, `flow.py` next question + handoff, `prompt.md` operating rules. Key goes in `reo/.env` (see `.env.example`).

## Decisions

(one line each: what, why)
- Two LLM calls per turn (extract -> engine -> reply), not a tool loop: the engine is always called in code each turn, so every number is from this turn (hard rule 2).
- Model `claude-opus-5-5` at effort `low` (override `REO_MODEL`, `REO_EFFORT`); server-side `fallbacks: "default"` on; any LLM failure returns None -> scripted fallback.
- Persona stays in `experience/persona.md` (app); reo only adds `reo/prompt.md` (how to use the engine result).
- Heating and EV are always asked while unknown (engine only assumes them, never lists them as missing); after that reo asks what the engine lists as high or medium impact. Handoff offer: heating + EV known, or nothing left to ask.
- `region` (engine 718cd3f) asked after roof as a choice of state codes; extracted from state or city names.
- Customer-stated yearly kWh -> `total_demand_kwh` (engine 336060e), not `annual_demand_kwh`.
- Engine down -> contract-shaped design with no numbers (`params_version: engine-offline`), reo says it can't calculate; installer edits return 503.
- Similar projects never go to the customer or the LLM (hard rule 5); flags are aggregate and may (persona).
- Promised app (ACK on board): `Plan.summary?`, `GET /prices` passthrough, locks persist across `/edit` (merged per field); instant chip turns without LLM; zero-fact first design.
