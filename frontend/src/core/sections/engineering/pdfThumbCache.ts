/**
 * X9: pdf.js page-1 thumbnails at idle, cached in IndexedDB by file sha256.
 * 2D canvas only — never opens WebGL.
 */

import { loadPdfJs } from "@/lib/canvas/pdf";

const DB_NAME = "jarvis-pdf-thumbs";
const DB_VERSION = 1;
const STORE = "thumbs";
const THUMB_EDGE = 112;

/** IndexedDB / in-memory key for a PDF thumbnail (sha256 hex). */
export function thumbnailCacheKey(sha256: string): string {
  const h = sha256.trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(h)) return "";
  return `pdf-thumb:v1:${h}`;
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB unavailable"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
  });
}

export async function getCachedThumb(sha256: string): Promise<string | null> {
  const key = thumbnailCacheKey(sha256);
  if (!key) return null;
  try {
    const db = await openDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(key);
      req.onerror = () => reject(req.error);
      req.onsuccess = () => {
        const v = req.result;
        resolve(typeof v === "string" && v.startsWith("data:") ? v : null);
      };
    });
  } catch {
    return null;
  }
}

export async function setCachedThumb(sha256: string, dataUrl: string): Promise<void> {
  const key = thumbnailCacheKey(sha256);
  if (!key || !dataUrl.startsWith("data:")) return;
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.objectStore(STORE).put(dataUrl, key);
    });
  } catch {
    /* cache is best-effort */
  }
}

/** Render PDF page 1 to a small JPEG data URL (2D canvas). */
export async function renderPdfPage1Thumb(data: ArrayBuffer, maxEdge = THUMB_EDGE): Promise<string> {
  const pdfjs = await loadPdfJs();
  const doc = await pdfjs.getDocument({ data: new Uint8Array(data) }).promise;
  const page = await doc.getPage(1);
  const base = page.getViewport({ scale: 1 });
  const fit = Math.min(maxEdge / base.width, maxEdge / base.height);
  const scale = Math.max(0.2, fit);
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(viewport.width));
  canvas.height = Math.max(1, Math.round(viewport.height));
  const ctx = canvas.getContext("2d", { alpha: false });
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  await page.render({ canvasContext: ctx, viewport, canvas }).promise;
  return canvas.toDataURL("image/jpeg", 0.82);
}

export function whenIdle(fn: () => void, timeoutMs = 2500): () => void {
  if (typeof window !== "undefined" && typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(() => fn(), { timeout: timeoutMs });
    return () => window.cancelIdleCallback(id);
  }
  const id = window.setTimeout(fn, Math.min(800, timeoutMs));
  return () => window.clearTimeout(id);
}

/** True when the card has a local PDF and no ready thumbnail URL. */
export function needsIdlePdfThumb(item: {
  thumbnailUrl?: string;
  localName?: string;
  mime?: string;
  filename?: string;
}): boolean {
  if (item.thumbnailUrl) return false;
  const name = (item.localName || item.filename || "").toLowerCase();
  const mime = (item.mime || "").toLowerCase();
  return name.endsWith(".pdf") || mime.includes("pdf");
}
