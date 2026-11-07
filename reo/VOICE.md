# Voice: talking to reo through ElevenLabs (plan)

> Owner: `EywaSahbi` (reo). Status: **plan, waiting for a human `DECISION`** (paid service beyond `docs/plan.md` budget, and customer audio goes to a third party). Earliest slot: after our M1 items are done (M2 window).

## Goal

The homeowner presses a mic button in the reo widget, speaks ("we're four people and heat with gas"), and reo answers out loud, while the chat and the plan card update exactly as with typed text. Text chat stays the default and keeps working without voice.

## How it works

```
app widget (mic, push-to-talk)                       reo (:8001)                                ElevenLabs
  MediaRecorder, webm/opus ── POST /sessions/{id}/voice ──► speech-to-text ─────────────────────► POST /v1/speech-to-text (scribe_v2)
                                                            text ──► same turn as /messages:
                                                                     extract (Claude) → engine /design → reply (Claude)
                                                            reply text ──► text-to-speech ──────► POST /v1/text-to-speech/{voice_id}
  plays audio, shows Turn ◄── Turn + heard + audio (mp3) ◄──                                       (eleven_flash_v2_5, mp3_44100_128)
```

- **One pipeline.** A voice turn is a text turn with a transcription step before and a speech step after. Hard rule 2 holds unchanged: reo speaks only the text it would have written, and every number in it comes from this turn's engine call.
- **Key stays on the server.** `ELEVENLABS_API_KEY` lives in `reo/.env` (gitignored). The browser never sees it; app only talks to reo.
- **Push-to-talk, not always listening.** Simple, no voice-activity detection, no interruptions to handle. Good enough for the demo.
- **Why not ElevenAgents (ElevenLabs' hosted voice agents with a "custom LLM")?** It would need a public URL for reo, an OpenAI-compatible streaming `/v1/chat/completions` endpoint, and ElevenLabs would own the conversation loop. That makes plan state, the engine-every-turn rule and an offline demo harder. Possible upgrade later, not needed now.

## ElevenLabs calls (from the official docs, checked 2026-11-07)

| Step | Request | Notes |
|---|---|---|
| Speech-to-text | `POST https://api.elevenlabs.io/v1/speech-to-text`, header `xi-api-key`, multipart: `file`, `model_id=scribe_v2`, optional `language_code` (`de`/`en`, else auto-detect) | transcript in response field `text` |
| Text-to-speech | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128`, header `xi-api-key`, JSON `{text, model_id}` | `eleven_flash_v2_5` (low latency, German + English); `eleven_v4_turbo` as alternative; response body is the audio |

Plain `httpx` calls, no extra SDK (two endpoints).

## Config (`reo/.env`)

```
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=          # picked by app (reo's voice is app's creative call)
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
ELEVENLABS_STT_MODEL=scribe_v2
```

## Contract additions (additive, planned; see `CONTRACT.md`)

- `GET /health` → `{ok: true, llm: boolean, voice: boolean}`. app shows the mic only when `voice` is `true`.
- `POST /sessions/{id}/voice`, multipart `audio` (webm/opus, mp3 or wav, max ~30 s) → `Turn & {heard: string, audio: string | null}`. `heard` is the transcript (shown as the customer's message), `audio` is base64 mp3 of reo's reply.
- `POST /tts` `{text}` → `audio/mpeg`. To read any reo message aloud (greeting, chip turns), on demand.

## Fallbacks (the demo must run without luck)

- No `ELEVENLABS_API_KEY` → `voice: false`, mic hidden, everything else unchanged.
- Speech-to-text fails or hears nothing → Turn with a short "Sorry, I didn't catch that, could you say it again or type it?" and no state change.
- Text-to-speech fails → normal Turn with `audio: null`; the reply is still shown as text.
- Voice is never part of the core demo path; at most a 20-second "and you can just talk to it" moment, with a recording as backup.

## Data and cost

- Audio contains only what this one customer says about their home. reo sends it to ElevenLabs for transcription and does not store or log the audio. This is a third party besides Anthropic, so it needs the humans' OK (hard rule 5 spirit, `DECISION`).
- Cost: an ElevenLabs plan with API access. The budget in `docs/plan.md` lists only the Anthropic key, so this is a `DECISION`.

## Latency (estimate)

Speech-to-text ~1 s + extract ~2 s + engine + reply ~3–4 s + text-to-speech ~0.5–1 s, so roughly **6–8 s** per spoken turn. Later options: skip the extract call for short answers that the scripted parser understands, stream the speech output.

## Work split

| Who | Task | Size |
|---|---|---|
| reo | `voice.py` (two ElevenLabs calls), `/health`, `/sessions/{id}/voice`, `/tts`, fallbacks, one test with a mocked ElevenLabs | ~2–3 h |
| app | mic button (push-to-talk, MediaRecorder), show `heard` as the customer bubble, play `audio`, hide the mic when `voice: false`; pick reo's voice (`voice_id`) | ~1–2 h |
| qa | voice smoke test: with key (one spoken turn end to end), without key (mic hidden, text works) | ~30 min |
| engine, data | nothing | |

## Open points

- `DECISION` (humans): use ElevenLabs (cost + audio to a third party)? Yes/no.
- app: which voice for reo (German and English), and whether to read every reply aloud or only voice turns.
