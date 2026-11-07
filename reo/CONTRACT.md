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
  similar_projects: { project_id: string; facts: HomeFacts; expert: Record<ComponentKey, number | null> }[];
  installer_edits: { at: string; change: string; before: unknown; after: unknown }[];
  history: { at: string; trigger: string; total_eur: number }[];   // how the design evolved
  updated_at: string;
  summary?: string;                      // installer paragraph (flow.md 'Plan summary'), set once handed over
};

type Turn = {
  messages: Message[];                   // new reo messages this turn
  plan: Plan;
  suggestions: string[];                 // quick-reply chips
  ask?: { field: keyof HomeFacts; prompt: string; input: "number" | "boolean" | "choice" | "address"; options?: string[] };
};
```

Behaviour notes (v1):
- `design.params_version === "engine-offline"` means the engine was unreachable: the design carries no numbers (sizes `null`, totals `0`) and reo says so. Never shown as a real design.
- Chip taps sent as `/messages` text (exact chip/option texts) and `/facts` answer instantly without the LLM.
- `flags` (aggregate, from data's `benchmarks.json`) are set every turn. `similar_projects` (individual train homes) are filled once handed over and returned **only by installer endpoints** (`/plans/...`); customer responses always carry `[]`.
- Locks from `/plans/{id}/edit` persist across later edits (merged per component); prices likewise.
- A yearly kWh figure from the customer goes to `total_demand_kwh` (engine contract 336060e); the kWh ask uses that field.

## Customer side

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok, llm: boolean, voice: boolean, engine: boolean}` | done |
| POST | `/sessions` | `{}` → `Turn` (greeting; zero-fact design once engine allows `facts: {}`) | done |
| POST | `/sessions/{id}/messages` | `{text}` → `Turn` | done |
| POST | `/sessions/{id}/facts` | `{facts: Partial<HomeFacts>}` → `Turn` (no LLM) | done |
| POST | `/sessions/{id}/address` | `{address}` → `Turn` (mocked roof lookup for the demo addresses in `reo/addresses.json`: roof area, orientation, tilt, roof type, region; any other address → asks for roof m²) | done |
| POST | `/sessions/{id}/handoff` | `{name, email?}` → `Plan` (status `handed_over`) | done |
| GET | `/sessions/{id}` | → `Plan` (customer sees the final quote once `quoted`) | done |

## Installer side

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/plans?status=handed_over` | → `{id, customer, total_eur, status, updated_at}[]` | done |
| GET | `/plans/{id}` | → `Plan` | done |
| POST | `/plans/{id}/edit` | `{locks?, facts?, prices?}` → `Plan` (engine re-run, edit recorded; 503 if engine down) | done |
| POST | `/plans/{id}/ask` | `{text}` → `{answer: string}` ("why a 10 kWh battery?") | done (benchmarks M2) |
| POST | `/plans/{id}/finalize` | `{note?}` → `Plan` (status `quoted`) | done |
| GET | `/prices` | → engine `PriceList` passthrough (503 if engine down) | done |
| GET | `/validation` | → data's latest score JSON (for the reality-check panel) | M2 |

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

`Action.status` gains `"rejected"`. Effect classes: models only ever call `read` and `propose` tools; `execute` tools (`calendar.book`, `crm.create_task`, `quote.send`) run only from `/approve`. Installer edits re-run the guards on an existing pack and mark variants `stale: true` (`Variant.stale?: boolean`) instead of silently changing them.
