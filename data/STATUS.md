# data/ status (owner: `EywaSahbi`)

## Backlog (top = next)

- [x] Profile the raw CSVs → `docs/dataset_explanation.md`
- [x] `build.py` → `processed/projects.parquet` (HomeFacts column names) + `processed/split.csv`; `CONTRACT.md` v1 → `DONE` to engine, reo, qa (M0)
- [x] `score.py` + naive baseline on `val` → `DONE` to engine, qa (M1). Engine `all` on val: bundle 0.56 vs baseline 0.55
- [ ] Engine params must come from `train` only, or test numbers are in-sample (NEED to engine)
- [ ] `benchmarks.json` from `train` → `DONE` to reo, qa (M1)
- [ ] Test-set report, deviation analysis, charts → `DONE` to reo, app (M2)

## Published

- `docs/dataset_explanation.md` (commits 60f5b08, b81a28c)
- `processed/projects.parquet` (1,571 rows) + `processed/split.csv` (1,098 / 238 / 235), `CONTRACT.md` v1, `NOTES.md` (1e37ff2)
- `score.py`, `reports/score_all_val.json` (engine v0-handset+line on val)

## Decisions

- Expert option = highest `option_number` with hardware; documented default until Reonic confirms which option was signed.
- Split by customer (not only project) so no customer is in two splits; seed 42, 70/15/15 per installer.
- PV kWp from package name, else module count × Wp; count = max(Module rows, mounting rows). Estimates are marked in `target_source`.
- Keep large commercial-size projects; metrics use medians so they do not dominate.
- Size tolerance ±20 % relative (wallbox ±5 %), same as engine's own predict.py, so numbers are comparable.
- Baseline built from `train` medians only, so it never sees val/test.
