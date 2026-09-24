import { noteWorkerWebGLContext } from "@/lib/pane/perf";
import { SubstrateEngine } from "./engine";
import type { SubstrateIn, SubstrateOut } from "./protocol";

export type SubstrateHandle = {
  post: (msg: SubstrateIn) => void;
  dispose: () => void;
};

function forceInlineFromUrl(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return new URLSearchParams(window.location.search).get("substrate") === "inline";
  } catch {
    return false;
  }
}

function canUseWorker(): boolean {
  if (forceInlineFromUrl()) return false;
  if (typeof Worker === "undefined") return false;
  if (typeof OffscreenCanvas === "undefined") return false;
  if (typeof HTMLCanvasElement === "undefined") return false;
  if (typeof HTMLCanvasElement.prototype.transferControlToOffscreen !== "function") {
    return false;
  }
  return true;
}

/**
 * Worker + OffscreenCanvas when available; otherwise the same engine on the main
 * thread at a 30 fps cap. Force shim with ?substrate=inline.
 */
export function createSubstrate(
  canvas: HTMLCanvasElement,
  onOut?: (msg: SubstrateOut) => void,
): SubstrateHandle {
  const emit = (msg: SubstrateOut) => {
    onOut?.(msg);
  };

  if (canUseWorker()) {
    const worker = new Worker(new URL("./substrate.worker.ts", import.meta.url), {
      type: "module",
    });
    const offscreen = canvas.transferControlToOffscreen();
    const handle: SubstrateHandle = {
      post(msg: SubstrateIn) {
        if (msg.type === "init") {
          if (booted) return;
          booted = true;
          // Do not include the HTML canvas — it is already transferred and cannot be cloned.
          const { canvas: _ignored, ...rest } = msg;
          worker.postMessage({ ...rest, type: "init", canvas: offscreen }, [offscreen]);
          return;
        }
        worker.postMessage(msg);
      },
      dispose() {
        disposed = true;
        // Worker terminate does not fire main-thread webglcontextlost — release the credit.
        noteWorkerWebGLContext(handle, false);
        worker.terminate();
      },
    };

    let booted = false;
    let disposed = false;
    worker.onmessage = (event: MessageEvent<SubstrateOut>) => {
      if (disposed) return;
      const msg = event.data;
      emit(msg);
      // OffscreenCanvas.getContext runs in the worker realm; credit once on ready.
      if (msg.type === "ready") {
        noteWorkerWebGLContext(handle, true);
      }
    };
    worker.onerror = (event) => {
      console.error("[substrate] worker error", event.message);
    };

    return handle;
  }

  // Inline shim — same engine, 30 fps cap, canvas stays on the main thread.
  // getContext is hooked in perf.ts; loseContext on dispose drops the live count.
  const engine = new SubstrateEngine(emit, { fpsCap: 30 });
  return {
    post(msg: SubstrateIn) {
      engine.handle(msg);
    },
    dispose() {
      engine.dispose();
    },
  };
}
