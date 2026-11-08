// Records the real customer flow of the app (mock backend) as a cursor-less clip + a pointer/mark log.
//   node capture/capture-customer.mjs            -> capture/out/customer.mp4, capture/out/customer.events.json
//
// The film draws its OWN large pointer from the event log, so the clip has no cursor and the pointer can be re-timed.
// Requires the app on APP_URL (default http://localhost:5183/, `cd app && npx vite --port 5183`), ffmpeg on PATH,
// and the chrome-headless-shell that HyperFrames downloads (override with CHROME=...).
import puppeteer from "puppeteer-core";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, "out");
const FRAMES = path.join(OUT, "frames");
const URL = process.env.APP_URL ?? "http://localhost:5183/";
const CHROME = process.env.CHROME ?? path.join(homedir(), ".cache/hyperframes/chrome/chrome-headless-shell/win64-152.0.7977.30/chrome-headless-shell-win64/chrome-headless-shell.exe");
const W = 1440, H = 900, DPR = Number(process.env.DPR ?? 2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = () => Date.now() / 1000;

await rm(FRAMES, { recursive: true, force: true });
await mkdir(FRAMES, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "shell",
  args: ["--enable-gpu", "--ignore-gpu-blocklist", "--hide-scrollbars", "--force-color-profile=srgb", `--force-device-scale-factor=${DPR}`],
  defaultViewport: { width: W, height: H, deviceScaleFactor: DPR },
});
const page = await browser.newPage();
await page.goto(URL, { waitUntil: "networkidle0" });
await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
await page.reload({ waitUntil: "networkidle0" });
await sleep(800);

// ---- screencast: JPEG frames with wall-clock timestamps --------------------------------------------------------------
const cdp = await page.createCDPSession();
const frames = [];
cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
  const i = frames.length;
  frames.push({ t: metadata.timestamp, file: `f${String(i).padStart(6, "0")}.jpg` });
  await writeFile(path.join(FRAMES, frames[i].file), Buffer.from(data, "base64"));
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: Number(process.env.QUALITY ?? 85), maxWidth: W * DPR, maxHeight: H * DPR, everyNthFrame: 1 });
await sleep(400);

// ---- pointer log + helpers --------------------------------------------------------------------------------------------
const events = []; // {t, kind, ...}  t = seconds (epoch), made relative to the first frame later
let mx = W + 60, my = 220; // start off the right edge
const log = (kind, extra = {}) => events.push({ t: now(), kind, ...extra });
const ease = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);

async function glide(x, y, ms = 700) {
  log("move", { from: [mx, my], to: [x, y], ms });
  const steps = Math.max(8, Math.round(ms / 40));
  const x0 = mx, y0 = my, t0 = performance.now();
  for (let i = 1; i <= steps; i++) {
    const p = ease(i / steps);
    await page.mouse.move(x0 + (x - x0) * p, y0 + (y - y0) * p);
    const wait = t0 + (ms * i) / steps - performance.now();
    if (wait > 0) await sleep(wait);
  }
  mx = x; my = y;
  log("arrive", { at: [x, y] });
}
async function click(hold = 110) {
  log("down", { at: [mx, my] });
  await page.mouse.down();
  await sleep(hold);
  await page.mouse.up();
  log("up", { at: [mx, my] });
}
async function centerOf(finder, arg) {
  const h = await page.evaluateHandle(finder, arg);
  const el = h.asElement();
  if (!el) throw new Error(`element not found: ${arg}`);
  const b = await el.boundingBox();
  return { x: b.x + b.width / 2, y: b.y + b.height / 2, el };
}
const byText = (text) => ({ x: 0 }, (t) => [...document.querySelectorAll("button, dt, a")].find((e) => e.getClientRects().length && e.innerText.trim().replace(/\s+/g, " ") === t));
const byTextRe = (re) => (r) => [...document.querySelectorAll("button")].find((e) => e.getClientRects().length && new RegExp(r).test(e.innerText));
async function target(text) { return centerOf((t) => [...document.querySelectorAll("button")].find((e) => e.getClientRects().length && e.innerText.trim().replace(/\s+/g, " ") === t), text); }
async function targetRe(re) { return centerOf((r) => [...document.querySelectorAll("button")].find((e) => e.getClientRects().length && new RegExp(r).test(e.innerText)), re); }
async function typeText(text, delay) {
  log("type", { text, delay });
  await page.keyboard.type(text, { delay });
}
async function smoothScroll(toY, ms = 1200) {
  log("scroll", { to: toY, ms });
  await page.evaluate(async (toY, ms) => {
    const sc = [...document.querySelectorAll("*")].filter((e) => e.scrollHeight > e.clientHeight + 200 && /(auto|scroll)/.test(getComputedStyle(e).overflowY))
      .sort((a, b) => b.clientHeight * b.clientWidth - a.clientHeight * a.clientWidth)[0];
    const y0 = sc.scrollTop, t0 = performance.now();
    await new Promise((res) => {
      const f = (t) => {
        const p = Math.min(1, (t - t0) / ms), e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
        sc.scrollTop = y0 + (toY - y0) * e;
        p < 1 ? requestAnimationFrame(f) : res();
      };
      requestAnimationFrame(f);
    });
  }, toY, ms);
  log("scrolled");
}
const mark = (name) => log("mark", { name });

// ---- the run -------------------------------------------------------------------------------------------------------------
mark("home");
await sleep(1200);
let p = await targetRe("Plan my home");
await glide(p.x, p.y, 1000);
await sleep(300);
await click();

mark("step1");
await sleep(3000);
p = await centerOf(() => document.querySelector('input[placeholder*="4,500"]'), "input");
await glide(p.x, p.y, 700);
await click();
await sleep(250);
await typeText("4500", 150);
await sleep(700);
p = await target("Next");
await glide(p.x, p.y, 600);
await click();

mark("step2");
await sleep(2600);
p = await centerOf(() => document.querySelector('input[placeholder*="Musterstra"]'), "input");
await glide(p.x, p.y, 700);
await click();
await sleep(250);
await typeText("Musterstraße 12, 80331 München", 40);
await sleep(500);
p = await target("Find roof");
await glide(p.x, p.y, 550);
await click();

mark("roof");
await sleep(3400);

mark("step3");
p = await target("Planned");
await glide(p.x, p.y, 800);
await click();

mark("step4");
await sleep(2800);
p = await target("Gas");
await glide(p.x, p.y, 800);
await click();

mark("results");
await sleep(5200);
p = await targetRe("^€[\\d,]+–[\\d,]+$");
await glide(p.x, p.y, 900);
await sleep(1500);
p = await targetRe("^€1,\\d{3}$");
await glide(p.x, p.y, 700);
mark("explain");
await sleep(250);
await click();
await sleep(4200);

mark("send");
await glide(700, 640, 600);
await smoothScroll(700, 1300);
await sleep(600);
p = await targetRe("Send plan to Sonnfeld");
await glide(p.x, p.y, 800);
await sleep(300);
await click();
await sleep(1200);
p = await centerOf(() => [...document.querySelectorAll("input")].find((e) => e.type === "text" && e.getClientRects().length && !e.placeholder), "name");
await glide(p.x, p.y, 600);
await click();
await sleep(250);
await typeText("Anna Demo", 110);
await sleep(500);
p = await targetRe("^Send plan$");
await glide(p.x, p.y, 600);
await sleep(300);
mark("sent");
await click();
await sleep(1500);
await smoothScroll(0, 1200);
await sleep(2200);
mark("end");
await sleep(500);

await cdp.send("Page.stopScreencast");
await sleep(300);
await browser.close();

// ---- assemble: constant-frame-rate mp4 from the timestamped frames -------------------------------------------------------
const T0 = frames[0].t;
const fps = frames.length / (frames.at(-1).t - T0);
console.log(`frames ${frames.length}, span ${(frames.at(-1).t - T0).toFixed(1)} s, mean ${fps.toFixed(1)} fps`);
const list = frames.map((f, i) => `file '${f.file}'\nduration ${(((frames[i + 1]?.t ?? f.t + 0.5) - f.t)).toFixed(4)}`).join("\n") + `\nfile '${frames.at(-1).file}'\n`;
await writeFile(path.join(FRAMES, "list.txt"), list);
const r = spawnSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", path.join(FRAMES, "list.txt"),
  "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", path.join(OUT, "customer.mp4")], { encoding: "utf8" });
if (r.status !== 0) throw new Error(r.stderr);
await writeFile(path.join(OUT, "customer.events.json"), JSON.stringify({ width: W, height: H, dpr: DPR, t0: T0, events: events.map((e) => ({ ...e, t: +(e.t - T0).toFixed(3) })) }, null, 1));
console.log("wrote capture/out/customer.mp4 and customer.events.json");
