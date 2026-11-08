# qa/ — verification, never fixes

> Back to the [project README](../README.md). Owner: `RaneemK-commits` (a Codex agent). QA reports breakages with steps to reproduce; the owning folder fixes them.

| File | What it does |
|---|---|
| [REPORT.md](REPORT.md) | newest-first log of what was verified: clean-clone run, live flow, score reproduction, findings |
| [smoke.py](smoke.py) | contract smoke checks against the running engine (`:8000`), reo (`:8001`) and the data files |
| [reproduce_score.py](reproduce_score.py) | re-runs the engine on the dataset from its `train`-fitted parameters and re-scores `val`/`test` |
| [STATUS.md](STATUS.md) | backlog and what is verified |

What was reproduced (see the report for the exact runs): a fresh clone passes all tests without API keys, the 9 harness scenarios pass in scripted mode, and the published validation numbers match a fresh run with 0 missing predictions.

```bash
# services already running
python qa/smoke.py
cd engine && uv run python ../qa/reproduce_score.py --split both
```
