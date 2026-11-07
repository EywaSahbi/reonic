# reo — home energy planning for installers

reo gives homeowners an initial energy-system design and estimated price, then prepares an offer for the installer to review. The customer experience is white-label; the demo installer is Sonnfeld.

**Numbers come from the engine; words come from reo.** A deterministic Python engine sizes solar, battery, heat pump and wallbox systems, prices them, and explains its decisions. The reo backend handles conversations and runs skills with scoped tools, grounding checks, budgets and an approval gate. The React app shows the customer journey and planner workspace.

## Run locally

Requirements: Python 3.12+, uv, Node.js and npm. Run each service in its own terminal from the repository root:

```sh
cd engine
uv sync
uv run uvicorn api:app --port 8000
```

```sh
cd reo
uv sync
uv run uvicorn api:app --port 8001
```

```sh
cd app
npm install
npm run dev
```

The frontend defaults to an in-browser mock. For the live backend, set `VITE_API_URL=http://localhost:8001` before starting Vite. In PowerShell:

```powershell
$env:VITE_API_URL = 'http://localhost:8001'
npm run dev
```

Open the [customer site](http://localhost:5173/) and [planner workspace](http://localhost:5173/#/installer). Start with “we use about 4,500 kWh a year”, answer the heating, EV and existing-solar questions, and send the plan to the installer. Open the new plan in the planner workspace to review variants, edit the design and approve or reject proposed actions.

Copy `reo/.env.example` to `reo/.env` for optional Anthropic and ElevenLabs credentials. Without an Anthropic key, reo uses a scripted planner with the same tool and approval workflow. Voice needs ElevenLabs credentials. Never commit keys.

## What the planner gets

- Three offer variants with engine designs and estimated prices.
- Reasons, confidence, similar-project flags, site-visit checklist and editable customer message.
- Harness traces for offer preparation and “Ask reo why”, including grounding checks.
- Proposed actions that require a planner click to execute.
- A reality-check panel showing published held-out validation scores.

## Validation and limits

The fixed project split separates training, validation and test homes. Parameters are fitted on training homes; `data/score.py` compares predictions with historical expert designs. The reality-check panel reads the published scores through reo's `/validation` endpoint. See [data reports](data/reports/) for methodology and results.

Expert agreement is imperfect: full-bundle agreement remains close to the simple baseline, and battery sizing is difficult. Existing equipment and installer preferences matter. Customer prices are estimates until the installer confirms a quote. Roof outlines are estimates and need site verification. Mock-mode designs and prices are UI placeholders, not engine validation evidence.

## Checks and demo

```sh
cd app
npm run build
```

Backend checks and harness evaluations:

```sh
cd reo
uv run pytest test_api.py
uv run python -m evals
```

The [five-minute demo script](pitch/demo-script.md) covers the customer → planner → confirmed quote journey and recording fallback. Rehearsal, final deck and fallback recording remain scheduled for the freeze. Raw and derived project data stay within the team.

Team workflow and ownership: [AGENTS.md](AGENTS.md). API boundaries: [reo contract](reo/CONTRACT.md), [engine contract](engine/CONTRACT.md).
