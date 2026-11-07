# app/ — UI, demo, pitch, README (owner: `RaneemK-commits`)

You own what the judges see: the planner UI, the five-minute demo story, the pitch deck and the README.
You write only in `app/`, `pitch/` and `README.md`. You talk to the engine over HTTP only and never edit `engine/` or `data/`.

## Deliverables

1. **Planner UI** (React + Vite + TypeScript, `:5173`), built against [engine/CONTRACT.md](../engine/CONTRACT.md):
   - Input form with the few facts a planner knows; sensible defaults.
   - Design card per component: on/off, size, confidence, alternatives, reasons; the overall summary.
   - Refine: change an input or lock / resize a component → updated design, with what changed highlighted.
   - "Checked against reality": proposed vs expert for a real test project, plus metrics across many projects.
   - Until the engine is live, use a local mock that matches the contract exactly, behind one switch (`VITE_API_URL`).
2. Stretch: homeowner view on the same engine (plain language, only the variants the installer allows, home data fixed); planner validation flags ("battery unusually large for a home like this").
3. **`pitch/demo-script.md`**: the five-minute story (home described → design appears → refined, e.g. EV next year → checked against reality), with the exact inputs to type.
4. **`pitch/`**: deck outline and content (problem, solution, evaluation, value for installers and homeowners); fallback recording plan.
5. **`README.md`** (submission): setup, approach, evaluation results, known limitations.

UX principles: the planner stays in control (every value overridable, reasons visible); no black box; fast. Plain language in the homeowner view.

## Commands

```bash
cd app && npm install
npm run dev          # http://localhost:5173, expects the engine on :8000 (or the mock)
npm run build        # must pass before you push
```
