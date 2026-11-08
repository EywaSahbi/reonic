# reo/ contract (v1 — owner `EywaSahbi`)

HTTP JSON API on `http://localhost:8001`, CORS open to `http://localhost:5173`. The only API app talks to.
Types `HomeFacts`, `Design`, `ComponentKey`, `PriceList` are from [engine/CONTRACT.md](../engine/CONTRACT.md).
Changes: additive → `CONTRACT` message to app and qa; breaking → app must `ACK` (after M1: `DECISION`).

## Types

```ts
type Message = { role: "reo" | "customer" | "installer"; text: string; at: string };

type Plan = {
  id: string;
  status: "drafting" | "handed_over" | "quoted";
  customer: { name?: string; email?: string };
  facts: HomeFacts;
  design: Design;                        // always the latest engine output
  transcript: Message[];
  flags: { component: ComponentKey; text: string; severity: "info" | "warn" }[];   // from data benchmarks
  installer_edits: { at: string; change: string; before: unknown; after: unknown }[];
  history: { at: string; trigger: string; total_eur: number }[];   // how the design evolved
  updated_at: string;
  roof_location?: { label: string; lat: number; lon: number; outline: [number, number][] };  // last address lookup that found the building (OSM, [lat, lon] outline); none for demo addresses; app shows a satellite view
  summary?: string;                      // installer paragraph (flow.md 'Plan summary'), set once handed over
};

type Turn = {
  messages: Message[];                   // new reo messages this turn
  plan: Plan;
  suggestions: string[];                 // quick-reply chips
  ask?: { field: keyof HomeFacts; prompt: string; input: "number" | "boolean" | "choice" | "address" | "dimensions"; options?: string[] };
  // "dimensions": two number fields (width, length in m) -> POST /facts {roof_width_m, roof_length_m}
};
```

Behaviour notes (v1):
- `design.params_version === "engine-offline"` means the engine was unreachable: the design carries no numbers (sizes `null`, totals `0`) and reo says so. Never shown as a real design.
- The customer's design builds up with the answers: until answered (or skipped) a topic's components are locked off for the engine call (pv + battery until total/annual demand or household size, wallbox until the EV question, heat pump until heating). The first design is empty (`total_eur` 0); the customer's own locks win. Installer views and the offer pack are unaffected.
- Chip taps sent as `/messages` text (exact chip/option texts) and `/facts` answer instantly without the LLM.
- `flags` (aggregate, from data's `benchmarks.json`) are set every turn. Individual homes are never served (`similar_projects` and `GET /validation` removed 2026-11-08 on EywaSahbi's request, together with the app's Reality check and Similar projects panels).
- Roof: the roof ask is `input: "address"` with chips `Enter width × length` / `Skip`. Width × length (from `/facts` or free text "8 x 6 m") is sent to the engine as `roof_width_m`, `roof_length_m` plus `roof_area_sqm` = width × length; the engine caps PV modules to the roof (engine NEED 21:10).
- Locks from `/plans/{id}/edit` persist across later edits (merged per component); prices likewise.
- Question order (2026-11-08, `flow.py` `next_question`): `total_demand_kwh` (number; chips About 3,000 / 4,500 kWh, Skip) → if skipped `num_inhabitants` (choice 1..5+, Skip) → address (`roof_area_sqm`, input `address`; Skip) → if skipped `region` (choice, Skip) → if skipped `roof_dims` (input `dimensions`, Skip; also asked when an address is not found) → `has_ev` → `heating_type` → `has_existing_pv` (+ `existing_pv_kwp`, kept so retrofits are not planned with duplicate panels) → handoff offer. Skip on any ask marks it skipped and moves on; the customer can still volunteer any fact at any time.
- Heat pump option (2026-11-08): for gas / oil / district / other heating the customer plan stays WITHOUT a heat pump (reo sets lock `heatpump` off) until the customer answers the ask `heatpump_option` (choice: "Yes, show me the heat pump option" / "No, keep my plan"; app sends `/facts {heatpump_option: true|false}`, typed yes/no also works). While it is open the Turn carries additive `heatpump_option: {without: Design, with: Design}` (two engine calls of that turn; the price difference in the text is the engine's /explain delta). Yes keeps lock `heatpump` on (plan = the heat pump design), No keeps it off. `heatpump_option` is never stored as a home fact. Electric / heat pump heating: no step. Order: ... heating -> heatpump_option -> has_existing_pv.
- Heating advice: when `heating_type` is gas / oil / district / other, the reply adds the engine's `heating_comparison` (energy factor, yearly cost now vs heat pump on grid power, CO₂ only when the engine gives a positive reduction); cost is called cheaper only if `heatpump_cheaper`. Scripted text: `scripted.heating_advice`; with a key the model follows `prompt.md` rule 9.
- A yearly kWh figure from the customer goes to `total_demand_kwh` (engine contract 336060e); the kWh ask uses that field.

## Access (deployment, v1.4)

- `REO_INSTALLER_TOKEN` (env / `reo/.env`, never committed or bundled): when set, installer routes `/plans*`, `/runs*` (incl. SSE `/runs/{id}/events`), `/calendar/slots`, `/prices` need `Authorization: Bearer <token>`, else `401 {"error": "planner token required"}`. Unset (local dev): no check. No `?token=` query (the app streams SSE with fetch + Bearer).
- Customer routes (`/health`, `/sessions*`, `/tts`) stay open; the session id is the customer's key and never returns the offer pack.
- CORS: localhost:5173 plus `REO_ALLOWED_ORIGINS` (comma-separated, e.g. `https://sonnfeld-reo.vercel.app`); 401s carry CORS headers; preflights need no token.

## Customer side

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok, llm: boolean, voice: boolean, engine: boolean}` | done |
| POST | `/sessions` | `{}` → `Turn` (greeting; zero-fact design once engine allows `facts: {}`) | done |
| POST | `/sessions/{id}/messages` | `{text}` → `Turn` | done |
| POST | `/sessions/{id}/facts` | `{facts: Partial<HomeFacts>}` → `Turn` (no LLM) | done |
| POST | `/sessions/{id}/address` | `{address}` → `Turn & {roof?: {source: "OpenStreetMap" \| "demo data", label, footprint_sqm?}}`: demo addresses (`reo/addresses.json`) offline, any other German address via OpenStreetMap (Nominatim + building outline → estimated sunny roof area, region, roof type); not found → `ask` input `"dimensions"` + chip `Skip` | done |
| POST | `/sessions/{id}/handoff` | `{name, email?}` → `Plan` (status `handed_over`) | done |
| GET | `/sessions/{id}` | → `Plan` (customer sees the final quote once `quoted`) | done |

## Installer side

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/plans?status=handed_over` | → `{id, customer, total_eur, status, updated_at}[]` | done |
| GET | `/plans/{id}` | → `Plan` | done |
| DELETE | `/plans/{id}` | → `{deleted: id}` (plan, its state and runs removed; 404 if unknown; booked slots stay) | done |
| POST | `/plans/{id}/edit` | `{locks?, facts?, prices?}` → `Plan` (engine re-run, edit recorded; 503 if engine down) | done |
| POST | `/plans/{id}/ask` | `{text}` → `{answer: string}` ("why a 10 kWh battery?") | done (benchmarks M2) |
| POST | `/plans/{id}/finalize` | `{note?}` → `Plan` (status `quoted`) | done |
| GET | `/prices` | → engine `PriceList` passthrough (503 if engine down) | done |

## Voice (additive, built; details in [VOICE.md](VOICE.md))

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok: true, llm: boolean, voice: boolean}` (app shows the mic only when `voice`) | done |
| POST | `/sessions/{id}/voice` | multipart `audio` (webm/opus, mp3 or wav, ≤ ~30 s) → `Turn & {heard: string, audio: string \| null}` (`heard` = transcript, `audio` = base64 mp3 of reo's reply) | done |
| POST | `/tts` | `{text}` → `audio/mpeg` (read any reo message aloud; 503 if voice off) | done |

## Phase 2 (v1.1, additive; app may mock against this)

```ts
type Variant = { name: "Basic" | "Recommended" | "Independence"; locks: Partial<Record<ComponentKey, {recommended: boolean, size?: number}>>;
                 design: Design; why: string };            // every number in `why` comes from `design`
type Action = { id: string; kind: "book_visit" | "send_quote" | "create_crm_task" | "request_document";
                label: string; payload: Record<string, unknown>; status: "proposed" | "approved" | "done";
                result?: string; at?: string };             // nothing runs until the planner approves
type TraceStep = { step: number; tool: string; summary: string };   // tool: "engine.design" | "engine.explain" | "benchmarks" | "calendar" | "crm" | "llm" | "scripted"
type OfferPack = { status: "preparing" | "ready" | "failed"; variants: Variant[]; recommended: Variant["name"];
                   flags: Plan["flags"]; site_visit_checklist: string[]; open_questions: string[];
                   customer_message_draft: string; actions: Action[]; trace: TraceStep[];
                   duration_s: number; model: string; prepared_at: string;   // model: "claude-opus-5-5" or "scripted"
                   chosen?: Variant["name"];                                 // set by POST /variant
                   draft_for?: Variant["name"] };                            // which variant customer_message_draft describes; /variant regenerates the draft
type GoalResult = { goal: "budget" | "independence" | "lowest_bill"; budget_eur?: number;
                    recommendation: Variant; alternatives: Variant[]; trace: TraceStep[] };

// additions
Plan.offer_pack?: OfferPack;          // installer endpoints only
Turn.goal_result?: GoalResult;        // when the customer states a goal ("keep it under €20,000")
Turn.bill?: { read: Partial<HomeFacts> & { provider?: string }; confirmed: false };   // after a bill photo
```

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| POST | `/plans/{id}/prepare` | `{}` → `Plan` with `offer_pack.status = "preparing"`; runs in the background (also starts automatically on `/handoff`). Poll `GET /plans/{id}` until `ready` (Opus ~30–60 s, scripted < 1 s) | Sun 03:00 |
| POST | `/plans/{id}/variant` | `{name}` → `Plan` (applies that variant's locks as installer edits, recorded) | Sun 03:00 |
| POST | `/plans/{id}/actions/{action_id}/approve` | `{payload?}` (e.g. a different slot) → `Plan`; runs the mocked tool: `book_visit` (payload `{slot}` from `/calendar/slots` overrides the proposed slot) → calendar (JSON under `reo/`), `create_crm_task` / `request_document` → CRM log, `send_quote` (payload `{message}` = the planner's edited draft, sent to the customer as the finalise note) → finalise (status `quoted`) | Sun 03:00 |
| GET | `/calendar/slots` | → `{slots: string[]}` (mock, next free site-visit slots) | Sun 03:00 |
| POST | `/sessions/{id}/bill` | multipart `image` (jpg/png/pdf) → `Turn` with `bill.read` and chips `["Yes, that's right", "Not quite"]`; facts are applied only after "Yes, that's right" | Sun 03:00 |
| POST | `/sessions/{id}/messages` | unchanged; a goal message returns `Turn.goal_result` (recommendation + 2 alternatives + trace) | Sun 09:00 |
| POST | `/plans/{id}/ask` | → `{answer, goal_result?}` (goal questions from the planner) | Sun 09:00 |

Models (env-overridable): chat turns + bill photo `REO_MODEL` = `claude-haiku-5-5`; offer agent `REO_AGENT_MODEL` = `claude-sonnet-5-5`. Without an API key the scripted path builds the same `OfferPack` from fixed lock sets (`model: "scripted"`).

## Agent harness (v1.2, additive; docs/plan.md "reo: the reo agent harness")

```ts
type RunStep = { n: number; kind: "think" | "tool" | "guard"; tool?: string;   // e.g. "engine.design", "evidence.percentile", "grounding", "effect_gate"
                 effect?: "read" | "propose" | "execute"; args_summary: string; result_summary: string; ms: number;
                 ok?: boolean };                                                   // guards: ok false = violation (then retry or scripted)
type Run = { id: string; skill: "chat_turn" | "offer_prep" | "goal_planner" | "bill_reader" | "installer_qa" | "follow_up";
             plan_id: string; trigger: string;                                    // "handoff", "prepare", "goal message", "bill upload", "approve a2", ...
             status: "running" | "done" | "failed" | "needs_approval";           // needs_approval: finished with proposed actions waiting
             steps: RunStep[]; output: unknown | null; model: string;            // "claude-opus-5-5" | "claude-sonnet-5-5" | "scripted"
             started_at: string; duration_s: number | null };

OfferPack.run_id: string;       // the offer_prep run; OfferPack.trace stays as the short summary
GoalResult.run_id: string;
```

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/runs/{id}` | → `Run` | Sat 23:30 |
| GET | `/runs/{id}/events` | Server-Sent Events: one `event: step` per `RunStep` (data = JSON step) as it happens, then `event: done` (data = `{status, duration_s}`). Replays past steps first, so a late subscriber sees the whole run | Sun 03:00 |
| GET | `/plans/{id}/runs` | → `Run[]` without `output` (newest first) | Sat 23:30 |
| POST | `/plans/{id}/actions/{action_id}/approve` | as v1.1; runs the `execute` tool and appends a step to the offer run | Sat 23:30 |
| POST | `/plans/{id}/actions/{action_id}/reject` | `{reason?}` → `Plan` (action `status: "rejected"`, nothing executed) | Sat 23:30 |

State rules (v1.3, cleanup 2026-11-08; no shape changes):
- Customer responses (`/sessions/...`) never carry `offer_pack`. While `handed_over` their `design` is the design the customer handed over (the planner's working copy, with installer prices such as the grant line, stays installer-only); once `quoted` it is the confirmed design.
- After handoff a customer message changes no facts or design: reo keeps it in the transcript for the planner, answers "why/cost" questions from the design the customer sees, no `ask`. A repeated `/handoff` returns the plan unchanged.
- A `quoted` plan is frozen: `/edit`, `/variant`, `/prepare`, `/finalize` → 409. `/finalize` also closes a pending `send_quote` (status `done`), so it can't send a second confirmation.
- `customer_message_draft` (and the pending `send_quote.payload.message`) is regenerated whenever the plan design changes (edit, variant, stale pack) or a visit is booked (it then names the booked slot); `draft_for` = `chosen ?? recommended`.
- `send_quote` quotes the plan as the planner left it: `payload.variant` if the planner sends one, else the chosen variant or later edits; the proposed variant only while no variant was chosen and nothing was edited since prep. Engine down → 503, nothing executed.
- Edits made while a pack is `preparing` mark its variants `stale` when it lands. Choosing a stale variant re-runs it on today's facts (card, plan and draft agree; `stale` cleared). A newer `/prepare` wins over an older run still finishing.
- A run cut off by a reo restart shows `status: "failed"` (last step `interrupted`) and its pack `failed`; `/prepare` again.

Offer pack holds **one quotation** (2026-11-08, EywaSahbi): `variants` = `[Recommended]` (the engine's design, no extra locks), `recommended` = `"Recommended"`; no Basic / Independence. Shapes unchanged; `/variant` still accepts `Recommended` (re-runs an outdated card). The goal planner still returns alternatives.

`Action.status` gains `"rejected"`. Effect classes: models only ever call `read` and `propose` tools; `execute` tools (`calendar.book`, `crm.create_task`, `quote.send`) run only from `/approve`. Installer edits re-run the guards on an existing pack and mark variants `stale: true` (`Variant.stale?: boolean`) instead of silently changing them.

## Demo access and laptop admission limits (v1.5)

Enabled only when REO_DEMO_PIN is set on the backend. All HTTP routes except GET /health and OPTIONS require X-Demo-Pin; planner routes additionally require the existing Bearer token. No PIN/token in URLs. GET /demo/access returns {ok:true} after PIN verification without creating a session. Health adds demo_auth_required and demo_limits, never secret values. CORS exposes Retry-After.

Defaults (environment-configurable, single process/worker):
- REO_MAX_ACTIVE_SESSIONS=5; REO_SESSION_IDLE_SECONDS=900. Creation/resumption occupies a slot, activity refreshes it, idle slots expire without deleting saved plans. Excess returns 429, Retry-After:30. Invalid session IDs and failed creations release new slots.
- REO_MAX_CONCURRENT_RUNS=2. Includes synchronous goal/bill/planner skills and background offers. Reject excess with 429/Retry-After:5 before starting a run; handoff remains drafting if capacity is full. Run leases release even on exceptions; completed offer runs read from persistent storage rather than accumulating in the live registry.
- REO_MAX_CONCURRENT_MUTATIONS=2 and REO_MAX_INFLIGHT_REQUESTS=12 (includes SSE) reject work instead of creating an unbounded queue.
- REO_MAX_REQUESTS_PER_MINUTE=240, including health/invalid-PIN requests. Wrong PINs: 5 failures per source IP and 12 globally per rolling minute; valid PINs are not locked out by these failure counters. Excess returns 429/Retry-After:60.
- REO_MAX_BODY_BYTES=8388608 (8 MiB multipart); non-multipart bodies additionally capped at 64 KiB. Declared and chunked uploads are bounded before application processing; excess returns 413.

These are conservative demo admission settings, not a measured hardware maximum or a guarantee against memory pressure caused by other programs. State/counters reset at restart; do not run multiple workers. The shared four-digit demo PIN is an invitation gate, not per-user identity. Keep the separate planner token.
