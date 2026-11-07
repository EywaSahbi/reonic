# qa/ status (owner: `RaneemK-commits`, Codex agent)

## Backlog (top = next)

- [x] `smoke.py` v0 from the first `engine/CONTRACT.md` and `data/CONTRACT.md`
- [x] Rewrite `smoke.py` for the restructured `engine/CONTRACT.md` and the new `reo/CONTRACT.md` (v0 targets the retired engine contract)
- [ ] Verify each M0 `DONE` (engine stub, reo stub, data table + split, app skeleton) as it lands
- [ ] M1: end-to-end demo walk; fallback without API key; hard-rule-2 number check; reproduce engine's `val` score
- [ ] Test-leak check on `engine/`
- [ ] M2: reproduce test-set numbers; rehearse `pitch/demo-script.md`
- [ ] M3: final full run on a clean clone before submission

## Published

- `qa/smoke.py` v1: current engine + reo contract checks and optional processed-data/split integrity checks; later milestone endpoints skip on 404/405.
- Verified app customer mock skeleton at `8ce3904`: install/build pass; 4,500 kWh → gas → planned EV → mock handoff flow completes.

## Decisions

(one line each: what, why)
