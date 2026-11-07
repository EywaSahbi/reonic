# QA report

Newest first. Only build, contract, metric, and demo findings are tracked.

## 2026-11-07 — smoke checks updated for reo architecture

- Rewrote `qa/smoke.py` for current engine and reo contract shapes, including every contracted endpoint and milestone-gated optional routes. Added data column and split coverage checks using the renamed `HomeFacts` fields.
- Syntax check: passed with `python -m py_compile qa/smoke.py`.
- Runtime check: `python qa/smoke.py` stops at the engine health call because `localhost:8000` actively refused the connection; engine/reo service code and processed artifacts are not yet published in this clone. Full checks await the M0 `DONE` handoffs.

## 2026-11-07 — initial QA setup

- `qa/smoke.py` v0 syntax check passed with `python -m py_compile qa/smoke.py` (superseded by current-contract rewrite above).
- Engine smoke: unable to connect to `http://localhost:8000` (`WinError 10013` in the restricted environment). No engine implementation is currently present in this clone, so `/health` and `/design` are not yet available to verify.
- Data artifact check: skipped; `data/processed/projects.parquet` and `split.csv` are not published in this clone.
- App build/API client check: skipped; app source and package manifest are not published in this clone.
