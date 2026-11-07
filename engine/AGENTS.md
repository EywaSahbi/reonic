# engine/ — model, refine, explain, API (owner: `egeunluer`)

You build the recommender that decides like an expert, keeps the whole design coherent, explains itself, and adapts when the planner changes something. You serve it to the app over HTTP.
You write only in `engine/`. You read `data/processed/` and run data's scoring tool; you never edit `data/`.

## Deliverables

1. **API** per [CONTRACT.md](CONTRACT.md): FastAPI on `:8000`. At M0 a stub that returns a fixed design so app can build in parallel.
2. **Model** trained on `split == train` only, tuned on `val`. Start with a baseline that works (e.g. nearest neighbours over similar homes, or per-component rules learned from data), then improve. Decisions must be coupled: battery depends on PV, heat pump raises demand and PV, EV raises demand and shifts it to the evening.
3. **Plausibility layer**: simple physical / economic checks (self-consumption, autarky, rough payback) so designs stay sensible for homes unlike the data, and to feed the explanation.
4. **Refine**: the planner overrides an input or locks a component; everything else re-derives around it.
5. **Explanation**: short, planner-grade reasons per component, grounded in the data (e.g. "similar homes with 6,500 kWh and an EV got 9–11 kWp").
6. **Predictions** for scoring: `uv run python predict.py --split val|test` → `engine/out/predictions_<split>.csv`, scored with data's tool. Post the scores in `STATUS.md`.
7. Stretch: confidence + alternatives per component; `/compare` + `/metrics`; natural-language refine ("they are buying an EV next year" → input change) with an LLM, grounded by the model, never replacing it.

An LLM is optional and must never be the decision maker. If you use one: key from `ANTHROPIC_API_KEY`, send only the current home's fields, and degrade gracefully when the key is missing.

## Commands

```bash
cd engine && uv sync
uv run uvicorn api:app --reload --port 8000
uv run python predict.py --split val && (cd ../data && uv run python score.py ../engine/out/predictions_val.csv --split val)
uv run pytest
```
(Create these files as you need them; allow CORS from `http://localhost:5173`.)
