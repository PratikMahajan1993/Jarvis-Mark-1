/**
 * Isolated offline diarization. The HUD does not import this module.
 * Later: `import { createDiarizeClient } from "@/lib/diarize"` from a meeting mode.
 */
export { createDiarizeClient } from "./client";
export { clipDuration, decodeToMono16k, encodeWav, startMic } from "./audio";
export {
  ASR_MODEL,
  DIARIZE_MAX_SECONDS,
  DIARIZE_SAMPLE_RATE,
  EMBED_MODEL,
} from "./types";
export type {
  DiarizeClient,
} from "./client";
export type {
  DiarizeProgress,
  DiarizeResult,
  DiarizeRunOptions,
  SpeakerTurn,
} from "./types";
