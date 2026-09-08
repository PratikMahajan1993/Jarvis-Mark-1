import {
  AutoFeatureExtractor,
  AutoModelForXVector,
  AutoProcessor,
  env,
  pipeline,
} from "@huggingface/transformers";
import { clusterSpeakers, l2norm, mergeTurns } from "./cluster";
import { ASR_MODEL, DIARIZE_SAMPLE_RATE, EMBED_MODEL, type DiarizeResult, type WorkerIn, type WorkerOut } from "./types";
import { embedWindows, speechSpans } from "./vad";

env.allowLocalModels = false;
env.useBrowserCache = true;
const wasm = env.backends.onnx.wasm as { numThreads?: number; proxy?: boolean } | undefined;
if (wasm) {
  wasm.numThreads = 1;
  wasm.proxy = false;
}

type AudioFront = {
  (input: Float32Array): Promise<unknown>;
};

type Embedder = {
  processor: AudioFront;
  model: Awaited<ReturnType<typeof AutoModelForXVector.from_pretrained>>;
};

type Transcriber = Awaited<ReturnType<typeof pipeline<"automatic-speech-recognition">>>;

let embedder: Embedder | null = null;
let transcriber: Transcriber | null = null;

function post(message: WorkerOut) {
  self.postMessage(message);
}

function progressLabel(info: { status?: string; file?: string; name?: string; progress?: number }): { label: string; progress: number } | null {
  if (info.status === "progress") {
    return {
      label: info.file || info.name || "Downloading",
      progress: Math.round(info.progress || 0),
    };
  }
  if (info.status === "initiate" || info.status === "download") {
    return { label: info.file || info.name || "Fetching model", progress: 0 };
  }
  if (info.status === "done" || info.status === "ready") {
    return { label: info.name || "Model ready", progress: 100 };
  }
  return null;
}

async function loadEmbedder(id: number): Promise<Embedder> {
  if (embedder) return embedder;
  const onProgress = (info: { status?: string; file?: string; name?: string; progress?: number }) => {
    const next = progressLabel(info);
    if (next) post({ id, type: "progress", ...next });
  };
  let processor: AudioFront;
  try {
    processor = (await AutoProcessor.from_pretrained(EMBED_MODEL, { progress_callback: onProgress })) as AudioFront;
  } catch {
    processor = (await AutoFeatureExtractor.from_pretrained(EMBED_MODEL, {
      progress_callback: onProgress,
    })) as AudioFront;
  }
  const model = await AutoModelForXVector.from_pretrained(EMBED_MODEL, {
    dtype: "q8",
    progress_callback: onProgress,
  });
  embedder = { processor, model };
  return embedder;
}

async function loadTranscriber(id: number): Promise<Transcriber> {
  if (transcriber) return transcriber;
  transcriber = await pipeline("automatic-speech-recognition", ASR_MODEL, {
    dtype: "q8",
    progress_callback: (info) => {
      const next = progressLabel(info);
      if (next) post({ id, type: "progress", ...next });
    },
  });
  return transcriber;
}

function asFloat32(value: unknown): Float32Array {
  if (value instanceof Float32Array) return l2norm(new Float32Array(value));
  if (ArrayBuffer.isView(value) && "length" in value) {
    return l2norm(Float32Array.from(value as unknown as ArrayLike<number>));
  }
  if (value && typeof value === "object" && "data" in value) {
    return asFloat32((value as { data: unknown }).data);
  }
  throw new Error("Could not read a speaker embedding from the model.");
}

function slicePcm(pcm: Float32Array, start: number, end: number): Float32Array {
  const from = Math.max(0, Math.floor(start * DIARIZE_SAMPLE_RATE));
  const to = Math.min(pcm.length, Math.ceil(end * DIARIZE_SAMPLE_RATE));
  const min = DIARIZE_SAMPLE_RATE;
  if (to - from >= min) return pcm.subarray(from, to);
  const padded = new Float32Array(min);
  padded.set(pcm.subarray(from, to));
  return padded;
}

async function embedWindow(session: Embedder, chunk: Float32Array): Promise<Float32Array> {
  const inputs = await session.processor(chunk);
  const output = (await session.model(inputs as never)) as { embeddings?: { data: unknown } };
  if (!output?.embeddings) throw new Error("Speaker model did not return embeddings.");
  return asFloat32(output.embeddings);
}

function speakerName(index: number): string {
  return `Speaker ${index + 1}`;
}

async function runDiarize(id: number, pcm: Float32Array, transcribe: boolean, threshold: number): Promise<DiarizeResult> {
  const duration = pcm.length / DIARIZE_SAMPLE_RATE;
  const session = await loadEmbedder(id);
  const windows = embedWindows(speechSpans(pcm, DIARIZE_SAMPLE_RATE));
  if (!windows.length) {
    return { duration, speakers: [], turns: [], transcript: "" };
  }

  const embeddings: Float32Array[] = [];
  for (let i = 0; i < windows.length; i += 1) {
    post({
      id,
      type: "progress",
      label: `Embedding ${i + 1} / ${windows.length}`,
      progress: Math.round(((i + 1) / windows.length) * 100),
    });
    embeddings.push(await embedWindow(session, slicePcm(pcm, windows[i].start, windows[i].end)));
  }

  const labels = clusterSpeakers(embeddings, threshold);
  const merged = mergeTurns(
    windows.map((window, i) => ({ start: window.start, end: window.end, speaker: labels[i] })),
  );
  const speakerIds = [...new Set(merged.map((turn) => turn.speaker))].sort((a, b) => a - b);
  const turns = merged.map((turn) => ({
    speaker: speakerName(speakerIds.indexOf(turn.speaker)),
    start: Number(turn.start.toFixed(2)),
    end: Number(turn.end.toFixed(2)),
    text: "",
  }));

  let transcript = "";
  if (transcribe) {
    post({ id, type: "progress", label: "Transcribing", progress: 5 });
    const asr = await loadTranscriber(id);
    const output = await asr(pcm, {
      return_timestamps: true,
      chunk_length_s: 30,
      stride_length_s: 5,
    });
    const result = Array.isArray(output) ? output[0] : output;
    transcript = (result?.text || "").trim();
    for (const chunk of result?.chunks || []) {
      const start = chunk.timestamp?.[0] ?? 0;
      const end = chunk.timestamp?.[1] ?? start;
      const mid = (start + end) / 2;
      const turn =
        turns.find((item) => mid >= item.start && mid <= item.end) ||
        turns.reduce<(typeof turns)[number] | null>((best, item) => {
          if (!best) return item;
          const bestDist = Math.min(Math.abs(mid - best.start), Math.abs(mid - best.end));
          const nextDist = Math.min(Math.abs(mid - item.start), Math.abs(mid - item.end));
          return nextDist < bestDist ? item : best;
        }, null);
      if (turn) turn.text = `${turn.text} ${chunk.text}`.trim();
    }
    if (transcript && turns.length === 1 && !turns[0].text) turns[0].text = transcript;
  }

  return {
    duration: Number(duration.toFixed(2)),
    speakers: speakerIds.map((_, i) => speakerName(i)),
    turns,
    transcript,
  };
}

self.addEventListener("message", async (event: MessageEvent<WorkerIn>) => {
  const msg = event.data;
  try {
    if (msg.type === "load") {
      await loadEmbedder(msg.id);
      if (msg.transcribe) await loadTranscriber(msg.id);
      post({ id: msg.id, type: "ready" });
      return;
    }
    if (msg.type === "run") {
      const result = await runDiarize(msg.id, msg.pcm, msg.transcribe, msg.threshold);
      post({ id: msg.id, type: "result", result });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Diarization failed.";
    post({ id: msg.id, type: "error", message });
  }
});
