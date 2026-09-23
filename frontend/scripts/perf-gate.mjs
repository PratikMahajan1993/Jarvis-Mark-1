#!/usr/bin/env node
/**
 * Phase 0 perf baseline — headless Chrome, no Playwright.
 * Loads ?perf=1, cycles workspace switcher 20× (2 s apart), writes JSON + screenshot.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(FRONTEND_ROOT, "..");
const HUD_URL = "http://127.0.0.1:3000/?perf=1";
const SWITCH_COUNT = 20;
const SWITCH_GAP_MS = 2000;
const DEBUG_PORT = 9333;

/** monitor → casual → engineering → monitor … */
const LENS_CYCLE = ["Monitor", "Casual", "Engineering"];

const OUT_JSON = path.join(REPO_ROOT, "work", "perf", "baseline-overhaul.json");
const ARTIFACT_DIR = path.join(FRONTEND_ROOT, ".artifacts", "phase-0");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function httpRequest(url, method = "GET") {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method }, (res) => {
      let body = "";
      res.on("data", (c) => {
        body += c;
      });
      res.on("end", () => {
        if (res.statusCode && res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode} ${url}`));
          return;
        }
        resolve(body);
      });
    });
    req.on("error", reject);
    req.end();
  });
}

function httpGet(url) {
  return httpRequest(url, "GET");
}

async function waitForHud(port = 3000, timeoutMs = 120_000) {
  const url = `http://127.0.0.1:${port}/`;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      await httpGet(url);
      return;
    } catch {
      await sleep(1500);
    }
  }
  throw new Error(`HUD not responding on :${port} after ${timeoutMs}ms`);
}

function hudListening(port = 3000) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/`, (res) => {
      res.resume();
      resolve(true);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function startDevServerIfNeeded() {
  return hudListening().then(async (up) => {
    if (up) {
      console.log("HUD already on :3000");
      return null;
    }
    console.log("Starting npm run dev in frontend/ …");
    const child = spawn("npm run dev", {
      cwd: FRONTEND_ROOT,
      stdio: "ignore",
      detached: true,
      shell: true,
    });
    child.unref();
    await waitForHud();
    return child;
  });
}

function findChromeExecutable() {
  const envPath = process.env.CHROME_PATH || process.env.GOOGLE_CHROME_BIN;
  if (envPath && fs.existsSync(envPath)) return envPath;

  const candidates =
    process.platform === "win32"
      ? [
          path.join(
            process.env.PROGRAMFILES || "C:\\Program Files",
            "Google",
            "Chrome",
            "Application",
            "chrome.exe",
          ),
          path.join(
            process.env["PROGRAMFILES(X86)"] || "C:\\Program Files (x86)",
            "Google",
            "Chrome",
            "Application",
            "chrome.exe",
          ),
          path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
        ]
      : process.platform === "darwin"
        ? [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
          ]
        : ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"];

  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error(
    "Chrome not found. Set CHROME_PATH to chrome.exe (Windows) or install Google Chrome.",
  );
}

class CdpSession {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.addEventListener("open", () => resolve());
      this.ws.addEventListener("error", (e) => reject(e));
      this.ws.addEventListener("message", (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve: res, reject: rej } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) rej(new Error(msg.error.message || JSON.stringify(msg.error)));
          else res(msg.result);
        }
      });
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    if (this.ws) this.ws.close();
  }

  evaluate(expression, awaitPromise = false) {
    return this.send("Runtime.evaluate", {
      expression,
      awaitPromise,
      returnByValue: true,
    });
  }
}

async function openCdpPage(chromePath, url) {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "jarvis-chrome-perf-"));
  const args = [
    `--remote-debugging-port=${DEBUG_PORT}`,
    "--headless=new",
    "--enable-unsafe-swiftshader",
    "--disable-gpu-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${userDataDir}`,
    "about:blank",
  ];

  const chrome = spawn(chromePath, args, { stdio: "ignore" });
  chrome.unref?.();

  const start = Date.now();
  while (Date.now() - start < 30_000) {
    try {
      await httpGet(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
      break;
    } catch {
      await sleep(200);
    }
  }

  let targets;
  try {
    targets = JSON.parse(
      await httpRequest(
        `http://127.0.0.1:${DEBUG_PORT}/json/new?${encodeURIComponent(url)}`,
        "PUT",
      ),
    );
  } catch {
    const list = JSON.parse(await httpGet(`http://127.0.0.1:${DEBUG_PORT}/json/list`));
    targets = list.find((t) => t.type === "page") ?? list[0];
    if (!targets?.webSocketDebuggerUrl) {
      throw new Error("No CDP page target from Chrome");
    }
  }

  const session = new CdpSession(targets.webSocketDebuggerUrl);
  await session.connect();
  await session.send("Page.enable");
  await session.send("Runtime.enable");
  if (!targets.url?.includes("perf=1")) {
    await session.send("Page.navigate", { url });
  }

  return { session, chrome, userDataDir };
}

function nextLensLabel(current) {
  const idx = LENS_CYCLE.indexOf(current);
  const base = idx >= 0 ? idx : 0;
  return LENS_CYCLE[(base + 1) % LENS_CYCLE.length];
}

async function waitForPerfApi(session, timeoutMs = 90_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const { result } = await session.evaluate("Boolean(window.__JARVIS_PERF__)", false);
    if (result?.value) return;
    await sleep(500);
  }
  throw new Error("window.__JARVIS_PERF__ not available");
}

async function getActiveLens(session) {
  const expr = `(function(){
    const g = document.querySelector('[aria-label="HUD workspace"]');
    if (!g) return null;
    const pressed = g.querySelector('button[aria-pressed="true"]');
    return pressed ? pressed.textContent.trim() : null;
  })()`;
  const { result } = await session.evaluate(expr, false);
  return result?.value ?? "Monitor";
}

async function clickLens(session, label) {
  const expr = `(function(){
    const g = document.querySelector('[aria-label="HUD workspace"]');
    if (!g) throw new Error('workspace switcher missing');
    const btn = Array.from(g.querySelectorAll('button')).find(
      (b) => b.textContent.trim() === ${JSON.stringify(label)},
    );
    if (!btn) throw new Error('button ${label} missing');
    btn.click();
    return true;
  })()`;
  await session.evaluate(expr, false);
}

async function captureScreenshot(session, outPath) {
  const { data } = await session.send("Page.captureScreenshot", { format: "png" });
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, Buffer.from(data, "base64"));
}

async function readPerfSnapshot(session) {
  const { result } = await session.evaluate("window.__JARVIS_PERF__.snapshot()", false);
  if (result?.type === "object" && result.objectId) {
    throw new Error("Unexpected object snapshot; expected returnByValue plain object");
  }
  return result?.value;
}

async function main() {
  if (typeof WebSocket === "undefined") {
    throw new Error("Global WebSocket required (Node 22+). Upgrade Node or set experimental websocket.");
  }

  fs.mkdirSync(path.dirname(OUT_JSON), { recursive: true });
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

  await startDevServerIfNeeded();
  await waitForHud();

  const chromePath = findChromeExecutable();
  console.log(`Chrome: ${chromePath}`);

  const { session, chrome, userDataDir } = await openCdpPage(chromePath, HUD_URL);
  try {
    await waitForPerfApi(session);
    await sleep(4000);

    let current = await getActiveLens(session);
    console.log(`Initial lens: ${current}`);

    for (let i = 0; i < SWITCH_COUNT; i += 1) {
      const target = nextLensLabel(current);
      console.log(`Switch ${i + 1}/${SWITCH_COUNT}: ${current} → ${target}`);
      await clickLens(session, target);
      current = target;
      await sleep(SWITCH_GAP_MS);
    }

    await sleep(1500);

    const shotPath = path.join(ARTIFACT_DIR, "perf-overlay-baseline.png");
    await captureScreenshot(session, shotPath);
    console.log(`Screenshot: ${shotPath}`);

    const snap = await readPerfSnapshot(session);
    if (!snap) throw new Error("Empty perf snapshot");

    const payload = {
      capturedAt: new Date().toISOString(),
      hudUrl: HUD_URL,
      switchCount: SWITCH_COUNT,
      rafHistogram: snap.rafHistogram,
      rafP95Ms: snap.rafP95Ms,
      longTasks: snap.longTasks,
      webglContextCount: snap.webglContextCount,
      orchestratorShellCommits: snap.orchestratorShellCommits,
    };

    fs.writeFileSync(OUT_JSON, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    console.log(`Wrote ${OUT_JSON}`);
    console.log(
      JSON.stringify({
        switchCount: payload.switchCount,
        webglContextCount: payload.webglContextCount,
        orchestratorShellCommits: payload.orchestratorShellCommits,
        longTaskCount: payload.longTasks.length,
        rafP95Ms: payload.rafP95Ms,
      }),
    );
  } finally {
    session.close();
    try {
      chrome.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    try {
      fs.rmSync(userDataDir, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
