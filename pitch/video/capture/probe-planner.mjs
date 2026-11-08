// Runs the customer flow to the hand-off (fast), opens the planner view and saves screenshots + the interactive elements.
//   node capture/probe-planner.mjs [outDir]
import puppeteer from "puppeteer-core";
import { homedir } from "node:os";
import path from "node:path";
import { mkdir } from "node:fs/promises";

const URL = process.env.APP_URL ?? "http://localhost:5183/";
const CHROME = process.env.CHROME ?? path.join(homedir(), ".cache/hyperframes/chrome/chrome-headless-shell/win64-152.0.7977.30/chrome-headless-shell-win64/chrome-headless-shell.exe");
const OUT = process.argv[2] ?? path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\//, "")), "out", "probe");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await mkdir(OUT, { recursive: true });

const browser = await puppeteer.launch({ executablePath: CHROME, headless: "shell", args: ["--enable-gpu", "--ignore-gpu-blocklist", "--hide-scrollbars"], defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 } });
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("PAGE ERROR:", e.message));
await page.goto(URL, { waitUntil: "networkidle0" });
await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
await page.reload({ waitUntil: "networkidle0" });

const btn = (re) => page.evaluateHandle((r) => [...document.querySelectorAll("button")].find((b) => b.getClientRects().length && new RegExp(r).test(b.innerText.trim())), re);
const click = async (re) => { const h = (await btn(re)).asElement(); if (!h) throw new Error("no button " + re); await h.click(); };

await click("Plan my home"); await sleep(2500);
await page.type("input", "4500"); await page.keyboard.press("Enter"); await sleep(2200);
await page.type("input", "Sandstraße 33, 80335 München", { delay: 5 }); await page.keyboard.press("Enter"); await sleep(3200);
await page.screenshot({ path: path.join(OUT, "c1-after-address.png") });
await click("^Planned$"); await sleep(2200);
await click("^Gas$"); await sleep(4500);
await page.screenshot({ path: path.join(OUT, "c2-results.png") });
await click("Send plan to Sonnfeld"); await sleep(1200);
const name = await page.evaluateHandle(() => [...document.querySelectorAll("input")].find((e) => e.type === "text" && e.getClientRects().length && !e.placeholder));
await name.asElement().click(); await page.keyboard.type("Anna Demo", { delay: 30 });
await click("^Send plan$"); await sleep(1500);

await page.goto(URL + "#/installer", { waitUntil: "networkidle0" });
await sleep(6500);
const dump = async (label) => console.log("\n== " + label + "\n" + (await page.evaluate(() => [...document.querySelectorAll("button, input, select, textarea, h1, h2, h3")].filter((e) => e.getClientRects().length).map((e) => { const r = e.getBoundingClientRect(); return `${e.tagName.toLowerCase()} "${(e.innerText || e.value || e.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ").slice(0, 50)}" @${Math.round(r.x)},${Math.round(r.y)} ${Math.round(r.width)}x${Math.round(r.height)}`; }).join("\n"))));
await page.screenshot({ path: path.join(OUT, "p1-top.png") });
await dump("planner top");
for (let i = 1; i <= 4; i++) {
  await page.evaluate((i) => { const sc = [...document.querySelectorAll("*")].filter((e) => e.scrollHeight > e.clientHeight + 100 && /(auto|scroll)/.test(getComputedStyle(e).overflowY)).sort((a, b) => b.clientHeight - a.clientHeight)[0] ?? document.scrollingElement; (sc).scrollTop = i * 760; window.scrollTo(0, i * 760); }, i);
  await sleep(900);
  await page.screenshot({ path: path.join(OUT, `p${i + 1}-scroll${i}.png`) });
}
await browser.close();
console.log("screens in", OUT);
