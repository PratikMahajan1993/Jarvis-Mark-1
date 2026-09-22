"use client";

import { useCallback, useEffect, useState } from "react";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";

const ANALYSE_LABEL = "analyse this drawing (spends 1 of 5)";

type BenchItem = {
  file_sha256: string;
  display_name: string;
  path?: string;
};

type BenchPayload = {
  enabled: boolean;
  items: BenchItem[];
  used: number;
  total: number;
  reset_at: string;
};

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

function formatResetAt(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function VisionBenchQueue() {
  const [bench, setBench] = useState<BenchPayload | null>(null);
  const [busyHash, setBusyHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase()}/api/vision/bench`);
      if (!res.ok) return;
      const data = (await res.json()) as BenchPayload;
      if (!data.enabled) {
        setBench(null);
        return;
      }
      setBench(data);
    } catch {
      setBench(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onAnalyse = async (file_sha256: string) => {
    setError(null);
    setBusyHash(file_sha256);
    try {
      const res = await fetch(`${apiBase()}/api/vision/bench/analyse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_sha256 }),
      });
      const data = (await res.json()) as { ok?: boolean; error?: string; enabled?: boolean };
      if (!data.enabled) {
        setBench(null);
        return;
      }
      if (!data.ok && data.error) {
        setError(data.error);
      }
      await refresh();
    } catch {
      setError("Could not reach the vision bench.");
    } finally {
      setBusyHash(null);
    }
  };

  if (!bench?.enabled) return null;

  return (
    <SpotlightCard
      className="shrink-0 rounded-2xl border border-[color:var(--border)] bg-black/40 backdrop-blur-md"
      bodyClassName="p-4"
    >
      <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em]">
        <GradientText className="font-mono text-[10px] uppercase tracking-[0.22em]" animationSpeed={9}>
          Vision queue
        </GradientText>
      </p>
      <p className="mb-3 font-mono text-[11px] text-[color:var(--muted)]">
        {bench.used}/{bench.total} used this cycle
        {bench.reset_at ? (
          <span className="block text-[10px] uppercase tracking-[0.12em] opacity-80">
            Resets {formatResetAt(bench.reset_at)}
          </span>
        ) : null}
      </p>
      {error ? (
        <p className="mb-2 text-xs text-amber-200/90">{error}</p>
      ) : null}
      <ul className="space-y-2">
        {bench.items.map((item) => (
          <li
            key={item.file_sha256}
            className="flex flex-col gap-2 rounded-xl border border-[color:var(--border)] bg-black/35 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between"
          >
            <span className="truncate font-display text-sm text-[color:var(--fg)]/90" title={item.display_name}>
              {item.display_name}
            </span>
            <button
              type="button"
              disabled={busyHash === item.file_sha256}
              onClick={() => void onAnalyse(item.file_sha256)}
              className="shrink-0 rounded-lg border border-[#7dffe0]/35 bg-[#7dffe0]/10 px-3 py-1.5 text-left font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--fg)] transition hover:bg-[#7dffe0]/20 disabled:opacity-50"
            >
              {ANALYSE_LABEL}
            </button>
          </li>
        ))}
      </ul>
      {!bench.items.length ? (
        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]/70">
          No drawings waiting for vision.
        </p>
      ) : null}
    </SpotlightCard>
  );
}
