/**
 * Phase 1b headless verify — swiftshader Chrome.
 * Usage: node scripts/phase1b-verify.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, "../.artifacts/phase-1b");
const CHROME =
  process.env.CHROME_PATH ||
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.HUD_URL || "http://127.0.0.1:3000";

fs.mkdirSync(OUT, { recursive: true });

async function waitReady(page, timeoutMs = 15000) {
  await page.waitForFunction(() => Boolean(window.__JARVIS_SUBSTRATE__?.ready), {
    timeout: timeoutMs,
  });
}

async function waitSettled(page, timeoutMs = 12000) {
  await waitReady(page, timeoutMs);
  await page.waitForFunction(() => Boolean(window.__JARVIS_SUBSTRATE__?.settled), {
    timeout: timeoutMs,
  });
}

async function snap(page, name) {
  const dest = path.join(OUT, name);
  await page.screenshot({ path: dest, type: "png" });
  console.log(`SHOT ${name} ${fs.statSync(dest).size}b`);
}

async function substrateState(page) {
  return page.evaluate(() => {
    const s = window.__JARVIS_SUBSTRATE__;
    const p = window.__JARVIS_PERF__?.snapshot?.();
    return {
      mode: s?.mode,
      settled: s?.settled,
      stats: s?.stats,
      contextLost: s?.contextLost,
      ready: s?.ready,
      webgl: p?.webglContextCount ?? null,
    };
  });
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: [
      "--enable-unsafe-swiftshader",
      "--use-angle=swiftshader",
      "--window-size=1440,900",
      "--hide-scrollbars",
    ],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  page.on("console", (m) => {
    if (m.type() === "error") console.log("CONSOLE error", m.text());
  });

  await page.goto(`${BASE}/?perf=1&lens=casual&v=p1b`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  try {
    await waitSettled(page);
  } catch (e) {
    console.log("WAIT_FAIL casual", e.message);
    console.log("STATE", JSON.stringify(await substrateState(page)));
  }
  await new Promise((r) => setTimeout(r, 1000));
  console.log("CASUAL", JSON.stringify(await substrateState(page)));
  await snap(page, "orb-casual.png");

  await page.evaluate(() => {
    window.__JARVIS_SUBSTRATE__?.post?.({ type: "quality", scale: 0.4, fps: 30 });
  });
  await new Promise((r) => setTimeout(r, 1500));
  const degraded = await page.evaluate(() => window.__JARVIS_SUBSTRATE__?.stats?.scale);
  console.log("QUALITY_FORCED", degraded);

  await page.evaluate(() => {
    window.__JARVIS_SUBSTRATE__?.post?.({ type: "quality", scale: 0.6, fps: 60 });
  });
  await new Promise((r) => setTimeout(r, 1500));
  const recovered = await page.evaluate(() => window.__JARVIS_SUBSTRATE__?.stats?.scale);
  console.log("QUALITY_RECOVERED", recovered);

  await page.goto(`${BASE}/?perf=1&lens=engineering&v=p1b`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  try {
    await waitSettled(page);
  } catch (e) {
    console.log("WAIT_FAIL bench", e.message);
  }
  await new Promise((r) => setTimeout(r, 1000));
  console.log("BENCH", JSON.stringify(await substrateState(page)));
  await snap(page, "pilot-bench.png");

  await page.goto(`${BASE}/?perf=1&lens=monitor&v=p1b`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  try {
    await waitSettled(page);
  } catch (e) {
    console.log("WAIT_FAIL monitor", e.message);
  }
  await new Promise((r) => setTimeout(r, 800));
  console.log("MONITOR", JSON.stringify(await substrateState(page)));
  await snap(page, "eye-monitor.png");

  await page.evaluate(() => {
    window.__JARVIS_SUBSTRATE__?.post?.({
      type: "lens",
      lens: "converse",
      t0: performance.timeOrigin + performance.now(),
    });
  });
  await new Promise((r) => setTimeout(r, 300));
  await snap(page, "mid-morph.png");

  // Context loss — inline shim (main-thread canvas)
  await page.goto(`${BASE}/?perf=1&lens=casual&substrate=inline&v=p1b`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await waitSettled(page);
  console.log("CTX_BEFORE", JSON.stringify(await substrateState(page)));

  const lostOk = await page.evaluate(() => {
    const canvas = document.querySelector("[data-substrate] canvas");
    if (!canvas) return { ok: false, reason: "no canvas" };
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!gl) return { ok: false, reason: "no gl" };
    const ext = gl.getExtension("WEBGL_lose_context");
    if (!ext) return { ok: false, reason: "no ext" };
    // Keep extension on window so restore works after lose (getContext can go stale).
    window.__JARVIS_LOSE_EXT__ = ext;
    ext.loseContext();
    return { ok: true, lost: gl.isContextLost() };
  });
  console.log("LOSE_CALL", JSON.stringify(lostOk));

  try {
    await page.waitForFunction(() => window.__JARVIS_SUBSTRATE__?.contextLost === true, {
      timeout: 5000,
    });
    console.log("CTX_LOST true");
  } catch {
    console.log("CTX_LOST timeout", JSON.stringify(await substrateState(page)));
  }

  await page.evaluate(() => {
    const ext = window.__JARVIS_LOSE_EXT__;
    if (!ext) throw new Error("no lose ext");
    ext.restoreContext();
  });

  try {
    await page.waitForFunction(
      () =>
        window.__JARVIS_SUBSTRATE__?.contextLost === false &&
        window.__JARVIS_SUBSTRATE__?.ready != null,
      { timeout: 8000 },
    );
    console.log("CTX_RESTORED", JSON.stringify(await substrateState(page)));
  } catch {
    console.log(
      "CTX_RESTORE timeout",
      JSON.stringify(
        await page.evaluate(() => ({
          state: window.__JARVIS_SUBSTRATE__,
          latest: window.__JARVIS_SUBSTRATE__?.latest,
        })),
      ),
    );
  }

  await browser.close();
  console.log("DONE");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
