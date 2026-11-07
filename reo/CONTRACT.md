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
- Locks from `/plans/{id}/edit` persist across later edits (merged per component); prices likewise.
- A yearly kWh figure from the customer goes to `total_demand_kwh` (engine contract 336060e); the kWh ask uses that field.

## Customer side

| Method | Path | Body → Response | Milestone |
|---|---|---|---|
| GET | `/health` | → `{ok, llm: boolean, voice: boolean, engine: boolean}` | done |
| POST | `/sessions` | `{}` → `Turn` (greeting; zero-fact design once engine allows `facts: {}`) | done |
| POST | `/sessions/{id}/messages` | `{text}` → `Turn` | done |
| POST | `/sessions/{id}/facts` | `{facts: Partial<HomeFacts>}` → `Turn` (no LLM) | done |
| POST | `/sessions/{id}/address` | `{address}` → `Turn` (mocked roof lookup; until M2: asks for roof m²) | M2 |
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
