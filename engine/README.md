# engine/ — the deterministic design core

> Back to the [project README](../README.md). Owner: `egeunluer`.

Every size, yes/no, price, saving and reason that reo shows comes from here. **No LLM, no state, no randomness**: the same input always gives the same output, with reasons. It is a FastAPI service on `:8000`.

## What it does

A handful of facts about a home (`HomeFacts`) go in; a complete, coupled, priced and explained design comes out:

- **PV, battery, heat pump, wallbox**: whether each is recommended and how large. Decisions are coupled: an EV or heat pump raises demand and so the PV size, PV size drives the battery, a roof can cap the modules.
- **Price**: line items from real products (`catalog.json`) and sourced German labour rates, with a typical low/high band and the KfW heat-pump grant.
- **Economics**: a one-year hourly simulation gives self-consumption, autarky, bills before/after, savings and payback.
- **Heating comparison** for gas/oil/district homes: heat pump vs today's running cost and CO₂.
- **Honesty about gaps**: missing inputs get explicit defaults (listed in `assumptions`), widen the ranges, and are ranked by how much each would tighten the design (`missing_inputs`) so reo knows what to ask next.
- **Refine with locks**: fix any component (on/off and/or size) and the rest re-derives around it; `/explain` returns the reasons and what-ifs (Δ price, savings, payback).
- **Installer style**: optional per-installer profiles fitted on that installer's training projects only.
- **Roof layout**: the sizing module (`pv.module`) so the planner view can draw the modules on the roof ([ROOF_LAYOUT.md](ROOF_LAYOUT.md)).

## API

| Route | Purpose |
|---|---|
| `GET /health` | liveness and parameter version |
| `GET /prices` | subsidy, feed-in and fuel rates (overridable per request) |
| `POST /design` | `{facts, locks?, prices?, installer?}` → components, price, economics, ranges, reasons, missing inputs |
| `POST /explain` | reasons and what-if deltas for one component |

Full shapes: [CONTRACT.md](CONTRACT.md).

## Files

| File | Role |
|---|---|
| [`api.py`](api.py) | FastAPI app |
| [`inputs.py`](inputs.py) | reads facts, fills defaults, sizes PV (expert line or installer package), roof check |
| [`design.py`](design.py) | battery, wallbox, heat pump, locks, budget, pricing, economics, ranges, reasons, what-ifs |
| [`sim.py`](sim.py) | hourly simulation (H0 load profile, EV, heat pump, PVGIS PV) |
| [`dataset.py`](dataset.py), [`predict.py`](predict.py) | offline: run the engine on the dataset and write predictions for scoring |
| [`params.json`](params.json), [`prices.json`](prices.json), [`catalog.json`](catalog.json), [`profiles.json`](profiles.json) | parameters (fitted on `train` only), price list, real products, installer profiles |
| [`tools/`](tools/) | scripts that derive the parameters from the data and public sources |
| [`video-voiceover/`](video-voiceover/) | the product video's voice-over track |

## Read next

| Doc | What is in it |
|---|---|
| [METHOD.md](METHOD.md) | how a design is made, every rule and parameter, results, known limits |
| [CONTRACT.md](CONTRACT.md) | the API reo calls |
| [SOURCES.md](SOURCES.md) | where every outside number comes from |
| [STATUS.md](STATUS.md) | backlog, scores, decisions |
| [PLAN.md](PLAN.md) | build log |
| [ROOF_LAYOUT.md](ROOF_LAYOUT.md) | design of the planner's module placement |

## Run

```bash
cd engine
uv sync
uv run uvicorn api:app --port 8000
uv run python predict.py --split val     # then score it with data/score.py
```
