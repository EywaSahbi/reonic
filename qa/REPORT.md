# QA report

Newest first. Only build, contract, metric, and demo findings are tracked.

## 2026-11-07 — app experience contract check (commit 1155aa0)

- **BLOCKED app:** `experience/flow.md`, Stage 5 says to ask `{field: name, ..., input: "text"}`. In `reo/CONTRACT.md`, `Turn.ask.field` is `keyof HomeFacts` and `input` is only `number | boolean | choice | address`; `name` and `text` are invalid. Reproduce by comparing Stage 5's ask object with the `Turn` type. Expected: collect the name through a contract-valid handoff flow (the handoff body already has `name`). Actual: the prescribed ask object cannot conform to the reo response type.
- The documented HomeFacts field names otherwise match `engine/CONTRACT.md`. App build is not runnable yet because `app/` has no package manifest or source at this commit.
- **Verified fixed in app commit `fcd570d`:** Stage 5 now collects name/email in an app-owned form and sends them directly in the contracted `/handoff` body. Rechecked the Stage 5 text and confirmed the invalid `ask` object is gone.

## 2026-11-07 — persona update check (commit 5e3ecd0)

- Passed review of the new customer-facing statements: funding is described only as possible with no amounts or deadlines, and aggregate comparisons are allowed only when supported by the current plan's attached flags/benchmarks. Individual projects remain installer-only. No contract change was included.

## 2026-11-07 — smoke checks updated for reo architecture

- Rewrote `qa/smoke.py` for current engine and reo contract shapes, including every contracted endpoint and milestone-gated optional routes. Added data column and split coverage checks using the renamed `HomeFacts` fields.
- Syntax check: passed with `python -m py_compile qa/smoke.py`.
- Runtime check: `python qa/smoke.py` stops at the engine health call because `localhost:8000` actively refused the connection; engine/reo service code and processed artifacts are not yet published in this clone. Full checks await the M0 `DONE` handoffs.

## 2026-11-07 — initial QA setup

- `qa/smoke.py` v0 syntax check passed with `python -m py_compile qa/smoke.py` (superseded by current-contract rewrite above).
- Engine smoke: unable to connect to `http://localhost:8000` (`WinError 10013` in the restricted environment). No engine implementation is currently present in this clone, so `/health` and `/design` are not yet available to verify.
- Data artifact check: skipped; `data/processed/projects.parquet` and `split.csv` are not published in this clone.
- App build/API client check: skipped; app source and package manifest are not published in this clone.
