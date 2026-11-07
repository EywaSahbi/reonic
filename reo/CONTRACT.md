# reo/ contract (v0 draft — owner `EywaSahbi` agrees v1 with app at M0)

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
};

type Turn = {
  messages: Message[];                   // new reo messages this turn
  plan: Plan;
  suggestions: string[];                 // quick-reply chips
  ask?: { field: keyof HomeFacts; prompt: string; input: "number" | "boolean" | "choice" | "address"; options?: string[] };
};
```

## Customer side

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| POST | `/sessions` | `{}` → `Turn` (greeting) | M0 stub |
| POST | `/sessions/{id}/messages` | `{text}` → `Turn` | M0 stub, M1 real |
| POST | `/sessions/{id}/facts` | `{facts: Partial<HomeFacts>}` → `Turn` (no LLM needed) | M1 |
| POST | `/sessions/{id}/address` | `{address}` → `Turn` (mocked roof lookup) | M2 |
| POST | `/sessions/{id}/handoff` | `{name, email?}` → `Plan` (status `handed_over`) | M1 |
| GET | `/sessions/{id}` | → `Plan` (customer sees the final quote once `quoted`) | M1 |

## Installer side

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/plans?status=handed_over` | → `{id, customer, total_eur, status, updated_at}[]` | M1 |
| GET | `/plans/{id}` | → `Plan` | M1 |
| POST | `/plans/{id}/edit` | `{locks?, facts?, prices?}` → `Plan` (engine re-run, edit recorded) | M1 |
| POST | `/plans/{id}/ask` | `{text}` → `{answer: string}` ("why a 10 kWh battery?") | M2 |
| POST | `/plans/{id}/finalize` | `{note?}` → `Plan` (status `quoted`) | M1 |
| GET | `/validation` | → data's latest score JSON (for the reality-check panel) | M2 |

## Voice (planned, additive, waiting for a human `DECISION`; details in [VOICE.md](VOICE.md))

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok: true, llm: boolean, voice: boolean}` (app shows the mic only when `voice`) | M2 |
| POST | `/sessions/{id}/voice` | multipart `audio` (webm/opus, mp3 or wav, ≤ ~30 s) → `Turn & {heard: string, audio: string \| null}` (`heard` = transcript, `audio` = base64 mp3 of reo's reply) | M2 |
| POST | `/tts` | `{text}` → `audio/mpeg` (read any reo message aloud) | M2 |
