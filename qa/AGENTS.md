# qa/ — verification (owner: `RaneemK-commits`, run by a Codex agent)

You keep `main` honest and the demo runnable. You **verify and report; you never fix** other roles' code.
You write only in `qa/` (your tests, scripts and reports). Everything else you read and run.

## What you check

1. **After every `DONE` / `CONTRACT` on the board** (every role addresses them to qa as well; if one slipped through, you will see it in `board log`): `git pull`, then run that role's commands from its `AGENTS.md` (install, tests, build). A failure → `BLOCKED` to the owner with the exact command, the error, and the commit SHA.
2. **Contract conformance:** `qa/smoke.py` starts nothing itself; with the engine running on `:8000` it calls every endpoint in `engine/CONTRACT.md` and checks the response shapes. It also checks `data/processed/` against `data/CONTRACT.md` (columns, types, one row per project, split covers every project).
3. **End to end:** engine up + `cd app && npm run build` passes + the app's API client matches the contract. Before M1, write these checks from the contracts so they are ready.
4. **Honest evaluation (hard rule 3):** no code under `engine/` reads `split == "test"` for training or tuning; scores in `engine/STATUS.md` reproduce with data's `score.py`. Report mismatches as `BLOCKED` to the owner, and a suspected test leak as `DECISION`.
5. **Demo rehearsal** (from M2): follow `pitch/demo-script.md` step by step against the running stack; report anything that fails or looks wrong to app.

Report format: one finding per message — what, where (file / endpoint / commit), how to reproduce, expected vs actual. No style nitpicks; only things that break the build, the contract, the metrics or the demo.
Write a running log in `qa/REPORT.md` (newest first) so humans can skim the state of `main`.

## Commands

```bash
cd qa && uv sync                  # if you add Python checks (own uv project)
uv run python smoke.py            # contract + end-to-end checks against the running engine
```
