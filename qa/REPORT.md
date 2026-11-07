# QA report

Newest first. Only build, contract, metric, and demo findings are tracked.

## 2026-11-07 — initial QA setup

- `qa/smoke.py` syntax check: passed with `python -m py_compile qa/smoke.py`.
- Engine smoke: unable to connect to `http://localhost:8000` (`WinError 10013` in the restricted environment). No engine implementation is currently present in this clone, so `/health` and `/design` are not yet available to verify.
- Data artifact check: skipped; `data/processed/projects.parquet` and `split.csv` are not published in this clone.
- App build/API client check: skipped; app source and package manifest are not published in this clone.
