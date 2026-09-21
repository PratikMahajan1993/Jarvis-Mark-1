/** Fire-and-forget HUD beacons for live capability-test recording. Never blocks UI. */

function apiBase(): string {
  const fallback = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  if (typeof window === "undefined") return fallback;
  try {
    const configured = new URL(fallback, window.location.origin);
    const pageHost = window.location.hostname;
    const loopback = configured.hostname === "localhost" || configured.hostname === "127.0.0.1";
    if (loopback && pageHost !== "localhost" && pageHost !== "127.0.0.1") {
      return `${window.location.protocol}//${pageHost}:8000`;
    }
    return configured.origin;
  } catch {
    return fallback;
  }
}

export type LiveLogFields = Record<string, unknown>;

export function liveLog(
  kind: string,
  fields?: LiveLogFields,
  opts?: { sessionId?: string; latencyMs?: number },
): void {
  if (typeof window === "undefined") return;
  const payload = JSON.stringify({
    source: "hud",
    kind,
    session_id: opts?.sessionId ?? "default",
    latency_ms: opts?.latencyMs,
    fields: fields ?? {},
  });
  const url = `${apiBase()}/api/live-log`;
  try {
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      const blob = new Blob([payload], { type: "application/json" });
      if (navigator.sendBeacon(url, blob)) return;
    }
    void fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    /* swallow — logging must never affect HUD */
  }
}
