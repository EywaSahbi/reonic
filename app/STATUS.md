# app/ status (owner: `RaneemK-commits`)

## Backlog (top = next)

- [x] Fill `experience/persona.md` + `experience/flow.md` → `DONE` to reo, qa (M0, unblocks reo)
- [ ] Review `reo/CONTRACT.md` with reo; send a `NEED` for anything the UI needs (M0)
- [x] Vite + React + TS skeleton; typed client + mock for `reo/CONTRACT.md`; customer widget on the mock installer site (M0)
- [ ] Customer flow live against reo: chat, chips, inputs, plan card, handoff (M1)
- [ ] Installer view: inbox, plan detail, edits, finalise; customer sees final quote (M1)
- [ ] `pitch/demo-script.md` first draft (M1)
- [ ] Flags, similar projects, "ask reo why", reality-check panel (M2)
- [ ] Address input for the mocked lookup (M2)
- [ ] `README.md`, deck, fallback recording (M3)

## Published

- `experience/persona.md`, `experience/flow.md` v1 (installer brand: SolarHaus Müller)
- Customer view on mock: `cd app && npm install && npm run dev` → :5173. `VITE_API_URL` empty = in-browser mock (`src/mock.ts`, fake numbers), `http://localhost:8001` = live reo. Files: `src/types.ts` (contract types), `src/api.ts` (client + switch), `src/Widget.tsx`, `src/PlanCard.tsx`.

## Decisions

(one line each: what, why)
- Installer brand in demo is "SolarHaus Müller"; persona and flow use it verbatim.
- Handoff collects name/email in an app-side form posting to `/handoff` (contract-valid; qa BLOCKED on the `ask` version).
- Persona: reo may mention heat pump funding in general (never amounts), and aggregate "similar homes" comparisons from attached benchmarks in the customer chat; individual projects stay installer-only. Raneem's call.
- Mock persists plans in localStorage so the installer view (next) sees handoffs from the customer tab without reo.
