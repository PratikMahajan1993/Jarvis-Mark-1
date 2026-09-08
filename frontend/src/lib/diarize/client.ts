import type { DiarizeProgress, DiarizeResult, DiarizeRunOptions, WorkerIn, WorkerOut } from "./types";

type Pending = {
  resolve: (value: DiarizeResult | void) => void;
  reject: (err: Error) => void;
  onProgress?: (progress: DiarizeProgress) => void;
};

export type DiarizeClient = {
  load: (transcribe: boolean, onProgress?: (progress: DiarizeProgress) => void) => Promise<void>;
  diarize: (
    pcm: Float32Array,
    options?: DiarizeRunOptions,
    onProgress?: (progress: DiarizeProgress) => void,
  ) => Promise<DiarizeResult>;
  dispose: () => void;
};

export function createDiarizeClient(): DiarizeClient {
  const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  const pending = new Map<number, Pending>();
  let nextId = 1;

  worker.onmessage = (event: MessageEvent<WorkerOut>) => {
    const msg = event.data;
    const job = pending.get(msg.id);
    if (!job) return;
    if (msg.type === "progress") {
      job.onProgress?.({ label: msg.label, progress: msg.progress });
      return;
    }
    pending.delete(msg.id);
    if (msg.type === "error") {
      job.reject(new Error(msg.message));
      return;
    }
    if (msg.type === "ready") {
      job.resolve();
      return;
    }
    job.resolve(msg.result);
  };

  worker.onerror = (event) => {
    const err = new Error(event.message || "Diarize worker failed.");
    for (const job of pending.values()) job.reject(err);
    pending.clear();
  };

  const send = (
    message: WorkerIn,
    options: { transfer?: Transferable[]; onProgress?: (progress: DiarizeProgress) => void } = {},
  ) =>
    new Promise<DiarizeResult | void>((resolve, reject) => {
      pending.set(message.id, { resolve, reject, onProgress: options.onProgress });
      worker.postMessage(message, options.transfer ?? []);
    });

  return {
    async load(transcribe, onProgress) {
      const id = nextId;
      nextId += 1;
      await send({ id, type: "load", transcribe }, { onProgress });
    },
    async diarize(pcm, options = {}, onProgress) {
      const id = nextId;
      nextId += 1;
      const copy = new Float32Array(pcm);
      const result = await send(
        {
          id,
          type: "run",
          pcm: copy,
          transcribe: Boolean(options.transcribe),
          threshold: options.threshold ?? 0.72,
        },
        { transfer: [copy.buffer], onProgress },
      );
      return result as DiarizeResult;
    },
    dispose() {
      worker.terminate();
      pending.clear();
    },
  };
}
