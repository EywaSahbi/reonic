# app/ status (owner: `RaneemK-commits`)

## Backlog (top = next)

- [x] Fill `experience/persona.md` + `experience/flow.md` → `DONE` to reo, qa (M0, unblocks reo)
- [ ] Review `reo/CONTRACT.md` with reo; send a `NEED` for anything the UI needs (M0)
- [x] Vite + React + TS skeleton; typed client + mock for `reo/CONTRACT.md`; customer widget on the mock installer site (M0)
- [x] Customer flow + installer view live against reo v1 + engine stub (M1): kWh line -> design, Gas, EV -> handoff offer, region picker, handoff, installer edit, finalise -> customer quote
- [x] Installer view: inbox, plan detail, edits, finalise; customer sees final quote (M1, live)
- [ ] `pitch/demo-script.md` first draft (M1)
- [ ] Flags, similar projects, "ask reo why", reality-check panel (M2)
- [ ] Address input for the mocked lookup (M2)
- [ ] `README.md`, deck, fallback recording (M3)

## Published

- `experience/persona.md`, `experience/flow.md` v1 (installer brand: SolarHaus Müller)
- Tap-first visuals: `choice` asks render as picture tap cards (`src/Icons.tsx`: people, heating, EV, building, roof icons); plan card opens with a house that builds itself (`src/House.tsx`: panels = engine `pv.quantity`, battery, heat pump, car + wallbox animate in/out).
- Customer view on mock: `cd app && npm install && npm run dev` → :5173. `VITE_API_URL` empty = in-browser mock (`src/mock.ts`, fake numbers), `http://localhost:8001` = live reo. Files: `src/types.ts` (contract types), `src/api.ts` (client + switch), `src/Widget.tsx`, `src/PlanCard.tsx`.
- Installer view at `#/installer` (footer link "Planner login"): inbox, summary, flags, component toggle/resize (locks), facts editor, price breakdown, similar projects, ask reo why, transcript, edit log, finalise with note. Customer widget resumes its session after reload and shows the confirmed quote.

## Decisions

(one line each: what, why)
- Installer brand in demo is "SolarHaus Müller"; persona and flow use it verbatim.
- Handoff collects name/email in an app-side form posting to `/handoff` (contract-valid; qa BLOCKED on the `ask` version).
- Persona: reo may mention heat pump funding in general (never amounts), and aggregate "similar homes" comparisons from attached benchmarks in the customer chat; individual projects stay installer-only. Raneem's call.
- Installer summary is templated in the UI until reo adds `Plan.summary` (NEED). Price-list editing waits for a reo `GET /prices` passthrough (NEED).
- Visual theme = `experience/brand.md` (Reonic: zinc paper/ink, Geist, black pills, sunset only on hero word + hero card + precision bar, emerald/amber pills). Tokens live in `app/src/styles.css` :root.
- Engine-offline (`params_version: "engine-offline"`): plan card shows "Calculation paused", installer shows a warning, no €0 anywhere, edits + finalise disabled.
- Voice (reo/VOICE.md): mic in the composer (`src/Voice.tsx`), shown only when reo `/health` says `voice: true`, or forced with `?voice=1` for testing. Tap to talk, tap to send (30 s max) -> `/sessions/{id}/voice`; `heard` shown as the customer bubble, reo's mp3 plays with a Stop link. Mic blocked/unsupported -> plain notice, typing still works. Only replies to spoken turns are read aloud. Real ElevenLabs round trip verified by Raneem in Chrome (2026-11-07, reo + engine full design on this machine).
- Long choice lists (>8 options, no icons, e.g. 16 federal states) render as one picker, not cards. Customer plan card rounds sizes to 1 decimal and payback to whole years (display only).
- Mock persists plans in localStorage so the installer view (next) sees handoffs from the customer tab without reo.
