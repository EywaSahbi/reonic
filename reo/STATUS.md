# reo/ status (owner: `EywaSahbi`)

## Backlog (top = next)

- [ ] Agree `CONTRACT.md` v1 with app (`CONTRACT` to app, qa); stub API with canned turns and a fixed plan → `DONE` to app, qa (M0)
- [ ] Plan store; `/sessions` + `/facts` + `/handoff` + installer `/plans`, `/edit`, `/finalize` wired to the engine (M1)
- [ ] Conversation loop with Claude tool use: fact extraction → engine → next question → reply from engine numbers; persona from `experience/persona.md` (M1)
- [ ] Scripted fallback without API key, covering the demo script (M1)
- [ ] Flags + similar projects from data's benchmarks; `/plans/{id}/ask`; `/validation` (M2)
- [ ] Mocked address lookup for the demo addresses (M2)

## Published

- LLM layer (`llm.py`: `extract` facts via structured output, `reply` from engine result; `--check` verifies the key), `engine.py` client, `flow.py` next question + handoff, `prompt.md` operating rules. Key goes in `reo/.env` (see `.env.example`).

## Decisions

(one line each: what, why)
- Two LLM calls per turn (extract -> engine -> reply), not a tool loop: the engine is always called in code each turn, so every number is from this turn (hard rule 2).
- Model `claude-opus-5-5` at effort `low` (override `REO_MODEL`, `REO_EFFORT`); server-side `fallbacks: "default"` on; any LLM failure returns None -> scripted fallback.
- Persona stays in `experience/persona.md` (app); reo only adds `reo/prompt.md` (how to use the engine result).
- Promised app (ACK on board): `Plan.summary?`, `GET /prices` passthrough, locks persist across `/edit` (merged per field); instant chip turns without LLM; zero-fact first design.
