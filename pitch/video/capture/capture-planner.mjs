// Records the planner's run on the Sandstraße 33 plan (mock backend): summary, satellite placement, move / add / remove modules,
// the responsive price breakdown, next steps (calendar, CRM) and finalise. Cursor-less clip + pointer/step log, like capture-customer.
//   node capture/capture-planner.mjs   -> capture/out/planner.mp4, capture/out/planner.events.json
import puppeteer from "puppeteer-core";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, "out");
const FRAMES = path.join(OUT, "frames-planner");
const URL = process.env.APP_URL ?? "http://localhost:5183/";
const CHROME = process.env.CHROME ?? path.join(homedir(), ".cache/hyperframes/chrome/chrome-headless-shell/win64-152.0.7977.30/chrome-headless-shell-win64/chrome-headless-shell.exe");
const W = 1440, H = 900, DPR = Number(process.env.DPR ?? 1.5);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = () => Date.now() / 1000;

await rm(FRAMES, { recursive: true, force: true });
await mkdir(FRAMES, { recursive: true });

// module positions (metres east/north of the roof frame) from the demo roof, to aim drags at real free spots
const roofTs = await readFile(path.join(here, "..", "..", "..", "app", "src", "demoRoof.ts"), "utf8");
const MODS = [...roofTs.matchAll(/\{ x: (-?[\d.]+), y: (-?[\d.]+), rot_deg/g)].map((m) => [Number(m[1]), Number(m[2])]);

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "shell",
  args: ["--enable-gpu", "--ignore-gpu-blocklist", "--hide-scrollbars", "--force-color-profile=srgb", `--force-device-scale-factor=${DPR}`],
  defaultViewport: { width: W, height: H, deviceScaleFactor: DPR },
});
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("PAGE ERROR:", e.message));
await page.goto(URL, { waitUntil: "networkidle0" });
await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
await page.reload({ waitUntil: "networkidle0" });

// ---- preamble (not recorded): the customer hands over the Sandstraße 33 plan ----------------------------------------------
const btnH = (re) => page.evaluateHandle((r) => [...document.querySelectorAll("button")].find((b) => b.getClientRects().length && new RegExp(r).test(b.innerText.trim())), re);
const clickBtn = async (re) => { const h = (await btnH(re)).asElement(); if (!h) throw new Error("no button " + re); await h.click(); };
await clickBtn("Plan my home"); await sleep(2500);
await page.type("input", "4500"); await page.keyboard.press("Enter"); await sleep(2200);
await page.type("input", "Sandstraße 33, 80335 München", { delay: 5 }); await page.keyboard.press("Enter"); await sleep(3500);
await clickBtn("^Planned$"); await sleep(2200);
await clickBtn("^Gas$"); await sleep(4500);
await clickBtn("Send plan to Sonnfeld"); await sleep(1200);
const nameInput = await page.evaluateHandle(() => [...document.querySelectorAll("input")].find((e) => e.type === "text" && e.getClientRects().length && !e.placeholder));
await nameInput.asElement().click(); await page.keyboard.type("Anna Demo", { delay: 20 });
await clickBtn("^Send plan$"); await sleep(6000); // reo prepares the next steps for ~4 s after the hand-off
await page.goto(URL + "#/installer", { waitUntil: "networkidle0" });
await page.reload({ waitUntil: "networkidle0" });
await sleep(6500); // the satellite tiles and reo's next steps are ready now
await page.mouse.move(W + 60, 220);

// ---- screencast ---------------------------------------------------------------------------------------------------------------
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

const events = [];
let mx = W + 60, my = 220;
const log = (kind, extra = {}) => events.push({ t: now(), kind, ...extra });
const ease = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
async function glide(x, y, ms = 700, held = false) {
  log("move", { from: [mx, my], to: [x, y], ms, held });
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
async function click(hold = 110) { log("down", { at: [mx, my] }); await page.mouse.down(); await sleep(hold); await page.mouse.up(); log("up", { at: [mx, my] }); }
const mark = (name) => log("mark", { name });
async function centreOf(fn, arg) {
  const h = await page.evaluateHandle(fn, arg);
  const el = h.asElement();
  if (!el) throw new Error("element not found: " + arg);
  const b = await el.boundingBox();
  return { x: b.x + b.width / 2, y: b.y + b.height / 2, el };
}
const buttonText = (t) => centreOf((t) => [...document.querySelectorAll("button")].find((e) => e.getClientRects().length && e.innerText.trim().replace(/\s+/g, " ") === t), t);
const buttonRe = (r) => centreOf((r) => [...document.querySelectorAll("button")].find((e) => e.getClientRects().length && new RegExp(r).test(e.innerText.trim())), r);
async function scrollTo(selector, offset = 90, ms = 1300) {
  log("scroll", { selector, ms });
  await page.evaluate(async (selector, offset, ms) => {
    const el = document.querySelector(selector);
    const sc = [...document.querySelectorAll("*")].filter((e) => e.scrollHeight > e.clientHeight + 200 && /(auto|scroll)/.test(getComputedStyle(e).overflowY)).sort((a, b) => b.clientHeight - a.clientHeight)[0] ?? document.scrollingElement;
    const y0 = sc.scrollTop, target = y0 + el.getBoundingClientRect().top - offset, t0 = performance.now();
    await new Promise((res) => {
      const f = (t) => { const p = Math.min(1, (t - t0) / ms), e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; sc.scrollTop = y0 + (target - y0) * e; p < 1 ? requestAnimationFrame(f) : res(); };
      requestAnimationFrame(f);
    });
  }, selector, offset, ms);
  log("scrolled", { selector });
}
// screen position of module i's centre, and of an arbitrary roof position (metres), from two anchor modules
async function moduleCentres() {
  return page.evaluate(() => [...document.querySelectorAll(".pv-module")].map((g) => { const r = g.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }));
}
const screenOf = (cs, [x, y]) => {
  const a = 0, b = 9; // module 0 and module 9: the two ends of the south-west row
  const dm = Math.hypot(MODS[b][0] - MODS[a][0], MODS[b][1] - MODS[a][1]);
  const ds = Math.hypot(cs[b][0] - cs[a][0], cs[b][1] - cs[a][1]);
  const k = ds / dm;
  return [cs[a][0] + k * (x - MODS[a][0]), cs[a][1] - k * (y - MODS[a][1])];
};

// ---- the run -------------------------------------------------------------------------------------------------------------
mark("inbox");
await sleep(1400);
let p = await centreOf(() => document.querySelector(".summary-text"), "summary");
await glide(p.x - 120, p.y - 30, 1100);
await sleep(3400); // reo's summary is read

mark("roof");
await scrollTo('section[aria-label="Roof and solar modules"]', 70, 1400);
await sleep(600);
let cs = await moduleCentres();
await glide(cs[4][0] + 60, cs[4][1] + 40, 900);
await sleep(2600); // the automatic placement around the skylight and the rooftop units

mark("move");
cs = await moduleCentres();
const from = cs[20];                                  // a module of the north-east cluster
const to = screenOf(cs, MODS[24 + 7]);                // a free spot (row 0, first free position) in the middle of the roof
await glide(from[0], from[1], 900);
await sleep(250);
log("down", { at: [mx, my] }); await page.mouse.down();
await glide(to[0], to[1], 1500, true);
await sleep(150);
await page.mouse.up(); log("up", { at: [mx, my] });
await sleep(1200);

mark("add");
for (let i = 0; i < 3; i++) {
  p = await buttonText("Add module");
  await glide(p.x, p.y, i === 0 ? 800 : 350);
  await sleep(i === 0 ? 200 : 80);
  await click();
  await sleep(900);
}
await sleep(900);

mark("remove");
cs = await moduleCentres();
await glide(cs[0][0], cs[0][1], 900);
await sleep(200);
await click();
await sleep(900);
p = await buttonText("Remove");
await glide(p.x, p.y, 700);
await sleep(200);
await click();
await sleep(1700); // the price re-derives

mark("price");
await scrollTo(".price-table", 330, 1300);
await sleep(500);
p = await centreOf(() => document.querySelector(".price-table tr.changed td"), "row");
await glide(p.x, p.y, 800);
await sleep(3000);

mark("next");
await scrollTo(".next-steps", 220, 1300);
await sleep(700);
p = await centreOf(() => [...document.querySelectorAll(".next-steps li")].find((l) => /Calendar/.test(l.innerText)).querySelector("button:last-child"), "cal");
await glide(p.x, p.y, 900);
await sleep(300);
mark("calendar");
await click();
await sleep(1700);
p = await centreOf(() => [...document.querySelectorAll(".next-steps li")].find((l) => /CRM/.test(l.innerText)).querySelector("button:last-child"), "crm");
await glide(p.x, p.y, 800);
await sleep(300);
mark("crm");
await click();
await sleep(2200);

mark("finalise");
await scrollTo(".finalize", 400, 1200);
await sleep(400);
p = await centreOf(() => document.querySelector("#note"), "note");
await glide(p.x, p.y, 800);
await click();
await sleep(250);
log("type", { text: "We checked the roof photo: the skylight and the rooftop units stay clear.", delay: 35 });
await page.keyboard.type("We checked the roof photo: the skylight and the rooftop units stay clear.", { delay: 35 });
await sleep(500);
p = await buttonRe("^Finalise and send quote");
await glide(p.x, p.y, 800);
await sleep(300);
mark("sent");
await click();
await sleep(3000);
mark("end");
await sleep(400);

await cdp.send("Page.stopScreencast");
await sleep(300);
await browser.close();

const T0 = frames[0].t;
console.log(`frames ${frames.length}, span ${(frames.at(-1).t - T0).toFixed(1)} s, mean ${(frames.length / (frames.at(-1).t - T0)).toFixed(1)} fps`);
const list = frames.map((f, i) => `file '${f.file}'\nduration ${(((frames[i + 1]?.t ?? f.t + 0.5) - f.t)).toFixed(4)}`).join("\n") + `\nfile '${frames.at(-1).file}'\n`;
await writeFile(path.join(FRAMES, "list.txt"), list);
const r = spawnSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", path.join(FRAMES, "list.txt"),
  "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", path.join(OUT, "planner.mp4")], { encoding: "utf8" });
if (r.status !== 0) throw new Error(r.stderr);
await writeFile(path.join(OUT, "planner.events.json"), JSON.stringify({ width: W, height: H, dpr: DPR, t0: T0, events: events.map((e) => ({ ...e, t: +(e.t - T0).toFixed(3) })) }, null, 1));
console.log("wrote capture/out/planner.mp4 and planner.events.json");
