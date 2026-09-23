/**
 * Phase 3 — three rapid lens switches within 1s; dump perf snapshot.
 * Run: node scripts/phase-3-rapid-switches.mjs
 * Env: HUD_URL, CHROME_PATH, OUT (default frontend/.artifacts/phase-3/rapid-switches.json)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT =
  process.env.OUT ||
  path.resolve(__dirname, "../.artifacts/phase-3/rapid-switches.json");
const CHROME =
  process.env.CHROME_PATH ||
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.HUD_URL || "http://127.0.0.1:3000";

fs.mkdirSync(path.dirname(OUT), { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitReady(page) {
  await page.waitForFunction(() => Boolean(window.__JARVIS_SUBSTRATE__?.ready), {
    timeout: 25000,
  });
  await page.waitForFunction(() => Boolean(window.__JARVIS_PERF__?.snapshot), {
    timeout: 15000,
  });
}

async function runSwitchBurst(page) {
  return page.evaluate(async () => {
    window.__JARVIS_PERF__?.resetCounters?.();
    const beforeCommits = window.__JARVIS_PERF__?.snapshot()?.orchestratorShellCommits ?? 0;
    const t0 = performance.now();
    document.querySelector("#lens-tab-watch")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => requestAnimationFrame(r));
    document.querySelector("#lens-tab-converse")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await new Promise((r) => requestAnimationFrame(r));
    document.querySelector("#lens-tab-bench")?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const elapsed = performance.now() - t0;
    await new Promise((r) => setTimeout(r, 1600));
    const snap = window.__JARVIS_PERF__?.snapshot?.() ?? null;
    const longOver50 = (snap?.longTasks ?? []).filter((t) => t.duration > 50).length;
    const afterCommits = snap?.orchestratorShellCommits ?? 0;
    return {
      switchBurstMs: elapsed,
      longTasksOver50ms: longOver50,
      rafP95Ms: snap?.rafP95Ms ?? null,
      webglContextCount: snap?.webglContextCount ?? null,
      orchestratorShellCommitsDelta: afterCommits - beforeCommits,
      longTasks: snap?.longTasks ?? [],
    };
  });
}

async function sampleHeadless() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });
  const page = await browser.newPage();
  await page.goto(`${BASE}/?perf=1&lens=monitor`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await waitReady(page);
  await sleep(5000);
  const result = await runSwitchBurst(page);
  await browser.close();
  return result;
}

async function sampleDesk() {
  const connected = await puppeteer
    .connect({
      browserURL: "http://127.0.0.1:9222",
      defaultViewport: null,
    })
    .catch(() => null);
  if (connected) {
    const page = await connected.newPage();
    await page.goto(`${BASE}/?perf=1`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitReady(page);
    await sleep(5000);
    const result = await runSwitchBurst(page);
    await connected.disconnect();
    return result;
  }
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: false,
    args: ["--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });
  const page = await browser.newPage();
  await page.goto(`${BASE}/?perf=1`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await waitReady(page);
  await sleep(5000);
  const result = await runSwitchBurst(page);
  await browser.close();
  return result;
}

async function main() {
  const headless = await sampleHeadless();
  const desk = (await sampleDesk()) ?? null;
  const payload = {
    recordedAt: new Date().toISOString(),
    sequence: ["monitor", "casual", "engineering"],
    headless,
    ...(desk ? { desk } : {}),
  };
  fs.writeFileSync(OUT, `${JSON.stringify(payload, null, 2)}\n`);
  console.log(JSON.stringify(payload, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
