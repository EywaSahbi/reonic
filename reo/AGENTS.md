# reo/ — reo backend (owner: `EywaSahbi`)

You build reo's brain: the LLM layer around the engine, the conversation with the customer, the plan that is handed to the installer, and the installer-side assistant. You serve both of app's views over HTTP.
You write only in `reo/`. You read `experience/`, `engine/CONTRACT.md` and `data/processed/`; you never edit them.

## Deliverables

1. **API** per [CONTRACT.md](CONTRACT.md): FastAPI on `:8001`. At M0 a stub with canned replies and a fixed plan so app can build the UI.
2. **Conversation loop** per turn: extract facts from the customer's message (LLM tool call) → call engine `/design` → pick the next question from the engine's `missing_inputs` and `experience/flow.md` → LLM writes the reply **from the engine's numbers and reasons only** (hard rule 2). Also accept facts directly (chips, sliders, form fields) without the LLM.
3. **Persona**: load `experience/persona.md` at runtime into the system prompt; follow `experience/flow.md` for stages and the handoff moment. Never rewrite them; ask app with a `NEED`.
4. **Plan store + handoff**: one JSON/SQLite file in `reo/` (gitignored). A plan holds facts, the latest design, the transcript, status (`drafting` → `handed_over` → `quoted`), installer edits and a history of design changes.
5. **Installer side**: list handed-over plans; apply installer edits (locks, facts, prices) by re-calling the engine and recording what changed; answer the installer's "why …?" questions from the engine's reasons and data's benchmarks; finalise the quote so the customer sees it.
6. **Evidence**: attach flags and similar real projects to each plan from `data/processed/benchmarks.json` / `projects.parquet` ("battery larger than 85% of similar homes").
7. **Address lookup (mock)**: 2–3 demo addresses return roof area / orientation / tilt from a small JSON file; anything else says "not available, please enter roof size".
8. **Scripted fallback**: with no `ANTHROPIC_API_KEY` (or on any LLM error) reo still works: rule-based fact extraction for the demo phrases, template replies from engine reasons. The demo must never depend on the network.

LLM: Claude via the Anthropic SDK with tool use (pick a current fast model; check the SDK docs). Send only the current conversation's facts and messages, never bulk data (hard rule 5).

## Commands

```bash
cd reo && uv sync
uv run uvicorn api:app --reload --port 8001      # needs the engine on :8000
```
