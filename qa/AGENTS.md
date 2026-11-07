# qa/ — verification (owner: `RaneemK-commits`, run by a Codex agent)

You keep `main` honest and the demo runnable. You **verify and report; you never fix** other roles' code.
You write only in `qa/` (your checks and reports). Everything else you read and run.

## What you check

1. **After every `DONE` / `CONTRACT`** (every role addresses them to qa): `git pull`, then run that role's commands from its `AGENTS.md` (install, tests, build). A failure → `BLOCKED` to the owner with the exact command, the error and the commit SHA.
2. **Contract conformance** (`qa/smoke.py`): with the services running, call every endpoint in `engine/CONTRACT.md` (`:8000`) and `reo/CONTRACT.md` (`:8001`) and check response shapes; check `data/processed/` against `data/CONTRACT.md`. Skip what does not exist yet.
3. **Hard rule 2 (the engine decides, reo talks):** for a few customer turns, every number in reo's reply text must appear in the plan's `design` for that turn. A number that does not → `BLOCKED` to reo.
4. **Fallback:** reo must complete the demo flow with `ANTHROPIC_API_KEY` unset.
5. **End to end:** engine + reo up, `cd app && npm run build` passes, then walk the demo: session → facts → handoff → installer edit → finalise → customer sees the quote.
6. **Honest validation:** nothing in `engine/` reads `test` projects; engine's scores in `engine/STATUS.md` reproduce with data's `score.py`. A suspected test leak → `DECISION`.
7. **Demo rehearsal** (from M2): follow `pitch/demo-script.md` step by step; report anything that fails or looks wrong to app.

One finding per message: what, where (file / endpoint / commit), how to reproduce, expected vs actual. No style nitpicks.
Keep a running log in `qa/REPORT.md` (newest first).

## Commands

```bash
cd qa && uv sync && uv run python smoke.py
```
