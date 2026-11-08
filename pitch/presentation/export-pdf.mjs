// Export the deck to PDF: one 1920x1080 page per part, final state of each part.
//   node export-pdf.mjs [out.pdf] [--png]     (--png also writes a PNG per page for a quick look)
// Needs puppeteer-core (reused from ../video/node_modules) and an installed Chrome or Edge.
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "../video/package.json"));
const puppeteer = require("puppeteer-core");

const out = path.resolve(process.argv.find((a, i) => i > 1 && !a.startsWith("--")) ?? path.join(here, "reo-presentation.pdf"));
const png = process.argv.includes("--png");
const browserPath = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find((p) => p && existsSync(p));
if (!browserPath) throw new Error("No Chrome/Edge found. Set CHROME_PATH.");

const browser = await puppeteer.launch({ executablePath: browserPath, headless: true });
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080 });
await page.goto(pathToFileURL(path.join(here, "index.html")).href + "?print", { waitUntil: "networkidle0" });
await page.waitForSelector("body[data-ready]");
await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => {}))));
await page.emulateMediaType("print");
await page.pdf({ path: out, width: "1920px", height: "1080px", printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
if (png) {
  const n = await page.$$eval(".slide", (s) => s.length);
  for (let i = 0; i < n; i++) {
    const el = (await page.$$(".slide"))[i];
    await el.screenshot({ path: out.replace(/\.pdf$/, `-${i + 1}.png`) });
  }
}
await browser.close();
console.log("wrote", out);
