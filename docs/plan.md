# Plan

Times are Munich time. Each milestone ends with a `DONE` on the board from every role that delivered into it.
Humans own this file; agents propose changes with a `DECISION`.

## Architecture

```
Project Data/*.csv ──► data/ ──────────────► data/processed/{projects.parquet, split.csv}
   (read-only)          clean, expert            │
                        targets, split,          ▼
                        scoring           engine/  model + plausibility checks + refine + explain
                           ▲              FastAPI on :8000  (contract: engine/CONTRACT.md)
                           │                     │
   predictions CSV ────────┘                     ▼  HTTP / JSON
   (engine → data scoring tool)            app/  React planner UI on :5173 (+ homeowner view)
                                           pitch/ demo script, deck; README.md
```

## Milestones

| | When | data (EywaSahbi) | engine (egeunluer) | app (RaneemK-commits) |
|---|---|---|---|---|
| **M0 Contracts** | Sat 17:00 | `projects.parquet` v0 (one row per project: inputs + expert design), `split.csv`, `CONTRACT.md` filled in | `CONTRACT.md` v1 agreed with app; stub server returning a fixed design | UI skeleton against the stub: input form, design card |
| **M1 Minimum, end to end** | Sat 23:00 | scoring tool: predictions CSV → metrics; baseline numbers on `val` | baseline model (e.g. nearest neighbours / rules from data) behind `/design` + `/refine`, short explanation | form → design → explanation → change one input → updated design, live against the engine |
| **M2 Expert-grade** | Sun 09:00 | test-set report, deviation analysis (where and why we differ), charts for the deck | coupled model + physical/economic plausibility, confidence + alternatives, `/compare` + `/metrics` | "checked against reality" view (proposed vs expert, metrics across projects); refine by natural language if engine offers it; homeowner view if time |
| **M3 Freeze** | Sun 12:00 | final numbers frozen | bug fixes only | demo script rehearsed, fallback recording, deck, README |
| **Submit** | Sun 14:30 | | | humans submit (deadline 15:00) |

Minimum result first: nobody starts M2 work while an M1 item of theirs is open.

## qa (RaneemK-commits, Codex agent)

Verifies every `DONE` as it lands (tests, build, contract conformance), runs the end-to-end smoke test from M1, reproduces scores and checks for test leaks, rehearses the demo from M2, and does a final clean-clone run at M3. Reports to the owner; never fixes others' code. Brief: `qa/AGENTS.md`.

## Handoffs (who waits on whom)

- data → engine: processed table + split (M0), scoring tool (M1), deviation findings that suggest model fixes (M2).
- data → app: test metrics and charts for the reality-check view and the deck (M2).
- engine → app: contract + stub (M0), live `/design` + `/refine` (M1), `/compare` + `/metrics` (M2).
- app → engine: which inputs the form collects and which refine actions the UI offers (M0, as `NEED`).
- app → data: which metrics and charts the deck needs (M1, as `NEED`).

## Budget

No paid services beyond an LLM API key that the engine owner may use for explanations or natural-language refinement. Anything else is a `DECISION`.
