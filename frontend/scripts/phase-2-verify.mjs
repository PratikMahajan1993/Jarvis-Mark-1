/**
 * Phase 2 verify — parked visibility, scroll round-trip, perf counters.
 * Run: npx --yes --package=puppeteer-core@24.4.0 node scripts/phase-2-verify.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../.artifacts/phase-2");
const CHROME =
  process.env.CHROME_PATH ||
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.HUD_URL || "http://127.0.0.1:3000";

fs.mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitReady(page) {
  await page.waitForFunction(() => Boolean(window.__JARVIS_SUBSTRATE__?.ready), { timeout: 25000 });
}

async function snap(page, name) {
  const dest = path.join(OUT, name);
  await page.screenshot({ path: dest, type: "png" });
}

async function parkedReport(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("[data-panel]")].map((el) => ({
      id: el.getAttribute("data-panel"),
      depth: el.getAttribute("data-depth"),
      visibility: getComputedStyle(el).visibility,
      opacity: getComputedStyle(el).opacity,
    })),
  );
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });
  const page = await browser.newPage();
  await page.goto(`${BASE}/?perf=1&lens=monitor`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady(page);
  await sleep(2500);

  await snap(page, "watch.png");

  const scrollBefore = await page.evaluate(() => {
    const scroller = document.querySelector('[data-panel="tasks"] [data-tasks-scroll]');
    if (!scroller) return { ok: false, scrollTop: 0 };
    scroller.innerHTML = Array.from({ length: 24 })
      .map((_, i) => `<div style="height:72px;margin:8px 0;background:rgba(125,255,224,0.06);border-radius:8px">${i}</div>`)
      .join("");
    scroller.scrollTop = 320;
    return { ok: true, scrollTop: scroller.scrollTop };
  });

  await page.click("#lens-tab-converse");
  await sleep(1800);
  await snap(page, "converse.png");

  await page.click("#lens-tab-watch");
  await sleep(1800);

  const scrollAfter = await page.evaluate(() => {
    const scroller = document.querySelector('[data-panel="tasks"] [data-tasks-scroll]');
    return scroller?.scrollTop ?? null;
  });

  const watchParked = await parkedReport(page);
  const parkedHidden = watchParked.filter((p) => p.depth === "3").every((p) => p.visibility === "hidden");

  await page.click("#lens-tab-bench");
  await sleep(1800);
  await snap(page, "bench.png");
  const benchParked = await parkedReport(page);

  const perf = await page.evaluate(() => window.__JARVIS_PERF__?.snapshot?.() ?? null);

  console.log(
    JSON.stringify(
      {
        scrollBefore,
        scrollAfter,
        scrollSurvived: scrollBefore.ok && scrollAfter >= 280,
        parkedHiddenOnWatch: parkedHidden,
        watchParked: watchParked.filter((p) => p.depth === "3"),
        benchDepth0: benchParked.filter((p) => p.depth === "0").map((p) => p.id),
        perf,
      },
      null,
      2,
    ),
  );

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
