# reo/ — the reo backend (LLM layer, conversation, agent harness)

> Back to the [project README](../README.md). Owner: `EywaSahbi`. FastAPI on `:8001`.

reo is the layer that **talks**. It extracts facts from what the homeowner says, calls the [engine](../engine/README.md) for every number, picks the next question, writes the reply from the engine's reasons, keeps the plan, and prepares the installer's offer. It never invents a number (hard rule 2).

## What it does

- **Customer side** (`/sessions*`): step form and chat. Fixed question order (yearly kWh → people → address → state → roof size → EV → heating → heat pump option → existing solar), instant chip turns without an LLM, voice in and out (ElevenLabs), bill reading by vision, a goal planner ("lowest bill", "budget"). The plan builds up with each answer.
- **Roof from an address**: [`roof.py`](roof.py) finds the building outline (demo addresses offline, else OpenStreetMap); [`roof_vision.py`](roof_vision.py) lets Claude Opus trace the visible roof on the satellite photo (three parallel runs, median area, area/position guards) and re-derives the plan.
- **Handoff and installer side** (`/plans*`): the plan goes to the planner; reo's **offer agent** prepares an offer pack in the background (variants, flags against similar homes, site-visit checklist, draft message, proposed actions) with a visible trace.
- **Planner roof layout** ([`layout.py`](layout.py)): places the engine's module count on the roof outline; `PUT /plans/{id}/layout` turns the planner's count into a PV lock.
- **Evidence** ([`evidence.py`](evidence.py)): aggregate flags from `data/processed/benchmarks.json` ("battery larger than 85% of similar homes"). Individual homes never reach the customer or an LLM.
- **Runs without keys**: with no `ANTHROPIC_API_KEY`, or on any LLM error, a scripted mode ([`scripted.py`](scripted.py)) gives the same screens and the same tool/approval workflow.

## The agent harness (`harness/`)

One small runtime that every capability runs on, with no agent framework (Anthropic SDK tool-use loop plus our own code):

| Piece | Idea |
|---|---|
| [`tools.py`](harness/tools.py) | every tool declares an effect class: `read`, `propose`, or `execute`. `execute` (book visit, send quote) is **never callable by a model**; only the planner's approve click runs it |
| [`skills.py`](harness/skills.py), [`skills/`](harness/skills/) | a skill = prompt + allowed tools + budget + output schema (`offer_prep`, `installer_qa`, `bill_reader`, `goal_planner`) |
| [`guards.py`](harness/guards.py) | guardrails in code: grounding (every number in the output matches a tool result of the same run), budgets, no execute without approval |
| [`runner.py`](harness/runner.py) | one loop for every skill, every step recorded as a trace the UI shows (SSE) |
| [`evals/`](evals/) | harness evals on data's hard-case scenarios (9/9 pass, scripted) |

## Files

| File | Role |
|---|---|
| [`api.py`](api.py) | all routes, plan store, auth |
| [`flow.py`](flow.py) | next question and handoff offer |
| [`llm.py`](llm.py), [`prompt.md`](prompt.md) | extraction and reply calls, operating rules (persona comes from [`experience/persona.md`](../experience/persona.md)) |
| [`engine.py`](engine.py) | thin client for the engine; the only way numbers enter reo |
| [`voice.py`](voice.py) | ElevenLabs speech-to-text and text-to-speech, spoken-number rules |
| [`demo_guard.py`](demo_guard.py) | access code and admission limits for the deployed demo |
| `test_*.py` | 69 tests (fake engine, no keys needed) |

## Read next

[CONTRACT.md](CONTRACT.md) (every route and type) · [CUSTOMER.md](CUSTOMER.md) (customer-side brief) · [VOICE.md](VOICE.md) · [STATUS.md](STATUS.md) (decisions).

## Run

```bash
cd reo
uv sync
cp .env.example .env            # optional: ANTHROPIC_API_KEY, ELEVENLABS_API_KEY (never commit keys)
uv run uvicorn api:app --port 8001     # needs the engine on :8000
uv run pytest
uv run python -m evals                 # harness evals (scripted, needs the engine)
```
