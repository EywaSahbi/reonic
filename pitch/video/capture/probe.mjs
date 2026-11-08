// Prints the interactive elements the customer flow shows at each step, so capture-customer.mjs can target them by text.
import puppeteer from "puppeteer-core";
import { homedir } from "node:os";
import path from "node:path";

const URL = process.env.APP_URL ?? "http://localhost:5183/";
const CHROME = process.env.CHROME ?? path.join(homedir(), ".cache/hyperframes/chrome/chrome-headless-shell/win64-152.0.7977.30/chrome-headless-shell-win64/chrome-headless-shell.exe");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({ executablePath: CHROME, headless: "shell", args: ["--enable-gpu", "--ignore-gpu-blocklist", "--hide-scrollbars"], defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 } });
const page = await browser.newPage();
await page.goto(URL, { waitUntil: "networkidle0" });
await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
await page.reload({ waitUntil: "networkidle0" });

const dump = (label) => page.evaluate((label) => {
  const rows = [...document.querySelectorAll("button, input, textarea, dt, a[href]")].filter((e) => e.getClientRects().length).map((e) => {
    const r = e.getBoundingClientRect();
    return `${e.tagName.toLowerCase()}${e.type ? `[${e.type}]` : ""} "${(e.innerText || e.value || e.placeholder || e.getAttribute("aria-label") || "").trim().slice(0, 40)}" ph="${e.placeholder ?? ""}" @${Math.round(r.x)},${Math.round(r.y)} ${Math.round(r.width)}x${Math.round(r.height)}`;
  });
  return `\n== ${label}\n` + rows.join("\n");
}, label).then(console.log);

await dump("home");
await page.click('button[aria-label*="Plan my home"]');
await sleep(3000);
await dump("step 1");
await page.type("input", "4500", { delay: 30 });
await page.keyboard.press("Enter");
await sleep(2500);
await dump("step 2");
await page.type("input", "Musterstraße 12, 80331 München", { delay: 5 });
await page.keyboard.press("Enter");
await sleep(3000);
await dump("step 3");
const planned = await page.evaluateHandle(() => [...document.querySelectorAll("button")].find((b) => b.innerText.trim() === "Planned"));
await planned.asElement().click();
await sleep(2500);
await dump("step 4");
const gas = await page.evaluateHandle(() => [...document.querySelectorAll("button")].find((b) => b.innerText.trim() === "Gas"));
await gas.asElement().click();
await sleep(4000);
await dump("results");
await page.evaluate(() => { const s = document.querySelector(".sheet, [role=dialog], main, body"); document.querySelectorAll("*").forEach((e) => { if (e.scrollHeight > e.clientHeight + 50 && getComputedStyle(e).overflowY !== "visible") e.scrollTop = 99999; }); });
await sleep(1000);
await dump("results scrolled");
const send = await page.evaluateHandle(() => [...document.querySelectorAll("button")].find((b) => /Send plan to/.test(b.innerText)));
await send.asElement().click();
await sleep(1500);
await dump("handoff form");
await browser.close();
