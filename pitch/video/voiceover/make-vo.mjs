#!/usr/bin/env node
// Generates the video's voice-over with ElevenLabs and places every line at its cue.
//
//   one clip per line (cached, only changed lines cost credits)  ->  out/<id>.mp3
//   all clips placed at their start second on one 46 s track     ->  out/vo.wav, out/vo.mp3
//   subtitles from the real durations                            ->  out/vo.srt
//
// Needs: Node 18+, ffmpeg + ffprobe on PATH, ELEVENLABS_API_KEY and a voice id.
//   PowerShell:  $env:ELEVENLABS_API_KEY = "..."; $env:ELEVENLABS_VOICE_ID = "..."; node make-vo.mjs
//   Options:     --dry (plan only, no API calls)   --force (regenerate every line)
//                --voice <id>   --model <id>   (default model: eleven_multilingual_v2)
// The key is read from the environment only; never put it in a file.

import { readFile, writeFile, mkdir, access } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const flag = (n) => argv.includes(n);
const opt = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);

const KEY = process.env.ELEVENLABS_API_KEY;
const VOICE = opt("--voice", process.env.ELEVENLABS_VOICE_ID);
const MODEL = opt("--model", "eleven_multilingual_v2");
// Delivery. Defaults are calm; for an upbeat read try: --stability 0.35 --style 0.45 --speed 1.08
const STABILITY = Number(opt("--stability", 0.5)); // lower = more expressive
const STYLE = Number(opt("--style", 0.15)); // higher = more exaggerated, energetic delivery
const SPEED = opt("--speed", undefined) === undefined ? undefined : Number(opt("--speed")); // 0.7-1.2
const SETTINGS = { stability: STABILITY, similarity_boost: 0.8, style: STYLE, use_speaker_boost: true, ...(SPEED ? { speed: SPEED } : {}) };
const DRY = flag("--dry");
const FORCE = flag("--force");
const MAX_SPEEDUP = 1.12; // a line may be sped up by at most 12 % to fit its slot; beyond that, shorten the text

const spec = JSON.parse(await readFile(path.join(here, "vo.json"), "utf8"));
const out = path.join(here, "out");
await mkdir(out, { recursive: true });

if (!DRY && (!KEY || !VOICE)) {
  console.error("Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID (or pass --voice), or run with --dry.");
  process.exit(1);
}

const exists = (p) => access(p).then(() => true, () => false);
const sh = (cmd, args) => {
  const r = spawnSync(cmd, args, { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`${cmd} failed: ${r.stderr || r.stdout}`);
  return r.stdout;
};
const duration = (file) => parseFloat(sh("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file]));

// ---- 1. one clip per line ------------------------------------------------------------
const lines = spec.lines;
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  const mp3 = path.join(out, `${l.id}.mp3`);
  const meta = path.join(out, `${l.id}.json`);
  const fingerprint = createHash("sha1").update(JSON.stringify([l.text, VOICE, MODEL, SETTINGS])).digest("hex");
  const cached = !FORCE && (await exists(mp3)) && (await exists(meta)) && JSON.parse(await readFile(meta, "utf8")).fingerprint === fingerprint;
  l.file = mp3;
  if (DRY) continue;
  if (cached) { console.log(`= ${l.id} (cached)`); continue; }
  console.log(`+ ${l.id}: "${l.text}"`);
  const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE}?output_format=mp3_44100_128`, {
    method: "POST",
    headers: { "xi-api-key": KEY, "content-type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify({
      text: l.text,
      model_id: MODEL,
      // neighbouring lines give the model context so the delivery flows from line to line
      previous_text: lines[i - 1]?.text,
      next_text: lines[i + 1]?.text,
      voice_settings: SETTINGS,
    }),
  });
  if (!res.ok) throw new Error(`ElevenLabs ${res.status} on ${l.id}: ${await res.text()}`);
  await writeFile(mp3, Buffer.from(await res.arrayBuffer()));
  await writeFile(meta, JSON.stringify({ fingerprint, text: l.text }));
}

// ---- 2. timing report ----------------------------------------------------------------
const fmt = (s) => s.toFixed(2).padStart(6);
let problems = 0;
console.log("\n  id                  start    end  until  speed  status");
for (const l of lines) {
  if (DRY || !(await exists(l.file))) { console.log(`  ${l.id.padEnd(18)} ${fmt(l.start)}      -  ${fmt(l.until)}      -  (plan)`); continue; }
  l.dur = duration(l.file);
  const slot = l.until - l.start;
  l.tempo = l.dur > slot ? l.dur / slot : 1;
  l.end = l.start + l.dur / l.tempo;
  const status = l.tempo === 1 ? "ok" : l.tempo <= MAX_SPEEDUP ? "sped up to fit" : "TOO LONG: shorten the text";
  if (l.tempo > MAX_SPEEDUP) problems++;
  console.log(`  ${l.id.padEnd(18)} ${fmt(l.start)} ${fmt(l.end)} ${fmt(l.until)}  ${l.tempo.toFixed(2)}x  ${status}`);
}
if (DRY) { console.log("\nDry run: nothing generated."); process.exit(0); }

// ---- 3. place every clip on one track ------------------------------------------------
const inputs = lines.flatMap((l) => ["-i", l.file]);
const chains = lines.map((l, i) => {
  const t = Math.min(l.tempo, MAX_SPEEDUP);
  const ms = Math.round(l.start * 1000);
  return `[${i}:a]${t > 1 ? `atempo=${t.toFixed(4)},` : ""}adelay=${ms}:all=1[a${i}]`;
});
const mix = `${lines.map((_, i) => `[a${i}]`).join("")}amix=inputs=${lines.length}:normalize=0:duration=longest,apad=whole_dur=${spec.duration},atrim=0:${spec.duration}[mix]`;
sh("ffmpeg", ["-y", ...inputs, "-filter_complex", [...chains, mix].join(";"), "-map", "[mix]", "-ar", "44100", "-ac", "1", path.join(out, "vo.wav")]);
sh("ffmpeg", ["-y", "-i", path.join(out, "vo.wav"), "-b:a", "192k", path.join(out, "vo.mp3")]);

// ---- 3b. self-check: the track must be exactly as long as the video and speech must start on the first cue ----
const outDur = duration(path.join(out, "vo.mp3"));
if (Math.abs(outDur - spec.duration) > 0.3) console.error(`WARNING: vo.mp3 is ${outDur.toFixed(2)} s, the video is ${spec.duration} s.`);
{
  const r = spawnSync("ffmpeg", ["-hide_banner", "-i", path.join(out, "vo.mp3"), "-af", "silencedetect=noise=-40dB:d=0.3", "-f", "null", "-"], { encoding: "utf8" });
  const ends = [...(r.stderr || "").matchAll(/silence_end: ([\d.]+)/g)].map((m) => Number(m[1]));
  const starts = [...(r.stderr || "").matchAll(/silence_start: ([\d.]+)/g)].map((m) => Number(m[1]));
  const first = starts.length && starts[0] < 0.01 ? ends[0] : 0; // speech begins where the opening silence ends
  if (first !== undefined && Math.abs(first - lines[0].start) > 0.35) console.error(`WARNING: first speech at ${first.toFixed(2)} s but the first cue is ${lines[0].start} s: the track is shifted; fix before using it.`);
}

// ---- 4. subtitles from the real timings -----------------------------------------------
const ts = (s) => { const ms = Math.round(s * 1000); const p = (n, w = 2) => String(n).padStart(w, "0"); return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`; };
await writeFile(path.join(out, "vo.srt"), lines.map((l, i) => `${i + 1}\n${ts(l.start)} --> ${ts(l.end)}\n${l.text.replace("...", "…")}\n`).join("\n"));

console.log(`\nWrote ${path.join(out, "vo.mp3")} (${spec.duration} s), vo.wav and vo.srt.`);
if (problems) console.log(`${problems} line(s) are too long for their slot: shorten them in vo.json and run again (only those lines are regenerated).`);
console.log("To use it in the video: copy out/vo.mp3 to ../assets/vo.mp3 and add <audio id=\"vo\" src=\"assets/vo.mp3\" data-start=\"0\" data-duration=\"46\" data-volume=\"1\"></audio> to index.html.");
