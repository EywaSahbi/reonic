# Plan

Times are Munich time. Each milestone ends with a `DONE` on the board from every role that delivered into it (addressed to its consumers and qa).
Humans own this file; agents propose changes with a `DECISION`.
Restructured Sat ~17:30 for the reo vision (see `AGENTS.md` → Product).

## Milestones

| | When | engine (Ege) | reo (Eywa) | data (Eywa) | app (Raneem) |
|---|---|---|---|---|---|
| **M0 Contracts + stubs** | Sat 19:00 | `CONTRACT.md` v1 agreed with reo; stub `/design` | `CONTRACT.md` v1 agreed with app; stub API with canned turns | `projects.parquet` + `split.csv` | `persona.md` + `flow.md`; UI skeleton on the reo mock |
| **M1 Minimum, end to end** | Sat 23:30 | real coupled design, price, economics, reasons, locks; `val` score | conversation loop with Claude + scripted fallback; plan store, handoff, installer edit, finalise | `score.py` + baseline; `benchmarks.json` | customer flow + installer view live against reo; demo script draft |
| **M2 Expert-grade** | Sun 09:00 | `/explain` + what-ifs; refined params | flags, similar projects, "ask why", address mock, `/validation` | test report, deviation analysis, charts | flags, reality-check panel, address input, polish |
| **M3 Freeze** | Sun 12:00 | bug fixes only | bug fixes only | final numbers frozen | rehearsed demo, fallback recording, deck, README |
| **Submit** | Sun 14:30 | | | | humans submit (deadline 15:00) |

qa (Raneem's Codex) verifies every delivery as it lands, runs the end-to-end demo walk from M1, and does a final clean-clone run at M3.

**M1 is the challenge's minimum result:** a customer gives a few facts → complete design with explanation and price → one more fact changes the design → handoff → installer changes something → updated design and final quote; plus validation numbers against expert designs on `val`. Nobody starts M2 work while an M1 item of theirs is open.

## Handoffs (who waits on whom)

- app → reo: `experience/persona.md` + `flow.md` (M0), UI needs as `NEED`s.
- engine → reo: contract + stub (M0), real `/design` with locks and prices (M1), `/explain` (M2).
- reo → app: contract + stub (M0), live customer + installer endpoints (M1), flags, ask, validation (M2).
- data → engine: `projects.parquet` + `split.csv` (M0), `score.py` (M1).
- data → reo: `benchmarks.json` (M1), score JSON for `/validation` (M2).
- data → app: charts and numbers for the deck (M2).

## Demo story (five minutes)

1. A homeowner on the installer's website tells reo "we use about 4,500 kWh a year" → instant first design and price range.
2. reo asks for more; they mention gas heating and "we're buying an electric car next year" → the design adapts, reo explains why.
3. They hand the plan over. The installer opens it: reasons, flags vs similar real projects, edits one component → everything re-derives → finalise → the customer sees the final quote.
4. Reality check: the engine's designs compared with expert designs on projects it never saw.

## Budget

Only an Anthropic API key for reo. No other paid services (the address lookup is mocked). Anything else is a `DECISION`.

## Open decisions

- Fit `engine/params.json` on `train` projects, or keep hand-set values and use the data only for validation? (Humans.)
- Which option counts as the expert design when a project has several? (Ask the Reonic experts.)
