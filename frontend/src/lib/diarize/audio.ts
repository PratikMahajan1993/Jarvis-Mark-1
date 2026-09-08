import { DIARIZE_MAX_SECONDS, DIARIZE_SAMPLE_RATE } from "./types";

function mixdown(buffer: AudioBuffer): Float32Array {
  const length = buffer.length;
  const mixed = new Float32Array(length);
  const channels = buffer.numberOfChannels;
  for (let c = 0; c < channels; c += 1) {
    const data = buffer.getChannelData(c);
    for (let i = 0; i < length; i += 1) mixed[i] += data[i];
  }
  if (channels > 1) {
    for (let i = 0; i < length; i += 1) mixed[i] /= channels;
  }
  return mixed;
}

export function resample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.max(1, Math.round(input.length / ratio)));
  for (let i = 0; i < out.length; i += 1) {
    const x = i * ratio;
    const i0 = Math.min(input.length - 1, Math.floor(x));
    const i1 = Math.min(input.length - 1, i0 + 1);
    const t = x - i0;
    out[i] = input[i0] * (1 - t) + input[i1] * t;
  }
  return out;
}

export async function decodeToMono16k(blob: Blob, targetRate = DIARIZE_SAMPLE_RATE): Promise<Float32Array> {
  const ctx = new AudioContext();
  try {
    const audio = await ctx.decodeAudioData(await blob.arrayBuffer());
    return resample(mixdown(audio), audio.sampleRate, targetRate);
  } finally {
    await ctx.close();
  }
}

export function encodeWav(pcm: Float32Array, sampleRate = DIARIZE_SAMPLE_RATE): Blob {
  const bytes = pcm.length * 2;
  const buffer = new ArrayBuffer(44 + bytes);
  const view = new DataView(buffer);
  const write = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + bytes, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, bytes, true);
  let offset = 44;
  for (let i = 0; i < pcm.length; i += 1, offset += 2) {
    const sample = Math.max(-1, Math.min(1, pcm[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export function clipDuration(pcm: Float32Array, sampleRate = DIARIZE_SAMPLE_RATE): Float32Array {
  const max = sampleRate * DIARIZE_MAX_SECONDS;
  return pcm.length > max ? pcm.subarray(0, max) : pcm;
}

export type MicSession = {
  stop: () => Promise<{ blob: Blob; pcm: Float32Array }>;
};

export async function startMic(): Promise<MicSession> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "";
  const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  const chunks: BlobPart[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size) chunks.push(event.data);
  };
  recorder.start(250);

  return {
    stop: async () => {
      const blob = await new Promise<Blob>((resolve, reject) => {
        recorder.onerror = () => reject(new Error("Recording failed."));
        recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
        try {
          recorder.stop();
        } catch (err) {
          reject(err);
        }
      });
      stream.getTracks().forEach((track) => track.stop());
      const pcm = clipDuration(await decodeToMono16k(blob));
      return { blob, pcm };
    },
  };
}
