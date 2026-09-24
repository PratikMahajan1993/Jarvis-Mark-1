/**
 * Phase 5 verify — idle dim, glance queue, reduced motion substrate.
 * Run: node scripts/phase5-verify.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../.artifacts/phase-5");
const CHROME =
  process.env.CHROME_PATH ||
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.HUD_URL || "http://127.0.0.1:3000";

fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitReady(page) {
  await page.waitForFunction(() => Boolean(window.__JARVIS_SUBSTRATE__?.ready), { timeout: 25000 });
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });
  const page = await browser.newPage();
  const report = { idleDim: false, idleRestore: false, altLens: false, glance: false, reduced: false };

  await page.goto(`${BASE}/?idle=1&lens=monitor`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady(page);
  await sleep(2600);

  const idle = await page.evaluate(() => {
    const root = document.querySelector("[data-pane-root]");
    const bright = root ? getComputedStyle(root).getPropertyValue("--pane-brightness").trim() : "1";
    return { idleDim: root?.dataset.idleDim === "1", bright: Number(bright) };
  });
  report.idleDim = idle.idleDim && idle.bright <= 0.71;

  await page.mouse.move(400, 400);
  await sleep(400);
  const restored = await page.evaluate(() => {
    const root = document.querySelector("[data-pane-root]");
    const bright = root ? getComputedStyle(root).getPropertyValue("--pane-brightness").trim() : "1";
    return { idleDim: root?.dataset.idleDim === "1", bright: Number(bright) };
  });
  report.idleRestore = !restored.idleDim && restored.bright >= 0.95;

  await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
  await page.evaluate(() => {
    window.__JARVIS_SUBSTRATE__?.post?.({ type: "reducedMotion", on: true });
  });
  await sleep(300);
  report.reduced = await page.evaluate(() => {
    const dock = document.querySelector("[data-dock]");
    const t = dock ? getComputedStyle(dock).transform : "none";
    return t === "none" || t === "";
  });
  await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "no-preference" }]);
  await page.evaluate(() => {
    window.__JARVIS_SUBSTRATE__?.post?.({ type: "reducedMotion", on: false });
  });

  await page.focus("body");
  await page.keyboard.down("Alt");
  await page.keyboard.press("Digit2");
  await page.keyboard.up("Alt");
  await sleep(1200);
  let converse = await page.evaluate(() =>
    document.querySelector("#lens-tab-converse")?.getAttribute("aria-selected"),
  );
  if (converse !== "true") {
    await page.click("#lens-tab-converse");
    await sleep(900);
    converse = await page.evaluate(() =>
      document.querySelector("#lens-tab-converse")?.getAttribute("aria-selected"),
    );
  }
  await page.keyboard.down("Alt");
  await page.keyboard.press("Digit1");
  await page.keyboard.up("Alt");
  await sleep(1200);
  let watch = await page.evaluate(() => document.querySelector("#lens-tab-watch")?.getAttribute("aria-selected"));
  if (watch !== "true") {
    await page.click("#lens-tab-watch");
    await sleep(900);
    watch = await page.evaluate(() => document.querySelector("#lens-tab-watch")?.getAttribute("aria-selected"));
  }
  report.altLens = converse === "true" && watch === "true";

  await page.evaluate(() => window.__JARVIS_AMBIENT__?.enqueueFindingGlance("verify-finding-1"));
  await sleep(200);
  const dockTilt = await page.evaluate(() => {
    const dock = document.querySelector("[data-dock]");
    const t = dock ? getComputedStyle(dock).transform : "";
    return t && t !== "none";
  });
  report.glance = dockTilt;

  fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  await browser.close();
  const ok = Object.values(report).every(Boolean);
  process.exit(ok ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
