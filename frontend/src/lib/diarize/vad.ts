export type SpeechSpan = {
  start: number;
  end: number;
};

function rms(pcm: Float32Array, from: number, count: number): number {
  let sum = 0;
  const end = Math.min(pcm.length, from + count);
  for (let i = from; i < end; i += 1) sum += pcm[i] * pcm[i];
  const n = Math.max(1, end - from);
  return Math.sqrt(sum / n);
}

export function speechSpans(pcm: Float32Array, sampleRate: number): SpeechSpan[] {
  if (!pcm.length) return [];
  const frame = Math.max(1, Math.round(sampleRate * 0.025));
  const hop = Math.max(1, Math.round(sampleRate * 0.01));
  const energies: number[] = [];
  for (let i = 0; i + frame <= pcm.length; i += hop) {
    energies.push(rms(pcm, i, frame));
  }
  if (!energies.length) return [{ start: 0, end: pcm.length / sampleRate }];

  const ranked = [...energies].sort((a, b) => a - b);
  const noise = ranked[Math.floor(ranked.length * 0.2)] || 0;
  const threshold = Math.max(0.008, noise * 3.4);

  const raw: SpeechSpan[] = [];
  let open: number | null = null;
  for (let i = 0; i < energies.length; i += 1) {
    const t = (i * hop) / sampleRate;
    if (energies[i] >= threshold) {
      if (open === null) open = t;
    } else if (open !== null) {
      raw.push({ start: open, end: t });
      open = null;
    }
  }
  if (open !== null) raw.push({ start: open, end: pcm.length / sampleRate });

  const merged: SpeechSpan[] = [];
  for (const span of raw) {
    const last = merged[merged.length - 1];
    if (last && span.start - last.end < 0.35) {
      last.end = span.end;
    } else {
      merged.push({ ...span });
    }
  }

  const usable = merged.filter((span) => span.end - span.start >= 0.35);
  if (usable.length) return usable;

  const peak = ranked[ranked.length - 1] || 0;
  if (peak < 0.012) return [];
  return [{ start: 0, end: pcm.length / sampleRate }];
}

export function embedWindows(spans: SpeechSpan[], windowSec = 1.5, hopSec = 0.75): SpeechSpan[] {
  const windows: SpeechSpan[] = [];
  for (const span of spans) {
    const length = span.end - span.start;
    if (length <= windowSec + 0.05) {
      windows.push({ ...span });
      continue;
    }
    let start = span.start;
    while (start + 0.4 < span.end) {
      const end = Math.min(span.end, start + windowSec);
      windows.push({ start, end });
      if (end >= span.end) break;
      start += hopSec;
    }
  }
  return windows;
}
