# engine/ — deterministic design core (owner: `egeunluer`)

Every number reo shows comes from you: which components a home gets, how large, what it costs, what it saves, and why. **No LLM, no state, no randomness.** Same input, same output, with reasons.
You write only in `engine/`. You read `data/processed/` and run data's scoring tool; you never edit `data/`.

## Deliverables

1. **API** per [CONTRACT.md](CONTRACT.md): FastAPI on `:8000`. At M0 a stub that returns a fixed design so reo can build against it.
2. **Design rules**, coupled as a whole:
   - Total demand = household + EV (km/yr × ~0.18 kWh/km) + heat pump (heating demand / COP ~3). `energy_demand_wh` in the data **excludes** EV and heat pump (see `docs/dataset_explanation.md`).
   - PV from total demand, capped by roof area when known (~5.5 m² per kWp); snapped to real module counts (~0.43 kWp each).
   - Battery yes/no and size from PV size and demand; heat pump only with fossil heating and never when one exists; wallbox with EV (now or planned).
   - Missing inputs get explicit defaults (listed in `assumptions`) and widen the `range` of each size; each new fact narrows it. Report `missing_inputs` ranked by how much they would tighten the design: reo uses this to pick its next question.
3. **Parameters** live in `engine/params.json` (kWp per MWh, battery thresholds and ratio, typical package sizes, COP, …). v0 is hand-set from domain knowledge. Optional upgrade: fit them on `split == train` projects only (the team has not decided yet: ask with `DECISION` before doing it). Never look at `test`.
4. **Pricing** from a price list (`engine/prices.json`, public German market ranges: €/kWp installed, €/kWh battery, heat pump by kW, wallbox, fixed fees). Requests may override it (the installer edits prices in their view). Output line items + total + a low/high range while inputs are missing.
5. **Economics**: self-consumption, autarky, annual savings, simple payback, from the design and the home's price and tariff. Rough and transparent beats precise and opaque.
6. **Refine**: `locks` fix any component (on/off and/or size); everything else re-derives around it.
7. **Reasons**: per component, 1–3 short planner-grade reasons that name the input that drove them ("EV adds ~2,700 kWh/yr, so PV goes from 7 to 9 kWp").
8. **Predictions for validation**: `uv run python predict.py --split val|test` reads `data/processed/projects.parquet` and writes `engine/out/predictions_<split>.csv`; data scores it.

## Commands

```bash
cd engine && uv sync
uv run uvicorn api:app --reload --port 8000
uv run python predict.py --split val && (cd ../data && uv run python score.py ../engine/out/predictions_val.csv --split val)
```
(Create these files as you need them; CORS open to `http://localhost:5173` and `:8001`.)
