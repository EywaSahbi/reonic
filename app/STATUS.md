# app/ status (owner: `RaneemK-commits`)

## Where we are (Sat 7 Nov, ~21:45)

The full demo loop runs live on this machine: Sonnfeld site → advisor (reo) → handoff → planner offer pack (Sonnet, ~15–20 s) → choose variant → approve visit / send quote → customer sees the confirmed quote. Verified against reo `35f5a3d` + engine `4ed296c`.

- **Customer site (white-label):** installer brand **Sonnfeld** (invented name + logo `src/Logo.tsx`), Enpal-style full-bleed hero photo (`src/assets/house-hero.jpg`, 2000×1124, usage cleared), floating pill nav, trust bar. Centre call to action = the animated character (`src/ReoAvatar.tsx`, 132 px) under a "Plan my home" pill. Clicking pulls the hero copy back and slides the advisor sheet down from the top (`src/home.css`, `Widget variant="stage"`). No "reo" / "Reonic" / "powered by" anywhere a customer sees it.
- **Advisor widget:** tap cards with icons, inline inputs, long lists as one picker (16 federal states), address lookup (mocked by reo: "Musterstraße 12, 80331 München"), live plan card with the self-building house, engine-offline state, push-to-talk voice (ElevenLabs via reo, verified in Chrome), session resume after reload, handoff form.
- **Planner view (`#/installer`):** inbox, reo's summary, flags vs similar homes, component edits with re-derive banner, facts editor (incl. region), price breakdown, similar projects, ask reo why, transcript, edit log. **Offer pack** (`src/OfferPack.tsx`): live run timeline over SSE (plain-language steps, ✓ numbers verified), 3 variant cards (price, sizes, own power, payback, monthly bill / credit), use variant, checklist, open questions, editable customer message (flags a draft written for another variant, never overwrites planner edits, adopts reo's refreshed draft), approve / reject per action with a visit-slot picker.
- **Pitch:** `pitch/demo-script.md` draft v1 (setup, timed 5-minute run with exact inputs, honest reality-check numbers, fallbacks, recording plan). Not rehearsed yet (qa).
- **reo intro animation** (`src/ReoIntro.tsx`, `src/ReoIntroPreview.tsx`, route `#/reo-intro` in `main.tsx`, `.reo-stage` CSS): built in a separate session for the pitch; committed as is.

### How to run it

```bash
cd engine && uv run uvicorn api:app --port 8000
cd reo && uv run uvicorn api:app --port 8001        # keys in reo/.env (Anthropic, ElevenLabs); scripted without them
cd app && npm install && VITE_API_URL=http://localhost:8001 npm run dev   # :5173 live; leave VITE_API_URL empty for the in-browser mock
```
Customer: `http://localhost:5173/` · Planner: `http://localhost:5173/#/installer` · Voice test without key: `?voice=1`.

## Open decision (waiting on Raneem)

- **KfW heat-pump grant (−30%) in customer prices?** Engine `7b1d625` added it as a price line. Current state (reo `9c7fef1`, engine `4ed296c`): customers see prices **without** the grant, the planner sees the grant line ("planner view only"). Alternative: show it to customers as "estimated KfW grant, eligibility confirmed by your planner" (one line in reo `CUSTOMER_PRICES`, plus a persona.md change). DECISION posted on the board.

## Next (top = next)

- [x] Offer pack with live run timeline, bill upload and confirmation, goal chips, monthly bill headline, and reality-check panel from `/validation`.
- [x] Applied reo's NEED: roof address prompt, skip / width × length route and two-field dimensions input.
- [x] "Ask reo why" in the planner view: show the run trace (`run_id` from reo `ba790de`; the grounding retry is a nice demo moment).
- [ ] Check the bill reader against a real bill.
- [ ] Rehearse `pitch/demo-script.md` with qa; fix timings and wording.
- [ ] Pick the advisor's voice (`ELEVENLABS_VOICE_ID`, placeholder "Jessica").
- [ ] Check that "Sonnfeld" is not a real installer (web search) before the pitch.
- [ ] `README.md`, deck, fallback recording (M3, Sun 12:00).

## Codex continuation

- Offer pack and SSE timeline were already present in `src/OfferPack.tsx`; retained and verified in the app build.
- Bill upload posts multipart `image` to `/sessions/{id}/bill`; recognized facts are applied only after confirmation. The mock path mirrors this flow.
- Goal chips render reo's returned `Turn.goal_result` variants; no UI-side design or price calculations were added.
- Monthly bill headline displays the engine's before → after values, including a negative after-bill as a feed-in credit.
- Reality-check panel reads the published `/validation` scores: test default, val selector and per-installer profiles.
- `npm run build` passes.

## Published

- `experience/persona.md` (white-label rule, Sonnfeld, funding/benchmark rules), `experience/flow.md` (tap-first opening, question order incl. existing solar + region, handoff bar high ≤ 1.7× low), `experience/brand.md`.
- App: `src/types.ts` mirrors engine/reo contracts (reo v1.2 harness: Run, RunStep, OfferPack incl. `draft_for`, VoiceTurn); `src/api.ts` = one client, `VITE_API_URL` switch to `src/mock.ts` (mock includes an offer agent, voice, address).
- `pitch/demo-script.md` draft v1.

## Decisions

(one line each: what, why)
- White-label on the customer site (Raneem): no 'reo', 'Reonic' or 'powered by' anywhere a customer sees it; the advisor is "Sonnfeld's energy advisor". Centre CTA = big character (ReoAvatar 132 px) under a "Plan my home" pill. Planner view may say reo.
- Hero photo `app/src/assets/house-hero.jpg`: usage cleared by Raneem (2026-11-07).
- Installer brand in demo is "Sonnfeld" (was SolarHaus Müller, renamed by Raneem 2026-11-07); persona and flow use it verbatim. Site copy in English.
- Handoff collects name/email in an app-side form posting to `/handoff` (contract-valid).
- Persona: the advisor may mention heat pump funding in general (never amounts), and aggregate "similar homes" comparisons in the customer chat; individual projects stay planner-only.
- Visual theme = `experience/brand.md` tokens in `app/src/styles.css` :root; page-specific styles in `home.css`, `offerpack.css`, `voice.css`.
- Engine-offline (`params_version: "engine-offline"`): "Calculation paused", no €0 anywhere, edits + finalise disabled.
- Voice: mic only when reo `/health` says `voice: true` (or `?voice=1`); only replies to spoken turns are read aloud.
- Long choice lists (>8 options, no icons) render as one picker; customer plan card rounds sizes to 1 decimal and payback to whole years (display only).
- Offer pack: a customer message written for another variant is flagged; planner edits are never overwritten.
- Mock persists plans in localStorage so the planner view sees handoffs without reo.
- `app/learning/` holds auto-captured learning-mode session logs; committed at Raneem's request.

- Codex continuation: planner answers now expose their harness run timeline; roof fields have explicit labels, positive decimal validation and typed width/length facts. Mock supports dimension chips and address fallback. Build verified before push.

- README setup/architecture/limits drafted; demo script updated to engine a56e3f9 reported metrics and the reality-check panel. Initial Sonnfeld web search found related names (Sonnfeld ZT architecture; EWS Sonnenfeld project), no exact installer match; this is not name clearance. Voice choice, real-bill test and QA rehearsal still pending.

## Address frontend (Codex)

- Dedicated Find my roof form available from customer tools and backend address asks; uses existing reo `/sessions/{id}/address` only.
- Loading status, retained input on request errors, result card for backend label/source/sunny roof area/footprint/tilt, explicitly estimated. Demo results labeled as demo data.
- Unknown address falls back to width/length; manual dimensions and skip remain available. Opening lookup from another question and cancelling restores that question rather than skipping it on the backend.
- Backend has no map coordinates/outline in its published response, so no invented map or satellite image is shown.
- Browser verified in mock mode: demo address result, unknown-address fallback, decimal width/length submission. Live OSM path not exercised in this frontend session. Production build passes.
- Isolated UI refinement: original Plan my home pill raised 16px without moving reo; 104px advisor beside replies (64px on mobile); duplicate header avatar removed. Build passed and desktop preview checked on :5174.

- UI refinement follow-up: only the latest advisor reply mounts the animated avatar; older messages remain plain bubbles. Mobile avatar stays 64px.

## Deployment preparation

- Free Vercel project sonnfeld-reo created/linked; CLI authenticated. GitHub auto-link lacks repo access; CLI deploy is available.
- Added vercel.json, HTTPS API deployment guard, upload exclusions, laptop backend starter and DEPLOYMENT.md.
- No public tunnel or deployment yet: ngrok local token setup and reo authentication/CORS contract pending. Storage remains JSON, no SQLite migration implied.
- Engine 717be1f heating comparison typed/displayed: cost benefit gated by heatpump_cheaper, null CO2 remains unknown. Household choices already render. Approved flow and heating wording updated in experience/.

- Checks: production build, heating benefit/null-CO2 regression check, deployment URL guard rejection/acceptance, and laptop starter reusing healthy services passed. Windows blocked standalone ngrok; user installing official Store version. Vercel sign-in complete.

- Planner authentication client implemented against reo's proposed access contract: sessionStorage token entry/lock, Bearer only on installer paths, 401 relock. SSE uses authenticated fetch streaming rather than URL query tokens. ngrok warning header applies only to ngrok hosts, including uploads/streams. check-auth.mjs verifies scoping, split CRLF frames, no URL secret, 401 clearing. Backend middleware delivery still pending as of board ACK 23:45 UTC; agent remains active on board while deploying.

## Live laptop-backed production (8 Nov)

- https://sonnfeld-reo.vercel.app deployed to Vercel, using https://robin-ignore-oxidation.ngrok-free.dev as the live API. No backend secrets or dataset files uploaded.
- reo 7df79d3 running with generated planner token, allowed production origin, engine loopback-only. Token is local ignored app/.runtime/installer-token.txt; planner enters it once per tab.
- Auth tests (2), client auth/SSE regression, production build, browser customer flow/planner gate, public anonymous 401/authenticated 200, CORS and authenticated SSE replay passed.
- start-backend.ps1 -Protected and start-tunnel.ps1 provide guarded restart. Laptop must stay awake/online. See DEPLOYMENT.md. Existing OSM relation-outline limitation still belongs to reo; manual dimensions remain available.

## Demo PIN and capacity protection (in progress)

- User requests a whole-demo code and overload protection. Client gate verifies via proposed GET /demo/access, carries X-Demo-Pin on HTTP/uploads/authenticated fetch-SSE, keeps PIN runtime-only in sessionStorage, and relocks on demo 401 separately from planner Bearer auth.
- 429 displays backend Retry-After; 413 requests a smaller bill photo. Auth regression checks include PIN scoping, relock and capacity messaging.
- Requested reo-side caps: 5 active planning sessions with idle expiry, 2 concurrent agent jobs, throttled PIN attempts and bounded uploads. These are conservative requested settings, not measured maximum capacity. Laptop: 16 GiB RAM, 24 logical processors, ~1.7 GiB free at inspection, Python services ~150 MiB idle.
- Awaiting reo contract + implementation on board. Client changes are not yet deployed; no claim of backend-enforced PIN/capacity until verified.
