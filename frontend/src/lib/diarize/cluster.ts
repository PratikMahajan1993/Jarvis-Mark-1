export function cosine(a: ArrayLike<number>, b: ArrayLike<number>): number {
  const n = Math.min(a.length, b.length);
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < n; i += 1) {
    const x = a[i];
    const y = b[i];
    dot += x * y;
    na += x * x;
    nb += y * y;
  }
  const den = Math.sqrt(na) * Math.sqrt(nb);
  return den ? dot / den : 0;
}

export function l2norm(values: Float32Array): Float32Array {
  let n = 0;
  for (let i = 0; i < values.length; i += 1) n += values[i] * values[i];
  n = Math.sqrt(n) || 1;
  const out = new Float32Array(values.length);
  for (let i = 0; i < values.length; i += 1) out[i] = values[i] / n;
  return out;
}

export function clusterSpeakers(embeddings: Float32Array[], threshold: number): number[] {
  const centroids: Float32Array[] = [];
  const counts: number[] = [];
  const labels: number[] = [];

  for (const embedding of embeddings) {
    let best = -1;
    let bestSim = -1;
    for (let i = 0; i < centroids.length; i += 1) {
      const sim = cosine(embedding, centroids[i]);
      if (sim > bestSim) {
        bestSim = sim;
        best = i;
      }
    }
    if (best >= 0 && bestSim >= threshold) {
      labels.push(best);
      const centroid = centroids[best];
      const next = counts[best] + 1;
      for (let i = 0; i < centroid.length; i += 1) {
        centroid[i] += (embedding[i] - centroid[i]) / next;
      }
      counts[best] = next;
    } else {
      labels.push(centroids.length);
      centroids.push(new Float32Array(embedding));
      counts.push(1);
    }
  }

  return labels;
}

export type TimedLabel = {
  start: number;
  end: number;
  speaker: number;
};

export function mergeTurns(windows: TimedLabel[]): TimedLabel[] {
  if (!windows.length) return [];
  const out: TimedLabel[] = [{ ...windows[0] }];
  for (let i = 1; i < windows.length; i += 1) {
    const last = out[out.length - 1];
    const next = windows[i];
    if (next.speaker === last.speaker && next.start <= last.end + 0.45) {
      last.end = Math.max(last.end, next.end);
    } else {
      out.push({ ...next });
    }
  }
  return out;
}
