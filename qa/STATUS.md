# qa/ status (owner: `RaneemK-commits`, Codex agent)

## Backlog (top = next)

- [x] `smoke.py` v0 from `engine/CONTRACT.md` and `data/CONTRACT.md` (runs against whatever exists, skips what does not)
- [ ] Verify each M0 `DONE` (data table + split, engine stub, app skeleton) as it lands
- [ ] M1: end-to-end check (engine live + app build + refine round trip); reproduce engine's `val` score with data's tool
- [ ] Test-leak check on `engine/` code
- [ ] M2: reproduce test-set numbers; rehearse `pitch/demo-script.md`
- [ ] M3: final full run on a clean clone before submission

## Published

- `qa/smoke.py`: health/design/refine shape checks and optional processed-data/split integrity checks. Syntax checked; execution currently cannot reach an engine because no server is published/running.

## Decisions

(one line each: what, why)
