const FLAG_KEY = (id: string) => `jarvis.feature.${id}`;

const defaults = new Map<string, boolean>();

/** Register a feature flag default (from defineFeature). */
export function setFeatureFlagDefault(id: string, value: boolean) {
  defaults.set(id, value);
}

export function isFeatureEnabled(id: string): boolean {
  if (typeof window === "undefined") return defaults.get(id) ?? true;
  try {
    const raw = localStorage.getItem(FLAG_KEY(id));
    if (raw === null) return defaults.get(id) ?? true;
    if (raw === "0" || raw === "false") return false;
    if (raw === "1" || raw === "true") return true;
    return defaults.get(id) ?? true;
  } catch {
    return defaults.get(id) ?? true;
  }
}

export function setFeatureFlag(id: string, on: boolean) {
  try {
    localStorage.setItem(FLAG_KEY(id), on ? "true" : "false");
  } catch {
    /* ignore */
  }
}
