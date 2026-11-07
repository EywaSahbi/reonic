# app/ — frontend, reo's creative direction, pitch (owner: `RaneemK-commits`)

You own everything the judges see and hear: the two reo views, reo's voice, the five-minute demo, the deck and the README.
You write only in `app/`, `experience/`, `pitch/` and `README.md`. You talk to **reo's API only** ([reo/CONTRACT.md](../reo/CONTRACT.md)); never call the engine directly, never edit `reo/`, `engine/` or `data/`.

## Deliverables

1. **`experience/persona.md` and `experience/flow.md` first** (reo's backend loads them; they unblock reo). Persona: who reo is, tone, what reo may and may not say or promise. Flow: conversation stages, which facts to ask for in which order, when reo offers the handoff, what the installer sees.
2. **Customer view** (React + Vite + TypeScript, `:5173`): a mock installer website ("SolarHaus Müller" or similar) with the reo chat widget. Messages, quick-reply chips, inline inputs for `ask`, and a live plan card (components, sizes, price range that narrows as facts arrive, reasons). Handoff button. After the installer finalises: the final quote.
3. **Installer view**: inbox of handed-over plans → plan detail: design with reasons and confidence, flags ("battery larger than 85% of similar homes"), similar real projects, conversation summary, edit controls (lock / resize / toggle components, change facts, edit prices) with what changed highlighted, "ask reo why", finalise and send.
4. **Reality-check panel** (demo step 4): how the engine compares with expert designs across held-out projects (from `/validation`).
5. Until reo is live, use a local mock that matches `reo/CONTRACT.md` exactly, behind one switch (`VITE_API_URL`).
6. **`pitch/demo-script.md`**: the five-minute story with exact inputs (minimal facts → first design and price → more facts incl. "EV next year" → handoff → installer edit → final quote → reality check). **`pitch/`** deck content; fallback recording plan. **`README.md`** for the submission.

UX principles: the customer always sees a useful answer immediately and knows what would make it better; the installer stays in control and can justify every number; prices are clearly estimates until the installer confirms.

## Commands

```bash
cd app && npm install
npm run dev          # http://localhost:5173, expects reo on :8001 (or the mock)
npm run build        # must pass before you push
```
