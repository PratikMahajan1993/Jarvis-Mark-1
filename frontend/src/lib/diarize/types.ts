export const DIARIZE_SAMPLE_RATE = 16_000;
export const DIARIZE_MAX_SECONDS = 180;
export const EMBED_MODEL = "Xenova/wavlm-base-plus-sv";
export const ASR_MODEL = "Xenova/whisper-tiny.en";

export type DiarizeProgress = {
  label: string;
  progress: number;
};

export type SpeakerTurn = {
  speaker: string;
  start: number;
  end: number;
  text: string;
};

export type DiarizeResult = {
  duration: number;
  speakers: string[];
  turns: SpeakerTurn[];
  transcript: string;
};

export type DiarizeRunOptions = {
  transcribe?: boolean;
  threshold?: number;
};

export type WorkerIn =
  | { id: number; type: "load"; transcribe: boolean }
  | { id: number; type: "run"; pcm: Float32Array; transcribe: boolean; threshold: number };

export type WorkerOut =
  | { id: number; type: "progress"; label: string; progress: number }
  | { id: number; type: "ready" }
  | { id: number; type: "result"; result: DiarizeResult }
  | { id: number; type: "error"; message: string };
