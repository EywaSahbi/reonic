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

- `qa/smoke.py` v1: engine + reo route/shape checks, including empty/total/household demand and weekly/daily EV distance inputs, plus optional processed-data/split checks; later milestone endpoints skip on 404/405.
- Verified app mock flow (`0e16e40`), tap-first opening (`9ac9490`), Reonic branding (`e0b56cf`), and picture cards/house illustration (`adfa400`): production builds pass; customer design → handoff → installer edit/re-derive → rationale → finalise → confirmed quote; both views reviewed.

## Decisions

(one line each: what, why)
