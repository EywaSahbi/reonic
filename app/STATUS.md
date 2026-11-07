# app/ status (owner: `RaneemK-commits`)

## Backlog (top = next)

Phase 2 (docs/plan.md, 39adaa2): installer side + agentic reo.

- [ ] Reality-check panel from `/validation` (test numbers, per installer, honest where we lose); reo serves data's score JSON already (68a4d3b) (M2)
- [ ] `pitch/demo-script.md` first draft, updated story step 3 = offer agent (M1/M2)
- [~] Installer **offer pack** view (`src/OfferPack.tsx`): live run timeline (SSE `/runs/{id}/events`, falls back to `offer_pack.trace`), 3 variant cards + use variant, checklist, open questions, editable draft (sent with the quote), approve/reject per action, visit-slot picker. Verified live against reo 68e40f5 (Opus pack in 26.8 s, SSE timeline, variant, approve/reject, edited draft reached the customer). Quote follows the chosen variant since reo 352e824 (verified).
- [ ] Customer widget: bill photo upload (camera icon) + goal chips ("Keep it under €20,000", "As independent as possible"); waits for reo `/bill` + goal planning (Sun 03:00)
- [ ] Monthly bill before/after as headline + bundle (engine v1 fields `economics.bill_*_per_month`, `bundle`)
- [ ] Demo-site clean-up (one type scale, spacing, component set from brand.md, real copy): Raneem steering directly
- [ ] Pick reo's voice (`ELEVENLABS_VOICE_ID`), placeholder "Jessica"
- [ ] `README.md`, deck, fallback recording (M3)

Done in phase 1: persona + flow (incl. tap-first opening, region, existing solar), Vite app on mock + live reo, installer view, Reonic brand, tap cards, self-building house, engine-offline state, voice (verified in Chrome).

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
